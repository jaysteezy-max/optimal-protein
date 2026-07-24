# 📋 Backlog

Durable roadmap for this repo, so it's visible across Claude Code sessions and
on GitHub (the in-session task list is ephemeral — it does not persist here).
Last updated 2026-07-24.

## 🔜 Open

### Score v2 — leanness + saturated-fat penalty, web-verified only
**Status:** not started · **Blocked on:** data verification

Rework the Value Score from two terms to three:

| Term | Source | Notes |
|------|--------|-------|
| Protein per dollar | existing | value (keep) |
| **Leanness** = % calories from protein | `protein_g × 4 / calories` | derivable today, no new data |
| **Saturated-fat penalty** = sat fat per g protein | **new `sat_fat_g` column** | must be web-verified |

**Hard rule (locked):** only `web-verified` rows may feed the score. Seeded
(`seeded — verify`) rows are excluded from ranking until verified — no seeded
data in the numbers, full stop.

**Why it's blocked:** ~60 of 80 rows are still `seeded — verify`. Turning on the
hard rule today would shrink the scored board to ~20 items (the per-chain best
picks already cross-checked). The board grows back as verification proceeds.

**Sub-steps:**
1. Add a `sat_fat_g` column to `data/items.csv`.
2. Web-verify saturated fat + existing protein/calorie/price for each row
   (chain by chain); mark rows `web-verified`.
3. Decide the three weights in `config/scoring.yaml` (must sum to 1.0).
4. Update `compute()` in `build_rankings.py`: add leanness + sat-fat terms,
   exclude non-`web-verified` rows from scoring.
5. Update the detail-sheet score breakdown to show three terms + the equation.
6. Regenerate outputs, commit.

### Regional pricing v2 — per-item scraping (maybe never)
**Status:** deferred

v1 shipped: regional multipliers + IP auto-detect (`config/regions.yaml`).
v2 would scrape per-item store prices for the top ~5 chains — brittle, ToS-gray,
a maintenance treadmill. Only attempt if the multiplier approach proves too
coarse. Possible companion: a per-chain `offers_url` link in the detail sheet.

## ✅ Decided / done (for context)

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
