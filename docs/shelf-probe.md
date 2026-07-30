# 🛒 Shelf board — data probe spec

What the off-the-shelf board still needs before anything on it can be scored,
and where to get it. Every row currently in `data/items.csv` with
`source = seeded — verify` is listed but **unranked**: the hard rule applies to
this board exactly as it does to fast food — no score without nutrition verified
against the product's own current source, saturated fat included.

> **Why nothing is verified yet.** The session that built this board had no
> outbound network access (all HTTPS blocked at the gateway except package
> registries), so not one figure could be checked against an official source.
> Search-result snippets were available, and were deliberately **not** treated as
> verification: undated third-party summaries are the exact mechanism by which
> stale figures propagate, which this repo has been burned by repeatedly. The
> numbers in `items.csv` are seeds to be checked, not findings.

---

## 1. Required fields per row

`sat_fat_g` is the blocker on most rows. **8 of 13 seeded rows have no saturated
fat figure at all**, so they cannot be scored even once the rest is confirmed.

| Field | Where it comes from | Notes |
|---|---|---|
| `protein_g` | Nutrition Facts panel | Per the row's stated unit, not per package |
| `calories` | Nutrition Facts panel | |
| `sat_fat_g` | Nutrition Facts panel | **Required to score.** Missing on 8 rows |
| `national_price_usd` | Retailer listing | Price of the row's unit (see §3) |
| `purchase_price_usd` | Retailer listing | Register price of the whole package |
| `servings` | Package | How many of the row's unit per package |
| `retailer` | — | Which store the price basis came from |
| `format` | — | `rtd-single`, `shelf-single`, `multi-serve`, `requires-prep` |

The build cross-checks `purchase_price_usd / servings` against
`national_price_usd` and fails loudly if they disagree by more than 2¢ or 3%, so
a unit can't silently drift from its package price.

## 2. Official sources to fetch

Nutrition Facts panels are a firmer source than restaurant menu pages — but the
**panel** is the authority, not the marketing copy on the same page.

| Vendor | URL | Known trap |
|---|---|---|
| Fairlife Core Power | `fairlife.com/core-power/{chocolate,vanilla}-protein-shake/` | Sat fat differs by flavour at identical calories |
| Fairlife Core Power Elite | `fairlife.com/core-power/chocolate-protein-shake-42g/` | Seeded sat fat (2 g) reads *lower* than the 26 g line — suspect |
| Fairlife Nutrition Plan | `fairlife.com/nutrition-plan/{chocolate,vanilla}/` | |
| Premier Protein | `premierprotein.com/products/chocolate-protein-shake` | Best-documented pricing of the set |
| Muscle Milk | `musclemilk.com/product/muscle-milk-pro-advanced-nutrition-protein-shake/` | **Whole line reformulated spring 2026** — see §5 |
| OWYN Pro Elite | `liveowyn.com/products/chocolate-pro-elite-protein-shake` | Standard 20 g line is below the floor |
| Quest | `questnutrition.com/products/chocolate-protein-shake` | Site deliberately omits calories — needs the physical panel |
| Ensure Max Protein | `abbottnutrition.com/our-products/ensure-max-protein` | Not yet seeded (no sat fat found) |
| Slate | `slatemilk.com/pages/nutri-ingredients` | Not yet seeded — see §5, the "20 g" figure is stale |
| Optimum Nutrition | `optimumnutrition.com/products/gold-standard-100-whey-protein-powder` | Serving is 1 scoop; the row is 2 |
| Fage Total 0% | `usa.fage/products/yogurt/total-0/` | Panel is per 170 g; the row is 1.5 cups |
| StarKist | `starkist.com/products/chunk-light-tuna-in-water` | Panel is per 2 oz drained, not per can |
| Kirkland Signature | Costco item pages only | No brand site exists |

## 3. Price basis — decided

**Per-unit from a standard mass-retail multipack** (Walmart / Target / Amazon
list), *not* club per-unit and *not* a convenience-store single.

- It matches existing house practice: the Costco pizza slice is already priced
  as 1/6 of an 18" pie.
- Club per-unit is the cheapest *and* membership-gated, so using it as the
  primary basis would let a gated price set the 45%-weighted term.
- Convenience singles are the highest and most location-variable, and would make
  the category look artificially bad.

Record the single-bottle price in `notes` so the alternate basis is recoverable.

**The spread is real and needs measuring per product.** Premier Protein 30 g is
the one product documented end to end: Costco 18-pack works out to
**$1.67–1.83/bottle**, a Walmart single is **$2.47–2.97**, a Kroger single is
**$3.29–3.49** — a **1.4× to 2.1×** spread. Core Power Elite 12-pack figures
collected so far are internally contradictory (Costco $4.00/bottle vs Walmart
$5.65/bottle) and should not be trusted until confirmed directly.

