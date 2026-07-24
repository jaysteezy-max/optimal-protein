#!/usr/bin/env python3
"""Build the protein-value rankings from config/ + data/.

Reads:
    config/scoring.yaml      weights, protein threshold, PNW uplift
    config/chains.yaml       the chains in scope
    data/items.csv           one row per qualifying menu item
    data/manual_prices.csv   optional till-verified price overrides

Writes:
    docs/index.html          static page for GitHub Pages / offline use
    docs/data.json           machine-readable feed
    RANKINGS.md              markdown table readable straight on GitHub

Pure function of its inputs -- edit a data/config file, re-run, commit.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent


# ---------------------------------------------------------------- loading

def load_config():
    scoring = yaml.safe_load((ROOT / "config/scoring.yaml").read_text())
    chains_raw = yaml.safe_load((ROOT / "config/chains.yaml").read_text())["chains"]
    chains = {c["slug"]: c for c in chains_raw}
    weights = scoring["weights"]
    total = sum(weights.values())
    if abs(total - 1.0) > 1e-9:
        sys.exit(f"scoring.yaml weights must sum to 1.0 (got {total})")
    regions_cfg = yaml.safe_load((ROOT / "config/regions.yaml").read_text())
    codes = [r["code"] for r in regions_cfg["regions"]]
    if len(codes) != len(set(codes)):
        sys.exit("regions.yaml: duplicate region codes")
    if regions_cfg["default_region"] not in codes:
        sys.exit("regions.yaml: default_region not in regions")
    for r in regions_cfg["regions"]:
        if not (0.8 <= r["multiplier"] <= 1.3):
            sys.exit(f"regions.yaml: multiplier for {r['code']} out of sane "
                     f"range 0.8–1.3 ({r['multiplier']})")
    return scoring, chains, regions_cfg


def read_csv_rows(path: Path):
    """CSV reader that ignores blank lines and full-line # comments."""
    with path.open(newline="") as f:
        rows = [r for r in csv.DictReader(f)
                if any((v or "").strip() for v in r.values())
                and not (list(r.values())[0] or "").lstrip().startswith("#")]
    return rows


def load_items(chains):
    items = read_csv_rows(ROOT / "data/items.csv")
    for it in items:
        if it["chain"] not in chains:
            sys.exit(f"items.csv: unknown chain slug {it['chain']!r} "
                     f"({it['item']!r}) — add it to config/chains.yaml")
        it["protein_g"] = float(it["protein_g"])
        it["calories"] = float(it["calories"])
        raw_price = (it.get("national_price_usd") or "").strip()
        it["national_price_usd"] = float(raw_price) if raw_price else None
    return items


def load_manual_prices():
    path = ROOT / "data/manual_prices.csv"
    if not path.exists():
        return {}
    overrides = {}
    for r in read_csv_rows(path):
        overrides[(r["chain"], r["item"])] = {
            "price": float(r["pnw_price_usd"]),
            "as_of": r.get("as_of", ""),
        }
    return overrides


# ---------------------------------------------------------------- scoring

def compute(scoring, chains, items, overrides):
    threshold = scoring["protein_threshold_g"]
    uplift = 1 + scoring["pnw_uplift_pct"] / 100.0
    w_ppd = scoring["weights"]["protein_per_dollar"]
    w_pd = scoring["weights"]["protein_density"]

    rows = []
    for it in items:
        if it["protein_g"] < threshold:
            continue
        key = (it["chain"], it["item"])
        if key in overrides:
            price = overrides[key]["price"]
            price_kind = f"verified {overrides[key]['as_of']}".strip()
            price_national, price_fixed = None, True
        elif it["national_price_usd"] is not None:
            price = round(it["national_price_usd"] * uplift, 2)
            price_kind = "national +uplift"
            price_national, price_fixed = it["national_price_usd"], False
        else:
            price = None
            price_kind = "no price"
            price_national, price_fixed = None, False
        rows.append({
            "chain": it["chain"],
            "chain_name": chains[it["chain"]]["name"],
            "item": it["item"],
            "protein_g": it["protein_g"],
            "calories": it["calories"],
            "price": price,
            "price_kind": price_kind,
            "price_national": price_national,
            "price_fixed": price_fixed,
            "notes": (it.get("notes") or "").strip(),
            "protein_per_dollar": round(it["protein_g"] / price, 2) if price else None,
            "protein_per_100cal": round(it["protein_g"] / (it["calories"] / 100.0), 2),
        })

    priced = [r for r in rows if r["price"] is not None]
    if not priced:
        sys.exit("no priced items — nothing to rank")
    max_ppd = max(r["protein_per_dollar"] for r in priced)
    max_pd = max(r["protein_per_100cal"] for r in rows)

    for r in rows:
        r["density_norm"] = round(100 * r["protein_per_100cal"] / max_pd, 1)
        if r["price"] is not None:
            r["ppd_norm"] = round(100 * r["protein_per_dollar"] / max_ppd, 1)
            r["value_score"] = round(w_ppd * r["ppd_norm"] + w_pd * r["density_norm"], 1)
        else:
            r["ppd_norm"] = None
            r["value_score"] = None

    # scored items ranked first; unpriced items flagged at the bottom
    rows.sort(key=lambda r: (r["value_score"] is None,
                             -(r["value_score"] or 0),
                             -r["protein_per_100cal"]))
    for i, r in enumerate(rows):
        r["rank"] = i + 1 if r["value_score"] is not None else None
    return rows


