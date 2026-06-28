---
title: Research — Learning Fine-Tuning Concepts
type: spec
tags:
  - type/spec
created: '2026-06-28'
updated: '2026-06-28'
---
# Research: Learning Fine-Tuning Concepts

**Feature**: 048 Learning Fine-Tuning Concepts
**Date**: 2026-06-28

## Research Context

This feature adds 3 concept pages and 1 interactive widget to the existing anvil learning system. All unknowns were resolved during the clarification phase.

## Decision Log

### Decision 1: Widget System Pattern

- **Decision**: Follow the existing constructor + prototype pattern from `widget-base.js` / `embedding.js` / `sampling.js`
- **Rationale**: All 16 existing widgets use the same pattern. Reusing it means zero new framework code, the widget auto-registers via `WIDGET_CLASSES` in `concept.html`, and the carousel system handles step synchronization.
- **Alternatives considered**:
  - Vanilla JS inline in `concept.html`: would bypass the existing widget system and not match patterns
  - React/Vue component: violates Simplicity First (Article XI) and adds dependency overhead

### Decision 2: LoRA Widget Type

- **Decision**: Slider-based interactive visualization (similar to `sampling.js` and `params.js`)
- **Rationale**: The low-rank intuition is best conveyed by letting the user adjust the rank (r) and see how the approximation quality changes. A slider controlling `r` and a visual showing the A×B matrix approximation is the clearest interactive explanation.
- **Alternatives considered**:
  - Static diagram: doesn't meet FR-024c requirement for interactive widget
  - Animation-only: less instructive than user-driven exploration

### Decision 3: LoRA Widget API Source

- **Decision**: The widget visualizes a synthetic/mathematical LoRA decomposition (no backend API needed)
- **Rationale**: The conceptual page explains *what* LoRA does, not a specific trained model's weights. The widget shows rank-r decomposition of a random matrix, letting the user explore the concept independently of any trained model. This avoids needing to:
  - Add a new backend API endpoint
  - Have a trained model loaded
  - Handle empty states when no model exists (the widget works standalone)
- **Alternatives considered**:
  - Backend API returning actual LoRA weights: would require a model with LoRA applied, adding dependency on spec 044

### Decision 4: Page Content Structure

| Page | Steps | Interactive Element |
|------|-------|-------------------|
| What fine-tuning is | 4-5 steps | None (text + diagrams) |
| Warm-start vs PEFT/LoRA | 5-6 steps | `lora` widget for rank intuition |
| Fine-tune vs prompt vs RAG | 4-5 steps | Comparison table (inline HTML in step body) |

### Decision 5: Navigation Integration

- The 3 new pages are individual entries in `LEARNING_ARC` list, inserted after the "export" entry (key: `export`, line 173 of `learning.py`)
- They will appear in `LEARNING_ARC_LESSONS` automatically (not in `_ADDITIONAL_KEYS` or `_OPS_KEYS`)
- `_arc_context()` handles prev/next navigation automatically based on list order
- Resulting order in the arc: ... → Export → What Fine-Tuning Is → Warm-start vs PEFT/LoRA → Fine-Tune vs Prompt vs RAG → Chunking Strategies → ...

### Decision 6: "Coming Soon" Forward Links

- Implemented as inline `<span class="coming-soon-badge">` with a tooltip/popover describing the upcoming capability
- No dead links (no `<a href>`), no 404 pages
- Badge CSS lives in `components.css` alongside other widget styles

## Configuration

No new configuration, environment variables, or settings required. All content is inline in `learning.py`.

## Dependencies

| Dependency | Type | Purpose |
|-----------|------|---------|
| `anvil/api/v1/learning.py` | Existing module | Add `FINE_TUNING_STEPS` arrays, routes, `LEARNING_ARC` entries |
| `anvil/api/templates/archetypes/concept.html` | Existing template | Add `lora.js` script include and `WIDGET_CLASSES` entry |
| `anvil/api/static/js/widgets/widget-base.js` | Existing widget base | LoRA widget extends this pattern |
| `anvil/api/static/css/components.css` | Existing CSS | Add `.lora-*` and `.coming-soon-badge` widget styles |