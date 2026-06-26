---
title: Wizard-Stepper Component Pattern
type: reference
tags:
  - type/reference
  - domain/ui
created: '2026-06-14'
updated: '2026-06-14'
related:
  - '[[Reference/OpenQuestions]]'
---
## Discovery: Wizard-Stepper Component Pattern

The training page redesign introduced a **wizard-stepper** component — a reusable pattern for progressive multi-step forms within a single card.

### Structure

```
.section-card.training-wizard
  ├── .wizard-steps              (horizontal stepper bar)
  │   ├── .wizard-step           (clickable button, flex column)
  │   │   ├── .wizard-step-bubble (32px circle with number)
  │   │   └── .wizard-step-label (uppercase caption)
  │   ├── .wizard-step-connector (48×2px line)
  │   └── ...
  ├── .wizard-tabs               (pill tab switcher)
  │   ├── .wizard-tab            (pill button)
  │   └── ...
  └── .wizard-panel              (hidden, shown via --active)
```

### States

| Class | Appearance | Use |
|-------|-----------|-----|
| (default) `.wizard-step` | Gray outlined circle, dim label | Unvisited steps |
| `.wizard-step--active` | Blue filled circle + glow + scale(1.1), blue label | Current step |
| `.wizard-step--completed` | Green filled circle + ✓ checkmark, green label | Completed steps |
| `.wizard-step-connector--filled` | Blue line | Connector after completed step |
| `.wizard-step--train` | Forge orange gradient + glow (when active) | The action/start step |

### JS API

```javascript
switchWizardTab(tab)  // tab: 'data' | 'config'
```

Resets all step states, then:
- Marks `stepMap[tab]` as active
- Marks all prior steps as completed
- Fills connectors up to (but not including) the active step

### CSS Animation

`.wizard-panel--active` triggers a `panel-slide-in` animation (translateX(12px) → 0). This gives spatial orientation when switching tabs.

### When to use

- Settings/config forms with 2-4 logical steps that fit in one card
- Any multi-tab form where the tabs represent a progression (not just categories)
- Avoid for 5+ steps — the horizontal stepper gets cramped below 480px

### When NOT to use

- Tab categories that are parallel/equal (use plain tabs, not wizard)
- Forms where each step is a full page of content (use separate section-cards)
- More than 4 steps on mobile (connectors collapse to 24px, bubbles to 28px)

## See Also

- [[Reference/ArchitectureOverview|Architecture Overview]]
