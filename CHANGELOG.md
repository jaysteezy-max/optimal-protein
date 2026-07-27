# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the data itself is
refreshed continuously and is not versioned here — see commit history for
week-to-week data updates.

## [Unreleased]

### Added
- **Six new chains** — Panera Bread, Firehouse Subs, El Pollo Loco, Shake Shack,
  Costco Food Court and Dutch Bros, contributing 25 web-verified items. Dutch
  Bros' hot medium and large Protein Lattes clear the 25 g protein floor at
  33–42 g; the "20 g" figure repeated across the web is stale 2024 launch
  marketing. Costco has no official nutrition page (food-court data lives on
  in-warehouse menu boards), which is noted in `config/chains.yaml`.
- **Costco food-court Chicken Strips (5 ct)** — the new $6.99 item that rolled out
  nationwide in mid-2026. At 87 g it is the highest-protein single order on the
  board and lands at #4 overall. Tracked without the dipping sauce, consistent
  with how the board treats dressings: the viral "1,640 calories" figure includes
  the sauce, which alone accounts for 520 cal and 7 g of saturated fat; the strips
  themselves are 1,120 cal / 8 g sat fat.
- **"Off menu" unranked state.** An item pulled from a chain's menu keeps its
  last published nutrition for reference and is now labelled *off menu* in the
  list, the detail sheet and `RANKINGS.md`, instead of being lumped in with rows
  that are merely awaiting verification. Driven by an `off-menu` marker in the
  `source` column, so it stays a pure data decision.
- **Score v2.** The Value Score is now three terms — 50% protein-per-dollar,
  30% leanness (% of calories from protein), 20% low-saturated-fat — replacing
  the old value+density blend. A locked hard rule scores **only web-verified
  items with saturated-fat data**; seeded rows are listed but unranked with an
  "awaiting verification" state. New `sat_fat_g` column in `data/items.csv`.
- **Sort options.** Sort the list by value score, most protein, protein per
  dollar, leanest, or lowest price (control in the list header).
- **Compare mode.** Tap "Compare", pick any two items, and see their metrics
  side by side with the better value highlighted on each row.
- **Budget mode.** Enter a dollar amount (and optionally a chain) to get the
  single item and the best same-chain combo that maximize protein within it.
- **Chain view.** Filtering to one chain marks its top pick "Order this"; the
  chain name in an item's detail sheet is now a tappable "see all from this
  chain" shortcut.
- **Social/SEO.** Open Graph + Twitter card meta and a generated `docs/og.png`
  so shared links unfurl, an inline SVG favicon, and a description/theme-color.
- **Motion.** anime.js (v3.2.2, vendored into `docs/` to keep the page
  offline-capable and CDN-free) now drives six animations: staggered list
  entrance on load and filter changes, a "Best value" badge pop, a score
  count-up when the detail sheet opens, elastic score-breakdown bars, a
  choreographed sheet-open content sequence, and a price roll-in on region
  change. All of it degrades gracefully — under `prefers-reduced-motion`, or if
  the library fails to load, elements simply appear in their final state.
- `design.md` — documents the app's Apple/Cupertino design system: color
  tokens, type scale, spacing, components, and motion.
- `CHANGELOG.md` — this file.

### Changed
- **Nutrition verification finished.** All 61 rows previously marked
  `seeded — verify` are now web-verified with saturated fat, each checked against
  the chain's own published data plus at least one independent source, so nothing
  sits unranked for lack of verification.