def best_per_chain(rows):
    best = {}
    for r in rows:
        if r["value_score"] is None:
            continue
        if r["chain"] not in best:
            best[r["chain"]] = r
    return sorted(best.values(), key=lambda r: r["rank"])


# ---------------------------------------------------------------- outputs

def fmt_price(r):
    return f"${r['price']:.2f}" if r["price"] is not None else "—"


def write_json(scoring, regions_cfg, rows, path):
    payload = {
        "generated": date.today().isoformat(),
        "methodology": {
            "weights": scoring["weights"],
            "protein_threshold_g": scoring["protein_threshold_g"],
            "pnw_uplift_pct": scoring["pnw_uplift_pct"],
            "caveat": ("Prices are national averages + regional uplift, not "
                       "till-verified. Sales tax excluded. App deals excluded. "
                       "Rankings are region-invariant; only displayed prices "
                       "scale by region."),
        },
        "regions": {
            "default": regions_cfg["default_region"],
            "list": regions_cfg["regions"],
            "provenance": regions_cfg.get("provenance", "").strip(),
        },
        "items": rows,
    }
    path.write_text(json.dumps(payload, indent=1) + "\n")


def write_markdown(scoring, rows, best, path):
    today = date.today().isoformat()
    lines = [
        "# Protein Value Rankings (PNW)",
        "",
        f"Generated {today}. Prices are national averages + "
        f"{scoring['pnw_uplift_pct']}% PNW uplift, not till-verified — "
        "confirm in store. Sales tax and app deals excluded.",
        "",
        f"Value Score = {int(scoring['weights']['protein_per_dollar']*100)}% "
        f"protein-per-dollar + {int(scoring['weights']['protein_density']*100)}% "
        "protein density, each normalized to the best item in the list (=100).",
        "",
        "## Best pick per chain",
        "",
        "| Chain | Order | Price | Protein | Score |",
        "|---|---|---|---|---|",
    ]
    for r in best:
        lines.append(f"| {r['chain_name']} | {r['item']} | {fmt_price(r)} "
                     f"| {r['protein_g']:g} g | {r['value_score']} |")
    lines += [
        "",
        "## Full rankings",
        "",
        "| # | Chain | Item | Price | Protein | Cal | Prot/$ | Prot/100cal | Score |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        rank = r["rank"] if r["rank"] is not None else "–"
        ppd = r["protein_per_dollar"] if r["protein_per_dollar"] is not None else "—"
        score = r["value_score"] if r["value_score"] is not None else "no price"
        lines.append(
            f"| {rank} | {r['chain_name']} | {r['item']} | {fmt_price(r)} "
            f"| {r['protein_g']:g} g | {r['calories']:g} | {ppd} "
            f"| {r['protein_per_100cal']} | {score} |")
    lines.append("")
    path.write_text("\n".join(lines))


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Protein Value — PNW</title>
<style>
  :root{
    --bg:#f5f5f7; --card:#ffffff; --ink:#1d1d1f; --muted:#6e6e73; --muted2:#86868b;
    --line:#e5e5ea; --hair:#ebebf0; --blue:#0071e3; --blue-soft:#e8f1fd;
    --good:#1a8f4c; --shadow:0 4px 22px rgba(0,0,0,.06); --radius:18px;
  }
  @media (prefers-color-scheme:dark){
    :root{
      --bg:#000000; --card:#1c1c1e; --ink:#f5f5f7; --muted:#98989d; --muted2:#8e8e93;
      --line:#2c2c2e; --hair:#2c2c2e; --blue:#0a84ff; --blue-soft:#0a2540;
      --good:#30d158; --shadow:0 4px 22px rgba(0,0,0,.5);
    }
  }
  :root[data-theme="light"]{
    --bg:#f5f5f7; --card:#ffffff; --ink:#1d1d1f; --muted:#6e6e73; --muted2:#86868b;
    --line:#e5e5ea; --hair:#ebebf0; --blue:#0071e3; --blue-soft:#e8f1fd;
    --good:#1a8f4c; --shadow:0 4px 22px rgba(0,0,0,.06);
  }
  :root[data-theme="dark"]{
    --bg:#000000; --card:#1c1c1e; --ink:#f5f5f7; --muted:#98989d; --muted2:#8e8e93;
    --line:#2c2c2e; --hair:#2c2c2e; --blue:#0a84ff; --blue-soft:#0a2540;
    --good:#30d158; --shadow:0 4px 22px rgba(0,0,0,.5);
  }
  *{box-sizing:border-box;margin:0}
  html{-webkit-text-size-adjust:100%}
  body{
    background:var(--bg); color:var(--ink);
    font:16px/1.47 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,sans-serif;
    -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility;
    max-width:600px; margin:0 auto; padding:0 16px 64px;
    font-variant-numeric:tabular-nums; overscroll-behavior-y:none;
  }
  /* hero */
  header{padding:30px 4px 8px; text-align:center}
  .eyebrow{font-size:12px; font-weight:600; letter-spacing:.02em; color:var(--blue); margin-bottom:8px}
  h1{font-size:clamp(30px,8vw,40px); font-weight:600; letter-spacing:-.03em; line-height:1.05;
    text-wrap:balance}
  .sub{color:var(--muted); font-size:15px; margin-top:10px; line-height:1.4}
  .meta{color:var(--muted2); font-size:12.5px; margin-top:8px; line-height:1.4}
  .caveat{color:var(--muted2); font-size:12px; line-height:1.5; margin:14px auto 0; max-width:44ch}
  .caveat b{color:var(--muted); font-weight:600}
  /* controls (frosted, sticky) */
  .controls{
    position:sticky; top:0; z-index:20; margin:16px -16px 0; padding:12px 16px;
    display:grid; grid-template-columns:1fr 1.2fr; gap:8px;
    background:color-mix(in srgb,var(--bg) 82%,transparent);
    backdrop-filter:saturate(1.8) blur(20px); -webkit-backdrop-filter:saturate(1.8) blur(20px);
    border-bottom:1px solid var(--line);
  }
  select,input[type=search]{
    width:100%; padding:11px 13px; border:1px solid transparent; border-radius:12px;
    background:var(--card); color:var(--ink); font-size:16px; font-family:inherit;
    -webkit-appearance:none; appearance:none; box-shadow:var(--shadow);
  }
  select{background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8' fill='none' stroke='%2386868b' stroke-width='1.8' stroke-linecap='round'%3E%3Cpath d='M1 1l5 5 5-5'/%3E%3C/svg%3E");
    background-repeat:no-repeat; background-position:right 12px center; padding-right:32px}
  #region{grid-column:1/-1; padding-top:8px; padding-bottom:8px; font-size:13.5px;
    color:var(--muted); font-weight:500}
  input:focus,select:focus{outline:none; border-color:var(--blue);
    box-shadow:0 0 0 3.5px color-mix(in srgb,var(--blue) 22%,transparent)}
  .count{color:var(--muted2); font-size:12px; font-weight:500; padding:14px 6px 8px;
    letter-spacing:.01em}
  /* list — iOS inset grouped */
  .list{background:var(--card); border-radius:var(--radius); box-shadow:var(--shadow);
    overflow:hidden; border:1px solid var(--hair)}
  .row{display:grid; grid-template-columns:24px 1fr auto 8px; gap:13px; align-items:center;
    width:100%; text-align:left; background:none; border:0; border-bottom:1px solid var(--hair);
    padding:14px 16px; color:inherit; font:inherit; cursor:pointer;
    -webkit-tap-highlight-color:transparent}
  .row:last-child{border-bottom:0}
  .row:hover{background:color-mix(in srgb,var(--ink) 3%,transparent)}
  .row:active{background:color-mix(in srgb,var(--ink) 6%,transparent)}
  .row:focus-visible{outline:2px solid var(--blue); outline-offset:-2px}
  .rk{font-size:15px; font-weight:400; color:var(--muted2); text-align:center}
  .row.top .rk{color:var(--blue); font-weight:600}
  .main{min-width:0; display:block}
  .nm{display:block; font-size:15px; font-weight:590; letter-spacing:-.012em; line-height:1.25}
  .ch{display:block; font-size:12.5px; color:var(--muted); margin-top:2px}
  .best{display:inline-block; font-size:10.5px; font-weight:600; letter-spacing:.02em;
    color:var(--blue); background:var(--blue-soft); border-radius:6px; padding:1px 6px; margin-top:5px}
  .sc{font-size:17px; font-weight:600; letter-spacing:-.01em}
  .sc.no{color:var(--muted2); font-weight:500; font-size:14px}
  .chev{width:7px; height:12px; color:var(--muted2); opacity:.6}
  .empty{color:var(--muted); text-align:center; padding:40px 0}
  footer{color:var(--muted2); font-size:11.5px; text-align:center; margin-top:22px; line-height:1.6}
  /* ---- detail sheet ---- */
  .backdrop{position:fixed; inset:0; z-index:40; background:rgba(0,0,0,.36);
    opacity:0; transition:opacity .28s ease; -webkit-backdrop-filter:blur(2px); backdrop-filter:blur(2px)}
  .backdrop.open{opacity:1}
  .sheet{position:fixed; left:0; right:0; bottom:0; z-index:41; margin:0 auto; max-width:600px;
    background:var(--bg); border-radius:22px 22px 0 0; box-shadow:0 -8px 40px rgba(0,0,0,.28);
    max-height:90vh; display:flex; flex-direction:column;
    transform:translateY(100%); transition:transform .32s cubic-bezier(.32,.72,0,1)}
  .sheet.open{transform:translateY(0)}
  .handle{width:38px; height:5px; border-radius:3px; background:var(--muted2); opacity:.4;
    margin:8px auto 2px; flex:none; cursor:grab; touch-action:none}
  .sheet-close{position:absolute; top:12px; right:14px; width:30px; height:30px; border:0;
    border-radius:50%; background:color-mix(in srgb,var(--ink) 8%,transparent); color:var(--muted);
    display:grid; place-items:center; cursor:pointer; z-index:2}
  .sheet-close:focus-visible{outline:2px solid var(--blue); outline-offset:2px}
  .sheet-grab{position:relative; flex:none; padding:0 20px 14px; touch-action:none;
    cursor:grab; user-select:none; -webkit-user-select:none}
  .sheet-grab:active{cursor:grabbing}
  .sheet-scroll{flex:1; min-height:0; overflow-y:auto; padding:2px 20px 30px;
    -webkit-overflow-scrolling:touch; touch-action:pan-y}
  .sh-rank{font-size:11px; font-weight:600; letter-spacing:.06em; text-transform:uppercase;
    color:var(--muted2)}
  .sh-name{font-size:24px; font-weight:600; letter-spacing:-.02em; line-height:1.1; margin-top:8px}
  .sh-ch{font-size:14px; color:var(--muted); margin-top:3px}
  .sh-hero{display:flex; align-items:baseline; gap:10px; margin-top:16px}
  .sh-score{font-size:52px; font-weight:300; letter-spacing:-.03em; line-height:1}
  .sh-scorelbl{font-size:12px; font-weight:500; letter-spacing:.04em; text-transform:uppercase;
    color:var(--muted2)}
  .sh-pill{margin-left:auto; align-self:center; font-size:12px; font-weight:600; color:var(--blue);
    background:var(--blue-soft); border-radius:8px; padding:5px 10px}
  .panel{background:var(--card); border-radius:14px; padding:16px; margin-top:16px;
    border:1px solid var(--hair)}
  .panel-h{font-size:12px; font-weight:600; letter-spacing:.05em; text-transform:uppercase;
    color:var(--muted2); margin-bottom:12px}
  .brk{margin-bottom:13px}
  .brk:last-child{margin-bottom:0}
  .brk-top{display:flex; justify-content:space-between; align-items:baseline; font-size:14px}
  .brk-top .w{color:var(--muted); font-size:12px; font-weight:500}
  .brk-name{font-weight:550}
  .brk-val{font-weight:600; font-variant-numeric:tabular-nums}
  .bar{height:7px; border-radius:4px; background:color-mix(in srgb,var(--ink) 8%,transparent);
    margin-top:7px; overflow:hidden}
  .bar i{display:block; height:100%; border-radius:4px; background:var(--blue);
    width:0; transition:width .5s cubic-bezier(.32,.72,0,1)}
  .bar.g i{background:var(--good)}
  .eq{margin-top:14px; padding-top:13px; border-top:1px solid var(--hair);
    font-size:13px; color:var(--muted); text-align:center; font-variant-numeric:tabular-nums}
  .eq b{color:var(--ink); font-weight:600}
  .specs{display:grid; grid-template-columns:1fr 1fr 1fr; gap:14px 8px}
  .spec b{display:block; font-size:17px; font-weight:600; letter-spacing:-.01em}
  .spec span{display:block; font-size:11px; color:var(--muted2); margin-top:2px}
  .derived{display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:16px}
  .dcard{background:var(--card); border:1px solid var(--hair); border-radius:14px; padding:14px}
  .dcard .dv{font-size:19px; font-weight:600; letter-spacing:-.01em}
  .dcard .dl{font-size:11.5px; color:var(--muted); margin-top:4px; line-height:1.35}
  .tip{display:flex; gap:9px; margin-top:16px; padding:13px 14px; border-radius:12px;
    background:var(--blue-soft); color:var(--ink); font-size:13.5px; line-height:1.45}
  .tip svg{flex:none; color:var(--blue); margin-top:1px}
  .sh-foot{font-size:11.5px; color:var(--muted2); margin-top:18px; line-height:1.5; text-align:center}
  @media (prefers-reduced-motion:reduce){
    .sheet,.backdrop,.bar i{transition:none}
  }
