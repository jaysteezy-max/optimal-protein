# Protein Value Tracker — PNW

Best protein bang-for-buck across the top 20 PNW fast food / fast casual
chains. One question, answered at a glance on a phone: **"what's my best
protein-per-dollar order at whatever's near me right now?"**

- 📱 **The page:** `docs/index.html` — served via GitHub Pages, ranked by
  Value Score, filterable by chain ("I'm at Wendy's right now").
- 📋 **Readable in-repo:** [`RANKINGS.md`](RANKINGS.md)
- 🤖 **Machine feed:** `docs/data.json` (for a future iPhone Shortcut)

## How it works

Everything is a pure function of the editable files — change data or config,
re-run one script, commit.

```
config/scoring.yaml        weights, 25 g protein threshold, PNW price uplift
config/chains.yaml         the 20 chains + official nutrition sources
data/items.csv             ← THE data file: one row per qualifying item
data/manual_prices.csv     optional till-verified price overrides
data/raw/nutrition/        timestamped raw nutrition pulls (audit trail)
build_rankings.py          data+config → HTML / JSON / Markdown
pull_nutrition.py          refresh nutrition, diff menus, upsert items.csv
```

**Value Score** = 60% protein-per-dollar + 40% protein density
(protein per 100 cal — the lean bias), each normalized so the best item in
the list = 100. Weights live in `config/scoring.yaml`.

**Prices** are national averages + a flat 10% PNW uplift — *not*
store-verified. When you spot a real price, either fix `national_price_usd`
in `data/items.csv` or add a row to `data/manual_prices.csv` (used as-is, no
uplift, marked "verified" in output). Sales tax excluded (WA taxes prepared
food, OR doesn't). App deals excluded from the math, noted qualitatively.

## Updating (manual, on request)

```bash
# 1. refresh nutrition (quarterly, or on menu news) — best-effort fetchers,
#    prints a menu-change diff, adds new ≥25 g items with a blank price
python3 pull_nutrition.py

# 2. fill any blank prices in data/items.csv (rows noted "needs price")

# 3. rebuild all outputs
python3 build_rankings.py

# 4. commit & push — GitHub Pages redeploys automatically
```

Requires Python 3.10+ and PyYAML (`pip install pyyaml`).

Chains whose sites can't be fetched politely are marked `puller: curated` in
`config/chains.yaml` — refresh those by hand-saving
`data/raw/nutrition/<slug>_curated.json` (format documented in
`pull_nutrition.py`), ~5 min/chain/quarter. Nutrition data changes rarely.

## Hosting (one-time setup)

GitHub repo → **Settings → Pages** → Source: *Deploy from a branch* →
Branch: `main`, folder `/docs`. The page URL then works as a phone bookmark.

## Data honesty

- Nutrition values were seeded July 2026 from official chain nutrition
  pages via research; rows marked `seeded — verify` (or `seeded ESTIMATE`
  where the chain publishes less standardized data) haven't been re-checked
  against a live pull yet.
- Items with no reliable price appear in the output flagged, never silently
  dropped.
