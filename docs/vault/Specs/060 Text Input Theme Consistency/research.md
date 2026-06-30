# Research: Text Input Theme Consistency

**Date**: 2026-06-29  
**Plan**: [plan.md](plan.md)

## Theme Input Overrides

- **Decision**: No theme-specific input overrides needed
- **Rationale**: All 23 theme CSS files were searched for input/textarea/focus rules. Zero matches. Inputs styled via `--surface-2`, `--separator`, `--accent`, and `--text-tertiary` tokens will automatically adapt when themes override those tokens. Base token approach covers all themes.
- **Alternatives considered**: 
  - Adding per-theme input overrides (rejected: unnecessary complexity, violates YAGNI)

## Input Class Architecture

- **Decision**: Use `.form-input` as the canonical input class; consolidate `.terminal-input` into `.form-input`; keep `.widget-input` as a separate class inheriting visual tokens from `.form-input`
- **Rationale**: 
  - `.form-input` is the most widely used class (30+ instances across 5 templates)
  - `.terminal-input` is defined in the same CSS block as `.form-input` with identical styling — can be merged into a single selector
  - `.widget-input` intentionally uses mono font and widget-specific layout (7 widget files). It should share background/border/radius/focus tokens with `.form-input` but keep its unique font and width behavior
- **Alternatives considered**: 
  - Creating a single `.input` base class (rejected: would require rewriting 30+ template instances)
  - Using CSS `@extend` (rejected: native `@extend` is Sass-only, not available in vanilla CSS)

## Focus Ring Pattern

- **Decision**: Use `:focus-visible` with `box-shadow` focus ring, fall back to `:focus` with same style
- **Rationale**: 
  - `:focus-visible` is the modern accessibility best practice (WCAG 2.2) — ring only shows on keyboard navigation
  - Existing `:focus` rules in components.css already use `box-shadow: 0 0 0 2px var(--accent)` — can be adapted to `:focus-visible` with a `:focus` fallback
  - Theme picker already uses `:focus-visible` pattern (base.css line 179)
- **Alternatives considered**: 
  - Keep `:focus` only (rejected: shows ring on every mouse click, visually noisy)
  - `outline` instead of `box-shadow` (rejected: `box-shadow` allows rounded focus rings matching border-radius)

## Input Border Strategy

- **Decision**: Add `border: 1px solid var(--separator)` to `.form-input`, remove `border: none`
- **Rationale**: 
  - `--separator` (#38383a dark / #c6c6c8 light) provides subtle but visible boundary
  - Light mode fix: `--surface-2` (#f2f2f7) currently matches page background — border solves the invisibility issue
  - Matches existing `login-card__input` pattern (already uses `1px solid var(--border)`)
- **Alternatives considered**: 
  - Using `box-shadow` for boundary (rejected: `box-shadow` is the focus indicator, can't serve double duty)
  - Using a distinct background color for inputs (rejected: would require new token, `--surface-2` is the established input background)

## Login Page Input

- **Decision**: Migrate `login-card__input` to use `.form-input` class, keep login-specific layout in login.css
- **Rationale**: 
  - Login input already uses `--surface-2` background and `1px solid var(--border)` — structurally aligned with planned `.form-input` style
  - login.css can keep its layout classes (`.login-card`, `.login-card__field`, etc.) — only the input class changes
  - Login-specific focus style (uses hardcoded `#ff9f0a` fallback) will be replaced with `--accent` token via `.form-input`
- **Alternatives considered**: 
  - Keeping login separate (rejected per Q4 clarification — login must be in scope)

## Border-Radius Alignment

- **Decision**: Change `.form-input` border-radius from `var(--radius)` (13px) to `var(--radius-sm)` (8px)
- **Rationale**: 
  - DESIGN.md Shapes table specifies **sm (8px)** for inputs
  - Current 13px (`var(--radius)`) is the card/panel radius, not the input radius
- **Implication**: `.widget-input` also uses `var(--radius)` (13px) — should also change to `var(--radius-sm)` for consistency

## Disabled / Readonly States

- **Decision**: Add `.form-input:disabled` with `opacity: 0.4; cursor: not-allowed; box-shadow: none;` matching the button disabled pattern. Add `.form-input[readonly]` with `background: var(--surface); cursor: default;` for subtle tone shift.
- **Rationale**: No existing disabled/readonly input styles exist. Following established button pattern for disabled state.

## Touch Target Sizing

- **Decision**: Add `min-height: 44px` (var(--touch-min)) to `.form-input` for iOS HIG compliance
- **Rationale**: Current inputs are ~32px height (8px padding × 2 + ~16px line-height). iOS HIG requires 44pt minimum.