</style>
</head>
<body>
<header>
  <div class="eyebrow">PROTEIN VALUE INDEX</div>
  <h1>Gains for Less</h1>
  <div class="sub">Ranked by protein, not hype</div>
  <div class="meta">__SUBTITLE__</div>
  <div class="caveat">Prices are national averages scaled to your region
  (auto-detected, or pick below) &mdash; <b>not till-verified</b>. Sales tax and
  app deals excluded. Value Score = __WPPD__% protein-per-dollar + __WPD__%
  density, each normalized to the best item = 100. Rankings don&rsquo;t change by
  region &mdash; only prices do. Tap any item for the full breakdown.</div>
</header>
<div class="controls">
  <select id="chain" aria-label="Filter by chain"><option value="">All chains</option></select>
  <input id="q" type="search" placeholder="Search items…" aria-label="Search items">
  <select id="region" aria-label="Pricing region"></select>
</div>
<div class="count" id="count"></div>
<div class="list" id="list"></div>
<p class="empty" id="empty" hidden>No items match.</p>
<footer>__FOOTER__</footer>

<div class="backdrop" id="backdrop" hidden></div>
<div class="sheet" id="sheet" role="dialog" aria-modal="true" aria-labelledby="sh-name" hidden>
  <div class="sheet-grab" id="sheetGrab">
    <div class="handle" id="handle"></div>
    <button class="sheet-close" id="sheetClose" aria-label="Close details">
      <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M1 1l12 12M13 1L1 13"/></svg>
    </button>
    <div id="sheetHead"></div>
  </div>
  <div class="sheet-scroll" id="sheetBody"></div>