**Still missing entirely: a convenience/gas-station single price for any
product.** That's the top of the spread and nothing captured it.

### Stores to price at
Costco, Fred Meyer (Kroger's PNW banner), Walmart, WinCo, Trader Joe's. Note
that Kirkland and Costco rows carry `membership_required: true`, which drives a
badge and a filter on the page — the listed price is not one a non-member can
pay.

## 4. Unit choice — where the 25 g floor forces the issue

The floor stays at 25 g on both boards (a deliberate consistency call). The
consequence is that several staples only clear it above their natural label
serving, so the unit must be **disclosed, not quietly inflated**:

| Item | Natural serving | Fails floor | Unit used instead |
|---|---|---|---|
| Greek yogurt | 1 cup = 22 g | ✗ | 1.5 cups = 33 g |
| Eggs | 4 = 24 g | ✗ | 5 = 30 g |
| Cottage cheese | 1 cup = 24 g | ✗ | not yet seeded |
| Whey powder | 1 scoop = 24 g | ✗ | 2 scoops = 48 g |
| Deli turkey | 4 oz = 24 g | ✗ | not yet seeded |
| Canned tuna | 1 can = 27 g | ✓ | as sold |

Rotisserie chicken is the one row whose unit rests on an **estimated edible
yield** (1/4 bird, meat only). That assumption has to be stated and sourced;
Costco publishes no panel for it.

## 5. Stale figures to watch for

Every one of these is a case where the widely-repeated number is wrong:

1. **Muscle Milk — reformulated spring 2026.** PepsiCo removed all artificial
   sweeteners and moved to ultra-filtered milk; the line now spans 26–42 g. The
   commonly-quoted **"Pro 40 g" is now 42 g** and **"32 g" is now 33 g**. Also
   check whether `gatorade.com` or `musclemilk.com` is now canonical.
2. **Slate — "20 g" is stale.** Current SKUs are 30 g (11 oz) and 42 g (15 oz),
   so Slate clears the floor and should be seeded once confirmed.
3. **Muscle Milk Genuine sits at exactly 25 g** — one reformulation gram either
   way includes or excludes it. One source suggests the line now starts at 26 g.
4. **Core Power Elite sat fat** reads lower than base Core Power despite 16 g
   more protein. Plausible via milk-protein isolate, but verify before trusting.
5. **Quest publishes no calorie figure** on its own product pages.

## 6. Below the floor — don't spend effort

Confirmed under 25 g, so they can never rank: Muscle Milk Zero (20 g), standard
OWYN (20 g), Orgain Clean/Vegan (20 g), Iconic (20 g), Ripple (20 g), Barebells
Milkshake (24 g — one gram short), Boost High Protein (20 g), Quest bars (21 g).

## 7. Categories evaluated and deliberately excluded

Scoped, then dropped, so the reasoning isn't re-litigated later:

| Category | Why not |
|---|---|
| Costco frozen chicken breast | Near-duplicate of rotisserie chicken plus a cooking step; no marginal insight |
| Deli meat | Sits on top of canned chicken at a worse price; 4 oz fails the floor |
| Protein bars | Two of the three biggest names fail the floor; heavy SKU churn, near-zero insight |
| Jerky / meat sticks | ~3.75 g protein per dollar — worse than a Double Cheeseburger. One README sentence, not a row |
| Convenience-store items | No verifiable national price, no stable nutrition source |
| More warehouse-club prepared food | Widens the membership-comparability problem before it's settled |

## 8. Where the meal-plan literature points

High-protein meal planning converges on the same short list this board is built
around, which is a useful sanity check on scope rather than a source of numbers:
lean poultry, canned fish, eggs and egg whites, plain Greek yogurt and cottage
cheese, milk-protein-isolate drinks, and whey powder. Two implications worth
carrying:

- **The staples are the point.** Tuna, rotisserie chicken, whey and yogurt set
  the true scale; without them the shakes have nothing to be measured against
  and "is a $3 shake good value" has no answer.
- **Eggs are the useful negative result.** Cheap protein, but saturated fat and
  calorie density gut them under this rubric. Carrying the row is worth more than
  omitting it, because the finding is counterintuitive.

## 9. Explicitly out of scope

**No convenience or effort term in the score.** It can't be verified, so it
would be a fourth weight sourced from nothing but judgment, on a board whose
credibility rests on being auditable. The `format` flag plus the disclosed
register price and serving count carry the same information as facts.
