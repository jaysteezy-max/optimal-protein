# 📋 Backlog

Durable roadmap for this repo, so it's visible across Claude Code sessions and
on GitHub (the in-session task list is ephemeral — it does not persist here).
Last updated 2026-07-27 (nutrition verification finished; 6 new chains added;
re-audit of the ranked rows started).

## 🔜 Open

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

### Flag Costco as membership-gated
**Status:** not started · the one piece of the scoring problem still open

Score v3 fixed the math (see done section), but not the comparability issue.
Every other chain on the board sells to anyone; Costco's food court has required
a paid membership since April 2024, so its $1.99 and $6.99 prices exclude a
~$65/yr fee that no other row carries. The prices are honest, the comparison
isn't quite. Wants a badge on the chain, and probably a filter to exclude
membership-gated chains. Effort: S.

### More chains
**Status:** the original six are done; pick the next batch

Shipped this round: Panera Bread, Firehouse Subs, El Pollo Loco, Shake Shack,
Costco Food Court, Dutch Bros. Candidates for a next pass: Wingstop, Portillo's,
Sweetgreen, Jimmy John's, Torchy's, and PNW grocery delis (WinCo, Fred Meyer).
Each needs a `config/chains.yaml` entry plus web-verified items with `sat_fat_g`.

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
