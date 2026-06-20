# Contract: Theme CSS Layer & Token Override

**Purpose**: Define how a theme's CSS layer overrides the design-token contract from `004-frontend-refactor/contracts/design-tokens.md`, so that swapping a theme is a token edit (per AGENTS.md: "a systemic restyle must be a token edit") and existing token-reactive widgets need zero changes.

## Layering model

```
tokens.css                      ← base: :root (dark default) + [data-theme="light"]  (UNCHANGED)
  └─ themes/<id>.css            ← theme layer: [data-theme="<id>"] { token overrides + effect scaffolding }
```

- `tokens.css` remains the authoritative base. The `default` theme uses ONLY base tokens (`[data-theme="dark"]`/`[data-theme="light"]` ≈ today's behavior) and has NO layer file.
- Each non-default theme ships exactly one layer file `static/css/themes/<id>.css`, loaded after the base sheets (and after `components.css`/`archetypes.css`) so its selectors win.
- The layer is gated entirely under the theme's attribute selector — it MUST NOT affect other themes.

## Required selector form

```css
/* themes/forge.css */
[data-theme="forge"] {
  /* 1) Palette/type/motion token overrides (consumed by ALL existing widgets via getComputedStyle) */
  --bg: #0c0a09;
  --surface: #16120e;
  --accent: #ff6a3d;
  --accent-orange: #ff7a1a;
  --font-display: /* theme display face */;
  /* ...override only tokens that change; inherit the rest... */

  /* 2) Theme-private effect variables (read by themes/forge.js) */
  --heat: 0;            /* driven by tokens_per_sec */
  --prog: 1;            /* clarity = 1 − normalized loss */
}

/* light variant if the theme supports it */
[data-theme="forge"][data-mode="light"] { /* ...light overrides... */ }

/* Accessibility resets — MANDATORY, mirror tokens.css global reset */
@media (prefers-reduced-motion: reduce) {
  [data-theme="forge"] * { animation: none !important; transition: none !important; }
}
```

## Rules

| # | Rule | Maps to |
|---|---|---|
| T1 | A theme overrides design tokens; it MUST NOT hardcode raw values in component selectors. Widgets read tokens via `getComputedStyle`, so token overrides auto-propagate with no per-widget change. | AGENTS.md token rule; SC-009 |
| T2 | All token overrides MUST keep WCAG AA contrast for primary text/controls in every supported mode. | FR-016, SC-006 |
| T3 | The layer MUST include a `@media (prefers-reduced-motion: reduce)` reset scoped to its `[data-theme]`. | FR-017, SC-005 |
| T4 | Legibility-degrading effects (glyph corruption, heavy overlays) MUST be behind a class/var the manager can disable for reduced-effects/maximum-legibility. | FR-018, SC-006 |
| T5 | Theme-private effect variables (e.g. `--heat`, `--prog`, `--disturbance`) are namespaced to the theme and written by the theme's JS mapping; the backend never sets them (neutral signals). | FR-011, R6 |
| T6 | `single`-mode themes define one inherent appearance; light/dark control is inert (manager communicates this). | FR-023 |
| T7 | A theme layer MUST NOT modify base `tokens.css` or another theme's selectors. | FR-015, FR-019 |
| T8 | The `default` theme MUST be byte-for-byte the current experience (no layer, base tokens only). | FR-019, SC-007 |

## Reference theme token intents (binding behavior, refine-able values — FR-027)

| Theme | Token/effect intent |
|---|---|
| **Forge** | Warm near-black bg; ember/amber accents; `--heat` (tokens_per_sec) drives forge-core glow + spark canvas; `--prog` (1−norm loss) drives sample clarity + cooling-metal curve gradient (white-hot→steel-blue); divergence ⇒ alarm-red + sample re-noised. |
| **Old Growth** | Single-mode phosphor-green CRT; `--disturbance` (client-derived instability) drives scanline flicker + chromatic aberration (text-shadow) + glyph corruption + inverse signal-lock meter; divergence ⇒ `--disturbance`=1. Effects fully gated by T3/T4. |
| **Default** | No layer; existing iOS-modern dark/light. |
| **New behavioral theme** | ≥1 additional, distinct token palette + a distinct signal→expression intent (FR-008, FR-028). |

## Validation

- **Contrast audit**: every theme/mode passes WCAG AA for primary content (manual/automated check) — SC-006.
- **Reduced-motion audit**: no continuous animation runs under `prefers-reduced-motion` in any theme — SC-005.
- **Widget regression**: existing token-reactive widgets (adam, loss, sampling, …) render correctly under each theme with no widget code change — SC-009.
- **Default parity**: `default` theme visually identical to pre-feature baseline — SC-007.
