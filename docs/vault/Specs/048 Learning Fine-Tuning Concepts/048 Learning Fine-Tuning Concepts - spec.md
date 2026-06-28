---
title: 048 Learning Fine-Tuning Concepts - spec
type: spec
tags:
  - type/spec
  - domain/learning
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

Teaches the *why* and *when* of fine-tuning as the next rung of anvil's learning ladder. Adds explorable
pages — what fine-tuning is, warm-start vs PEFT/LoRA (with LoRA intuition), and when to fine-tune vs
prompt vs RAG — wired into the existing learning navigation as an ordered progression from the
from-scratch material. Pedagogy is first-class (FT-AD-10): this ships alongside the capabilities it
frames (039, 044), not after.

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-024, FR-026 (concepts aspect) |
| **Owned decisions** | FT-AD-10 |
| **Depends on** | Existing learning content system (`anvil/api/v1/learning.py`, learning UI/widgets) |
| **Invariant risk** | **NONE** — content + UI only |

---

## User Story

### US — Learner Progresses Into Fine-Tuning Concepts (Priority: P1)

A learner who has trained from scratch follows an ordered arc explaining what fine-tuning is, how
warm-start differs from PEFT/LoRA, and when to fine-tune vs prompt vs RAG.

**Independent Test**: Open the fine-tuning learning section; verify pages exist for (a) what fine-tuning
is, (b) warm-start vs PEFT/LoRA, (c) fine-tune vs prompt vs RAG, each in the explorable-explanation style
and linked as a progression from the from-scratch material.

**Acceptance Scenarios**:

1. **Given** the learning section, **When** the learner opens the fine-tuning arc, **Then** concepts are
   presented as an ordered progression continuing from the existing from-scratch lessons.
2. **Given** the LoRA page, **When** the learner explores it, **Then** the low-rank-adapter intuition is
   conveyed interactively, consistent with the existing widget/Distill-style approach.
3. **Given** the decision page, **When** the learner reads it, **Then** fine-tune vs prompt vs RAG
   trade-offs are presented evenhandedly.

### Edge Cases

- A capability is not yet shipped (e.g., 044) → the concept page still stands alone and links forward
  without dead ends.
- Learner arrives directly (deep link) → the page situates itself in the arc with clear prev/next.

## Requirements

- **FR-024**: The learning arc MUST add fine-tuning content as an ordered progression from the existing
  from-scratch material: what fine-tuning is, warm-start vs PEFT/LoRA, and when to fine-tune vs prompt vs
  RAG.
- **FR-026 (concepts)**: Each shippable fine-tuning capability MUST ship with its corresponding learning
  content; this spec provides the conceptual pages for 039 (warm-start) and 044 (PEFT/LoRA).
- **FR-024a**: Pages MUST use the existing explorable-explanation style and integrate with the learning
  navigation (prev/next, arc membership).

## Success Criteria

- **SC-001**: The fine-tuning concept pages exist, are linked as an ordered progression, and match the
  existing learning style.
- **SC-002**: The LoRA page conveys the low-rank intuition interactively.
- **SC-003**: The decision page presents fine-tune vs prompt vs RAG evenhandedly.
- **SC-004 (NMRG)**: Pre-existing tests pass unmodified; content-only change.

## Key Entities

- **LearningModule (concepts)**: explorable units for fine-tuning concepts within the learning arc.

## Definition of Done

- Concept pages exist in the explorable style, linked as a progression, integrated with learning nav;
  **NMRG (full)**.

## Assumptions

- Architecture-difference content is owned by spec 049; this spec owns the conceptual/decision pages.
