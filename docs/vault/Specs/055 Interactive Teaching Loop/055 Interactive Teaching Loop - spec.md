---
title: 055 Interactive Teaching Loop - spec
type: spec
tags:
  - type/spec
  - domain/training
  - domain/content
status: draft
spec-refs:
  - docs/vault/Specs/055 Interactive Teaching Loop/
related:
  - '[[055 Interactive Teaching Loop]]'
  - '[[038 Fine-Tuning Arc]]'
  - '[[Reference/FineTuningArchitectureDecisions]]'
created: '2026-06-28'
updated: '2026-06-28'
---

# Feature Specification: Interactive Teaching Loop

**Feature Branch**: `055-interactive-teaching-loop`
**Created**: 2026-06-28
**Status**: Draft
**Parent Spec**: [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc (umbrella)]]

> **Scope note (2026-07-02)**: This document states the full arc-level vision (including adapter support and formal evaluation via 054). The **implementation-scoped, MVP spec** is `spec.md` in this same directory, which — after a critical architecture review (see `research.md` §9-§12) — scopes the MVP to **native full-model teaching**, extracts a reusable `TrainingRunService`, chains on the **native experiment id** (not `ExternalModel.id`), and **defers** adapter support + formal evaluation. Where the two differ, `spec.md` governs implementation; FR-003/SC-003/"compare (054)" here describe the eventual arc goal, not the MVP.

## Overview

Makes "teaching a model" a first-class, **iterative** experience rather than a one-shot job: add or
curate a few examples → run a short fine-tune from the current checkpoint → inspect the model's outputs
→ repeat. Each iteration is **checkpoint-chained** (the next round warm-starts from the previous round's
result), producing a visible lineage of how the model was taught. This composes existing pieces —
warm-start (039), dataset preparation (053), inference (045), and evaluation (054) — into a guided loop,
realizing the project's "teach it" pedagogical goal (FT-AD-10).

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-036 (+ spec-local FR-001..FR-003) |
| **Owned decisions** | FT-AD-10 (pedagogy-first); reuses FT-AD-1 (warm-start) |
| **Depends on** | 039 (warm-start lineage), 053 (dataset prep), 045 (inference), 054 (compare); existing training/SSE pipeline |
| **Invariant risk** | **LOW** — orchestration over existing capabilities; pretraining and base install untouched |

---

## User Story

### US — Learner Teaches a Model Iteratively (Priority: P1)

A learner runs a short fine-tune, inspects the outputs, adds a few corrective examples, and runs another
short round that builds on the previous one — repeating until satisfied, with the whole teaching history
visible.

**Independent Test**: Start a teaching session on a small base; run round 1 (a few examples, short
budget); inspect samples; add examples; run round 2 warm-started from round 1; verify round 2's lineage
chains to round 1 and the session history is visible.

**Acceptance Scenarios**:

1. **Given** a base model, **When** the learner runs a teaching round, **Then** a short fine-tune runs
   from the current checkpoint and outputs are shown for inspection.
2. **Given** a completed round, **When** the learner adds/curates examples and runs again, **Then** the
   new round warm-starts from the previous round's checkpoint (checkpoint-chained, 039).
3. **Given** a multi-round session, **When** the learner views it, **Then** the chain of rounds (examples
   added, checkpoints, outputs) is visible as a lineage.
4. **Given** any round, **When** the learner wants to compare, **Then** they can evaluate the round
   against the base or a prior round (054).

### Edge Cases

- A round diverges/worsens → the learner can roll back to a prior checkpoint in the chain (no data loss).
- Examples conflict with earlier teaching → surfaced; the loop does not silently overwrite history.
- Long sessions → checkpoint retention is bounded/configurable, consistent with registry storage norms.
- External (PEFT) base → each round produces/updates an adapter rather than full weights (045/FT-AD-7).

## Requirements

- **FR-036**: The system MUST support an iterative teaching loop — add/curate examples, run a short
  fine-tune from the current checkpoint, inspect outputs, and repeat — with each round
  **checkpoint-chained** to the previous (warm-start, 039) and the session history recorded as lineage.
- **FR-001** (spec-local): Each round MUST record its added/changed examples, resulting checkpoint, and
  outputs, forming an auditable teaching lineage.
- **FR-002** (spec-local): The learner MUST be able to roll back to a prior round's checkpoint and
  branch from it.
- **FR-003** (spec-local): The loop MUST work for both native (warm-start full model) and external
  (adapter) models, producing the appropriate artifact per round.

## Success Criteria

- **SC-001**: A learner teaches a model across ≥2 chained rounds, each building on the last, with visible
  lineage.
- **SC-002**: A worsening round can be rolled back / branched from a prior checkpoint.
- **SC-003**: The loop works for native and adapter models alike.
- **SC-004 (NMRG)**: Pre-existing tests pass unmodified; pretraining and base install unaffected.

## Key Entities

- **TeachingSession**: an ordered chain of teaching rounds over a model.
- **TeachingRound**: one iteration (examples added, checkpoint produced, outputs), chained to the prior.

## Definition of Done

- Multi-round, checkpoint-chained teaching with visible lineage, rollback/branch, and native+adapter
  support; integrates inspect (045) and compare (054); **NMRG (full)**.

## Assumptions

- Composes existing capabilities (039/053/045/054) rather than introducing a new training engine.
- The pedagogical framing/copy for the loop is reinforced by the learning arc (048); this spec owns the
  interactive workflow itself.
