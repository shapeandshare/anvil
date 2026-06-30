---
title: Spec 060 — Text Input Theme Consistency
type: session-log
tags:
  - type/session-log
  - domain/ui
  - domain/ui
created: '2026-06-30'
updated: '2026-06-30'
status: draft
source: agent
aliases: Text Input Theme Consistency
---

# Spec 060 — Text Input Theme Consistency

**Session**: Unified all text-editing inputs across the anvil web UI — consolidated
4 input class variants into a single `.form-input` class with consistent border,
radius, focus ring (now `:focus-visible`), disabled/readonly/hover states, and
44px touch targets.

## What was done

### Core CSS changes (`anvil/api/static/css/components.css`)
- Added `border: 1px solid var(--separator)` to `.form-input`, `.form-select`, `.widget-input`
- Changed `border-radius` from `var(--radius)` (13px) to `var(--radius-sm)` (8px) per DESIGN.md
- Added `min-height: var(--touch-min)` (44px) for iOS HIG touch-target compliance
- Migrated focus ring from `:focus` to `:focus-visible` with `:focus` fallback
- Added `.form-input:disabled`, `.form-input[readonly]`, `.form-input:hover:not(:disabled)`
- Consolidated `.terminal-input` selectors into `.form-input`
- Preserved file-selector-button styling under `.form-input[type="file"]`

### Template migrations
- **training.html**: Added `class="form-input"` to 7 bare `<input type="number">` + compute backend `<select>`
- **login.html**: Changed `class="login-card__input"` to `class="form-input"`
- **config.html**: Changed `class="input"` to `class="form-input"` (2 occurrences)

### CSS cleanup
- **login.css**: Removed `.login-card__input` rule block (now covered by `.form-input`)
- **archetypes.css**: Simplified `.param-block input` — let `.form-input` handle visual properties
- **components.css**: Updated `.filter-bag` focus overrides to use `:focus-visible`
- Added `min-height: var(--touch-min)` to `.widget-input`

### Verification
- `make ux-lint`: PASS (S4 gate)
- `make lint` (ruff, black, isort): PASS
- `mypy --strict`: no issues in 440 source files
- Playwright audit: 21/21 checks passed across training page, login page, mobile 480px, light mode, Tide/Old Growth/Forge themes, and Reduce Effects mode
- `pytest`: 122 passed, 6 skipped (pre-existing API test import errors for mlflow.pyfunc)

## Files modified (6 files, +36/-54 lines)

| File | Change |
|------|--------|
| `anvil/api/static/css/components.css` | Core class rewrite |
| `anvil/api/static/css/archetypes.css` | `.param-block input` simplification |
| `anvil/api/static/css/login.css` | Removed `.login-card__input` |
| `anvil/api/templates/login.html` | Class swap |
| `anvil/api/templates/config.html` | Class swap (×2) |
| `anvil/api/templates/archetypes/training.html` | 7 inputs + select migration |

## Key decisions
- **Border**: `1px solid var(--separator)` — solves invisible input boundaries in light mode
- **Radius**: `var(--radius-sm)` (8px) — matches DESIGN.md Shapes table
- **Focus**: `:focus-visible` with `:focus` fallback — keyboard-only focus ring
- **Themes**: No theme-level changes needed — token inheritance covers all 23 themes
- **Touch targets**: 44px matches iOS HIG, applied via `--touch-min` token