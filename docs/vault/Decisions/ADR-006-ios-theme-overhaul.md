---
title: ADR-006 iOS Design Overhaul
type: decision
tags: [type/decision, domain/ui]
created: 2026-06-13
updated: 2026-06-13
---

# ADR-006: iOS Design Overhaul

## Status
Accepted

## Context
The microgpt-workbench UI currently uses an "editorial whimsy" design language — a cross between a mid-century textbook publisher's typesetting and a modern terminal emulator. This includes dark cinema-like backgrounds, Times New Roman serif display type, monospace data display, pixel art, ASCII banners, and a unicorn mascot.

The user requested a full visual retheme to iOS mobile aesthetics:
- Drop the retro/terminal/whimsy personality entirely
- Adopt iOS design language (SF typography, glass effects, spring animations, rounded forms)
- Full structural change: bottom tab bar, large title navigation, mobile-first layout
- Preserve all existing functionality and routes

This requires amending Constitution Article VIII (Whimsy Without Compromise) and replacing the entire DESIGN.md specification.

## Decision
1. **Amend Constitution Article VIII** from "Whimsy Without Compromise" to "iOS-Grade Polish" — replacing pixel art, ASCII banners, and unicorn mascot mandates with requirements for fluid animations, clear hierarchy, precise typography, and platform-appropriate delight.

2. **Replace DESIGN.md** with a complete iOS design system specification covering:
   - iOS system color palette (dark/light)
   - System sans-serif typography throughout
   - Glass navigation bars with `backdrop-filter`
   - Spring-based motion system
   - Bottom tab bar + large title navigation shell
   - iOS component patterns (grouped lists, filled buttons, etc.)
   - WCAG AA contrast compliance

3. **Restructure the app shell** from header-tabs + status-bar to large-title-nav + tab-bar layout using `100dvh` flexbox with `env(safe-area-inset-*)` support.

4. **Preserve existing CSS class names** in widget JS `innerHTML` — restyle definitions, don't rename classes. This avoids breaking 9 widget JS files with ~40+ hardcoded class references.

5. **Delete `style.css` and `legacy.css`** — eliminate 2,231 lines of redundant CSS that shadow the token system.

## Consequences
### Easier
- Modern, polished UI aligned with user's mobile-first expectations
- Elimination of 2,231 lines of CSS debt
- Clean separation between token system and component styles
- Better mobile UX with proper touch targets and safe area handling
- Server-rendered architecture preserved (no SPA framework needed)

### Harder
- `backdrop-filter` glass effects require WCAG AA-compliant scrim management
- Canvas widgets (7 files) need manual color updates to read new CSS tokens
- SF Pro font cannot be legally embedded — iOS look is pixel-perfect only on Apple devices
- No iOS-like page transitions possible with server-rendered navigation
- Scrollable tab bar with 7 items is non-standard iOS pattern

## Compliance
- All 11 page routes return 200
- Theme switching (dark/light) via `localStorage` + `data-theme` still works
- All interactive elements have ≥44px touch targets
- All text/background pairs meet WCAG AA (4.5:1 normal, 3:1 large)
- `backdrop-filter` falls back to solid backgrounds when unsupported
- No hardcoded hex values remain in JS files
- All existing functionality preserved

## Dependencies
- Supersedes Article VIII of CONSTITUTION.md
- Supersedes the entire DESIGN.md specification
- Constitution version bumped to 1.2.0
