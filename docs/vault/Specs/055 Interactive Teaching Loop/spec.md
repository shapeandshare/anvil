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
| **Route** | `/v1/teach` — dedicated teaching page with session list/management and active round workflow |
| **Owned FRs** | FR-036 (+ spec-local FR-001..FR-004) |
| **Owned decisions** | FT-AD-10 (pedagogy-first); composes via MLflow tags; reuses FT-AD-1 (warm-start) |
| **Depends on** | 039 (warm-start lineage), 053 (dataset prep), 045 (inference); existing training/SSE pipeline. Requires extracting the training lifecycle into a reusable `TrainingRunService` (see plan.md). |
| **Invariant risk** | **MEDIUM** — the `TrainingRunService` extraction refactors the `/training/start` route; existing behavior must be preserved byte-for-byte (route-parity test). Pretraining and base install untouched. |
| **MVP scope** | Native (full-model) iterative teaching: session mgmt, chained rounds, inspect, rollback/branch. "Compare" = side-by-side inference between rounds. |
| **Deferred (post-MVP)** | Formal evaluation via 054 (needs `ExternalModel.id`; teaching models have only experiment id); LoRA/adapter rounds (no persisted loadable artifact + no auto-registered adapter DB row); imported HF/local model as round-1 seed (no experiment artifact to warm-start). See plan.md Complexity Tracking. |

---

## Clarifications

### Session 2026-07-02

- Q: Where does the teaching loop UI live? → A: Dedicated teaching page at `/v1/teach` — standalone route, sidebar entry, full teaching session UI.
- Q: What is explicitly out of scope for v1? → A: Nothing — full v1 scope includes session management, export/import, sharing, and templates.
- Q: TeachingSession data model — new DB entities or composed from existing? → A: Lightweight hybrid — minimal TeachingSession table; TeachingRound = tagged MLflow run with all artifacts as native entities (training run, dataset, inference outputs).
- Q: Can a learner have multiple concurrent teaching sessions? → A: Yes — session list/selector UI; work in one at a time.
- Q: TeachingSession lifecycle states? → A: Draft → Active → Completed (Draft: base model selected, no rounds; Active: rounds in progress; Completed: learner marked done).

### Session 2026-07-02 (Analysis Remediation)

- Q: [F2] What does "surfaced" mean for example conflicts? → A: Warning badge on conflicting round; learner must acknowledge before proceeding.
- Q: [F3] What is the default checkpoint retention? → A: Keep last 10 checkpoints per session; older archived on completion.
- Q: [F5] What is the rollback mechanism? → A: New round warm-starting from target round's experiment id — append, not replace.

### Session 2026-07-02 (Critical Architecture Review — Oracle-guided)

- Q: How does a teaching round produce a loadable model, given the persistence logic lives in the `/training/start` route closure? → A: Extract the training lifecycle into a reusable `TrainingRunService` (new FR-005); both the route and teaching consume it. Route parity test guarantees NMRG.
- Q: What ID does TeachingSession chain on — experiment id or `ExternalModel.id`? → A: Native integer experiment id (the one warm-start + inference agree on). Session stores `current_base_experiment_id`. No `ExternalModel` FK.
- Q: Can "compare" use formal evaluation (054)? → A: No — 054 needs `ExternalModel.id` which teaching models lack. MVP "compare" = side-by-side inference between two experiment ids. Formal eval deferred.
- Q: [supersedes F8] Are adapter/PEFT teaching rounds in MVP? → A: Deferred. Adapter runs don't persist a loadable `experiment_{id}.json` and don't auto-create a LoRAAdapter DB row. Native full-model only for MVP.
- Q: Is an imported HF/local model a valid round-1 base? → A: Deferred — an imported ExternalModel has no experiment artifact to warm-start from. MVP round 1 = train from scratch or seed from an existing experiment id.

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
4. **Given** any two rounds (or a round and the seed), **When** the learner wants to compare, **Then**
   they can view side-by-side inference outputs for the same prompts from each round's model (MVP). Formal
   metric-based evaluation (054) is deferred post-MVP.

> **Note (scope)**: MVP teaching operates on native full-model checkpoints (the artifact at
> `data/models/experiment_{id}.json`). External (PEFT/adapter) bases and formal evaluation are deferred —
> see the Scope table's "Deferred" row and plan.md Complexity Tracking. The former acceptance scenario 5
> (adapter artifact per round) is deferred to a future spec/iteration.

