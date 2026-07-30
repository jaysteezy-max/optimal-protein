#!/usr/bin/env python3
"""Refresh nutrition data (protein / calories) for chains in config/chains.yaml.

Usage:
    python3 pull_nutrition.py                # all chains
    python3 pull_nutrition.py --chain chipotle taco-bell

Per chain it:
  1. fetches nutrition data — via a chain-specific fetcher (puller: auto) or a
     hand-saved data/raw/nutrition/<slug>_curated.json (puller: curated);
  2. archives the normalized pull to data/raw/nutrition/<slug>_<date>.json
     (pull date + source URL included — the audit trail);
  3. diffs against the previous archived pull and prints added / removed /
     changed items (menu-change radar);
  4. upserts protein/calories into data/items.csv for existing rows, and
     appends rows (price left blank) for new items at/above the protein
     threshold. Removed items are only warned about, never auto-deleted.

Fetchers are BEST-EFFORT: chain sites change and bot-harden without notice.
A failed fetcher is reported and skipped — it never corrupts items.csv. When a
fetcher dies permanently, flip the chain to `puller: curated` in chains.yaml
and maintain data/raw/nutrition/<slug>_curated.json by hand (nutrition changes
rarely; this is ~5 min/chain/quarter).

Curated-file format (same shape a fetcher returns):
    {"source_url": "https://…", "items": [
        {"item": "Grilled Chicken Sandwich", "protein_g": 28, "calories": 390},
        …]}

This script only performs read-only GETs of public nutrition pages at a
polite, quarterly cadence. No ordering flows, no store selection, no
bot-evasion — chains that don't work get the curated path.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data/raw/nutrition"
UA = "protein-tracker/1.0 (personal, quarterly nutrition refresh)"


def http_get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# ------------------------------------------------------------- fetchers
# Each fetcher returns {"source_url": str, "items": [{item, protein_g, calories}]}.
# All are best-effort against undocumented endpoints — expect breakage.

def fetch_mcdonalds():
    """McDonald's exposes menu categories/items as JSON under /dnaapp/."""
    base = "https://www.mcdonalds.com"
    cats = json.loads(http_get(
        f"{base}/dnaapp/itemList?country=US&language=en"))
    items = []
    for it in cats.get("items", {}).get("item", []):
        nutrients = {n.get("name", "").lower(): n
                     for n in it.get("nutrient_facts", {}).get("nutrient", [])}
        protein = nutrients.get("protein", {}).get("value")
        cal = nutrients.get("calories", {}).get("value")
        if protein is None or cal is None:
            continue
        items.append({"item": it.get("item_name", "").strip(),
                      "protein_g": float(protein), "calories": float(cal)})
    return {"source_url": f"{base}/dnaapp/itemList?country=US&language=en",
            "items": items}


def fetch_taco_bell():
    """Taco Bell product pages embed nutrition JSON in script tags."""
    url = "https://www.tacobell.com/food"
    html = http_get(url).decode("utf-8", "replace")
    blobs = re.findall(
        r'<script[^>]*type="application/(?:ld\+)?json"[^>]*>(.*?)</script>',
        html, re.S)
    items, seen = [], set()
    for blob in blobs:
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            continue
        for node in _walk_dicts(data):
            name = node.get("name")
            nut = node.get("nutrition") or node
            protein = _num(nut.get("proteinContent") or nut.get("protein"))
            cal = _num(nut.get("calories"))
            if name and protein is not None and cal is not None and name not in seen:
                seen.add(name)
                items.append({"item": str(name).strip(),
                              "protein_g": protein, "calories": cal})
    return {"source_url": url, "items": items}


def fetch_chipotle():
    """Chipotle publishes per-ingredient nutrition for its calculator."""
    url = "https://www.chipotle.com/nutrition-calculator"
    html = http_get(url).decode("utf-8", "replace")
    m = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise RuntimeError("no embedded nutrition JSON found (page changed?)")
    data = json.loads(m.group(1))
    items, seen = [], set()
    for node in _walk_dicts(data):
        name = node.get("itemName") or node.get("name")
        protein = _num(node.get("protein"))
        cal = _num(node.get("calories"))
        if name and protein is not None and cal is not None and name not in seen:
            seen.add(name)
            items.append({"item": str(name).strip(),
                          "protein_g": protein, "calories": cal})
    return {"source_url": url, "items": items}


def fetch_panda_express():
    """Panda Express nutrition page embeds item data as JSON."""
    url = "https://www.pandaexpress.com/nutritioninformation"
    html = http_get(url).decode("utf-8", "replace")
    blobs = re.findall(r'<script[^>]*type="application/(?:ld\+)?json"[^>]*>(.*?)</script>',
                       html, re.S)
    items, seen = [], set()
    for blob in blobs:
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            continue
        for node in _walk_dicts(data):
            name = node.get("name")
            nut = node.get("nutrition") or node
            protein = _num(nut.get("proteinContent") or nut.get("protein"))
            cal = _num(nut.get("calories"))
            if name and protein is not None and cal is not None and name not in seen:
                seen.add(name)
                items.append({"item": str(name).strip(),
                              "protein_g": protein, "calories": cal})
    return {"source_url": url, "items": items}


FETCHERS = {
    "mcdonalds": fetch_mcdonalds,
    "taco-bell": fetch_taco_bell,
    "chipotle": fetch_chipotle,
    "panda-express": fetch_panda_express,
}


