#!/usr/bin/env python3
"""Build the protein-value rankings from config/ + data/.

Reads:
    config/scoring.yaml      weights, protein threshold, PNW uplift
    config/chains.yaml       the chains in scope
    data/items.csv           one row per qualifying menu item
    data/manual_prices.csv   optional till-verified price overrides

Writes:
    docs/index.html          static page for GitHub Pages (phone-glance view)
    docs/data.json           machine-readable feed (future iPhone Shortcut)
    RANKINGS.md              markdown table readable straight on GitHub

Pure function of its inputs — edit a data/config file, re-run, commit.
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
        "# Protein Value Rankings — PNW",
        "",
        f"_Generated {today}. Prices = national average + "
        f"{scoring['pnw_uplift_pct']}% PNW uplift, **not till-verified** — "
        "confirm in store. Tax excluded, app deals excluded._",
        "",
        f"_Score = {int(scoring['weights']['protein_per_dollar']*100)}% "
        f"protein-per-$ + {int(scoring['weights']['protein_density']*100)}% "
        "protein density, each normalized to best-in-list = 100._",
        "",
        "## Best pick per chain",
        "",
        "| Chain | Order this | Price | Protein | Score |",
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
    --bg: #f6f5f2; --card: #ffffff; --ink: #1c1b19; --muted: #6f6b63;
    --line: #e4e1da; --accent: #1a7f5a; --accent-ink: #ffffff; --flag: #b3541e;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #161513; --card: #201f1c; --ink: #ece9e2; --muted: #9b968c;
      --line: #34322d; --accent: #2fa87c; --accent-ink: #10241c; --flag: #d97c45;
    }
  }
  * { box-sizing: border-box; margin: 0; }
  body {
    background: var(--bg); color: var(--ink);
    font: 16px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    padding: 16px 12px 48px; max-width: 760px; margin: 0 auto;
  }
  h1 { font-size: 1.35rem; letter-spacing: -0.01em; }
  .sub { color: var(--muted); font-size: 0.8rem; margin: 6px 0 14px; }
  .controls { position: sticky; top: 0; background: var(--bg); padding: 8px 0 10px; z-index: 2; }
  select, input[type=search] {
    width: 100%; padding: 10px 12px; border: 1px solid var(--line); border-radius: 10px;
    background: var(--card); color: var(--ink); font-size: 1rem; margin-bottom: 8px;
    -webkit-appearance: none; appearance: none;
  }
  .card {
    background: var(--card); border: 1px solid var(--line); border-radius: 12px;
    padding: 10px 12px; margin-bottom: 8px; display: grid;
    grid-template-columns: 2.2rem 1fr auto; gap: 2px 10px; align-items: center;
  }
  .rank { font-weight: 700; font-size: 1.05rem; color: var(--muted); grid-row: span 2; }
  .top .rank { color: var(--accent); }
  .name { font-weight: 600; }
  .chain { color: var(--muted); font-size: 0.8rem; }
  .score {
    grid-row: span 2; background: var(--accent); color: var(--accent-ink);
    border-radius: 9px; padding: 6px 9px; font-weight: 700; text-align: center;
    min-width: 3.2rem; font-size: 1.02rem;
  }
  .score small { display: block; font-weight: 500; font-size: 0.58rem; opacity: 0.85; }
  .noscore { background: var(--line); color: var(--muted); }
  .stats { grid-column: 2 / 4; color: var(--muted); font-size: 0.78rem; padding-top: 3px; }
  .stats b { color: var(--ink); font-weight: 600; }
  .note { grid-column: 2 / 4; font-size: 0.75rem; color: var(--flag); }
  .caveat {
    border: 1px dashed var(--line); border-radius: 10px; padding: 8px 10px;
    color: var(--muted); font-size: 0.75rem; margin-bottom: 12px;
  }
  .empty { color: var(--muted); text-align: center; padding: 24px 0; }
</style>
</head>
<body>
<h1>Protein Value — PNW</h1>
<p class="sub">__SUBTITLE__</p>
<div class="caveat">Prices are national averages + __UPLIFT__% PNW uplift — <b>not
till-verified</b>, confirm in store. Sales tax excluded. App deals excluded from the
math (see notes). Score = __WPPD__% protein-per-$ + __WPD__% protein density.</div>
<div class="controls">
  <select id="chain"><option value="">All chains — overall ranking</option></select>
  <input id="q" type="search" placeholder="Search items…">
</div>
<div id="list"></div>
<p class="empty" id="empty" hidden>No items match.</p>
<script>
const DATA = __DATA__;
const chainSel = document.getElementById('chain');
const q = document.getElementById('q');
const list = document.getElementById('list');
const empty = document.getElementById('empty');

[...new Map(DATA.items.map(i => [i.chain, i.chain_name])).entries()]
  .sort((a, b) => a[1].localeCompare(b[1]))
  .forEach(([slug, name]) => chainSel.add(new Option(name, slug)));

function esc(s) {
  return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}

function render() {
  const slug = chainSel.value, term = q.value.trim().toLowerCase();
  const rows = DATA.items.filter(i =>
    (!slug || i.chain === slug) &&
    (!term || (i.item + ' ' + i.chain_name).toLowerCase().includes(term)));
  list.innerHTML = rows.map((i, idx) => {
    const price = i.price != null ? '$' + i.price.toFixed(2) : 'no price';
    const scored = i.value_score != null;
    const localRank = slug ? idx + 1 : (i.rank ?? '–');
    return `<div class="card ${scored && idx < 3 ? 'top' : ''}">
      <div class="rank">${scored ? localRank : '–'}</div>
      <div><span class="name">${esc(i.item)}</span>
        <div class="chain">${esc(i.chain_name)}</div></div>
      <div class="score ${scored ? '' : 'noscore'}">${scored ? i.value_score : '—'}<small>score</small></div>
      <div class="stats"><b>${price}</b> · <b>${i.protein_g} g</b> protein ·
        ${i.calories} cal · ${i.protein_per_dollar ?? '—'} g/$ ·
        ${i.protein_per_100cal} g/100cal</div>
      ${i.notes || i.price_kind === 'no price'
        ? `<div class="note">${esc([i.notes, i.price_kind === 'no price' ? 'price missing — add it in data/' : ''].filter(Boolean).join(' · '))}</div>`
        : ''}
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
    subtitle = (f"{len(rows)} items ≥ {scoring['protein_threshold_g']} g protein "
                f"across {n_chains} chains · updated {today}")
    html = (HTML_TEMPLATE
            .replace("__SUBTITLE__", subtitle)
            .replace("__UPLIFT__", str(scoring["pnw_uplift_pct"]))
            .replace("__WPPD__", str(int(scoring["weights"]["protein_per_dollar"] * 100)))
            .replace("__WPD__", str(int(scoring["weights"]["protein_density"] * 100)))
            .replace("__DATA__", json.dumps(
                {"items": rows}, separators=(",", ":"))))
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
