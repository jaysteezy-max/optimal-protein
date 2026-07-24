# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the data itself is
refreshed continuously and is not versioned here — see commit history for
week-to-week data updates.

## [Unreleased]

### Added
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
- Tightened the header caveat to a crisp, Apple-style line ("Regional price
  estimates — not till-verified. Before tax and app deals. Tap any item for the
  full breakdown."). The scoring formula and region-invariance notes it used to
  spell out are already shown in the region selector and the per-item
  breakdown.

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
