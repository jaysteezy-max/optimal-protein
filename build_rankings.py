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
        raw_sat = (it.get("sat_fat_g") or "").strip()
        it["sat_fat_g"] = float(raw_sat) if raw_sat else None
        it["verified"] = "web-verified" in (it.get("source") or "")
        # An item pulled from the menu keeps its last published data for
        # reference but can never be ranked. Tracked separately so the page
        # doesn't imply it is merely waiting on verification.
        it["off_menu"] = "off-menu" in (it.get("source") or "")
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
    w_lean = scoring["weights"]["leanness"]
    w_sat = scoring["weights"]["sat_fat"]

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
            "sat_fat_g": it["sat_fat_g"],
            "verified": it["verified"],
            "off_menu": it["off_menu"],
            "price": price,
            "price_kind": price_kind,
            "price_national": price_national,
            "price_fixed": price_fixed,
            "notes": (it.get("notes") or "").strip(),
            "protein_per_dollar": round(it["protein_g"] / price, 2) if price else None,
            "protein_per_100cal": round(it["protein_g"] / (it["calories"] / 100.0), 2),
            # % of calories that come from protein (4 cal per gram)
            "leanness_pct": round(100 * it["protein_g"] * 4 / it["calories"], 1),
            "satfat_per_g": (round(it["sat_fat_g"] / it["protein_g"], 3)
                             if it["sat_fat_g"] is not None else None),
        })

    # HARD RULE: only web-verified rows with sat-fat data and a price are
    # scored. Everything else is listed but unranked until verified.
    def eligible(r):
        return r["verified"] and r["sat_fat_g"] is not None and r["price"] is not None

    scored = [r for r in rows if eligible(r)]
    if not scored:
        sys.exit("no verified, priced items with sat-fat data — nothing to rank")
    max_ppd = max(r["protein_per_dollar"] for r in scored)
    max_lean = max(r["leanness_pct"] for r in scored)
    sat_ratios = [r["satfat_per_g"] for r in scored]
    sat_min, sat_max = min(sat_ratios), max(sat_ratios)

    for r in rows:
        if eligible(r):
            r["ppd_norm"] = round(100 * r["protein_per_dollar"] / max_ppd, 1)
            r["lean_norm"] = round(100 * r["leanness_pct"] / max_lean, 1)
            # penalty scaled so cleanest = 100, fattiest = 0
            if sat_max > sat_min:
                r["satfat_norm"] = round(
                    100 * (sat_max - r["satfat_per_g"]) / (sat_max - sat_min), 1)
            else:
                r["satfat_norm"] = 100.0
            r["value_score"] = round(w_ppd * r["ppd_norm"] + w_lean * r["lean_norm"]
                                     + w_sat * r["satfat_norm"], 1)
            r["unranked_reason"] = None
        else:
            r["ppd_norm"] = None
            r["lean_norm"] = None
            r["satfat_norm"] = None
            r["value_score"] = None
            if r["off_menu"]:
                r["unranked_reason"] = "off menu"
            elif not r["verified"] or r["sat_fat_g"] is None:
                r["unranked_reason"] = "awaiting verification"
            else:
                r["unranked_reason"] = "no price"

    # scored items ranked first; unverified/unpriced flagged at the bottom
    rows.sort(key=lambda r: (r["value_score"] is None,
                             -(r["value_score"] or 0),
                             -r["leanness_pct"]))
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
            "hard_rule": ("Only web-verified rows with sat-fat data are "
                          "scored. Unverified rows are listed unranked as "
                          "awaiting verification; items pulled from the menu "
                          "are listed unranked as off menu."),
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
        f"protein-per-dollar + {int(scoring['weights']['leanness']*100)}% "
        f"leanness (% calories from protein) + "
        f"{int(scoring['weights']['sat_fat']*100)}% low-saturated-fat, "
        "each scaled so the best scored item = 100. **Only web-verified items "
        "are scored** — unverified rows are listed unranked until verified, "
        "and items pulled from the menu are listed unranked as off menu.",
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
        "| # | Chain | Item | Price | Protein | Cal | Sat fat | Prot/$ | Lean % | Score |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        rank = r["rank"] if r["rank"] is not None else "–"
        ppd = r["protein_per_dollar"] if r["protein_per_dollar"] is not None else "—"
        sat = f"{r['sat_fat_g']:g} g" if r["sat_fat_g"] is not None else "—"
        score = (r["value_score"] if r["value_score"] is not None
                 else r["unranked_reason"])
        lines.append(
            f"| {rank} | {r['chain_name']} | {r['item']} | {fmt_price(r)} "
            f"| {r['protein_g']:g} g | {r['calories']:g} | {sat} | {ppd} "
            f"| {r['leanness_pct']:g}% | {score} |")
    lines.append("")
    path.write_text("\n".join(lines))


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Protein Value — PNW</title>
<meta name="description" content="The best protein-per-dollar fast-food orders across the Pacific Northwest. Only verified items are ranked.">
<meta name="theme-color" content="#0071e3">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%230071e3'/%3E%3Crect x='13' y='34' width='9' height='16' rx='2.5' fill='white'/%3E%3Crect x='27.5' y='25' width='9' height='25' rx='2.5' fill='white'/%3E%3Crect x='42' y='15' width='9' height='35' rx='2.5' fill='white'/%3E%3C/svg%3E">
<meta property="og:type" content="website">
<meta property="og:title" content="Protein Value Tracker — Gains for Less">
<meta property="og:description" content="The best protein-per-dollar fast-food orders across the PNW. Only verified items are ranked.">
<meta property="og:url" content="https://jaysteezy-max.github.io/optimal-protein/">
<meta property="og:image" content="https://jaysteezy-max.github.io/optimal-protein/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Protein Value Tracker — Gains for Less">
<meta name="twitter:description" content="The best protein-per-dollar fast-food orders across the PNW. Only verified items are ranked.">
<meta name="twitter:image" content="https://jaysteezy-max.github.io/optimal-protein/og.png">
<style>
  :root{
    --bg:#f5f5f7; --card:#ffffff; --ink:#1d1d1f; --muted:#6e6e73; --muted2:#86868b;
    --line:#e5e5ea; --hair:#ebebf0; --blue:#0071e3; --blue-soft:#e8f1fd;
    --good:#1a8f4c; --warn:#c93400; --shadow:0 4px 22px rgba(0,0,0,.06); --radius:18px;
  }
  @media (prefers-color-scheme:dark){
    :root{
      --bg:#000000; --card:#1c1c1e; --ink:#f5f5f7; --muted:#98989d; --muted2:#8e8e93;
      --line:#2c2c2e; --hair:#2c2c2e; --blue:#0a84ff; --blue-soft:#0a2540;
      --good:#30d158; --warn:#ff9f0a; --shadow:0 4px 22px rgba(0,0,0,.5);
    }
  }
  :root[data-theme="light"]{
    --bg:#f5f5f7; --card:#ffffff; --ink:#1d1d1f; --muted:#6e6e73; --muted2:#86868b;
    --line:#e5e5ea; --hair:#ebebf0; --blue:#0071e3; --blue-soft:#e8f1fd;
    --good:#1a8f4c; --warn:#c93400; --shadow:0 4px 22px rgba(0,0,0,.06);
  }
  :root[data-theme="dark"]{
    --bg:#000000; --card:#1c1c1e; --ink:#f5f5f7; --muted:#98989d; --muted2:#8e8e93;
    --line:#2c2c2e; --hair:#2c2c2e; --blue:#0a84ff; --blue-soft:#0a2540;
    --good:#30d158; --warn:#ff9f0a; --shadow:0 4px 22px rgba(0,0,0,.5);
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
  .pr{display:inline-block}  /* transformable for the region price roll */
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
    max-height:90vh; display:flex; flex-direction:column; touch-action:none;
    transform:translateY(100%); transition:transform .32s cubic-bezier(.32,.72,0,1)}
  .sheet.open{transform:translateY(0)}
  .sheet[hidden],.m-sheet[hidden]{display:none}  /* [hidden] must beat the flex above */
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
    -webkit-overflow-scrolling:touch; touch-action:none}
  .sh-rank{font-size:11px; font-weight:600; letter-spacing:.06em; text-transform:uppercase;
    color:var(--muted2)}
  .sh-name{font-size:24px; font-weight:600; letter-spacing:-.02em; line-height:1.1; margin-top:8px}
  .sh-ch{font-size:14px; color:var(--muted); margin-top:3px}
  .sh-chlink{display:inline-flex; align-items:center; gap:7px; background:none; border:0;
    font:inherit; font-size:14px; color:var(--muted); cursor:pointer; padding:2px 0;
    -webkit-tap-highlight-color:transparent}
  .sh-chsee{display:inline-flex; align-items:center; gap:3px; font-size:12px; font-weight:600;
    color:var(--blue)}
  .sh-chsee .chev{width:6px; height:10px; color:var(--blue); opacity:1}
  .sh-chlink:focus-visible{outline:2px solid var(--blue); outline-offset:2px; border-radius:6px}
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
  .bar.w i{background:var(--warn)}
  .pend{font-size:10.5px; font-weight:590; color:var(--muted2)}
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
  /* ---- toolbar: count + sort + actions ---- */
  .listbar{display:flex; align-items:center; gap:10px; padding:14px 6px 8px}
  .listbar .count{padding:0; flex:1; min-width:0}
  .sortwrap{position:relative; flex:none}
  #sort{font-size:12px; font-weight:590; color:var(--ink); background:transparent;
    border:0; box-shadow:none; padding:4px 20px 4px 8px; width:auto; border-radius:8px;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='7' viewBox='0 0 12 8' fill='none' stroke='%2386868b' stroke-width='1.8' stroke-linecap='round'%3E%3Cpath d='M1 1l5 5 5-5'/%3E%3C/svg%3E");
    background-repeat:no-repeat; background-position:right 6px center}
  #sort:focus{outline:none; box-shadow:0 0 0 3px color-mix(in srgb,var(--blue) 20%,transparent)}
  .actions{display:flex; gap:8px; padding:0 6px 14px}
  .act{flex:1; font:inherit; font-size:13px; font-weight:590; letter-spacing:-.01em;
    color:var(--blue); background:var(--blue-soft); border:0; border-radius:11px;
    padding:10px 12px; cursor:pointer; display:flex; align-items:center; justify-content:center;
    gap:6px; -webkit-tap-highlight-color:transparent; transition:transform .12s ease}
  .act:active{transform:scale(.97)}
  .act:focus-visible{outline:2px solid var(--blue); outline-offset:2px}
  .act svg{flex:none}
  .act.on{background:var(--blue); color:#fff}
  /* compare selection state on rows */
  .row.cmp{cursor:pointer}
  .row.picked{background:color-mix(in srgb,var(--blue) 9%,transparent)}
  .row .tick{width:22px; height:22px; border-radius:50%; border:2px solid var(--muted2);
    display:none; place-items:center; flex:none; color:#fff}
  body.compare .row .chev{display:none}
  body.compare .row .tick{display:grid}
  body.compare .row.picked .tick{background:var(--blue); border-color:var(--blue)}
  body.compare .row .tick svg{opacity:0}
  body.compare .row.picked .tick svg{opacity:1}
  .order-badge{display:inline-block; font-size:10.5px; font-weight:600; letter-spacing:.02em;
    color:var(--good); background:color-mix(in srgb,var(--good) 15%,transparent);
    border-radius:6px; padding:1px 6px; margin-top:5px}
  /* ---- lightweight secondary modal (compare / budget) ---- */
  .m-sheet{position:fixed; left:0; right:0; bottom:0; z-index:45; margin:0 auto; max-width:600px;
    background:var(--bg); border-radius:22px 22px 0 0; box-shadow:0 -8px 40px rgba(0,0,0,.28);
    max-height:92vh; display:flex; flex-direction:column;
    transform:translateY(100%); transition:transform .32s cubic-bezier(.32,.72,0,1)}
  .m-sheet.open{transform:translateY(0)}
  .m-head{flex:none; display:flex; align-items:center; padding:18px 20px 12px; gap:12px}
  .m-head h2{font-size:20px; font-weight:600; letter-spacing:-.02em; flex:1}
  .m-body{flex:1; min-height:0; overflow-y:auto; padding:0 20px 30px; -webkit-overflow-scrolling:touch}
  .cmp-grid{display:grid; grid-template-columns:1fr 1fr; gap:12px}
  .cmp-col{background:var(--card); border:1px solid var(--hair); border-radius:14px; padding:14px}
  .cmp-col h3{font-size:15px; font-weight:600; letter-spacing:-.01em; line-height:1.2}
  .cmp-col .cc{font-size:12px; color:var(--muted); margin:2px 0 12px}
  .cmp-metric{padding:8px 0; border-top:1px solid var(--hair)}
  .cmp-metric .cm-l{font-size:11px; color:var(--muted2); font-weight:500}
  .cmp-metric .cm-v{font-size:16px; font-weight:600; letter-spacing:-.01em}
  .cmp-metric.win .cm-v{color:var(--good)}
  .fld{margin-bottom:14px}
  .fld label{display:block; font-size:12px; font-weight:600; letter-spacing:.02em;
    text-transform:uppercase; color:var(--muted2); margin-bottom:7px}
  .fld input,.fld select{width:100%; padding:11px 13px; border:1px solid var(--line);
    border-radius:12px; background:var(--card); color:var(--ink); font-size:16px;
    font-family:inherit; -webkit-appearance:none; appearance:none}
  .fld input:focus,.fld select:focus{outline:none; border-color:var(--blue);
    box-shadow:0 0 0 3.5px color-mix(in srgb,var(--blue) 22%,transparent)}
  .b-result{margin-top:4px}
  .b-pick{background:var(--card); border:1px solid var(--hair); border-radius:14px;
    padding:15px; margin-bottom:10px; display:grid; grid-template-columns:1fr auto; gap:10px;
    align-items:center}
  .b-pick .bp-h{font-size:11px; font-weight:600; letter-spacing:.05em; text-transform:uppercase;
    color:var(--blue); margin-bottom:5px}
  .b-pick.combo .bp-h{color:var(--good)}
  .b-pick .bp-n{font-size:15px; font-weight:590; letter-spacing:-.01em; line-height:1.25}
  .b-pick .bp-c{font-size:12px; color:var(--muted); margin-top:3px}
  .b-pick .bp-p{font-size:22px; font-weight:600; letter-spacing:-.02em; text-align:right}
  .b-pick .bp-pl{font-size:10.5px; color:var(--muted2); text-align:right}
  .b-empty{color:var(--muted); font-size:14px; text-align:center; padding:24px 0; line-height:1.5}
  @media (prefers-reduced-motion:reduce){
    .sheet,.backdrop,.bar i,.m-sheet{transition:none}
  }
</style>
</head>
<body>
<header>
  <div class="eyebrow">PROTEIN VALUE INDEX</div>
  <h1>Gains for Less</h1>
  <div class="sub">Ranked by protein, not hype</div>
  <div class="meta">__SUBTITLE__</div>
  <div class="caveat">Only verified items are ranked. Regional price estimates
  &mdash; <b>not till-verified</b>. Before tax and app deals. Tap any item for
  the full breakdown.</div>
</header>
<div class="controls">
  <select id="chain" aria-label="Filter by chain"><option value="">All chains</option></select>
  <input id="q" type="search" placeholder="Search items…" aria-label="Search items">
  <select id="region" aria-label="Pricing region"></select>
</div>
<div class="listbar">
  <div class="count" id="count"></div>
  <div class="sortwrap">
    <select id="sort" aria-label="Sort by">
      <option value="score">Sort: Value score</option>
      <option value="protein">Sort: Most protein</option>
      <option value="ppd">Sort: Protein per $</option>
      <option value="lean">Sort: Leanest</option>
      <option value="price">Sort: Lowest price</option>
    </select>
  </div>
</div>
<div class="actions">
  <button class="act" id="cmpBtn" aria-pressed="false">
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M8 1v14M3 5l-2 3 2 3M13 5l2 3-2 3"/></svg>
    Compare</button>
  <button class="act" id="budgetBtn">
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M8 1v14M11 4H6.5a2.5 2.5 0 000 5h3a2.5 2.5 0 010 5H4"/></svg>
    Budget</button>
</div>
<div class="list" id="list"></div>
<p class="empty" id="empty" hidden>No items match.</p>
<footer>__FOOTER__</footer>

<div class="backdrop" id="backdrop" hidden></div>
<div class="m-sheet" id="mSheet" role="dialog" aria-modal="true" aria-labelledby="mTitle" hidden>
  <div class="m-head">
    <h2 id="mTitle"></h2>
    <button class="sheet-close" id="mClose" aria-label="Close" style="position:static">
      <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M1 1l12 12M13 1L1 13"/></svg>
    </button>
  </div>
  <div class="m-body" id="mBody"></div>
</div>
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

<script src="anime.min.js"></script>
<script>
const DATA = __DATA__;
const W_PPD = __WPPD__, W_LEAN = __WLEAN__, W_SAT = __WSAT__;  // integer percents

/* Motion: anime.js drives staggering, springs, number tweens and the sheet
   timeline. Everything degrades: under prefers-reduced-motion, or if
   anime.min.js fails to load, elements simply appear in their final state. */
const RM = matchMedia('(prefers-reduced-motion:reduce)').matches;
const AN = () => (!RM && window.anime) ? window.anime : null;
const IOS_EASE = 'cubicBezier(.32,.72,0,1)';
const TOTAL = DATA.items.filter(i => i.value_score != null).length;  // ranked count
DATA.items.forEach((it, k) => it._id = k);

/* Why an item isn't ranked: [list badge, sheet header, sheet explanation]. */
const PEND = {
  'no price': ['No price yet', 'Unranked · no price',
    'Verified, but no confirmed price yet — it can\\u2019t be scored on value until one lands.'],
  'off menu': ['Off menu', 'Unranked · off menu',
    'This item has been pulled from the menu. Its last published nutrition is kept here for reference, but it can\\u2019t be ranked.'],
  'awaiting verification': ['Awaiting verification', 'Unranked · awaiting verification',
    'Only web-verified items are scored. This item\\u2019s nutrition and saturated fat haven\\u2019t been independently verified yet, so it\\u2019s listed but not ranked.'],
};
const pendOf = i => PEND[i.unranked_reason] || PEND['awaiting verification'];

const chainSel = document.getElementById('chain');
const q = document.getElementById('q');
const list = document.getElementById('list');
const empty = document.getElementById('empty');
const count = document.getElementById('count');
const cmpSel = new Set();      // item ids chosen for compare
let compareMode = false;

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
regionSel.onchange = () => { localStorage.setItem('pv_region', regionSel.value); render('prices'); };

// Auto-detect once per visit via free keyless IP lookup (no permission
// prompt). An explicit saved choice always wins; failures fall back silently.
if (!savedRegion) {
  fetch('https://ipwho.is/').then(r => r.json()).then(j => {
    if (j && j.success !== false && j.country_code === 'US') {
      const rc = stateRegion[j.region_code];
      if (rc && rc !== regionSel.value) { regionSel.value = rc; render('prices'); }
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

const TICK = '<span class="tick"><svg width="12" height="12" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M2 7.5l3.5 3.5L12 3.5"/></svg></span>';

// sort keys: scored items always sort ahead of pending ones
const SORTS = {
  score:   {label:'ranked by value',   key:i => i.value_score,        dir:-1},
  protein: {label:'most protein',      key:i => i.protein_g,          dir:-1},
  ppd:     {label:'protein per dollar',key:i => ppdOf(i),             dir:-1},
  lean:    {label:'leanest',           key:i => i.leanness_pct,       dir:-1},
  price:   {label:'lowest price',      key:i => priceOf(i),           dir:+1},
};
const sortSel = document.getElementById('sort');

function render(mode){
  const slug = chainSel.value, term = q.value.trim().toLowerCase();
  const sort = SORTS[sortSel.value] || SORTS.score;
  const rows = DATA.items.filter(i =>
    (!slug || i.chain === slug) &&
    (!term || (i.item + ' ' + i.chain_name).toLowerCase().includes(term)));
  // scored first, then the chosen metric; nulls sink to the bottom
  rows.sort((a, b) => {
    const sa = a.value_score != null, sb = b.value_score != null;
    if (sa !== sb) return sa ? -1 : 1;
    const ka = sort.key(a), kb = sort.key(b);
    if (ka == null && kb == null) return 0;
    if (ka == null) return 1;
    if (kb == null) return -1;
    return (ka - kb) * sort.dir;
  });
  count.textContent = rows.length + (rows.length === 1 ? ' item' : ' items')
    + (slug ? ' · ' + chainSel.options[chainSel.selectedIndex].text : ' · ' + sort.label);
  const byScore = sortSel.value === 'score';
  list.innerHTML = rows.map((i, idx) => {
    const scored = i.value_score != null;
    const pos = scored ? (byScore && !slug ? i.rank : idx + 1) : '·';
    const price = money(priceOf(i)) || 'no price';
    // top of an all-chains value sort = best value; top of a single-chain view = order this
    const badge = idx === 0 && scored && byScore
      ? (slug ? '<div class="order-badge">Order this</div>' : '<div class="best">Best value</div>')
      : '';
    const pend = scored ? '' : `<div class="pend">${pendOf(i)[0]}</div>`;
    return `<button class="row cmp${idx===0&&scored&&byScore&&!slug?' top':''}${cmpSel.has(i._id)?' picked':''}" data-id="${i._id}">
      <span class="rk">${pos}</span>
      <span class="main">
        <span class="nm">${esc(i.item)}</span>
        <span class="ch">${esc(i.chain_name)} · ${i.protein_g}g · <span class="pr">${price}</span></span>
        ${badge}${pend}
      </span>
      <span class="sc${scored?'':' no'}">${scored ? i.value_score.toFixed(1) : '—'}</span>
      ${TICK}${CHEV}
    </button>`;
  }).join('');
  empty.hidden = rows.length > 0;
  list.hidden = rows.length === 0;

  const anm = AN();
  if (!anm || mode === 'quiet') return;   // 'quiet' = compare-selection toggle
  if (mode === 'prices'){
    // region change: only the prices changed, so only the prices move
    anm({targets:'#list .pr', translateY:[9,0], opacity:[0,1],
      delay:anm.stagger(14), duration:300, easing:IOS_EASE});
    return;
  }
  // staggered entrance (first screenful only, so long lists stay snappy)
  anm({targets:'#list .row:nth-child(-n+20)', translateY:[8,0], opacity:[0,1],
    delay:anm.stagger(40), duration:420, easing:IOS_EASE});
  const b = list.querySelector('.best');
  if (b) anm({targets:b, scale:[.6,1], opacity:[0,1],
    duration:700, delay:260, easing:'easeOutElastic(1, .5)'});
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
  const cost100 = (rPrice!=null) ? (100/i.protein_g)*rPrice : null;
  const mult100 = (100/i.protein_g);
  const per25 = (rPrice!=null) ? (25/i.protein_g)*rPrice : null;
  const pctTop = scored ? Math.max(1, Math.round(i.rank/TOTAL*100)) : null;

  const breakdown = scored ? `
    <div class="panel">
      <div class="panel-h">Score breakdown</div>
      <div class="brk">
        <div class="brk-top"><span class="brk-name">Value per dollar <span class="w">· ${W_PPD}%</span></span>
          <span class="brk-val">${i.ppd_norm.toFixed(1)}</span></div>
        <div class="bar"><i data-w="${Math.max(2,Math.min(100,i.ppd_norm))}"></i></div>
      </div>
      <div class="brk">
        <div class="brk-top"><span class="brk-name">Leanness <span class="w">· ${W_LEAN}%</span></span>
          <span class="brk-val">${i.lean_norm.toFixed(1)}</span></div>
        <div class="bar g"><i data-w="${Math.max(2,Math.min(100,i.lean_norm))}"></i></div>
      </div>
      <div class="brk">
        <div class="brk-top"><span class="brk-name">Low sat fat <span class="w">· ${W_SAT}%</span></span>
          <span class="brk-val">${i.satfat_norm.toFixed(1)}</span></div>
        <div class="bar w"><i data-w="${Math.max(2,Math.min(100,i.satfat_norm))}"></i></div>
      </div>
      <div class="eq">${(W_PPD/100).toFixed(1)} × ${i.ppd_norm.toFixed(1)}
        &nbsp;+&nbsp; ${(W_LEAN/100).toFixed(1)} × ${i.lean_norm.toFixed(1)}
        &nbsp;+&nbsp; ${(W_SAT/100).toFixed(1)} × ${i.satfat_norm.toFixed(1)}
        &nbsp;=&nbsp; <b>${i.value_score.toFixed(1)}</b></div>
    </div>` : `
    <div class="panel">
      <div class="panel-h">Not ranked yet</div>
      <div style="font-size:13.5px; color:var(--muted); line-height:1.5">${pendOf(i)[2]}</div>
    </div>`;

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
    <div class="sh-rank">${scored ? `#${i.rank} of ${TOTAL} · top ${pctTop}%`
      : pendOf(i)[1]}</div>
    <div class="sh-name" id="sh-name">${esc(i.item)}</div>
    <button class="sh-ch sh-chlink" data-chain="${esc(i.chain)}">${esc(i.chain_name)}
      <span class="sh-chsee">See all ${CHEV}</span></button>
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
        <div class="spec"><b>${i.sat_fat_g != null ? i.sat_fat_g + ' g' : '—'}</b><span>Sat fat</span></div>
        <div class="spec"><b>${i.leanness_pct}%</b><span>Cals from protein</span></div>
        <div class="spec"><b>${ppdOf(i) ?? '—'}</b><span>g / dollar</span></div>
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
    const bars = sheetBody.querySelectorAll('.bar i');
    const anm = AN();
    if (!anm){
      bars.forEach(b => { b.style.width = b.dataset.w + '%'; });
      return;
    }
    // open timeline: the sheet itself rises via its CSS transition (the drag
    // gesture owns that transform); anime choreographs what happens inside it.
    anm({targets:[...document.getElementById('sheetHead').children, ...sheetBody.children],
      translateY:[10,0], opacity:[0,1],
      delay:anm.stagger(55, {start:90}), duration:380, easing:'easeOutQuart'});
    // score count-up
    const sEl = sheet.querySelector('.sh-score');
    if (sEl && i.value_score != null){
      const o = {v: 0};
      anm({targets:o, v:i.value_score, duration:900, easing:'easeOutExpo',
        update:() => { sEl.textContent = o.v.toFixed(1); }});
    }
    // breakdown bars: fill left to right, overshoot once, settle on the score
    // (kill the CSS width transition so it can't fight)
    bars.forEach(b => b.style.transition = 'none');
    anm({targets:bars,
      width:[
        {value:b => Math.min(100, b.dataset.w * 1.05) + '%',
         duration:620, easing:'easeOutQuart'},
        {value:b => b.dataset.w + '%', duration:280, easing:'easeOutSine'}
      ],
      delay:anm.stagger(90, {start:220})});
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
  const row = e.target.closest('.row'); if(!row) return;
  const id = +row.dataset.id;
  if (compareMode){ toggleCompare(id, row); return; }
  openSheet(id);
});
backdrop.addEventListener('click', () => { if(!sheet.hidden) closeSheet(); if(!mSheet.hidden) closeModal(); });
document.getElementById('sheetClose').addEventListener('click', closeSheet);
// tapping the chain name in the sheet → filter the list to that chain (best-to-worst)
document.getElementById('sheetHead').addEventListener('click', e => {
  const link = e.target.closest('.sh-chlink'); if(!link) return;
  chainSel.value = link.dataset.chain; sortSel.value = 'score';
  closeSheet(); render(); window.scrollTo({top:0, behavior: RM ? 'auto' : 'smooth'});
});
document.addEventListener('keydown', e => {
  if(e.key !== 'Escape') return;
  if(!sheet.hidden) closeSheet(); else if(!mSheet.hidden) closeModal();
});

/* ---------------- secondary modal (compare / budget) ---------------- */
const mSheet = document.getElementById('mSheet');
const mBody = document.getElementById('mBody');
const mTitle = document.getElementById('mTitle');
function openModal(title, html){
  lastFocus = document.activeElement;
  mTitle.textContent = title;
  mBody.innerHTML = html;
  backdrop.hidden = false; mSheet.hidden = false;
  requestAnimationFrame(() => { backdrop.classList.add('open'); mSheet.classList.add('open'); mBody.scrollTop = 0; });
  document.getElementById('mClose').focus();
  document.body.style.overflow = 'hidden';
}
function closeModal(){
  backdrop.classList.remove('open'); mSheet.classList.remove('open');
  document.body.style.overflow = '';
  const done = () => { backdrop.hidden = true; mSheet.hidden = true; mSheet.removeEventListener('transitionend', done); };
  mSheet.addEventListener('transitionend', done);
  if (RM) done();
  if (lastFocus) lastFocus.focus();
}
document.getElementById('mClose').addEventListener('click', closeModal);

/* ---------------- compare mode ---------------- */
const cmpBtn = document.getElementById('cmpBtn');
function setCompareMode(on){
  compareMode = on;
  document.body.classList.toggle('compare', on);
  cmpBtn.classList.toggle('on', on);
  cmpBtn.setAttribute('aria-pressed', on);
  cmpBtn.lastChild.textContent = on ? ' Cancel' : ' Compare';
  if (!on){ cmpSel.clear(); render(); }
}
function toggleCompare(id, row){
  if (cmpSel.has(id)) cmpSel.delete(id);
  else { if (cmpSel.size >= 2){ const first = cmpSel.values().next().value; cmpSel.delete(first); } cmpSel.add(id); }
  render('quiet');
  if (cmpSel.size === 2) showCompare();
}
cmpBtn.addEventListener('click', () => setCompareMode(!compareMode));

function cmpRow(label, a, b, fmt, better){
  const va = a, vb = b;
  const winA = better != null && va != null && vb != null && (better > 0 ? va > vb : va < vb) && va !== vb;
  const winB = better != null && va != null && vb != null && (better > 0 ? vb > va : vb < va) && va !== vb;
  return {label, a:fmt(va), b:fmt(vb), winA, winB};
}
function showCompare(){
  const [x, y] = [...cmpSel].map(id => DATA.items[id]);
  const px = priceOf(x), py = priceOf(y);
  const metrics = [
    cmpRow('Value score', x.value_score, y.value_score, v => v==null?'—':v.toFixed(1), +1),
    cmpRow('Protein', x.protein_g, y.protein_g, v => v+' g', +1),
    cmpRow('Price', px, py, v => v==null?'—':money(v), -1),
    cmpRow('Protein / $', ppdOf(x), ppdOf(y), v => v==null?'—':v.toFixed(1), +1),
    cmpRow('Calories', x.calories, y.calories, v => ''+v, -1),
    cmpRow('Cals from protein', x.leanness_pct, y.leanness_pct, v => v+'%', +1),
    cmpRow('Sat fat', x.sat_fat_g, y.sat_fat_g, v => v==null?'—':v+' g', -1),
  ];
  const col = (it, side) => `
    <div class="cmp-col">
      <h3>${esc(it.item)}</h3><div class="cc">${esc(it.chain_name)}</div>
      ${metrics.map(m => `<div class="cmp-metric${m['win'+side]?' win':''}">
        <div class="cm-l">${m.label}</div><div class="cm-v">${m[side==='A'?'a':'b']}</div></div>`).join('')}
    </div>`;
  openModal('Compare', `<div class="cmp-grid">${col(x,'A')}${col(y,'B')}</div>
    <p class="b-empty" style="padding-top:16px">Green marks the better value on each row. Prices shown for ${esc(regionByCode[regionSel.value].name)}.</p>`);
}

/* ---------------- budget mode ---------------- */
const budgetBtn = document.getElementById('budgetBtn');
budgetBtn.addEventListener('click', showBudget);
function showBudget(){
  const chainOpts = [...new Map(DATA.items.map(i => [i.chain, i.chain_name])).entries()]
    .sort((a,b) => a[1].localeCompare(b[1]))
    .map(([s,n]) => `<option value="${s}">${esc(n)}</option>`).join('');
  openModal('Budget', `
    <div class="fld"><label for="bAmt">Budget</label>
      <input id="bAmt" type="number" inputmode="decimal" min="1" step="0.50" value="10" placeholder="10.00"></div>
    <div class="fld"><label for="bChain">Chain (optional)</label>
      <select id="bChain"><option value="">Any chain</option>${chainOpts}</select></div>
    <div class="b-result" id="bResult"></div>`);
  const amt = document.getElementById('bAmt'), ch = document.getElementById('bChain'), res = document.getElementById('bResult');
  const run = () => { res.innerHTML = budgetSolve(parseFloat(amt.value), ch.value); };
  amt.addEventListener('input', run); ch.addEventListener('change', run); run();
}
// pick the single item, and the best 1–3 item combo, that maximize protein within budget
function budgetSolve(budget, chainSlug){
  if (!(budget > 0)) return '<p class="b-empty">Enter a budget to see the most protein you can get.</p>';
  const pool = DATA.items.filter(i => (!chainSlug || i.chain === chainSlug) && priceOf(i) != null && priceOf(i) <= budget);
  if (!pool.length) return `<p class="b-empty">Nothing on the menu fits ${money(budget)}${chainSlug?' at that chain':''}. Try a bigger budget.</p>`;
  const single = pool.slice().sort((a,b) => b.protein_g - a.protein_g)[0];
  // greedy combo: repeatedly add the highest-protein item that still fits (same chain if one is set)
  let best = null;
  const comber = (startChain) => {
    const items = DATA.items.filter(i => i.chain === startChain && priceOf(i) != null);
    let spent = 0, prot = 0, picks = [];
    const avail = items.slice().sort((a,b) => (b.protein_g/priceOf(b)) - (a.protein_g/priceOf(a)));
    for (let n=0; n<3; n++){
      const nxt = avail.find(i => spent + priceOf(i) <= budget);
      if (!nxt) break;
      picks.push(nxt); spent += priceOf(nxt); prot += nxt.protein_g;
      avail.splice(avail.indexOf(nxt), 1);
    }
    return picks.length ? {picks, spent, prot} : null;
  };
  const chains = chainSlug ? [chainSlug] : [...new Set(pool.map(i => i.chain))];
  for (const c of chains){ const r = comber(c); if (r && (!best || r.prot > best.prot)) best = r; }

  const singleCard = `<div class="b-pick"><div><div class="bp-h">Best single item</div>
      <div class="bp-n">${esc(single.item)}</div>
      <div class="bp-c">${esc(single.chain_name)} · ${money(priceOf(single))}</div></div>
      <div><div class="bp-p">${single.protein_g} g</div><div class="bp-pl">protein</div></div></div>`;
  let comboCard = '';
  if (best && best.picks.length > 1 && best.prot > single.protein_g){
    const names = best.picks.map(p => esc(p.item)).join(' + ');
    comboCard = `<div class="b-pick combo"><div><div class="bp-h">Most protein · ${best.picks.length} items, one chain</div>
      <div class="bp-n">${names}</div>
      <div class="bp-c">${esc(best.picks[0].chain_name)} · ${money(best.spent)}</div></div>
      <div><div class="bp-p">${best.prot} g</div><div class="bp-pl">protein</div></div></div>`;
  }
  return singleCard + comboCard;
}

/* Swipe gesture for the sheet. The initial direction of a swipe decides the
   whole gesture: swiping DOWN always drags the sheet down to dismiss (it never
   scrolls); swiping UP reveals any content below the fold. The header always
   dismisses. Touch scrolling is handled here (touch-action:none) so a
   downward swipe can never be swallowed by the scroll container. */
(function(){
  const maxScroll = () => Math.max(0, sheetBody.scrollHeight - sheetBody.clientHeight);
  let y0 = null, scroll0 = 0, mode = null, dy = 0, headerGrab = false;

  function onDown(e){
    // let real controls receive their click (pointer capture would steal it)
    if (e.target.closest('#sheetClose') || e.target.closest('.sh-chlink')) return;
    y0 = e.clientY; scroll0 = sheetBody.scrollTop; mode = null; dy = 0;
    headerGrab = !!e.target.closest('#sheetGrab');
    sheet.setPointerCapture(e.pointerId);
  }
  function onMove(e){
    if (y0 == null) return;
    const delta = e.clientY - y0;                 // + = finger moved down
    if (mode === null){
      if (Math.abs(delta) < 4) return;
      mode = (headerGrab || delta > 0) ? 'dismiss' : 'scroll';
      if (mode === 'dismiss') sheet.style.transition = 'none';
    }
    e.preventDefault();
    if (mode === 'dismiss'){
      dy = Math.max(0, delta);
      sheet.style.transform = `translateY(${dy}px)`;
    } else {
      sheetBody.scrollTop = Math.min(maxScroll(), Math.max(0, scroll0 - delta));
    }
  }
  function onUp(){
    if (y0 == null) return;
    if (mode === 'dismiss'){
      sheet.style.transition = ''; sheet.style.transform = '';
      if (dy > 90) closeSheet();
    }
    y0 = null; mode = null; dy = 0;
  }
  sheet.addEventListener('pointerdown', onDown);
  sheet.addEventListener('pointermove', onMove, { passive: false });
  sheet.addEventListener('pointerup', onUp);
  sheet.addEventListener('pointercancel', onUp);
})();

chainSel.onchange = () => render();
q.oninput = () => render();
sortSel.onchange = () => render();
render();
</script>
</body>
</html>
"""


def write_html(scoring, regions_cfg, rows, path):
    today = date.today().isoformat()
    n_chains = len({r["chain"] for r in rows})
    n_ranked = sum(1 for r in rows if r["rank"])
    n_pending = sum(1 for r in rows if r["unranked_reason"] == "awaiting verification")
    n_offmenu = sum(1 for r in rows if r["unranked_reason"] == "off menu")
    top = rows[0]
    parts = [f"{n_ranked} verified picks ranked"]
    if n_pending:
        parts.append(f"{n_pending} awaiting verification")
    if n_offmenu:
        parts.append(f"{n_offmenu} off menu")
    parts += [f"{n_chains} chains", f"updated {today}"]
    subtitle = " · ".join(parts)
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
            .replace("__WLEAN__", str(int(scoring["weights"]["leanness"] * 100)))
            .replace("__WSAT__", str(int(scoring["weights"]["sat_fat"] * 100)))
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