### Edge Cases

- A round diverges/worsens → the learner can roll back to a prior checkpoint in the chain (no data loss).
- Examples conflict with earlier teaching → a warning badge is shown on the conflicting round; the learner must acknowledge before proceeding. The loop does not silently overwrite history.
- Long sessions → checkpoint retention is bounded/configurable, consistent with registry storage norms. Default: keep the last 10 checkpoints per session; older checkpoints are archived after session completion.
- External (PEFT) base → each round produces/updates an adapter rather than full weights (045/FT-AD-7). **Deferred post-MVP** — see Scope table; requires adapter checkpoint persistence + adapter DB auto-registration that the current training pipeline does not provide.
- Starting a round when the `current_base_experiment_id` artifact is missing → the round is rejected with a clear error before training starts (validated via `InferenceService.load_model`).

## Requirements

- **FR-036**: The system MUST support an iterative teaching loop — add/curate examples, run a short
  fine-tune from the current checkpoint, inspect outputs, and repeat — with each round
  **checkpoint-chained** to the previous (warm-start, 039) and the session history recorded as lineage.
- **FR-001** (spec-local): Each round MUST record its added/changed examples, resulting checkpoint, and
  outputs, forming an auditable teaching lineage.
- **FR-002** (spec-local): The learner MUST be able to roll back to a prior round and branch from it.
  Rollback creates a **new** round that warm-starts from the target round's experiment id — the prior
  round and its lineage remain visible (append, not replace). The session's `current_base_experiment_id`
  updates to the new round's model only after its training finalizes.
- **FR-003** (spec-local): The loop MUST work for native (full-model warm-start) models in MVP,
  producing a loadable checkpoint per round. External (adapter/PEFT) model support is **deferred
  post-MVP** (see Scope table).
- **FR-004** (spec-local): The system MUST provide a dedicated teaching page at the route `/v1/teach`
  with a sidebar entry, presenting the teaching session workflow separate from one-shot training.
- **FR-005** (spec-local): The training lifecycle (validation → MLflow setup → run → model-artifact
  persistence at `data/models/experiment_{id}.json` → registration) MUST be exposed as a reusable
  service (`TrainingRunService`) consumed by BOTH the existing `/training/start` route and the teaching
  flow. The existing route's observable behavior MUST be preserved (NMRG, verified by a parity test).

## Success Criteria

- **SC-001**: A learner teaches a native model across ≥2 chained rounds, each warm-starting from the
  previous round's experiment id, with visible lineage.
- **SC-002**: A worsening round can be rolled back / branched from a prior round's checkpoint.
- **SC-003**: The loop works for native full-model checkpoints (MVP). Adapter support deferred.
- **SC-004 (NMRG)**: Pre-existing tests pass unmodified; the `/training/start` route behaves identically
  after the `TrainingRunService` extraction (parity test); pretraining and base install unaffected.

## Key Entities

- **TeachingSession**: lightweight DB table (id, name, description, `seed_experiment_id`, `current_base_experiment_id` [chain head], status: Draft→Active→Completed, created_at, updated_at) — container for an ordered chain of teaching rounds. Holds the current base experiment id the next round warm-starts from. **No `ExternalModel` FK** — chains on the native experiment id.
- **TeachingRound**: an MLflow run (created via `TrainingRunService`) tagged with `teaching_session_id`, `teaching_round_index`, and `teaching_parent_experiment_id` — one iteration (dataset curated via 053, warm-start train via 039, outputs via 045). The round is a first-class MLflow entity + persisted checkpoint, independently visible in training/inference pages.

## Definition of Done

- Multi-round, checkpoint-chained **native** teaching with visible lineage, rollback/branch; integrates
  inspect (045); "compare" = side-by-side inference between rounds; training lifecycle extracted into a
  reusable `TrainingRunService` with route parity; **NMRG (full)**. Adapter support and formal
  evaluation (054) are explicitly deferred (see Scope).

## Assumptions

- Composes existing capabilities (039/053/045) rather than introducing a new training engine. Requires a
  refactor (`TrainingRunService`) to make the training lifecycle reusable — this is the enabling change,
  not a new engine.
- Teaching chains on the native integer experiment id — the identifier warm-start and inference already
  agree on. No `ExternalModel` registration bridge is built in MVP.
- The pedagogical framing/copy for the loop is reinforced by the learning arc (048); this spec owns the
  interactive workflow itself.
