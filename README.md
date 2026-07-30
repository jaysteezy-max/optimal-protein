# 🍗 Protein Value Tracker (PNW)

The best **protein-per-dollar** fast-food orders across the Pacific Northwest. It
answers one question: at whatever chain is nearby, what's the best
protein-for-the-money order?

A second board, **Off the shelf**, answers the follow-up: what does the
convenience of the counter actually cost you? Same rubric, applied to grocery
protein — shakes, canned fish, rotisserie chicken, yogurt, whey, eggs. It exists
to be the benchmark the fast-food board is measured against, which is why the two
are scored separately rather than merged (see [Two boards](#-two-boards)).

### 🔗 Quick links

- 🏆 **[Live ranking page](https://jaysteezy-max.github.io/optimal-protein/)** — searchable, filterable, tap any item for a full score breakdown _(enable GitHub Pages first — see below)_
- 📊 **[RANKINGS.md](RANKINGS.md)** — the full table, readable right here on GitHub
- 🗄️ **[docs/data.json](docs/data.json)** — the same data, machine-readable
- 🛒 **[docs/shelf-probe.md](docs/shelf-probe.md)** — what the shelf board still needs verified, and where to get it
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
lets you sort on it rather than guessing on your behalf.

## 🗂 Two boards

The page has two tabs — **Fast food** and **Off the shelf** — and each is scored
against **its own pool**. A score is meaningful only against other rows on the
same board.

That isn't a cosmetic split. Winsorizing fixed the *single-outlier* problem; it
does nothing about a dominant *population*, because the percentile reference
itself moves. Comparing medians, shelf items beat fast food on every term at
once:

| | fast food | off the shelf |
|---|---|---|
| protein per dollar | 4.18 | **14.57** |
| calories per 50 g protein | 839 | **288** |
| sat fat per 50 g protein | 11.73 | **1.79** |

Pooled together, shakes alone took 8 of the top 10 on single-unit pricing, the
median score fell from 44.1 to 33.3, and the restaurant field lost 11.3 points on
average — a worse outcome than the Score v2 bug that v3 was written to fix, and
one with no single row to blame. Lowering `winsorize_pct` makes it worse: at 85
and below a dozen items tie at 100 and the board stops discriminating.

**What does compare across boards is the raw arithmetic.** `protein_per_dollar`,
`cal_per_50g` and `satfat_per_50g` are absolute costs per 50 g of protein, not
pool-relative — the table above is built from them. Cross-board claims should be
made with those numbers, never by putting two 0-100 scores side by side. The
compare view says so explicitly when you pick one item from each board.

Two knock-on differences, both deliberate:

- **Prices.** The 10% PNW uplift is calibrated on prepared food; packaged goods
  price far more nationally (chain-wide price zones, national promo calendars,
  and BEA goods RPPs compressed toward 1.00), so retail carries a 4% uplift and
  feels only 40% of the regional swing. Safe *because* the pools are separate — a
  multiplier uniform within a category still cancels out of that category's
  normalization.
- **Sales tax.** Excluding it used to be symmetric, since every row was prepared
  food. Across categories it isn't: WA taxes prepared food but exempts food
  ingredients, so the board understates restaurant cost relative to grocery in
  WA, while Oregon is a wash. Contained rather than solved — within a board the
  omission is symmetric again.

Because the shelf board prices things you buy as packages, rows there declare
`servings` and `purchase_price_usd`, and the detail sheet says both out loud:
*"$4.99 buys 4 servings — the score uses $1.25 per serving."* A 12-pack that
scores well per bottle still costs you the 12-pack. That's the honest version of
a "convenience" factor — a verifiable fact about the purchase rather than a
subjective effort rating, which is why there's no effort term in the score.

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

> ⚠️ **The shelf board is not verified yet.** All 13 rows are seeded and unranked,
> because the session that built the board had no outbound network access and
> search snippets are not verification — they're how stale figures spread. Eight
> of the rows have no saturated-fat figure at all, which blocks scoring on its
> own. **[docs/shelf-probe.md](docs/shelf-probe.md)** lists every official URL to
> fetch, the traps in each (Muscle Milk's whole line was reformulated in spring
> 2026; Slate's widely-quoted 20 g is stale; Quest publishes no calorie figure),
> and the pricing questions still open.

The page also lets you **sort** (value, protein, per-dollar, leanest, price),
**compare** any two items side by side, and run a **budget** ("most protein for
$X, optionally at one chain").

## 🗂️ How it works

Everything is generated from a few editable files — change one, run one script,
commit:

```
config/scoring.yaml       weights, 25 g threshold, per-kind price uplift, pools
config/chains.yaml        every vendor: chains + retail brands, kind, membership
config/regions.yaml       regional price multipliers (BEA-seeded estimates)
data/items.csv            one row per qualifying item (the main data file)
data/manual_prices.csv    optional price overrides you confirm yourself
build_rankings.py         data + config → HTML / JSON / Markdown
pull_nutrition.py         refresh nutrition, diff menus, update items.csv
pull_prices.py            validate / refresh the regional multipliers
docs/shelf-probe.md       what the shelf board still needs verified
```

A vendor's `kind` in `config/chains.yaml` (`restaurant`, the default, or
`retail`) is what puts an item on a board — items never declare it themselves, so
a row can't disagree with its vendor. `membership_required: true` marks a vendor
whose price needs a paid membership; it drives a badge and a filter on the page.

Item columns beyond the nutrition basics:

| Column | Meaning |
|---|---|
| `format` | `counter-order`, `rtd-single`, `shelf-single`, `multi-serve`, `requires-prep` |
| `servings` | How many of the row's unit come in one purchase |
| `purchase_price_usd` | Register price of the whole package |
| `retailer` | Which store the price basis came from |

`national_price_usd` is always the price of **one unit of the row** — the thing
`protein_g` describes. The build cross-checks it against
`purchase_price_usd / servings` and fails the build if they disagree by more than
2¢ or 3%, so a unit can't quietly drift from its package price.

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
out of the score normalization, so only displayed prices move — and that still
holds now that the two boards damp the regional swing differently, precisely
because scores never cross boards. Sales tax and app deals are excluded (see
[Two boards](#-two-boards) for the tax asymmetry that creates). To correct a
price, edit `national_price_usd` in `data/items.csv`, or add a row to
`data/manual_prices.csv` (used as-is, no uplift, and marked as a verified price).

Nutrition is the firmer half: every ranked row has been cross-checked against
the chain's own published data plus at least one independent source. Prices are
the softer half — no row on the board has been confirmed at a register yet, so
treat every figure as an estimate until it has a `manual_prices.csv` entry.

## 🌐 Hosting on GitHub Pages

The repo must be public (free tier). Then: **Settings → Pages → Deploy from a
branch → `main`, folder `/docs` → Save.** It publishes at
`https://jaysteezy-max.github.io/optimal-protein/`.
