# Design System — Protein Value Tracker

The app is one self-contained page (`docs/index.html`), generated from
`HTML_TEMPLATE` in `build_rankings.py`. There is no build step, no framework,
and no external asset — every rule below lives in the `<style>` block of that
template. **Edit the template, not the generated file:** `docs/index.html` is
overwritten on every `python3 build_rankings.py`.

The look is **Apple / Cupertino**: system font, tabular numerals, inset-grouped
lists, frosted sticky controls, a bottom sheet for detail, and restrained
motion. Everything is driven by CSS custom properties so light/dark and future
retheming stay in one place.

---

## Principles

1. **One surface, one source of truth.** All tokens are CSS variables on
   `:root`. Components reference tokens, never raw hex.
2. **Native-feeling, not flashy.** Motion exists to explain state changes
   (a sheet rising, a bar filling), not to decorate.
3. **Legible numbers.** `font-variant-numeric: tabular-nums` everywhere so
   scores and prices align in columns.
4. **Respect the system.** Honors `prefers-color-scheme` and
   `prefers-reduced-motion`; a manual `data-theme` on `:root` can override.
5. **Crisp copy.** Short, confident, lower-case-friendly. Say the necessary
   caveat once and move on.

---

## Color tokens

Defined three times so the theme resolves predictably: a light default under
`:root`, a `prefers-color-scheme: dark` block, and explicit
`:root[data-theme="light"]` / `:root[data-theme="dark"]` overrides for a manual
toggle.

| Token          | Light     | Dark      | Role                                        |
| -------------- | --------- | --------- | ------------------------------------------- |
| `--bg`         | `#f5f5f7` | `#000000` | Page background; sheet background            |
| `--card`       | `#ffffff` | `#1c1c1e` | List, panels, inputs                         |
| `--ink`        | `#1d1d1f` | `#f5f5f7` | Primary text                                 |
| `--muted`      | `#6e6e73` | `#98989d` | Secondary text                               |
| `--muted2`     | `#86868b` | `#8e8e93` | Tertiary text, labels, chevrons              |
| `--line`       | `#e5e5ea` | `#2c2c2e` | Structural borders (controls, list outline)  |
| `--hair`       | `#ebebf0` | `#2c2c2e` | Hairline dividers between rows/panels         |
| `--blue`       | `#0071e3` | `#0a84ff` | Accent: rank #1, links, focus, primary bar   |
| `--blue-soft`  | `#e8f1fd` | `#0a2540` | Accent fill: badges, pills, tips             |
| `--good`       | `#1a8f4c` | `#30d158` | Positive bar (leanness); compare "win" marks |
| `--warn`       | `#c93400` | `#ff9f0a` | Saturated-fat penalty bar (third score term) |

**Usage rules**

- Never hard-code a color in a component. If a new hue is needed, add a token.
- Semi-transparent states use `color-mix(in srgb, var(--ink) N%, transparent)`
  (row hover 3%, active 6%, bar track 8%) so they adapt to the theme
  automatically instead of needing a light/dark pair.
- `--blue` is the *only* accent. Use `--good` strictly for the density bar.

---

## Elevation & shape

| Token      | Value                        | Role                              |
| ---------- | ---------------------------- | --------------------------------- |
| `--shadow` | `0 4px 22px rgba(0,0,0,.06)` light / `…,.5` dark | Cards, inputs, list |
| `--radius` | `18px`                       | List container corner              |

Other radii are set locally and form a small scale: **22px** (sheet top
corners), **18px** (`--radius`, list), **14px** (panels, derived cards),
**12px** (inputs, tips), **8px** (pills), **6px** (small badges). Stay on this
ladder; don't introduce in-between values.

The detail sheet uses a heavier, upward shadow — `0 -8px 40px rgba(0,0,0,.28)`
— to read as a layer floating above the page.

---

## Typography

- **Family:** `-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI",
  Roboto, sans-serif`. No web fonts — the system stack is the design.
- **Base:** `16px / 1.47`, antialiased, `text-rendering: optimizeLegibility`.
- **Numerals:** `tabular-nums` globally.

Type scale (size / weight / tracking):

| Element                     | Size                    | Weight | Letter-spacing |
| --------------------------- | ----------------------- | ------ | -------------- |
| Hero `h1`                   | `clamp(30px, 8vw, 40px)`| 600    | `-.03em`       |
| Sheet score (`.sh-score`)   | `52px`                  | 300    | `-.03em`       |
| Sheet name (`.sh-name`)     | `24px`                  | 600    | `-.02em`       |
| Item score (`.sc`)          | `17px`                  | 600    | `-.01em`       |
| Row title (`.nm`)           | `15px`                  | 590    | `-.012em`      |
| Body / inputs               | `15–16px`               | 400    | —              |
| Eyebrow / section headers   | `11–12px`               | 600    | `+.02–.06em`, uppercase |
| Meta / caveat / footnotes   | `11.5–12.5px`           | 400    | —              |