</div>

<script>
const DATA = __DATA__;
const W_PPD = __WPPD__, W_PD = __WPD__;              // integer percents (e.g. 60, 40)
const TOTAL = DATA.items.length;
DATA.items.forEach((it, k) => it._id = k);

const chainSel = document.getElementById('chain');
const q = document.getElementById('q');
const list = document.getElementById('list');
const empty = document.getElementById('empty');
const count = document.getElementById('count');

[...new Map(DATA.items.map(i => [i.chain, i.chain_name])).entries()]
  .sort((a, b) => a[1].localeCompare(b[1]))
  .forEach(([slug, name]) => chainSel.add(new Option(name, slug)));

function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
const money = n => n == null ? null : '$' + n.toFixed(2);

/* ---------------- regional pricing ----------------
   A region multiplier scales displayed prices only. Rankings and Value
   Scores are region-invariant: the multiplier is uniform, so it cancels
   out of the normalization. */
const REGIONS = __REGIONS__;
const regionSel = document.getElementById('region');
const regionByCode = Object.fromEntries(REGIONS.list.map(r => [r.code, r]));
const stateRegion = {};
REGIONS.list.forEach(r => r.states.forEach(st => stateRegion[st] = r.code));

function regionLabel(r){
  const pct = Math.round((r.multiplier - 1) * 100);
  const tag = pct === 0 ? 'national avg' : (pct > 0 ? '+' + pct + '%' : pct + '%');
  return 'Prices: ' + r.name + ' · ' + tag;
}
REGIONS.list.forEach(r => regionSel.add(new Option(regionLabel(r), r.code)));
const savedRegion = localStorage.getItem('pv_region');
regionSel.value = (savedRegion && regionByCode[savedRegion]) ? savedRegion : REGIONS.default;
regionSel.onchange = () => { localStorage.setItem('pv_region', regionSel.value); render(); };

