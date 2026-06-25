---
title: Design Divergence Resolution
type: reference
tags:
  - type/reference
  - domain/ui
  - domain/governance
created: '2026-06-14'
updated: '2026-06-14'
---
During a design audit comparing DESIGN.md v2.0.0 against the live hero page and CSS implementation, we discovered several significant divergences. The hero page had introduced a "forge" sub-theme (orange/amber glow, ember particles, anvil icon, gradient text) that wasn't documented in the spec. The app shell had also diverged — the DESIGN.md described a bottom tab bar with large-title nav, but the actual implementation uses a top tab-strip nav bar with no bottom tab bar. Spacing tokens had expanded, ambient particles were present on every page, and button variants (gradient, forge) had been added.

**Resolution**: The divergence was intentional — the forge theme is the new brand identity. DESIGN.md was updated to v2.1.0 to canonize the current state.

## Post-canonization fixes (2026-06-14)

After the v2.1.0 DESIGN.md update, three cleanup issues were identified and fixed:

1. **Contradictory Do's/Don'ts**: The last "Don't" said ambient particles were hero-exclusive, but they're actually on every page via `base.html`. Fixed — now separates forge glow (hero-exclusive) from global ambient particles (all pages).
2. **Frontmatter naming drift**: `surface-secondary` in the YAML frontmatter didn't match the actual CSS token name `--surface-2`. Renamed to `surface-2` in both dark and light token blocks.
3. **Reduced-transparency exemption documented**: The exemption of ambient particles and radial gradient from `prefers-reduced-transparency` is now explicitly listed as intentional (they are atmosphere, not `backdrop-filter` effects), not an oversight.

## Key changes canonized

- **App shell**: No bottom tab bar. All navigation is a horizontal tab strip in the top nav bar. No large-title behavior. Glass nav bar has a vertical fade mask.
- **Archetype E (Hero/Landing)**: New 5th archetype for the root route. Centered layout with forge elements, 2-column feature card grid.
- **Orange as dual-purpose**: Warning semantic + forge brand accent (hero page only).
- **Ambient effects**: Orange radial gradient on every page's `.app-main` background + floating ember particles (`ambient-particles`).
- **Expanded spacing**: Added `space-3` (12px), `space-8` (48px), `space-9` (64px), `space-10` (96px) beyond the original 4/8/16/20/24/32 grid.
- **Gradient buttons**: `btn-accent` (blue→purple), `btn--forge` (orange→yellow with glow).
- **Hero card infinite bounce**: Hover triggers a 1s ease-in-out infinite bounce animation — a departure from the spec's 150ms restrained hover pattern.
- **glass-border token**: Border var for glass surfaces, not in original spec.

## Anvil emblem re-path (2026-06-14)

The `anvil-emblem.svg` path was replaced with one derived from an SVGRepo reference (English-pattern, right-facing horn). The original was a handcrafted left-facing shape; the new path traces the reference through a 7× coordinate transform into the 240×160 viewBox. The shape lives in three places that must stay in sync: `anvil/api/static/anvil-emblem.svg`, `hero.html` forge section inline SVG, and the `README.md` header. A favicon set was also added: `favicon.svg` (SVG, dark/light adaptive) and `apple-touch-icon.png` (180×180 PNG), both wired into `base.html`.

## Things that stayed consistent

- Token color values (still match iOS HIG)
- Type scale and font families
- `data-theme` switching mechanism
- Spinner (CSS circle, not ASCII)
- Spring timing functions
- Filled badges (not outlined)
- Safe area insets
- 17px → 16px responsive base font

## See Also

- [[Reference/ArchitectureOverview|Architecture Overview]]
