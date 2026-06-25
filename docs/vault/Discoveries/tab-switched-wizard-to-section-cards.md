---
title: Tab-Switched Wizard to Section Cards Pattern
type: discovery
source: agent
code-refs:
  - anvil/api/templates/archetypes/training.html
  - anvil/api/static/css/archetypes.css
tags:
  - type/discovery
  - domain/ui
created: '2026-06-20T00:00:00.000Z'
updated: '2026-06-20T00:00:00.000Z'
aliases:
  - Tab-Switched Wizard to Section Cards
---
# Tab-Switched Wizard to Section Cards Pattern

## Context

The training page originally used a tab-switched wizard: a single `section-card` containing hidden panels toggled by tab buttons, with a 1→2→3 stepper. This was replaced by three always-visible numbered section cards using the `ds-flow-section` pattern already established on the datasets page. This note documents the reusable pattern.

## The Pattern

Replace tab-switched wizards (one container, JS-toggle visibility) with always-visible numbered section cards using `ds-flow-section`:

```html
<div class="section-card ds-flow-section" data-step="1">
  <div class="ds-flow-header">
    <span class="ds-flow-bubble">1</span>
    <div>
      <div class="ds-flow-label">Step 1</div>
      <div class="ds-flow-title">Section Title</div>
    </div>
  </div>
  <p class="ds-flow-desc">Description text.</p>
  <!-- content -->
</div>
```

### Step Coloring Convention (from `archetypes.css`)

| data-step | Bubble color | Use case |
|-----------|-------------|----------|
| `1` | `var(--accent)` (blue) | First step, data selection |
| `2` | `var(--accent-purple)` (purple) | Configuration, tuning |
| `3` | `var(--accent-green)` (green) | Completion, results (datasets page default) |
| `3` + `.ds-flow-bubble--forge` | Orange/yellow gradient | Training's "Forge" step (overrides green) |

The forge variant was needed because the training page uses a forge (orange) identity for the train action, and green is reserved for "done" states.

### What to Remove When Converting

1. **HTML**: Tab container, tab buttons, hidden panels (`wizard-panel`, `wizard-tab`, `wizard-step`, `wizard-step-connector`), stepper
2. **JS**: Tab switching function, tab click listeners, step click listeners
3. **CSS**: Can leave unused classes (harmless dead code) or remove if the wizard classes are page-specific

### What Stays

All data interaction logic: data loading, form validation, auto-tune, model stats computation, training lifecycle. Only the presentation layer changes — the functional layer is untouched.

## Why This Works

- **No JS overhead** for tab state management
- **Visual hierarchy**: Each step gets its own card with entrance animation (`card-entrance` via `--stagger-i`)
- **Always visible**: Users see all steps at once, no need to click tabs
- **Consistent with datasets page**: Reuses existing `ds-flow-section` CSS from `archetypes.css`
- **Extensible**: Adding a step 4 means adding another `ds-flow-section` card — no JS changes needed

## Files Using This Pattern

- `anvil/api/templates/archetypes/training.html` — three sections (data, config, train)
- `anvil/api/templates/datasets.html` — original `ds-flow-section` implementation
- `anvil/api/static/css/archetypes.css` — all `ds-flow-section` rules including `.ds-flow-bubble--forge`

## References
- [[Discoveries/Discoveries|Discoveries]]

- [[Sessions/2026-06-20-training-page-wizard-to-section-cards|Session: Training Page Wizard to Section Cards]]