// Auto-detect once per visit via free keyless IP lookup (no permission
// prompt). An explicit saved choice always wins; failures fall back silently.
if (!savedRegion) {
  fetch('https://ipwho.is/').then(r => r.json()).then(j => {
    if (j && j.success !== false && j.country_code === 'US') {
      const rc = stateRegion[j.region_code];
      if (rc && rc !== regionSel.value) { regionSel.value = rc; render(); }
    }
  }).catch(() => {});
}

function regionMult(){ return regionByCode[regionSel.value].multiplier; }
function priceOf(i){
  if (i.price_fixed || i.price_national == null) return i.price;
  return Math.round(i.price_national * regionMult() * 100) / 100;
}
function ppdOf(i){
  const p = priceOf(i);
  return p ? Math.round((i.protein_g / p) * 100) / 100 : null;
}

const CHEV = '<svg class="chev" viewBox="0 0 8 14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 1l6 6-6 6"/></svg>';

function render(){
  const slug = chainSel.value, term = q.value.trim().toLowerCase();
  const rows = DATA.items.filter(i =>
    (!slug || i.chain === slug) &&
    (!term || (i.item + ' ' + i.chain_name).toLowerCase().includes(term)));
  count.textContent = rows.length + (rows.length === 1 ? ' item' : ' items')
    + (slug ? ' · ' + chainSel.options[chainSel.selectedIndex].text : ' · ranked by value');
  list.innerHTML = rows.map((i, idx) => {
    const scored = i.value_score != null;
    const pos = scored ? (slug ? idx + 1 : i.rank) : '·';
    const price = money(priceOf(i)) || 'no price';
    const best = idx === 0 && !slug && scored ? '<div class="best">Best value</div>' : '';
    return `<button class="row${idx===0&&scored?' top':''}" data-id="${i._id}">
      <span class="rk">${pos}</span>
      <span class="main">
        <span class="nm">${esc(i.item)}</span>
        <span class="ch">${esc(i.chain_name)} · ${i.protein_g}g · ${price}</span>
        ${best}
      </span>
      <span class="sc${scored?'':' no'}">${scored ? i.value_score.toFixed(1) : '—'}</span>
      ${CHEV}
    </button>`;
  }).join('');
  empty.hidden = rows.length > 0;
  list.hidden = rows.length === 0;
}

