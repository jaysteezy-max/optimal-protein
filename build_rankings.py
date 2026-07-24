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
    return scoring, chains


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
        elif it["national_price_usd"] is not None:
            price = round(it["national_price_usd"] * uplift, 2)
            price_kind = "national +uplift"
        else:
            price = None
            price_kind = "no price"
        rows.append({
            "chain": it["chain"],
            "chain_name": chains[it["chain"]]["name"],
            "item": it["item"],
            "protein_g": it["protein_g"],
            "calories": it["calories"],
            "price": price,
            "price_kind": price_kind,
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


def write_json(scoring, rows, path):
    payload = {
        "generated": date.today().isoformat(),
        "methodology": {
            "weights": scoring["weights"],
            "protein_threshold_g": scoring["protein_threshold_g"],
            "pnw_uplift_pct": scoring["pnw_uplift_pct"],
            "caveat": ("Prices are national averages + PNW uplift, not "
                       "till-verified. Sales tax excluded. App deals excluded."),
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
  :root {
    --bg: #f3f5f4; --card: #ffffff; --ink: #14181a; --muted: #5f6a71;
    --line: #e2e7e5; --line-strong: #ccd4d1;
    --accent: #0f7a52; --accent-ink: #ffffff; --accent-soft: #e3f3ec;
    --flag: #a8501c;
    --gold: #b8860b; --silver: #6b7378; --bronze: #a5622c;
    --radius: 13px;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #12161a; --card: #1b2126; --ink: #e9edeb; --muted: #98a3a9;
      --line: #29323a; --line-strong: #3a454d;
      --accent: #34b483; --accent-ink: #062319; --accent-soft: #17352a;
      --flag: #e08a52;
      --gold: #e6b23e; --silver: #b7c0c7; --bronze: #d08a54;
    }
  }
  :root[data-theme="light"] {
    --bg: #f3f5f4; --card: #ffffff; --ink: #14181a; --muted: #5f6a71;
    --line: #e2e7e5; --line-strong: #ccd4d1;
    --accent: #0f7a52; --accent-ink: #ffffff; --accent-soft: #e3f3ec;
    --flag: #a8501c; --gold: #b8860b; --silver: #6b7378; --bronze: #a5622c;
  }
  :root[data-theme="dark"] {
    --bg: #12161a; --card: #1b2126; --ink: #e9edeb; --muted: #98a3a9;
    --line: #29323a; --line-strong: #3a454d;
    --accent: #34b483; --accent-ink: #062319; --accent-soft: #17352a;
    --flag: #e08a52; --gold: #e6b23e; --silver: #b7c0c7; --bronze: #d08a54;
  }
  * { box-sizing: border-box; margin: 0; }
  html { -webkit-text-size-adjust: 100%; }
  body {
    background: var(--bg); color: var(--ink);
    font: 15px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    padding: 18px 12px 56px; max-width: 720px; margin: 0 auto;
    overscroll-behavior: contain;
    font-variant-numeric: tabular-nums;
  }
  header { margin-bottom: 12px; }
  h1 { font-size: 1.4rem; letter-spacing: -0.02em; }
  .sub { color: var(--muted); font-size: 0.78rem; margin-top: 4px; }
  .caveat {
    border: 1px solid var(--line); border-left: 3px solid var(--accent);
    border-radius: 8px; padding: 8px 11px; color: var(--muted);
    font-size: 0.74rem; line-height: 1.35; margin-top: 12px;
  }
  .caveat b { color: var(--ink); font-weight: 600; }
  .controls {
    position: sticky; top: 0; z-index: 3; background: var(--bg);
    padding: 12px 0 10px; margin-top: 4px;
    display: grid; grid-template-columns: 1fr 1fr; gap: 8px;
  }
  select, input[type=search] {
    width: 100%; padding: 10px 12px; border: 1px solid var(--line-strong);
    border-radius: 10px; background: var(--card); color: var(--ink);
    font-size: 0.95rem; -webkit-appearance: none; appearance: none;
  }
  input[type=search]:focus, select:focus {
    outline: 2px solid var(--accent); outline-offset: 1px; border-color: transparent;
  }
  .count { color: var(--muted); font-size: 0.72rem; padding: 2px 2px 8px; }

  .row {
    background: var(--card); border: 1px solid var(--line); border-radius: var(--radius);
    padding: 11px 13px; margin-bottom: 7px;
    display: grid; grid-template-columns: 2.1rem 1fr auto; column-gap: 11px;
    align-items: center;
  }
  .row.r1 { border-left: 3px solid var(--gold); }
  .row.r2 { border-left: 3px solid var(--silver); }
  .row.r3 { border-left: 3px solid var(--bronze); }
  .rk { text-align: center; font-weight: 700; font-size: 1.1rem; color: var(--muted); }
  .r1 .rk { color: var(--gold); }
  .r2 .rk { color: var(--silver); }
  .r3 .rk { color: var(--bronze); }
  .main { min-width: 0; }
  .nm { font-weight: 650; font-size: 0.96rem; letter-spacing: -0.01em; }
  .ch { color: var(--muted); font-size: 0.78rem; margin-top: 1px; }
  .sc {
    background: var(--accent); color: var(--accent-ink);
    border-radius: 10px; padding: 7px 10px; text-align: center; min-width: 3.3rem;
    font-weight: 700; font-size: 1.05rem;
  }
  .sc small { display: block; font-weight: 600; font-size: 0.52rem;
    letter-spacing: 0.08em; opacity: 0.82; margin-top: 1px; }
  .sc.noscore { background: var(--line); color: var(--muted); }
  .st { color: var(--muted); font-size: 0.79rem; margin-top: 4px; }
  .st b { color: var(--ink); font-weight: 600; }
  .st .sep { opacity: 0.45; margin: 0 5px; }
  .meter { height: 5px; background: var(--line); border-radius: 3px;
    overflow: hidden; margin-top: 7px; }
  .meter i { display: block; height: 100%; background: var(--accent); border-radius: 3px; }
  .r1 .meter i { background: var(--gold); }
  .r2 .meter i { background: var(--silver); }
  .r3 .meter i { background: var(--bronze); }
  .note { font-size: 0.73rem; color: var(--flag); margin-top: 5px; }
  .empty { color: var(--muted); text-align: center; padding: 28px 0; }
  footer { color: var(--muted); font-size: 0.68rem; text-align: center;
    margin-top: 18px; line-height: 1.5; }
</style>
</head>
<body>
<header>
  <h1>Protein Value &mdash; PNW</h1>
  <div class="sub">__SUBTITLE__</div>
  <div class="caveat">Prices are national averages + __UPLIFT__% PNW uplift &mdash;
  <b>not till-verified</b>, confirm in store. Sales tax and app deals excluded.
  Value Score = __WPPD__% protein-per-dollar + __WPD__% protein density (per 100 cal),
  each normalized to the best item = 100.</div>
</header>
<div class="controls">
  <select id="chain" aria-label="Filter by chain"><option value="">All chains</option></select>
  <input id="q" type="search" placeholder="Search items…" aria-label="Search items">
</div>
<div class="count" id="count"></div>
<div id="list"></div>
<p class="empty" id="empty" hidden>No items match.</p>
<footer>__FOOTER__</footer>
<script>
const DATA = __DATA__;
const chainSel = document.getElementById('chain');
const q = document.getElementById('q');
const list = document.getElementById('list');
const empty = document.getElementById('empty');
const count = document.getElementById('count');

[...new Map(DATA.items.map(i => [i.chain, i.chain_name])).entries()]
  .sort((a, b) => a[1].localeCompare(b[1]))
  .forEach(([slug, name]) => chainSel.add(new Option(name, slug)));

function esc(s) {
  return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}
function num(n) { return n == null ? '—' : n; }

function render() {
  const slug = chainSel.value, term = q.value.trim().toLowerCase();
  const rows = DATA.items.filter(i =>
    (!slug || i.chain === slug) &&
    (!term || (i.item + ' ' + i.chain_name).toLowerCase().includes(term)));
  count.textContent = rows.length + (rows.length === 1 ? ' item' : ' items')
    + (slug ? ' · ' + chainSel.options[chainSel.selectedIndex].text : ' · ranked by value');
  list.innerHTML = rows.map((i, idx) => {
    const scored = i.value_score != null;
    const medal = scored && idx < 3 ? ' r' + (idx + 1) : '';
    const pos = scored ? (slug ? idx + 1 : i.rank) : '·';
    const price = i.price != null ? '$' + i.price.toFixed(2) : 'no price';
    const w = scored ? Math.max(3, Math.min(100, i.value_score)) : 0;
    return `<div class="row${medal}">
      <div class="rk">${pos}</div>
      <div class="main">
        <div class="nm">${esc(i.item)}</div><div class="ch">${esc(i.chain_name)}</div>
        <div class="st"><b>${price}</b><span class="sep">·</span><b>${i.protein_g}g</b> protein<span class="sep">·</span>${i.calories} cal<span class="sep">·</span>${num(i.protein_per_dollar)} g/$<span class="sep">·</span>${i.protein_per_100cal} g/100cal</div>
        ${scored ? `<div class="meter"><i style="width:${w}%"></i></div>` : ''}
        ${i.notes || !scored ? `<div class="note">${esc([i.notes, scored ? '' : 'no price — add one in data/items.csv'].filter(Boolean).join(' · '))}</div>` : ''}
      </div>
      <div class="sc ${scored ? '' : 'noscore'}">${scored ? i.value_score : '—'}<small>SCORE</small></div>
    </div>`;
  }).join('');
  empty.hidden = rows.length > 0;
}
chainSel.onchange = render;
q.oninput = render;
render();
</script>
</body>
</html>
"""


def write_html(scoring, rows, path):
    today = date.today().isoformat()
    n_chains = len({r["chain"] for r in rows})
    n_ranked = sum(1 for r in rows if r["rank"])
    top = rows[0]
    subtitle = (f"{n_ranked} items ≥ {scoring['protein_threshold_g']} g protein "
                f"across {n_chains} chains · updated {today}")
    footer = (f"Top pick: {top['chain_name']} — {top['item']} "
              f"(score {top['value_score']}). Generated {today} from data/items.csv.")
    html = (HTML_TEMPLATE
            .replace("__SUBTITLE__", subtitle)
            .replace("__FOOTER__", footer)
            .replace("__UPLIFT__", str(scoring["pnw_uplift_pct"]))
            .replace("__WPPD__", str(int(scoring["weights"]["protein_per_dollar"] * 100)))
            .replace("__WPD__", str(int(scoring["weights"]["protein_density"] * 100)))
            .replace("__DATA__", json.dumps({"items": rows}, separators=(",", ":"))))
    path.write_text(html)


def main():
    scoring, chains = load_config()
    items = load_items(chains)
    overrides = load_manual_prices()
    rows = compute(scoring, chains, items, overrides)
    best = best_per_chain(rows)

    (ROOT / "docs").mkdir(exist_ok=True)
    write_json(scoring, rows, ROOT / "docs/data.json")
    write_markdown(scoring, rows, best, ROOT / "RANKINGS.md")
    write_html(scoring, rows, ROOT / "docs/index.html")

    print(f"ranked {sum(1 for r in rows if r['rank'])} items "
          f"({len(rows)} total) across {len({r['chain'] for r in rows})} chains")
    print("wrote docs/index.html, docs/data.json, RANKINGS.md")
    top = rows[0]
    print(f"#1: {top['chain_name']} — {top['item']} "
          f"(score {top['value_score']}, {fmt_price(top)}, {top['protein_g']:g} g)")


if __name__ == "__main__":
    main()