**Rules of thumb:** big display text gets *negative* tracking and lighter
weight; small labels get *positive* tracking, uppercase, and `--muted2`.
Titles use the unusual `590` weight (SF's optical mid-bold) — keep it.

---

## Spacing

Loose 4px-ish rhythm; there is no rigid grid. Common paddings: rows `14px 16px`,
panels `16px`, inputs `11px 13px`, controls `12px 16px`. Content column is
capped at `max-width: 600px` and the caveat at `44ch` for a comfortable measure.

---

## Components

- **Sticky controls** (`.controls`) — frosted bar: `backdrop-filter:
  saturate(1.8) blur(20px)` over an 82%-opaque `--bg`, `--line` bottom border.
  Board switch spanning full width on top, then vendor filter + search on one
  row, then the region selector spanning full width below.
- **Board switch** (`.seg`) — iOS segmented control, `role="tablist"` with two
  real `<button role="tab">`s over an absolutely-positioned `.seg-ind`. The
  indicator slides via `transform` on `.seg[data-board="shelf"]` using the same
  `cubic-bezier(.32,.72,0,1)` as the sheet, so board switching feels like the
  rest of the app. Left/right arrows move between tabs.
  **The track mixes toward `--bg`, not `--ink`** — mixing toward ink inverts in
  dark mode and makes the track read *above* the raised indicator. Any new
  recessed surface should do the same.
- **Row flags** (`.flags` / `.flag`) — small muted chips under a row title that
  *qualify* it without competing with the score: `.flag.mem` (uses `--warn`) for
  a membership-gated price, plain `.flag` for the purchase format. Deliberately
  quieter than `.best` and `.order-badge`, which are calls to action.
- **Benchmark strip** (`.vs`) — three cards of raw cross-board metrics, shown
  only on the shelf board and only when both boards have scored rows. Carries
  raw per-50 g figures exclusively; never two value scores, which aren't
  comparable across boards.
- **Package disclosure** (`.pkg`) — a hairline-separated footnote inside the
  nutrition panel stating what the register charges versus what the score prices
  ("$4.99 buys 4 servings — the score uses $1.25 per serving").
- **Inset-grouped list** (`.list` / `.row`) — single `--card` container,
  `--radius` corners, `--hair` dividers, last row borderless. Rows are real
  `<button>`s: hover/active tint via `color-mix`, `focus-visible` shows a
  `--blue` inset outline. Rank #1 gets `.top` (blue rank + "Best value" badge).
- **Detail sheet** (`.sheet`) — bottom sheet to `max-height: 90vh` over a
  blurred `.backdrop`. Grab handle + close button; drag-to-dismiss handled in
  JS (see Motion). Contains score **breakdown bars**, a **specs grid**,
  **derived cost cards**, and an optional **tip** callout.
- **Bars** (`.bar`) — 7px track (`--ink` 8% mix), fill in `--blue`; add `.g`
  for the `--good` density bar. Fill animates from width 0 on sheet open.
- **Badges & pills** — `--blue` text on `--blue-soft`, small radii. "Best
  value" badge (list) and score pill (sheet) share this treatment.

---

## Motion

Keep it physical and brief. Structural motion (sheet, backdrop) is CSS;
expressive motion is **anime.js v3.2.2**, vendored at `docs/anime.min.js` so
the page stays offline-capable and CDN-free.

CSS easing curves:

- **`cubic-bezier(.32, .72, 0, 1)`** — the iOS "decelerate" curve. Sheet
  transform (`.32s`); also reused by anime as `IOS_EASE`.
- **`ease`** — backdrop fade (`.28s`).

anime.js choreography (all calls go through the `AN()` guard, which returns
nothing under reduced motion or if the library didn't load):

| Moment                    | Effect                                          | Easing |
| ------------------------- | ----------------------------------------------- | ------ |
| List render               | Rows rise/fade, `stagger(40)`, first 20 only    | `IOS_EASE` |
| #1 row badge              | Scale pop from .6                               | `easeOutElastic(1,.5)` |
| Region change             | Prices roll in, `stagger(14)` (`render('prices')` animates only `.pr`) | `IOS_EASE` |
| Sheet open — content      | Head + panels stagger in, `stagger(55)`         | `easeOutQuart` |
| Sheet open — score        | Number tween 0 → value over 900 ms              | `easeOutExpo` |
| Sheet open — bars         | Left-to-right fill, one 5% overshoot, settle on the score; `stagger(90)` (CSS width transition disabled first so they don't fight) | `easeOutQuart` → `easeOutSine` |
| Board switch              | Segmented indicator slides (CSS `transform`); the new list runs the standard render stagger | `cubic-bezier(.32,.72,0,1)` |

The sheet's own rise stays a CSS transition because the drag-to-dismiss
gesture manipulates that transform directly.

Interaction model for the sheet: the first few pixels of a drag decide the
gesture for its whole duration — down always dismisses (past a ~90px
threshold), up scrolls content. The header is always a dismiss target.

**Accessibility:** CSS transitions are disabled under
`@media (prefers-reduced-motion: reduce)`, and every anime.js call is skipped
by the `AN()` guard in the same condition — elements are authored in their
final state, so skipping the animation is always safe. Any new motion must
degrade the same way, and must not be required to understand a state change.

---

## Extending the system

- Add a **color** → new `:root` token in all three theme blocks; reference it,
  don't inline it.
- Add a **radius/shadow** → reuse the existing ladder before inventing a value.
- Add a **component** → compose from tokens; match the type-scale and spacing
  rhythm above; wire hover/active/`focus-visible` states; verify light **and**
  dark; confirm it collapses cleanly under reduced motion.
- Then regenerate: `python3 build_rankings.py`, and eyeball
  `docs/index.html` in both themes.