/* ---------------- detail sheet ---------------- */
const backdrop = document.getElementById('backdrop');
const sheet = document.getElementById('sheet');
const sheetBody = document.getElementById('sheetBody');
let lastFocus = null;

function sheetHTML(i){
  const scored = i.value_score != null;
  const rPrice = priceOf(i);
  const price = money(rPrice);
  const ppdN = i.ppd_norm, densN = i.density_norm;
  const fP = (W_PPD/100), fD = (W_PD/100);
  const cost100 = (rPrice!=null) ? (100/i.protein_g)*rPrice : null;
  const mult100 = (100/i.protein_g);
  const per25 = (rPrice!=null) ? (25/i.protein_g)*rPrice : null;
  const pctTop = scored ? Math.max(1, Math.round(i.rank/TOTAL*100)) : null;

  const breakdown = scored ? `
    <div class="panel">
      <div class="panel-h">Score breakdown</div>
      <div class="brk">
        <div class="brk-top"><span class="brk-name">Value per dollar <span class="w">· ${W_PPD}%</span></span>
          <span class="brk-val">${ppdN.toFixed(1)}</span></div>
        <div class="bar"><i data-w="${Math.max(2,Math.min(100,ppdN))}"></i></div>
      </div>
      <div class="brk">
        <div class="brk-top"><span class="brk-name">Protein density <span class="w">· ${W_PD}%</span></span>
          <span class="brk-val">${densN.toFixed(1)}</span></div>
        <div class="bar g"><i data-w="${Math.max(2,Math.min(100,densN))}"></i></div>
      </div>
      <div class="eq">${fP.toFixed(1)} × ${ppdN.toFixed(1)} &nbsp;+&nbsp; ${fD.toFixed(1)} × ${densN.toFixed(1)} &nbsp;=&nbsp; <b>${i.value_score.toFixed(1)}</b></div>
    </div>` : '';

  const derived = (rPrice!=null) ? `
    <div class="derived">
      <div class="dcard"><div class="dv">${money(cost100)}</div>
        <div class="dl">to reach <b>100 g protein</b> (≈ ${mult100.toFixed(1)}×)</div></div>
      <div class="dcard"><div class="dv">${money(per25)}</div>
        <div class="dl">per <b>25 g protein</b> serving</div></div>
    </div>` : '';

  const tip = i.notes ? `
    <div class="tip">
      <svg width="15" height="15" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0a8 8 0 100 16A8 8 0 008 0zm.9 12H7.1V7h1.8v5zM8 5.6A1.05 1.05 0 118 3.5a1.05 1.05 0 010 2.1z"/></svg>
      <span>${esc(i.notes)}</span>
    </div>` : '';

  const head = `
    <div class="sh-rank">${scored ? `#${i.rank} of ${TOTAL} · top ${pctTop}%` : 'Unranked'}</div>
    <div class="sh-name" id="sh-name">${esc(i.item)}</div>
    <div class="sh-ch">${esc(i.chain_name)}</div>
    <div class="sh-hero">
      <div class="sh-score">${scored ? i.value_score.toFixed(1) : '—'}</div>
      <div class="sh-scorelbl">value<br>score</div>
      ${idxIsBest(i) ? '<span class="sh-pill">Best value</span>' : ''}
    </div>`;
  const body = `
    ${breakdown}
    <div class="panel">
      <div class="panel-h">Nutrition &amp; price</div>
      <div class="specs">
        <div class="spec"><b>${i.protein_g} g</b><span>Protein</span></div>
        <div class="spec"><b>${i.calories}</b><span>Calories</span></div>
        <div class="spec"><b>${price || '—'}</b><span>Price</span></div>
        <div class="spec"><b>${ppdOf(i) ?? '—'}</b><span>g / dollar</span></div>
        <div class="spec"><b>${i.protein_per_100cal}</b><span>g / 100 cal</span></div>
        <div class="spec"><b>${Math.round(i.calories / (i.protein_g||1))}</b><span>cal / g protein</span></div>
      </div>
    </div>
    ${derived}
    ${tip}
    <div class="sh-foot">Price: ${esc(i.price_kind || 'n/a')}${i.price_fixed ? '' : ' · shown for ' + esc(regionByCode[regionSel.value].name)} — not till-verified. Confirm in store.</div>`;
  return { head, body };
}

function idxIsBest(i){ return i.rank === 1; }

function openSheet(id){
  const i = DATA.items[id];
  if(!i) return;
  lastFocus = document.activeElement;
  const c = sheetHTML(i);
  document.getElementById('sheetHead').innerHTML = c.head;
  sheetBody.innerHTML = c.body;
  backdrop.hidden = false; sheet.hidden = false;
  requestAnimationFrame(() => {
    backdrop.classList.add('open'); sheet.classList.add('open');
    sheetBody.scrollTop = 0;
    sheetBody.querySelectorAll('.bar i').forEach(b => { b.style.width = b.dataset.w + '%'; });
  });
  document.getElementById('sheetClose').focus();
  document.body.style.overflow = 'hidden';
}
function closeSheet(){
  backdrop.classList.remove('open'); sheet.classList.remove('open');
  document.body.style.overflow = '';
  const done = () => { backdrop.hidden = true; sheet.hidden = true; sheet.removeEventListener('transitionend', done); };
  sheet.addEventListener('transitionend', done);
  if (matchMedia('(prefers-reduced-motion:reduce)').matches) done();
  if (lastFocus) lastFocus.focus();
}

list.addEventListener('click', e => {
  const row = e.target.closest('.row'); if(row) openSheet(+row.dataset.id);
});
backdrop.addEventListener('click', closeSheet);
document.getElementById('sheetClose').addEventListener('click', closeSheet);
document.addEventListener('keydown', e => { if(e.key === 'Escape' && !sheet.hidden) closeSheet(); });

/* swipe-down-to-dismiss: from the handle always, or from anywhere on the
   sheet once its content is scrolled to the top (so it never fights
   normal scrolling inside the sheet) */
(function(){
  let y0 = null, dy = 0, dragging = false;

  function onDown(e){
    if (e.target.closest('#sheetClose')) return;
    y0 = e.clientY; dy = 0;
    // the whole header (handle + title + score) is a drag target;
    // the scrolling body only initiates a drag when already at the top
    dragging = !!e.target.closest('#sheetGrab');
    if (dragging) { sheet.style.transition = 'none'; sheet.setPointerCapture(e.pointerId); }
  }
  function onMove(e){
    if (y0 == null) return;
    const raw = e.clientY - y0;
    if (!dragging) {
      if (raw > 6 && sheetBody.scrollTop <= 0) {
        dragging = true;
        sheet.style.transition = 'none';
        sheet.setPointerCapture(e.pointerId);
      } else {
        return; // let the content scroll normally
      }
    }
    dy = Math.max(0, raw);
    e.preventDefault();
    sheet.style.transform = `translateY(${dy}px)`;
  }
  function onUp(){
    if (!dragging) { y0 = null; return; }
    sheet.style.transition = ''; sheet.style.transform = '';
    if (dy > 90) closeSheet();
    dragging = false; y0 = null;
  }
  sheet.addEventListener('pointerdown', onDown);
  sheet.addEventListener('pointermove', onMove, { passive: false });
  sheet.addEventListener('pointerup', onUp);
  sheet.addEventListener('pointercancel', onUp);
})();

chainSel.onchange = render;
q.oninput = render;
render();
</script>
</body>
</html>
"""


def write_html(scoring, regions_cfg, rows, path):
    today = date.today().isoformat()
    n_chains = len({r["chain"] for r in rows})
    n_ranked = sum(1 for r in rows if r["rank"])
    top = rows[0]
    subtitle = (f"{n_ranked} items ≥ {scoring['protein_threshold_g']} g protein "
                f"across {n_chains} chains · updated {today}")
    footer = (f"Top pick: {top['chain_name']} — {top['item']} "
              f"(score {top['value_score']}). Generated {today} from data/items.csv.")
    regions_payload = {
        "default": regions_cfg["default_region"],
        "list": [{"code": r["code"], "name": r["name"],
                  "multiplier": r["multiplier"], "states": r["states"]}
                 for r in regions_cfg["regions"]],
    }
    html = (HTML_TEMPLATE
            .replace("__SUBTITLE__", subtitle)
            .replace("__FOOTER__", footer)
            .replace("__UPLIFT__", str(scoring["pnw_uplift_pct"]))
            .replace("__WPPD__", str(int(scoring["weights"]["protein_per_dollar"] * 100)))
            .replace("__WPD__", str(int(scoring["weights"]["protein_density"] * 100)))
            .replace("__REGIONS__", json.dumps(regions_payload, separators=(",", ":")))
            .replace("__DATA__", json.dumps({"items": rows}, separators=(",", ":"))))
    path.write_text(html)


def main():
    scoring, chains, regions_cfg = load_config()
    items = load_items(chains)
    overrides = load_manual_prices()
    rows = compute(scoring, chains, items, overrides)
    best = best_per_chain(rows)

    (ROOT / "docs").mkdir(exist_ok=True)
    write_json(scoring, regions_cfg, rows, ROOT / "docs/data.json")
    write_markdown(scoring, rows, best, ROOT / "RANKINGS.md")
    write_html(scoring, regions_cfg, rows, ROOT / "docs/index.html")

    print(f"ranked {sum(1 for r in rows if r['rank'])} items "
          f"({len(rows)} total) across {len({r['chain'] for r in rows})} chains")
    print("wrote docs/index.html, docs/data.json, RANKINGS.md")
    top = rows[0]
    print(f"#1: {top['chain_name']} — {top['item']} "
          f"(score {top['value_score']}, {fmt_price(top)}, {top['protein_g']:g} g)")


if __name__ == "__main__":
    main()
