# 🍗 Protein Value Tracker (PNW)

The best **protein-per-dollar** fast-food orders across the Pacific Northwest. It
answers one question: at whatever chain is nearby, what's the best
protein-for-the-money order?

### 🔗 Quick links

- 🏆 **[Live ranking page](https://jaysteezy-max.github.io/optimal-protein/)** — searchable, filterable, tap any item for a full score breakdown _(enable GitHub Pages first — see below)_
- 📊 **[RANKINGS.md](RANKINGS.md)** — the full table, readable right here on GitHub
- 🗄️ **[docs/data.json](docs/data.json)** — the same data, machine-readable
- 🎨 **[design.md](design.md)** — the app's design system (tokens, type, motion)
- 📓 **[CHANGELOG.md](CHANGELOG.md)** — what changed, release by release

## 📐 How it's scored

**Value Score = 45% protein-per-dollar + 40% calorie efficiency + 15%
low-saturated-fat.** Every term asks the same question — *what does 50 g of
protein cost you here?* — in dollars, in calories, and in saturated fat. Because
all three are measured per 50 g, portion size cancels out: a 3-piece and a
6-piece of the same thing score identically, as they should.

Each term is scaled against the **95th percentile**, not against the single best
item. That one detail matters more than the weights. Scaling to the best item
lets a lone bargain set the ruler for everyone — a $1.99 Costco pizza slice at
18.7 g protein per dollar once dragged the *median* item down to 22/100 on the
heaviest term and won the whole board while scoring near-last on calories and
saturated fat. Capping at a percentile (winsorizing, the standard treatment for a
skewed indicator) still gives a standout full marks on its own term without
flattening the field. Weights and the percentile live in `config/scoring.yaml`.
On the page, tap any item to see the exact math.

Total calories are deliberately *not* in the score. Whether 1,120 calories is a
great deal or a dealbreaker depends on your day, so the page shows the number and
gives calorie efficiency its own board rather than guessing on your behalf.

**Only web-verified items are ranked.** A row is scored only once its nutrition
— including saturated fat — has been confirmed against the chain's own current
source, so no unverified data reaches the numbers. Anything unconfirmed is listed
but held out of the scoring. Items that have been pulled from a chain's menu keep
their last published nutrition for reference and are listed as **off menu**,
never scored.

Because chains quietly reformulate and resize items — and third-party nutrition
databases lag behind, sometimes by years — a `web-verified` stamp is a snapshot,
not a guarantee. Ranked rows get re-audited against official sources rather than
trusted indefinitely.

The page has four **boards**, one per intent: **Value** (the blended score),
**Per $** (raw protein per dollar), **Lean** (fewest calories per 50 g of
protein), and **Budget** — a target board that answers either "most protein for
$X" or "cheapest way to hit N g", as a single item or a same-chain combo whose
combined nutrition opens in the same detail sheet. You can also **compare** any
two items side by side.

## 🗂️ How it works

Everything is generated from a few editable files — change one, run one script,
commit:

```
config/scoring.yaml       weights, 25 g protein threshold, PNW price uplift
config/chains.yaml        the chains and their nutrition sources
config/regions.yaml       regional price multipliers (BEA-seeded estimates)
data/items.csv            one row per qualifying item (the main data file)
data/manual_prices.csv    optional price overrides you confirm yourself
build_rankings.py         data + config → HTML / JSON / Markdown
pull_nutrition.py         refresh nutrition, diff menus, update items.csv
pull_prices.py            validate / refresh the regional multipliers
```

> **Editing the app's look?** `docs/index.html` is _generated_ — it's
> overwritten on every build. The page markup, CSS, and JS live in
> `HTML_TEMPLATE` inside `build_rankings.py`; edit there, then re-run. The
> design tokens and conventions are documented in **[design.md](design.md)**.
> Animations use [anime.js](https://animejs.com), vendored at
> `docs/anime.min.js` (committed, not rebuilt) so the page works offline; they
> switch off automatically under `prefers-reduced-motion`. The social-share
> image `docs/og.png` is a committed asset (the build doesn't regenerate it);
> re-render it if the branding changes.

## 🔄 Updating

```bash
python3 pull_nutrition.py    # refresh nutrition, print any menu changes
python3 build_rankings.py    # regenerate all outputs
git commit -am "update" && git push
```

Requires Python 3.10+ and PyYAML (`pip install pyyaml`).

## 🤖 Automation

A GitHub Actions workflow ([refresh-data.yml](.github/workflows/refresh-data.yml))
runs the whole pipeline weekly and commits the result — Pages redeploys
automatically. It never invents data: when a fetcher fails or a new menu item
lacks a verified price, it opens a `data-refresh` issue instead. Free on
public repos. Optional: add a free `BEA_API_KEY` secret to refresh the
regional multipliers from BEA Regional Price Parities.

## 💵 Prices & accuracy

Prices are **national averages scaled by a regional multiplier** — _not_
till-verified, so confirm in store. The page auto-detects your US region (free
IP lookup, no permission prompt; pick manually anytime — the choice sticks in
your browser). Rankings don't change by region: a uniform multiplier cancels
out of the score normalization, so only displayed prices move. Sales tax and app deals are excluded. To correct one, edit
`national_price_usd` in `data/items.csv`, or add a row to
`data/manual_prices.csv` (used as-is, no uplift, and marked as a verified price).

Nutrition is the firmer half: every ranked row has been cross-checked against
the chain's own published data plus at least one independent source. Prices are
the softer half — no row on the board has been confirmed at a register yet, so
treat every figure as an estimate until it has a `manual_prices.csv` entry.

## 🌐 Hosting on GitHub Pages

The repo must be public (free tier). Then: **Settings → Pages → Deploy from a
branch → `main`, folder `/docs` → Save.** It publishes at
`https://jaysteezy-max.github.io/optimal-protein/`.
