---
title: 048 Learning Fine-Tuning Concepts - spec
type: spec
tags:
  - type/spec
  - domain/content
  - domain/ui
status: draft
spec-refs:
  - docs/vault/Specs/048 Learning Fine-Tuning Concepts/
related:
  - '[[048 Learning Fine-Tuning Concepts]]'
  - '[[038 Fine-Tuning Arc]]'
  - '[[Reference/FineTuningArchitectureDecisions]]'
created: '2026-06-28'
updated: '2026-06-28'
---

# Feature Specification: Learning Arc — Fine-Tuning Concepts

**Feature Branch**: `048-learning-fine-tuning-concepts`
**Created**: 2026-06-28
**Status**: Draft
**Parent Spec**: [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc (umbrella)]]

## Overview

Teaches the *why* and *when* of fine-tuning as the next rung of anvil's learning ladder. Adds three
explorable pages in order: (1) what fine-tuning is, (2) warm-start vs PEFT/LoRA (with LoRA intuition),
and (3) fine-tune vs prompt vs RAG — wired into the existing learning navigation as individual entries
in `LEARNING_ARC`, positioned after "Model Export" as the final core lessons. Pedagogy is first-class
(FT-AD-10): this ships alongside the capabilities it frames (039, 044), not after.

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-024, FR-026 (concepts aspect) |
| **Owned decisions** | FT-AD-10 |
| **Depends on** | Existing learning content system (`anvil/api/v1/learning.py`, learning UI/widgets) |
| **Invariant risk** | **LOW** — content + UI only; new widget JS required for LoRA page is scoped to existing widget framework |

---

## User Story

### US — Learner Progresses Into Fine-Tuning Concepts (Priority: P1)

A learner who has trained from scratch follows an ordered arc explaining what fine-tuning is, how
warm-start differs from PEFT/LoRA, and when to fine-tune vs prompt vs RAG — in that order.

**Independent Test**: Open the fine-tuning learning section; verify pages exist for (a) what fine-tuning
is, (b) warm-start vs PEFT/LoRA, (c) fine-tune vs prompt vs RAG, each in the explorable-explanation style
and linked as a progression from the from-scratch material.

**Acceptance Scenarios**:

1. **Given** the learning section, **When** the learner opens the fine-tuning arc, **Then** concepts are
   presented as an ordered progression continuing from the existing from-scratch lessons.
2. **Given** the LoRA page, **When** the learner explores it, **Then** the low-rank-adapter intuition is
   conveyed interactively — widget/Distill-style approach (live visualization with controls, rendering in
   an HTML canvas, following the same pattern as the existing embedding, attention, and sampling widgets).
3. **Given** the decision page, **When** the learner reads it, **Then** fine-tune vs prompt vs RAG
   trade-offs are presented evenhandedly.

### Edge Cases

- A capability is not yet shipped (e.g., 044) → the concept page still stands alone and links forward
  with a "Coming soon" badge/banner describing the upcoming capability; no dead links or 404s.
- Learner arrives directly (deep link) → the page situates itself in the arc with clear prev/next.

## Requirements

- **FR-024**: The learning arc MUST add three fine-tuning concept pages as an ordered progression from the
  existing from-scratch material, in this order: (1) what fine-tuning is, (2) warm-start vs PEFT/LoRA, and
  (3) fine-tune vs prompt vs RAG.
- **FR-026 (concepts)**: Each shippable fine-tuning capability MUST ship with its corresponding learning
  content; this spec provides the conceptual pages for 039 (warm-start) and 044 (PEFT/LoRA).
- **FR-024a**: Pages MUST use the existing explorable-explanation style and integrate with the learning
  navigation (prev/next, arc membership).
- **FR-024b**: Pages MUST be inserted as individual entries in `LEARNING_ARC`, positioned after "Model
  Export" and before ops/additional content — becoming the final entries in the main core lesson
  progression.
- **FR-024c**: The LoRA low-rank intuition page MUST include a new interactive widget (new JS file in
  `anvil/api/static/js/widgets/`) consistent with the existing widget system (widget-base.js registration,
  `concept.html` rendering).

## Success Criteria

- **SC-001**: The fine-tuning concept pages exist, are linked as an ordered progression, and match the
  existing learning style.
- **SC-002**: The LoRA page conveys the low-rank intuition interactively — the user can adjust a rank
  slider (1–16) and see the matrix approximation and reconstruction error update in real time.
- **SC-003**: The decision page presents fine-tune vs prompt vs RAG evenhandedly in a comparison table
  (rows per approach, columns for strengths/weaknesses/use-cases).
- **SC-004 (NMRG)**: Pre-existing tests pass unmodified. New e2e route tests are added for the three new
  pages (per codebase convention — one `test_learn_<name>` per lesson in `tests/e2e/api/test_pages.py`);
  NMRG applies to pre-existing tests, not to new public routes which require their own coverage.

## Key Entities

- **LearningModule (concepts)**: explorable units for fine-tuning concepts within the learning arc.

## Definition of Done

- Concept pages exist in the explorable style, linked as a progression, integrated with learning nav;
  **NMRG (full)**.

## Assumptions

- Architecture-difference content is owned by spec 049; this spec owns the conceptual/decision pages.

## Clarifications

### Session 2026-06-28

- Q: Where should the fine-tuning concept pages insert in the existing `LEARNING_ARC`? → A: Insert as individual entries after "Model Export", before ops/additional content. Each fine-tuning concept page becomes an independent entry in the core lesson progression. Documented in FR-024b.
- Q: Should the LoRA page include a full interactive widget or use text + static diagrams? → A: Full interactive widget (new JS file in `anvil/api/static/js/widgets/`), consistent with existing widget/Distill-style approach. Documented in FR-024c. Risk updated to LOW.
- Q: What form should forward links to unshipped capabilities (039/044) take? → A: "Coming soon" badge/banner with capability description — no dead links or 404s. Updated Edge Cases.
- Q: How should the fine-tune vs prompt vs RAG page present the trade-offs evenhandedly? → A: Comparison table with rows per approach and columns for strengths/weaknesses/use-cases. Updated SC-003.
- Q: What is the ordering of the three fine-tuning pages within `LEARNING_ARC`? → A: (1) What fine-tuning is, (2) Warm-start vs PEFT/LoRA, (3) Fine-tune vs prompt vs RAG. Updated FR-024, Overview, and User Story.
