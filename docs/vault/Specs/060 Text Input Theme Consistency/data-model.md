# Data Model: Text Input Theme Consistency

**Date**: 2026-06-29  
**Plan**: [plan.md](plan.md)

This feature is purely visual — there is no runtime data model. The "model" is the CSS component architecture for text inputs.

## Input Component States

Every text input has these visual states, each driven by CSS custom properties:

| State | CSS Selector | Visual Properties | Token Dependencies |
|-------|-------------|-------------------|-------------------|
| **Default** | `.form-input` | `background: var(--surface-2)`, `border: 1px solid var(--separator)`, `border-radius: var(--radius-sm)` | `--surface-2`, `--separator`, `--radius-sm` |
| **Focus** | `.form-input:focus-visible` | `box-shadow: 0 0 0 2px var(--accent)` | `--accent` |
| **Focus fallback** | `.form-input:focus` | Same as `:focus-visible` (backup for older browsers) | `--accent` |
| **Hover** | `.form-input:hover:not(:disabled)` | `border-color: var(--text-tertiary)` (subtle border lighten) | `--text-tertiary` |
| **Disabled** | `.form-input:disabled` | `opacity: 0.4`, `cursor: not-allowed`, no focus/hover effects | — (opacity-based) |
| **Readonly** | `.form-input[readonly]` | `background: var(--surface)`, `cursor: default` | `--surface` |
| **Placeholder** | `.form-input::placeholder` | `color: var(--text-tertiary)` | `--text-tertiary` |

## Component Hierarchy

```
.form-input  (canonical — all text/number/select inputs)
├── .form-input:focus-visible   (keyboard focus ring)
├── .form-input:disabled        (reduced opacity)
├── .form-input[readonly]       (shifted background)
└── .form-input::placeholder    (tertiary text color)

.widget-input  (concept widgets — inherits visual tokens, adds mono font)
├── .widget-input:focus-visible (same ring pattern)
└── .widget-textarea            (multi-line variant within widgets)
```

## CSS Custom Properties Used

| Property | Current Value | Usage |
|----------|--------------|-------|
| `--surface-2` | `#2c2c2e` / `#f2f2f7` | Input background |
| `--separator` | `#38383a` / `#c6c6c8` | Input border color |
| `--radius-sm` | `8px` | Input border radius |
| `--accent` | `#007aff` | Focus ring color |
| `--text-tertiary` | `#8e8e93` | Placeholder text, hover border |
| `--touch-min` | `44px` | Input minimum height |
| `--text` | `#ffffff` / `#000000` | Input text color |
| `--font-body` | `-apple-system, ...` | Input font family |

## State Transitions

```
                 +----------+
                 | Disabled | ←── disabled attribute
                 +----------+
                       ↑
    +---------+    +---------+    +----------+
    | Default | →→ | Focused | →→ | Blurred  | (returns to Default)
    +---------+    +---------+    +----------+
         ↓
    +----------+
    | Readonly | ←── readonly attribute
    +----------+
```

All transitions are pure CSS — no JavaScript needed for state management.