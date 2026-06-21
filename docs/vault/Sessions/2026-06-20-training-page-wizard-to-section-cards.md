---
title: 'Session: Training Page Wizard Converted to Numbered Section Cards'
type: session-log
tags:
  - type/session-log
  - domain/ui
  - domain/training
source: agent
created: '2026-06-20T00:00:00.000Z'
updated: '2026-06-20T00:00:00.000Z'
aliases:
  - 'Session: Training Page Wizard to Section Cards'
  - Training Page Wizard to Section Cards
---
# Session: Training Page Wizard Converted to Numbered Section Cards

**Date**: 2026-06-20
**Status**: Completed

## Summary

Replaced the single-section tab-switched training wizard (Data ⇄ Configure tabs + 1→2→3 stepper) with three standalone numbered section cards, each always visible. Removed the `switchWizardTab()` JS function, wizard tab/step click listeners, and the `wizard-panel`/`wizard-tab`/`wizard-step` CSS classes from the template. The three sections now follow the existing `ds-flow-section` pattern from the datasets page.

## Changes

### Template Restructure (`training.html`)

**Before**: One monolithic `.training-data-source.section-card.training-wizard` containing:
- Wizard stepper (1→2→3) with connectors
- Tab switcher (Select Data / Configure & Auto-Tune)
- Two `wizard-panel` divs toggled by JS (`#panel-data`, `#panel-config`)

**After**: Three independent `.section-card.ds-flow-section` blocks:

| Section | Step | Bubble | Content |
|---------|------|--------|---------|
| Select Data Source | 1 | Blue `①` | Corpus/dataset selectors, conflict warnings, data context card, model stats card |
| Configure & Auto-Tune | 2 | Purple `②` | All 8 param blocks (n_embd, n_layer, n_head, block_size, num_steps, lr, temperature, compute backend), memory estimate, OOM warning, Auto-Tune button |
| Forge Your Model | 3 | Orange forge `⛏` | Start Training + Stop buttons only |

### JavaScript Removed
- `switchWizardTab()` function (~30 lines of panel/tab/step/connector state management)
- Wizard tab click handlers (`document.querySelectorAll('.wizard-tab')`)
- Wizard step click handlers (`document.querySelectorAll('.wizard-step[data-step]')`)

All data interaction logic (autotune, model stats, data source switching, training lifecycle) left untouched.

### CSS Added (`archetypes.css`)
- `.ds-flow-bubble--forge` — orange/yellow gradient background with glow shadow for step 3, matching the forge theme of the Start Training button

### Stagger Animation
- Stagger-i indices updated (runs→0, data→1, config→2, train→3, chart→4, metrics→5, output→6) to maintain entrance animation timing

## Design Rationale

The datasets page already used `ds-flow-section` with numbered bubbles (1→2→3 flow sections all always visible). Reusing this pattern creates visual consistency across pages and eliminates the cognitive overhead of tab-switching — users can see all three steps at once. The "Step 3" bubble uses a forge (orange/yellow) variant instead of the datasets page's green, since training completion uses green for "done" states and the orange forge theme is the training page's identity.

## Files Modified
- `anvil/api/templates/archetypes/training.html` — major template restructure + JS cleanup
- `anvil/api/static/css/archetypes.css` — added `.ds-flow-bubble--forge`

## References
- [[Discoveries/tab-switched-wizard-to-section-cards|Tab-Switched Wizard to Section Cards Pattern]] — Pattern documentation for replacing tabbed wizards with always-visible numbered flow sections
- `anvil/api/static/css/archetypes.css` — `.ds-flow-section` rules at lines 1271–1336, `.ds-flow-bubble--forge` at line 1306
