#!/usr/bin/env python3
"""Validate (and optionally refresh) the regional price multipliers.

Usage:
    python3 pull_prices.py             # validate config/regions.yaml
    BEA_API_KEY=... python3 pull_prices.py --refresh
                                       # refresh multipliers from BEA RPP data

The multipliers in config/regions.yaml scale displayed prices client-side.
They are seeded from BEA Regional Price Parities (food services) and are
estimates, not store prices.

Validation (always):
  - every region has code / name / multiplier / states
  - multipliers within a sane 0.8-1.3 band
  - no state is mapped to two regions
  - default_region exists

Refresh (--refresh, needs BEA_API_KEY):
  - pulls state-level Regional Price Parities from the BEA API
    (https://apps.bea.gov/api/ — free key, no cost),
  - averages states into this file's regions, normalizes to national = 1.00,
  - rewrites the multipliers ONLY when a region moves by >= 0.01, and prints
    each change so the CI log / commit diff shows exactly what moved.

Exit codes: 0 ok, 1 validation error, 2 refresh requested but failed
(validation result still reported). The CI workflow treats nonzero as
"open an issue for a human", never as "guess".
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
REGIONS_PATH = ROOT / "config/regions.yaml"

SANE_LO, SANE_HI = 0.8, 1.3
# BEA Regional data: RPPs all items, state level (annual)
BEA_URL = ("https://apps.bea.gov/api/data/?UserID={key}&method=GetData"
           "&datasetname=Regional&TableName=SARPP&LineCode=1"
           "&GeoFips=STATE&Year=LAST5&ResultFormat=JSON")


def load():
    cfg = yaml.safe_load(REGIONS_PATH.read_text())
    return cfg


def validate(cfg) -> list[str]:
    errors = []
    codes = set()
    seen_states = {}
    for r in cfg.get("regions", []):
        for field in ("code", "name", "multiplier", "states"):
            if field not in r:
                errors.append(f"region missing {field!r}: {r}")
        code = r.get("code")
        if code in codes:
            errors.append(f"duplicate region code {code!r}")
        codes.add(code)
        m = r.get("multiplier")
        if not isinstance(m, (int, float)) or not (SANE_LO <= m <= SANE_HI):
            errors.append(f"{code}: multiplier {m!r} outside {SANE_LO}-{SANE_HI}")
        for st in r.get("states", []):
            if st in seen_states:
                errors.append(f"state {st} mapped to both "
                              f"{seen_states[st]!r} and {code!r}")
            seen_states[st] = code
    if cfg.get("default_region") not in codes:
        errors.append(f"default_region {cfg.get('default_region')!r} "
                      f"not a defined region")
    return errors


def refresh(cfg) -> bool:
    """Refresh multipliers from BEA RPP data. Returns True if file changed."""
    key = os.environ.get("BEA_API_KEY")
    if not key:
        print("refresh: BEA_API_KEY not set — skipping refresh, "
              "validation only", file=sys.stderr)
        return False
    with urllib.request.urlopen(BEA_URL.format(key=key), timeout=30) as resp:
        payload = json.load(resp)
    results = payload["BEAAPI"]["Results"]
    if "Error" in results:
        raise RuntimeError(f"BEA API error: {results['Error']}")
    data = results["Data"]
    latest_year = max(d["TimePeriod"] for d in data)
    # GeoName -> RPP (all items, national = 100)
    by_state_name = {d["GeoName"]: float(d["DataValue"])
                     for d in data if d["TimePeriod"] == latest_year}
    # BEA uses full state names; map from the postal codes in regions.yaml
    postal = {
        "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
        "CA": "California", "CO": "Colorado", "CT": "Connecticut",
        "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida",
        "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
        "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky",
        "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
        "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
        "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
        "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
        "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
        "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
        "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
        "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
        "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
        "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
        "WI": "Wisconsin", "WY": "Wyoming",
    }
    changed = False
    for r in cfg["regions"]:
        if not r["states"]:          # 'national' style regions stay 1.00
            continue
        vals = [by_state_name[postal[st]] for st in r["states"]
                if postal.get(st) in by_state_name]
        if not vals:
            print(f"refresh: no BEA data for {r['code']} — left unchanged",
                  file=sys.stderr)
            continue
        new_mult = round(sum(vals) / len(vals) / 100.0, 2)
        if not (SANE_LO <= new_mult <= SANE_HI):
            print(f"refresh: {r['code']} -> {new_mult} outside sane band — "
                  f"left unchanged, review manually", file=sys.stderr)
            continue
        if abs(new_mult - r["multiplier"]) >= 0.01:
            print(f"refresh: {r['code']} {r['multiplier']} -> {new_mult} "
                  f"(BEA RPP {latest_year})")
            r["multiplier"] = new_mult
            changed = True
    if changed:
        cfg["provenance"] = (f"Refreshed from BEA Regional Price Parities "
                             f"({latest_year}, all-items RPP as proxy for "
                             f"food services). Estimates, not store prices.")
        REGIONS_PATH.write_text(yaml.safe_dump(cfg, sort_keys=False,
                                               allow_unicode=True))
    return changed


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true",
                    help="refresh multipliers from BEA (needs BEA_API_KEY)")
    args = ap.parse_args()

    cfg = load()
    errors = validate(cfg)
    for e in errors:
        print(f"regions.yaml: {e}", file=sys.stderr)
    if errors:
        sys.exit(1)
    print(f"regions.yaml: {len(cfg['regions'])} regions valid "
          f"(default: {cfg['default_region']})")

    if args.refresh:
        try:
            changed = refresh(cfg)
            print("refresh: multipliers updated" if changed
                  else "refresh: no changes")
        except Exception as e:
            print(f"refresh FAILED ({e.__class__.__name__}: {e})",
                  file=sys.stderr)
            sys.exit(2)


if __name__ == "__main__":
    main()