def _walk_dicts(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk_dicts(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_dicts(v)


def _num(v):
    if v is None:
        return None
    m = re.search(r"[\d.]+", str(v))
    return float(m.group()) if m else None


# ------------------------------------------------------------- archive/diff

def previous_pull(slug: str):
    pulls = sorted(RAW.glob(f"{slug}_2*.json"))  # dated files only, not _curated
    if not pulls:
        return None
    return json.loads(pulls[-1].read_text())


def archive(slug: str, pull: dict) -> Path:
    RAW.mkdir(parents=True, exist_ok=True)
    out = RAW / f"{slug}_{date.today().isoformat()}.json"
    out.write_text(json.dumps(
        {"chain": slug, "pulled": date.today().isoformat(),
         "source_url": pull["source_url"], "items": pull["items"]}, indent=1) + "\n")
    return out


def diff_pulls(prev: dict | None, cur: dict):
    if prev is None:
        return None
    old = {i["item"]: i for i in prev["items"]}
    new = {i["item"]: i for i in cur["items"]}
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(
        n for n in set(new) & set(old)
        if (new[n]["protein_g"], new[n]["calories"])
        != (old[n]["protein_g"], old[n]["calories"]))
    return {"added": added, "removed": removed, "changed": changed}


# ------------------------------------------------------------- items.csv upsert

ITEMS_CSV = ROOT / "data/items.csv"

# The column set is read from items.csv itself rather than hard-coded. A
# hard-coded list silently drifted out of date once already: it omitted
# sat_fat_g (added in Score v2), so DictWriter raised ValueError on every write
# that had something to save. Deriving it means new columns can be added to the
# CSV without touching this file.
FALLBACK_FIELDS = ["chain", "item", "protein_g", "calories", "sat_fat_g",
                   "national_price_usd", "source", "pulled_date", "notes"]


def items_fields() -> list[str]:
    with ITEMS_CSV.open(newline="") as f:
        header = next(csv.reader(f), None)
    return [h for h in (header or []) if h] or FALLBACK_FIELDS


def upsert_items(slug: str, pull: dict, threshold: float) -> tuple[int, int]:
    fields = items_fields()
    with ITEMS_CSV.open(newline="") as f:
        rows = list(csv.DictReader(f))
    by_key = {(r["chain"], r["item"].strip().lower()): r for r in rows}
    today = date.today().isoformat()
    updated = added = 0
    for it in pull["items"]:
        key = (slug, it["item"].strip().lower())
        if key in by_key:
            r = by_key[key]
            if (float(r["protein_g"]), float(r["calories"])) != (
                    float(it["protein_g"]), float(it["calories"])):
                r["protein_g"] = f"{it['protein_g']:g}"
                r["calories"] = f"{it['calories']:g}"
                r["pulled_date"] = today
                updated += 1
        elif it["protein_g"] >= threshold:
            new = {k: "" for k in fields}
            new.update({"chain": slug, "item": it["item"],
                        "protein_g": f"{it['protein_g']:g}",
                        "calories": f"{it['calories']:g}",
                        "source": pull["source_url"],
                        "pulled_date": today,
                        "notes": "NEW from nutrition pull — needs price"})
            rows.append(new)
            added += 1
    if updated or added:
        with ITEMS_CSV.open("w", newline="") as f:
            # restval/extrasaction keep a column added to items.csv from
            # crashing the writer if some in-memory row predates it
            w = csv.DictWriter(f, fieldnames=fields, restval="",
                               extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
    return updated, added


# ------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--chain", nargs="*", help="chain slugs (default: all)")
    args = ap.parse_args()

    scoring = yaml.safe_load((ROOT / "config/scoring.yaml").read_text())
    threshold = scoring["protein_threshold_g"]
    chains = yaml.safe_load((ROOT / "config/chains.yaml").read_text())["chains"]
    wanted = set(args.chain) if args.chain else {c["slug"] for c in chains}
    unknown = wanted - {c["slug"] for c in chains}
    if unknown:
        sys.exit(f"unknown chain slug(s): {', '.join(sorted(unknown))}")

    any_failure = False
    for chain in chains:
        slug = chain["slug"]
        if slug not in wanted:
            continue
        # -- acquire
        if chain.get("puller") == "auto" and slug in FETCHERS:
            try:
                pull = FETCHERS[slug]()
            except Exception as e:  # noqa: BLE001 — any breakage = skip, report
                print(f"[{slug}] FETCH FAILED ({e.__class__.__name__}: {e}) — "
                      f"skipped; consider puller: curated")
                any_failure = True
                continue
        else:
            curated = RAW / f"{slug}_curated.json"
            if not curated.exists():
                print(f"[{slug}] curated — no {curated.name}; "
                      f"items.csv left as-is")
                continue
            pull = json.loads(curated.read_text())
        if not pull.get("items"):
            print(f"[{slug}] fetch returned 0 items — page layout likely "
                  f"changed; skipped")
            any_failure = True
            continue
        # -- archive + diff + upsert
        d = diff_pulls(previous_pull(slug), pull)
        archive(slug, pull)
        updated, added = upsert_items(slug, pull, threshold)
        qual = sum(1 for i in pull["items"] if i["protein_g"] >= threshold)
        status = (f"[{slug}] {len(pull['items'])} items ({qual} ≥ {threshold} g); "
                  f"csv: {updated} updated, {added} added")
        if d is None:
            status += "; first pull — no diff"
        elif not (d["added"] or d["removed"] or d["changed"]):
            status += "; no menu changes since last pull"
        else:
            status += (f"; MENU CHANGES — added: {d['added'] or '–'}, "
                       f"removed: {d['removed'] or '–'}, "
                       f"changed: {d['changed'] or '–'}")
        print(status)

    print("\ndone. next: fill any blank prices in data/items.csv, "
          "then run: python3 build_rankings.py")
    sys.exit(1 if any_failure else 0)


if __name__ == "__main__":
    main()
