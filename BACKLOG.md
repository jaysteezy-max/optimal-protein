# 📋 Backlog

Durable roadmap for this repo, so it's visible across Claude Code sessions and
on GitHub (the in-session task list is ephemeral — it does not persist here).
Last updated 2026-07-30 (shelf board added with per-category scoring; membership
gating made a real field; two long-standing bugs fixed).

## 🔜 Open

### Verify the shelf board — nothing on it is scored
**Status:** blocked on network access, not on a decision · **the top item**

All 13 shelf rows are seeded and unranked. The session that built the board had
no outbound HTTPS (blocked at the gateway for every host), and search snippets
were deliberately not treated as verification — undated third-party summaries are
exactly how the stale figures documented below propagate.

**[docs/shelf-probe.md](docs/shelf-probe.md) is the work order**: every official
URL, the trap in each, the price-basis decision and the spread behind it. Highest
value first:

1. **Saturated fat for 8 of the 13 rows** — hard-blocks scoring on its own.
2. **A convenience/gas-station single price for any product** — the top of the
   pricing spread; nothing captured it, so the multipack-vs-single question is
   still only half answered.
3. **Kirkland US pricing and sat fat** — no brand site exists, so the Costco item
   page is the only possible source.

Two seeded figures should be treated as suspect until a panel confirms them:
Core Power Elite's saturated fat reads *lower* than the 26 g line despite 16 g
more protein, and the rotisserie chicken row rests on an estimated edible yield
that must be stated rather than assumed.

Effort: M, and it is all fetching and cross-checking — no code.

### Shelf board follow-ons, once rows are verified
**Status:** not started · cheap once the data lands

- **Slate** clears the floor (30 g / 42 g SKUs; the widely-quoted 20 g is stale)
  and should be seeded.
- **Quest** needs the physical panel — its own product pages omit calories.
- **Cottage cheese and deli turkey** were scoped and left out; revisit only if the
  board looks thin, since both cluster on top of rows already present.
- **The benchmark strip** on the shelf board (raw cross-board medians) is built
  and wired but stays hidden until the board has scored rows. It'll light up on
  its own — worth eyeballing when it does.

### Verified-price workflow — the last soft spot
**Status:** not started · `data/manual_prices.csv` still has zero entries

Every price on the board is a national-average estimate plus a regional
multiplier. The plumbing to do better already exists — a row in
`data/manual_prices.csv` (chain slug + exact item name) is used as-is with no
uplift and marks that item's price verified — but nothing uses it yet. Needed:

- a documented routine for logging a real till price when you order;
- a "verified price" affordance on the page, so a confirmed price visibly
  outranks an estimate instead of both rendering identically;
- ideally a verified-price count in the header alongside the item count.

This is now the biggest gap between what the page claims and what it knows.
Effort: S–M.

### More chains
**Status:** the original six are done; pick the next batch

Shipped: Panera Bread, Firehouse Subs, El Pollo Loco, Shake Shack, Costco Food
Court, Dutch Bros. Each new one needs a `config/chains.yaml` entry plus
web-verified items with `sat_fat_g`.

Worth doing, in order of insight per row:

1. **More rows at chains already tracked** — the double-protein / add-a-patty /
   a-la-carte builds: Chipotle's full High Protein menu, Panda double entree,
   Cava and Qdoba double protein, Subway double meat, McDonald's add-a-patty.
   This is the highest-value item on the whole list and it keeps getting skipped
   in favour of new logos. No new sources, no new config, no positioning
   question, and it serves the README's promise directly — the actionable finding
   of this tool is "order the a-la-carte protein, not the sandwich", and there are
   four rows proving it where there could be twenty.
2. **WinCo / Fred Meyer deli hot bar** — the most on-mission item of the grocery
   expansion: still a counter you order at, and the bridge between the two boards.
3. **Wingstop** — real PNW footprint, a genuinely wings-shaped hole, lands
   mid-table so it disturbs nothing.
4. **Sweetgreen** — worth it for the negative result. At roughly 2.3 g protein per
   dollar the healthy-looking salad chain is near the bottom of the board, which
   is a finding.