- Tightened the header caveat to a crisp, Apple-style line ("Regional price
  estimates — not till-verified. Before tax and app deals. Tap any item for the
  full breakdown."). The scoring formula and region-invariance notes it used to
  spell out are already shown in the region selector and the per-item
  breakdown.

### Fixed
Verification corrected a lot of seeded data. The material ones:

- **Items that had been seeded as the wrong build.** Jersey Mike's cold subs were
  seeded plain, but the numbers people actually eat are Mike's Way — the oil
  blend adds roughly 200 cal (the #8 Club Sub went from 750 to 1120 cal). Chipotle
  and Cava bowls were recomputed from official per-component tables (Chipotle's
  chicken bowl 48 g/665 cal → 45 g/565).
- **Items that no longer exist as seeded.** KFC's 3-piece tenders row described
  the discontinued Extra Crispy Tenders and now tracks Original Recipe Tenders
  (27 g/390 cal → 33 g/510). Carl's Jr.'s Super Star was renamed Double Famous
  Star in 2022. Burgerville's Colossal Cheeseburger matched no current variant.
- **Rows built on legacy "official" data.** Both In-N-Out rows were stale: the
  chain's own table now reads 610 cal/34 g for a Double-Double, while third-party
  sites still publish 670 cal/37 g. KFC's Famous Bowl was reformulated
  (26 g/740 cal → 31 g/590).
- **Under-counted totals.** Carl's Jr. Charbroiled Chicken Club 34 g → 43 g;
  Raising Cane's Box Combo 52 g → 61 g once the sides are counted; Five Guys
  Cheeseburger 43 g → 47 g; Arby's Double Roast Beef 34 g → 38 g.
- **Five rows fell below the 25 g protein threshold** once corrected and dropped
  off the board: Wendy's 10-pc nuggets (27 g → 23 g), Arby's Beef 'n Cheddar
  (26 g → 23 g), Jack in the Box Chicken Fajita Pita (26 g → 24 g), Subway's
  6-inch Rotisserie-Style Chicken (29 g → 23 g, its chicken portion cut to 71 g),
  and Costco's hot dog combo at 24 g.
- **Prices refreshed** where the seed had drifted — Panda Express's a la carte
  Orange Chicken entree was $6.70 on file against a current medium price of
  $8.50; Chipotle's steak bowl $10.70 → $11.68.

An adversarial re-audit of the already-ranked rows then corrected the rows that
were driving the board. Every previously-verified row that got re-checked needed
a change:

- **Five ranked items were not orderable.** Wendy's Grilled Chicken Sandwich has
  been discontinued in the US since 2023 — the one still documented online is a
  UK item — and Subway's Footlong Rotisserie-Style Chicken is no longer a named
  menu item. Taco Bell's Double Steak Grilled Cheese Burrito was a limited-time
  offer; the row now tracks the current Steak Grilled Cheese Burrito
  (40 g/910 cal → 28 g/680). All are listed *off menu* rather than deleted.
- **Chipotle's double bowl had the right totals on the wrong build.** 81 g and
  760 cal are official, but they belong to the named Double High Protein Bowl,
  whose build includes Monterey Jack and light rice — so its saturated fat was
  7 g on a cheese-less build against an official 11 g. Renamed and corrected.
- **All three Costco rows were 2021-vintage panels**, and the pizza saturated fat
  was a whole-pie figure divided by six rather than a reading — the one line on
  that panel that doesn't divide cleanly. Cheese slice 40 g/760 cal/16.5 g sat →
  41/710/14; pepperoni 33/710/13 → 34/650/11; Chicken Bake 46/770/10 → 52/840/11.
- **Qdoba Chicken Protein Bowl 60 g → 51 g** — Qdoba replaced its 2025 brochure in
  February 2026, moving adobo chicken from 23 g to 19 g per 3.5 oz.
- Also corrected: In-N-Out 3x3 52 g/860 cal → 48/790 (derived from the chain's
  current published increments, since In-N-Out publishes no 3x3 panel); Cava
  double bowl 780 → 825 cal; McDonald's Double Cheeseburger 450 → 440 cal;
  Burgerville's double cheeseburger was understated, not overstated (480 → 520
  cal); El Pollo Loco's chicken breast 220 → 200 cal.
- Confirmed unchanged against official sources: Arby's Half Pound Roast Beef
  nutrition, Taco Bell's Grilled Cheese Burrito (verified against an official
  label exposing unrounded values), and both Dutch Bros Protein Lattes.

The re-audit stopped on a session limit with 11 rows unchecked, two of which
anchor the score normalization. `BACKLOG.md` lists exactly which.

## [1.0.0] — 2026-07-24

First complete release: a self-contained ranking page plus the data pipeline
that generates it.

### Added
- **Data pipeline.** `build_rankings.py` turns `config/` + `data/` into
  `docs/index.html`, `docs/data.json`, and `RANKINGS.md` — a pure function of
  its inputs.
- **Value scoring.** Value Score = 60% protein-per-dollar + 40% protein density
  (protein per 100 cal), each normalized so the best item = 100. Weights and the
  25 g protein threshold live in `config/scoring.yaml`.
- **Ranking page** with searchable, chain-filterable, inset-grouped list and a
  tap-to-open **detail sheet** showing the full score breakdown, nutrition and
  price specs, and derived cost-per-protein cards.
- **Regional pricing.** Prices are national averages scaled by a per-region
  multiplier (`config/regions.yaml`), with keyless IP auto-detect and a manual
  picker whose choice persists in the browser. Rankings are region-invariant —
  a uniform multiplier cancels out of the normalization, so only displayed
  prices move.
- **Weekly automation.** A GitHub Actions workflow refreshes nutrition and
  prices, regenerates all outputs, and opens a `data-refresh` issue instead of
  inventing data when a fetcher fails or a new item lacks a verified price.
- **Verified data.** Each chain's best pick cross-checked against several
  nutrition databases and marked `web-verified`; remaining rows flagged
  `seeded — verify`.

### Changed
- Redesigned the ranking UI around an Apple/Cupertino language (system font,
  frosted sticky controls, bottom sheet) and reworked the README.
- Refined the hero copy to the "Gains for Less" title with a new eyebrow and
  tagline.
- Removed the earlier location hint in favor of the region selector.

### Fixed
- Detail-sheet gesture handling: a downward swipe anywhere on the sheet — and
  anywhere on its header — now reliably dismisses instead of being swallowed by
  the scroll container.

[Unreleased]: https://github.com/jaysteezy-max/optimal-protein/compare/main...HEAD
[1.0.0]: https://github.com/jaysteezy-max/optimal-protein/releases/tag/v1.0.0
