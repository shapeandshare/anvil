---
title: "Session: Theme Gallery Expansion (+13 behavioral themes)"
type: session-log
tags:
- type/session-log
- domain/ui
created: 2026-06-19
updated: 2026-06-19
aliases:
- Session: Theme Gallery Expansion
source: agent
---

# Session: Theme Gallery Expansion (+13 behavioral themes)

**Date**: 2026-06-19

## Summary

Expanded the behavioral theme engine (see [[2026-06-20-theme-engine-implementation]]
and [[ADR-031-behavioral-theme-engine]]) from 4 to **17 themes**, in response to a
request for "many more." No engine code changed — every theme was added via the
documented three-step contract (CSS layer + JS module + one `base.html` include),
proving the FR-015 / SC-009 extensibility guarantee.

## Themes added (13)

| Theme | Modes | Driving signal | Metaphor |
|---|---|---|---|
| Tide | light+dark | loss / tps | rising shoreline, wave surge |
| Bloom | light+dark | loss / loss-volatility | garden opens, sway, milestone flower |
| Tectonic | light+dark | grad_norm + volatility | seismic shake, fault cracks, rupture |
| Glacier | light+dark | loss | crystalline freeze vs melt |
| Reactor | single | tps / loss | core glow, SCRAM strobe |
| Hyperspace | single | tps / loss | starfield streaks, jump flash |
| Mainframe | light+dark | tps | calm terminal cursor tick |
| Hologram | single | loss | wireframe focus, chromatic ghosting |
| Storm Front | light+dark | grad_norm / loss | lightning frequency, sky clearing |
| Ember Drift | single | loss / tps | drifting sparks, ambient warmth |
| Resonance | light+dark | grad_norm / loss | spectrum bars **+ opt-in WebAudio** |
| Inkwash | light+dark | loss | sumi-e bleed → crisp strokes |
| Stained Glass | single | loss / milestone | jewel panes light up |

## Key decisions

1. **Maximize dual light/dark.** 9 of 17 themes now ship both modes (was 2/4).
   Inherently luminous/degrading concepts (Reactor, Hyperspace, Hologram, Ember
   Drift, Stained Glass) stay `modes: ['single']`; Forge stays dark-only.
2. **Diversify the driving signal.** Prior themes were almost all loss-led. Added
   throughput-led (Reactor, Hyperspace, Ember Drift, Mainframe) and
   instability-led (Tectonic, Storm Front) themes so the same run *feels*
   different per theme.
3. **First use of the audio dimension (FR-020).** `Resonance` synthesizes a
   low-gain WebAudio tone (pitch ← loss, gain ← gradient amplitude). Created
   lazily on the opt-in toggle (a user gesture, satisfying autoplay policy),
   gated by the effect-level resolver via `EffectLevel.onChange`, and fully torn
   down on theme switch. No theme emits sound without explicit opt-in.
4. **Legibility contract (T4) honored.** Hologram ghosting, Inkwash bleed,
   Tectonic shake, and Old-Growth-style overlays sit behind a theme-private var
   the mapping zeroes when `effectLevel.legible` is set.

## Verification

- `node --check` passes on all 17 theme JS modules.
- System test `tests/system/test_theme_engine.py` updated: `THEME_IDS`,
  registrations, CSS-layer asset checks, and in-container CSS existence now
  parametrize all 17 themes (16 CSS layers; `default` has none).
- `pyproject.toml` `package-data` glob `api/static/**/*` already ships the new
  assets — no packaging change required.
- `DESIGN.md` "Behavioral Themes" section updated (gallery list, audio
  dimension, expanded theme-private var vocabulary).

## Follow-ups

- Browser QA of each new theme across both modes + reduced-motion / max-legibility.
- WCAG AA spot-check of light-mode accents (Bloom, Tide, Inkwash, Storm Front).
- Consider an overfitting-aware theme once the spec-flagged `VAL_LOSS` signal is
  emitted by the engines (still out of scope today).

## Picker redesign (same session)

The single-column dropdown overflowed the screen at 17 themes and had no keyboard
support. Reworked `theme_picker` into a **scrollable 2-column grid with full
keyboard navigation and live preview** (all in `theme-manager.js` + `base.css`;
no markup change to `theme_picker.html` since items are built client-side):

- **Keyboard**: Arrow Left/Right move by one, Up/Down by a row (`colCount()`
  derives columns from `offsetTop` so it stays correct if the grid reflows),
  Home/End jump to ends, **Enter/Space commit**, **Escape cancels**. Roving
  `tabindex` + `focus()` track the active tile.
- **Live preview**: highlighting a tile (arrow or hover) calls `previewApply()`
  → `apply(id, mode, {persist:false})`, so the whole UI re-themes instantly
  **without** writing `localStorage`. `previewBase` captured on open; Escape /
  click-away / trigger-toggle revert to it; Enter/click persist.
- **Overflow**: `.theme-picker__grid` is `max-height: min(58vh,440px)` with
  `overflow-y:auto`; the effect-control checkboxes stay pinned below the scroll
  area. Menu width fixed at 320px (`max-width: calc(100vw - space-4)`); tile
  name/hint truncate with ellipsis (full text in `title`).
- **Verification**: a throwaway jsdom harness drove open → arrow-preview →
  no-persist → Enter-persist → Escape/click-away-revert → Home/End (23 assertions,
  all green). Added CI guards in `tests/system/test_theme_engine.py`
  (`TestPickerKeyboardNavigation`) asserting the shipped `theme-manager.js`/`base.css`
  contain the arrow handlers, `previewApply`/`persist:false`/`commitSelection`, and
  the scrollable grid.

The reusable pattern is captured in
[[Reference/theme-picker-grid-keyboard-nav]].

## Nav-bar chrome + ambient background (same session)

Two follow-on UI-chrome changes, both token-based and theme-safe (`base.css` only).
These complete the layout direction begun in
[[Sessions/2026-06-20-ui-layout-overhaul]] (footer removal + nav-as-scrolling-card
+ `app-shell` scroll container): when this work started, that note's
gradient-move and nav-card styling were not actually present in `base.css`, so the
edits below realize them.

- **Floating nav box**: `.nav-bar` is now a rounded box inset from the screen
  edges — `margin: space-3 space-3 space-2` (tighter at ≤480px),
  `border-radius: --radius-lg`, a 1px `--glass-border`, solid `--surface`, and
  **no drop shadow** (per the design rule, the border + surrounding background
  define it). Horizontal padding trimmed `--space-6` → `--space-4`.
- **Continuous ambient background**: moved the atmospheric accent-glow
  `radial-gradient` from `.app-main` up to `.app-shell` (origin nudged `8%` →
  `5%`) and removed it from `.app-main` to avoid doubling. The page background
  now spans the full viewport and reads continuously **around** the floating nav
  box instead of starting below it. Ambient particles and `body`'s `--bg` still
  show through the gradient's transparent regions (unchanged layering).
- **Docs reconciled**: `DESIGN.md` updated — app-shell layers, Ambient
  background, the Navigation Bar component, a new Theme Picker component section,
  the reduced-transparency exemption, and the nav drop-shadow Do/Don't. Also
  corrected a pre-existing divergence: DESIGN.md had described the nav as a
  `backdrop-filter` glass bar with a fade mask, but the shipped CSS has always
  been a solid `--surface` bar (now the floating box). Marked the solid box as
  canonical.
