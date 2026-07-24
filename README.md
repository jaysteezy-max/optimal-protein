# Protein Value Tracker (PNW)

A ranking of the best protein-per-dollar orders across 20 Pacific Northwest
fast food and fast casual chains. It answers one question: at whatever chain
is nearby, what is the best protein-for-the-money order.

## Outputs

- `docs/index.html` — the ranking page. Works as a hosted page (GitHub Pages)
  or opened directly from disk in any browser. Ranked by value, filterable by
  chain, searchable.
- `RANKINGS.md` — the same data as a Markdown table, readable in GitHub.
- `docs/data.json` — the data in machine-readable form.

## How it works

Everything is generated from a few editable files. Change a file, run one
script, commit.

```
config/scoring.yaml        weights, 25 g protein threshold, PNW price uplift
config/chains.yaml         the 20 chains and their nutrition sources
data/items.csv             one row per qualifying item (the main data file)
data/manual_prices.csv     optional price overrides you confirm yourself
data/raw/nutrition/        timestamped nutrition pulls (audit trail)
build_rankings.py          data + config -> HTML / JSON / Markdown
pull_nutrition.py          refresh nutrition, diff menus, update items.csv
```

Value Score = 60% protein-per-dollar + 40% protein density (protein per
100 calories), each normalized so the best item in the list scores 100.
Weights live in `config/scoring.yaml`.

Prices are national averages plus a 10% PNW uplift. They are not
store-verified — the honest weak point of the data. To correct one, edit
`national_price_usd` in `data/items.csv`, or add a row to
`data/manual_prices.csv` (used as-is, no uplift). Sales tax is excluded (it
varies across the region); app deals are excluded from the math.

## Updating

```bash
python3 pull_nutrition.py      # refresh nutrition, print any menu changes
                               # (fill blank prices it flags in items.csv)
python3 build_rankings.py      # regenerate all outputs
git commit -am "update" && git push
```

Requires Python 3.10+ and PyYAML (`pip install pyyaml`).

Chains whose sites cannot be fetched are marked `puller: curated` in
`config/chains.yaml`; refresh those by hand-saving
`data/raw/nutrition/<slug>_curated.json` (format documented in
`pull_nutrition.py`).

## Data sources and accuracy

- The 20 ranking-driving items (each chain's best pick) were cross-checked on
  2026-07-23 against several nutrition databases (fastfoodnutrition,
  mynetdiary, CalorieKing, fatsecret); those rows are marked `web-verified`.
  These are third-party figures, not pulled from the chains directly, so treat
  a razor-thin gap between two items as a tie until confirmed in-app.
- Remaining rows are `seeded — verify` from research and not yet re-checked.
- Jamba currently has no item at or above 25 g protein (its 16 oz Protein
  Berry Workout is about 20 g). Add a larger size to `data/items.csv` to
  include it.
- Prices are national average + uplift everywhere; refine them as you confirm
  real numbers.

## Hosting on GitHub Pages

The repository must be public for Pages on a free account. Then:
Settings -> Pages -> Build and deployment -> Source: Deploy from a branch ->
Branch: `main`, folder `/docs` -> Save. The page publishes at
`https://<user>.github.io/optimal-protein/`.
