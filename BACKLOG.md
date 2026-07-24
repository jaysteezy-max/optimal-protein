# 📋 Backlog

Durable roadmap for this repo, so it's visible across Claude Code sessions and
on GitHub (the in-session task list is ephemeral — it does not persist here).
Last updated 2026-07-24 (Score v2 + app features shipped).

## 🔜 Open

### Finish nutrition verification — remaining seeded rows
**Status:** in progress · ~61 rows still `seeded — verify`

Score v2's hard rule scores only web-verified rows, so the board grows as these
are verified. For each seeded row, web-verify protein / calories / price **and**
the new `sat_fat_g`, then change its `source` to `web-verified <date>`. Work
chain by chain. The 19 ranking-driving picks are already done.

### New chains
**Status:** not started

Candidates: Panera, Firehouse Subs, El Pollo Loco, Shake Shack, Costco food
court, Dutch Bros. Each needs a `config/chains.yaml` entry plus web-verified
items (with `sat_fat_g`) to enter the scored board under the v2 hard rule.

### Regional pricing v2 — per-item scraping (maybe never)
**Status:** deferred

v1 shipped: regional multipliers + IP auto-detect (`config/regions.yaml`).
v2 would scrape per-item store prices for the top ~5 chains — brittle, ToS-gray,
a maintenance treadmill. Only attempt if the multiplier approach proves too
coarse. Possible companion: a per-chain `offers_url` link in the detail sheet.

## ✅ Decided / done (for context)

- **Score v2 shipped.** Three-term score (50% protein-per-dollar / 30% leanness
  / 20% low-sat-fat), verified-only hard rule enforced in `compute()`, new
  `sat_fat_g` column, three-bar sheet breakdown, unranked "awaiting
  verification" state. 19 ranked / 61 pending at ship.
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