5. **Jimmy John's** — fine, on-mission, low insight. Four sub chains are already
   present and they all cluster in the 20s–30s. Coverage, not learning.

**Removed from this list: Portillo's and Torchy's.** Portillo's has no Washington
or Oregon locations and Torchy's PNW footprint is thin at best — they were on the
next-chains list of a *PNW* tracker by mistake.

### Finish the re-audit — 11 rows left
**Status:** in progress · stopped early on a session limit, not on a conclusion

Less urgent since Score v3: under v2 a single item set the scale for a whole
term, so one bad row silently moved all 96 scores. Winsorizing removed that
lever — the worst a wrong row can now do is misplace itself and nudge a
percentile. It still needs finishing, but it is no longer load-bearing.

Every previously-verified row that got re-audited needed correcting — **10 out of
10** — so the untouched rows should be assumed wrong until checked, not trusted.
Three of the ten turned out to be items you can't even order any more.

Still to re-audit:

| Row | Why it matters |
|---|---|
| Chick-fil-A Grilled Nuggets (12 ct) | Best calorie efficiency on the board (263 cal per 50 g). Its 0.75 g sat fat was scaled from the 8-ct panel rather than read. |
| Popeyes Blackened Tenders (5 pc) | Reports exactly 0.0 g saturated fat. Chicken tenderloin carries roughly 0.3–0.5 g per 100 g, so this is very likely label rounding rather than a true zero. |
| KFC Original Recipe Chicken Breast | ranked top 10 |
| Popeyes Fried Chicken Breast | ranked top 20 |
| Panda Express Grilled Teriyaki Chicken (entree) | ranked top 10; a la carte price never confirmed against the bowl price |
| Raising Cane's 6 Chicken Fingers | ranked top 10 |
| Carl's Jr. Big Carl · Jack in the Box Double Jack · Five Guys Bacon Cheeseburger | mid-board, never re-checked |
| Jersey Mike's #7 Turkey Sub in a Tub | build ambiguity — same plain-vs-Mike's-Way trap that made the cold subs wrong |
| Jamba Protein Berry Workout (16 oz) | the only row with **no `sat_fat_g` at all**; below the 25 g floor so it never scores, but the gap should be closed |

The two rows that mattered most under the old scoring *were* audited and
survived: the Costco cheese slice (three independent lenses) and Taco Bell's
Grilled Cheese Burrito (confirmed against an official label exposing unrounded
values).

### Re-verification cadence — official-first, and it decays
**Status:** policy worth writing down

This round found that third-party nutrition databases routinely serve data the
chains have already superseded, and that verified-once does not stay verified:

- In-N-Out's own table now reads 610 cal / 34 g for a Double-Double; the
  670 cal / 37 g figures still published across third-party sites are legacy.
- Costco's food-court panels were revised after 2021, and the widely-mirrored
  figures are the old ones. Worse, the mirrors' "per slice" pages are the
  whole-pie panel divided by six — detectable because the sodium comes out as
  1767 mg, a number no label would ever print. A real per-slice panel exists
  in-warehouse, so the division was never necessary.
- Qdoba replaced its 2025 brochure in Feb 2026, moving adobo chicken from
  170 cal / 23 g to 190 cal / 19 g per 3.5 oz — enough to knock 9 g off the
  Chicken Protein Bowl.
- Chipotle's "double protein bowl" is a real named menu item (Double High
  Protein Bowl) whose official build includes cheese and light rice. The row had
  the right totals attached to the wrong ingredient list, so its saturated fat
  was understated by 4 g.
- KFC's 3-piece tenders row described an item that no longer exists — Extra
  Crispy Tenders were replaced by Original Recipe Tenders in late 2024.
- Subway's rotisserie chicken portion was cut to 71 g, and Subway's 2026
  nutrition document now publishes chef-build values, so plain-build numbers
  have to be computed from component tables rather than read off a row.
- Jersey Mike's third-party data splits into "plain" and "Mike's Way" builds
  about 200 cal apart, with nothing saying which one you're looking at.

