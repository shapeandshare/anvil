---
title: Research — Learning Architecture Differences
type: spec
tags:
  - type/spec
created: '2026-06-28'
updated: '2026-06-28'
---
# Research: Learning Architecture Differences

**Feature**: 049 Learning Architecture Differences
**Date**: 2026-06-28

## Research Context

This feature adds 1 accordion-style learning page to the existing anvil learning system. Unlike standard carousel-based lessons, this page uses the existing FAQ accordion pattern for a single-page expandable layout. All unknowns were resolved during spec clarification and codebase exploration.

## Decision Log

### Decision 1: Template Pattern

- **Decision**: Create a new template `architecture-differences.html` reusing existing `.faq-item` accordion CSS and `toggleFaq()` JS rather than the carousel `concept.html`
- **Rationale**: FR-025 UX explicitly requires "single-page layout with expandable/collapsible sections (accordion pattern)" — not the step-by-step carousel. The FAQ accordion pattern (`.faq-item` / `.faq-question` / `.faq-answer` in `components.css`, `toggleFaq()` in `faq-common.html`) is the closest existing pattern and can be adapted cleanly.
- **Alternatives considered**:
  - Reusing `concept.html` with carousel: violates FR-025 UX requirement for accordion layout
  - Custom JS accordion from scratch: violates Simplicity First (Article XI) — existing pattern can be reused
  - Third-party accordion library: violates Simplicity First + no new dependencies policy

### Decision 2: Template Structure

- **Decision**: New template extends `base.html`, reuses `concept-lesson-header` block for arc navigation, renders step data as accordion panels
- **Rationale**: Header block from `concept.html` provides consistent prev/next + "Back to Learning Index" navigation. Step data structure (`key`, `title`, `body`) maps naturally to accordion panels.
- **Alternatives considered**: Inline all content in template — would break the data-driven pattern and prevent content reuse

### Decision 3: Accordion Auto-Open on Load

- **Decision**: The template includes inline JS that checks `window.location.hash` on load and auto-opens the matching accordion section
- **Rationale**: FR-025a UX requires cross-links from 041 to land on the allow-list section via anchor ID. Without auto-open, the user would land at the page top and need to manually find and click the correct section.
- **Alternatives considered**: Server-side conditional — requires route query param; client-side hash detection is simpler and matches existing `concept.html` hash behavior

### Decision 4: LEARNING_ARC Insertion Point

- **Decision**: Insert `"architecture-differences"` entry after the 048 entries (`"finetune-vs-prompt-vs-rag"`) and before `"chunking"` in `LEARNING_ARC`
- **Rationale**: This keeps the Fine-Tuning Arc (038) lessons grouped together (048 concepts → 049 architecture differences → then back to general lessons). `_arc_context()` handles prev/next navigation automatically based on list order.
- **Alternatives considered**: Before 048 entries — breaks the fine-tuning arc grouping; After all general lessons — dilutes the fine-tuning arc continuity

### Decision 5: Content Section Order

- **Decision**: 5 accordion sections in this order: (1) Tokenization Differences, (2) Attention Variants, (3) Parameter Scaling, (4) Context Length, (5) Architecture Allow-List
- **Rationale**: Follows the logical progression from fundamental building blocks (tokenization → attention → parameters → context) to the practical conclusion (allow-list). The allow-list section is last because it's the "so what" — the practical implication of all the differences.
- **Alternatives considered**: Allow-list first — violates flow (user needs to understand differences before they understand why the allow-list exists)

### Decision 6: Accordion Behavior

- **Decision**: Use the existing `toggleFaq()` single-open pattern (one section open at a time, closing any previously open section)
- **Rationale**: Matches existing FAQ behavior; simpler UX for the learner (no competing open sections)
- **Alternatives considered**: Multi-open (clicking a second section keeps the first open) — violates Simplicity First for marginal UX benefit

## Configuration

No new configuration, environment variables, or settings required. All content is inline in `learning.py`.

## Dependencies

| Dependency | Type | Purpose |
|-----------|------|---------|
| `anvil/api/v1/learning.py` | Existing module | Add `ARCHITECTURE_DIFFERENCES_STEPS` array, `LEARNING_ARC` entry, route handler |
| `anvil/api/templates/archetypes/` | Template directory | New `architecture-differences.html` template |
| `anvil/api/static/css/components.css` | Existing CSS | Reuse `.faq-item`, `.faq-question`, `.faq-answer`, `.faq-toggle` classes |
| `anvil/api/templates/partials/faq-common.html` | Existing JS | Reuse `toggleFaq()` function |
| `anvil/api/static/css/archetypes.css` | Existing CSS | Reuse `.concept-lesson-header`, `.learn-arc-nav`, `.section-card` classes |
