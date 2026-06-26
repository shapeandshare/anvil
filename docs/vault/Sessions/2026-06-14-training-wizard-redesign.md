---
title: Training Wizard Redesign
type: session-log
tags:
  - type/session-log
  - domain/ui
  - domain/training
created: '2026-06-14'
updated: '2026-06-14'
aliases:
  - 2026-06-14-training-wizard-redesign
source: agent
---
## Summary

Redesigned the training page to reduce visual clutter by merging the "Select Data" and "Configure & Auto-Tune" section-cards into a single wizard card with a step stepper and tabs. The active runs list, loss chart, metrics, and output sections remain unchanged.

## Files changed

- `anvil/api/templates/archetypes/training.html` — Restructured DOM: merged two `<div class="section-card">` (data-source + config) into one `training-wizard` card containing the wizard stepper, tab bar, and two tab panels. Renumbered `--stagger-i` on remaining sections. Added `type="button"` to action buttons and converted wizard-step divs to `<button>` elements for accessibility. Added `switchWizardTab()` JS function with click handlers.
- `anvil/api/static/css/archetypes.css` — Added ~190 lines of wizard component styles: `.wizard-steps`, `.wizard-step` (with active/completed states and forge train variant), `.wizard-step-connector` (with filled state), `.wizard-tab` (pill tabs), `.wizard-panel` (with slide-in animation). Added button reset properties to `.wizard-step`.

## Wizard component structure

Single `section-card` with three layers:
1. **Step stepper** (`div.wizard-steps`): Three clickable `<button>` step bubbles connected by horizontal lines. States: gray outlined (inactive) → blue filled + glow (active) → green filled + checkmark (completed). The Train step uses forge orange gradient when active.
2. **Tab bar** (`div.wizard-tabs`): Two pill buttons — "Select Data" and "Configure & Auto-Tune". Active tab fills blue.
3. **Tab panels** (`div.wizard-panel`): Data panel (corpus/dataset selectors + context/stat cards) and Config panel (parameter grid + auto-tune + action buttons). Slide-in spring animation on switch.

## Key decisions

1. **Tabs over accordion**: Tabs keep both panels addressable and avoid scroll-jumping. The slide-in animation provides spatial context.
2. **Step bubbles don't persist "completed" state**: Going from Configure back to Data reverts step 1 from completed back to active. This avoids confusion — neither tab is a "finished" gateway.
3. **CSS pseudo-element for checkmark**: `.wizard-step--completed .wizard-step-bubble::after { content: '✓' }` + CSS `display: none` on the number `<span>`. Avoids inline style persistence bugs.
4. **Button elements for steps**: Using `<button>` instead of `<div role="button">` satisfies the HTML linter and provides native keyboard accessibility. Required adding button reset CSS (`background: none; border: none; padding: 0; font: inherit`).

## Bug caught during review

The initial implementation set `span.style.display = 'none'` inline on completed step bubbles, redundant with the CSS `.wizard-step--completed .wizard-step-bubble span { display: none; }` rule. Inline styles persist when the CSS class is removed, so switching from Configure back to Data would leave the number hidden. Fixed by removing the JS inline style — the CSS class toggle handles it correctly.

## Design system alignment

- All colors use CSS custom properties from `tokens.css` (no hardcoded hex)
- Spring animation on panel entrance (`--spring-quick`, 0.35s)
- Card follows `section-card` pattern (iOS rounded surface with shadow)
- Tab pills use `--radius-xl` (30px) matching iOS pill convention
- All touch targets ≥ 44px where interactive

## Related

- [[Design/Design|Design]] — UI design system including wizard and tab patterns
- [[Reference/TrainingDataFlow|Training Data Flow]] — training pipeline context
- [[Reference/wizard-stepper-pattern|Wizard Stepper Pattern]] — reusable wizard component reference