Rules that follow: prefer the chain's own current source; treat any
official-versus-third-party disagreement as official-wins; record which build
was priced; and re-audit ranked rows periodically rather than trusting a past
`web-verified` stamp. Note the weekly workflow refreshes prices, not nutrition.

### Off-menu items — keep or prune?
**Status:** needs a decision

Five rows are listed unranked as **off menu**: Taco Bell Power Menu Bowl, Subway
Footlong Steak & Cheese, Subway Footlong Rotisserie-Style Chicken, Burgerville
Best Coast Turkey Burger, and Wendy's Grilled Chicken Sandwich. They keep their
last published nutrition for reference and can never be scored. Decide whether
that reads as useful history or as clutter — and if useful, whether to link each
to its closest current replacement (all five have one named in `notes`).

Two of these were *ranked* items before this round: Wendy's Grilled Chicken
Sandwich (discontinued in the US since 2023 — the sandwich still on the web is a
UK item) and Subway's Footlong Rotisserie-Style Chicken. Both were sitting in the
top 20.

### Not yet picked from the earlier feature list
**Status:** not started

- **PWA / installable** — manifest + service worker so the page installs to the
  home screen and works fully offline. It's already self-contained, so this is
  the last mile. Effort: S–M.
- **"My picks" favorites** — star items into a shortlist in localStorage, with a
  filter chip. Effort: S.

### Regional pricing v2 — per-item scraping (maybe never)
**Status:** deferred

v1 shipped: regional multipliers + IP auto-detect (`config/regions.yaml`).
v2 would scrape per-item store prices for the top ~5 chains — brittle, ToS-gray,
a maintenance treadmill. Only attempt if the multiplier approach proves too
coarse. Possible companion: a per-chain `offers_url` link in the detail sheet.

## ✅ Decided / done (for context)

- **Off-the-shelf board added, scored separately.** A `Shelf` tab with full
  feature parity (search, sorts, compare, budget, swipe sheet, regional pricing,
  motion), 13 seeded rows across 9 brands. The decision that mattered was *not*
  merging it into the main board: winsorizing protects against one outlier, not
  against a dominant population, because the percentile reference itself moves.
  Shelf items beat fast food 3.5x on protein per dollar, 2.9x on calories per
  50 g and 6.6x on saturated fat at the median; pooled, shakes alone took 8 of the
  top 10 and the median score fell 44.1 → 33.3. Each category now normalizes
  against itself, ranks restart per board, and every pre-existing restaurant score
  is bit-identical (verified row-by-row as the gate on the change). Cross-board
  comparison is done with the raw per-50 g figures, which are absolute; the
  compare view warns when two picks span boards.
- **Costco membership flagged — closes the old "flag Costco as membership-gated"
  item.** It's now a real `membership_required` field on the vendor rather than a
  YAML comment and free-text notes that nothing downstream could read, and it
  drives a badge plus a filter. It covers the Kirkland shelf rows as well as the
  food court, which is the widened scope the original item anticipated.
- **The unit-of-comparison problem, resolved as disclosure rather than a score
  term.** New `format` / `servings` / `purchase_price_usd` / `retailer` columns,
  and the sheet states what the register charges next to what the score prices.
  A convenience or effort weight was considered and **rejected**: it can't be
  verified, so it would be a fourth term sourced from judgment alone on a board
  whose credibility rests on being auditable. The 25 g floor was kept on both
  boards by decision, accepting that some staples only clear it above their label
  serving — which is why those rows must declare the unit.
- **Two long-standing bugs fixed.** `pull_nutrition.py`'s hard-coded `FIELDS` had
  drifted (missing `sat_fat_g`), so `upsert_items` raised `ValueError` any time it
  had something to write — masked only because every curated chain exits early.
  And `pnw_uplift_pct` never reached the page: `__UPLIFT__` was substituted into a
  token that doesn't exist in the template, while `priceOf()` substituted the
  region multiplier *for* the uplift, agreeing with the score only because the PNW
  multiplier happened to equal it.
