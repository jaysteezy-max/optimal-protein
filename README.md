# 🍗 Protein Value Tracker (PNW)

The best **protein-per-dollar** fast-food orders across the Pacific Northwest. It
answers one question: at whatever chain is nearby, what's the best
protein-for-the-money order?

### 🔗 Quick links

- 🏆 **[Live ranking page](https://jaysteezy-max.github.io/optimal-protein/)** — searchable, filterable, tap any item for a full score breakdown _(enable GitHub Pages first — see below)_
- 📊 **[RANKINGS.md](RANKINGS.md)** — the full table, readable right here on GitHub
- 🗄️ **[docs/data.json](docs/data.json)** — the same data, machine-readable

## 📐 How it's scored

**Value Score = 60% protein-per-dollar + 40% protein density** (protein per 100
cal), each normalized so the best item in the list = 100. Weights live in
`config/scoring.yaml`. On the page, tap any item to see the exact math.

## 🗂️ How it works

Everything is generated from a few editable files — change one, run one script,
commit:

```
config/scoring.yaml       weights, 25 g protein threshold, PNW price uplift
config/chains.yaml        the chains and their nutrition sources
data/items.csv            one row per qualifying item (the main data file)
data/manual_prices.csv    optional price overrides you confirm yourself
build_rankings.py         data + config → HTML / JSON / Markdown
pull_nutrition.py         refresh nutrition, diff menus, update items.csv
```

## 🔄 Updating

```bash
python3 pull_nutrition.py    # refresh nutrition, print any menu changes
python3 build_rankings.py    # regenerate all outputs
git commit -am "update" && git push
```

Requires Python 3.10+ and PyYAML (`pip install pyyaml`).

## 💵 Prices & accuracy

Prices are **national averages + 10% PNW uplift** — _not_ till-verified, so
confirm in store. Sales tax and app deals are excluded. To correct one, edit
`national_price_usd` in `data/items.csv`, or add a row to
`data/manual_prices.csv` (used as-is, no uplift). Each chain's best pick was
cross-checked against several nutrition databases and marked `web-verified`;
remaining rows are `seeded — verify`.

## 🌐 Hosting on GitHub Pages

The repo must be public (free tier). Then: **Settings → Pages → Deploy from a
branch → `main`, folder `/docs` → Save.** It publishes at
`https://jaysteezy-max.github.io/optimal-protein/`.