- **Nutrition verification finished.** All 61 rows that were `seeded — verify`
  are now web-verified and carry `sat_fat_g`, so nothing is unranked for lack of
  verification. Notable corrections: Jersey Mike's cold subs were seeded as plain
  builds (the #8 Club was 750 cal, actually 1120); Carl's Jr. Charbroiled Chicken
  Club 34 g → 43 g; Chipotle's bowls were inflated (chicken bowl 48 g/665 cal →
  45 g/565); both In-N-Out rows were legacy official data; Cane's Box Combo
  52 g → 61 g once the sides are counted. Five rows fell below the 25 g threshold
  once corrected and dropped off the board — Wendy's 10-pc nuggets, Arby's Beef
  'n Cheddar, Jack in the Box Chicken Fajita Pita, Subway 6-inch Rotisserie, and
  Costco's hot dog combo at 24 g.
- **Score v3 — fixed the normalization, not just the weights.** v2 scaled each
  term against the single best item, which let one outlier set the ruler: the
  Costco pizza slice pushed the *median* item to 22/100 on the heaviest-weighted
  term and won the board while scoring near-last on calories and saturated fat.
  Reweighting alone was simulated and did nothing — pizza stayed #1 under every
  weighting that kept protein-per-dollar dominant. v3 winsorizes at the 95th
  percentile instead (the textbook default; clips ~5% of items), reweights to
  45/40/15, and restates every term as a cost per 50 g of protein so portion size
  cancels out. "Leanness %" became "calories per 50 g protein" — same ranking,
  readable. Top of the board went from cheese pizza to El Pollo Loco's chicken
  breast; pizza sits at #18. Verified stable across percentiles 85–95.
- **Adversarial re-audit of the ranked rows started** (and found plenty — see the
  open item above for what's left). Corrected: Chipotle's double bowl renamed with
  sat fat 7 → 11 g; Qdoba Chicken Protein Bowl 60 → 51 g; In-N-Out 3x3
  52 g/860 cal → 48/790; all three Costco rows were 2021-vintage panels; Cava's
  double bowl 780 → 825 cal; McDonald's Double Cheeseburger 450 → 440 cal;
  Burgerville's double was *understated*, not overstated; El Pollo Loco's breast
  220 → 200 cal. Confirmed unchanged: Arby's Half Pound Roast Beef nutrition,
  Taco Bell's Grilled Cheese Burrito (official unrounded label), Dutch Bros'
  Protein Lattes.
- **Six chains added** — Panera Bread, Firehouse Subs, El Pollo Loco, Shake
  Shack, Costco Food Court, Dutch Bros. Dutch Bros' hot medium and large Protein
  Lattes do clear the 25 g floor (33–42 g); the widely-quoted "20 g" figure is
  stale 2024 launch marketing.
- **"Off menu" state added** to the build and the page, so an item pulled from
  the menu no longer renders as merely "awaiting verification".
- **Score v2** (superseded by v3, above). Introduced the three-term score, the
  verified-only hard rule enforced in `compute()`, the `sat_fat_g` column, the
  three-bar sheet breakdown and the unranked states. Its 50/30/20 weighting and
  best-item normalization did not survive.
- **App features shipped:** sort options (score/protein/$/lean/price), compare
  mode (two items side by side), budget mode (max protein for $X, optional
  chain), chain view ("Order this" + "see all from chain"), OG/Twitter cards +
  `docs/og.png` + SVG favicon.
- **anime.js motion** (vendored, reduced-motion-safe): list stagger, score
  count-up, elastic bars, badge pop, sheet-open timeline, price roll.
- **Concept 07 "The Apple"** chosen from the 7-concept gallery and shipped as
  the production page.
- **Item detail sheet** with transparent score breakdown, nutrition, cost-to-100g
  and $/25g; swipe-down-to-dismiss (down = close, up = reveal overflow).
- **Regional pricing** (client-side multipliers, free IP auto-detect, region
  picker persisted in localStorage). Rankings are region-invariant by design.
- **Weekly automation** (`.github/workflows/refresh-data.yml`): pull → validate
  prices → rebuild → commit; opens a `data-refresh` issue instead of ever
  promoting unverified data. Free on public repos.
- **Chain logo icons: dropped.** Trademark + offline-bundle cost outweighs the
  benefit; a neutral colored-initial chip is the fallback if ever revisited.
