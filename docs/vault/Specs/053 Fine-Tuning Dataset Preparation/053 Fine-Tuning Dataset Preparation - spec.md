---
title: 053 Fine-Tuning Dataset Preparation - spec
type: spec
tags:
  - type/spec
  - domain/training
  - domain/content
status: draft
spec-refs:
  - docs/vault/Specs/053 Fine-Tuning Dataset Preparation/
related:
  - '[[053 Fine-Tuning Dataset Preparation]]'
  - '[[038 Fine-Tuning Arc]]'
  - '[[Reference/FineTuningArchitectureDecisions]]'
created: '2026-06-28'
updated: '2026-06-28'
---

# Feature Specification: Fine-Tuning Dataset Preparation

**Feature Branch**: `053-fine-tuning-dataset-preparation`
**Created**: 2026-06-28
**Status**: Draft
**Parent Spec**: [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc (umbrella)]]

## Overview

The missing prerequisite that makes external fine-tuning actually usable: turn raw examples into a
**properly formatted fine-tuning dataset**. Covers supervised prompt→response (SFT) pairs, applying the
base model's **chat template**, and (optionally) preference pairs — tracked through the existing dataset
governance (spec 005) so a prepared dataset is a first-class, versioned input to a fine-tune (044/047).
Without this, `FineTuneSpec`'s "a dataset" is underspecified for instruction tuning.

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-034 (+ spec-local FR-001..FR-005) |
| **Owned decisions** | reuses FT-AD-3 (tokenizer abstraction), FT-AD-5 (governance/storage); **introduces** the `ChatTemplate` concept (chat-template handling is new to this spec, not provided by 043) |
| **Depends on** | 005 (dataset curation), datasets service; 043 (tokenizer abstraction — encode/decode only; this spec adds chat-template handling on top); 040 (base model whose tokenizer is the formatting source) |
| **Invariant risk** | **LOW** — extends the dataset domain; no change to pretraining or base install |

---

## User Story

### US — Learner Prepares an Instruction Dataset (Priority: P1)

A learner turns raw examples (or an existing corpus/dataset) into prompt→response pairs formatted with
the target model's chat template, ready to fine-tune on.

**Independent Test**: Provide a handful of instruction examples; produce a prepared dataset whose records
are prompt→response pairs rendered with a TinyLlama-class chat template; verify a fine-tune (044) accepts
it unchanged.

**Acceptance Scenarios**:

1. **Given** raw instruction examples, **When** the learner prepares a dataset, **Then** records are
   structured as prompt→response (SFT) pairs and tracked via the datasets governance (005).
2. **Given** a target base model, **When** the dataset is prepared, **Then** the model's chat template is
   applied (or a clearly labeled default is used) so tokens match what the model expects.
3. **Given** a prepared dataset, **When** a fine-tune is configured (044/047), **Then** it consumes the
   dataset directly without ad-hoc reformatting.
4. **Given** preference data is desired, **When** the learner prepares it, **Then** chosen/rejected pairs
   are produced and tracked (for future preference-tuning).

### Edge Cases

- Base model has no chat template → use a clearly labeled default template and warn (do not silently
  guess).
- Malformed/empty examples → validated per existing curation rules (005); bad records are skipped
  and processing continues, with per-record errors in the job summary report.
- Mismatched template vs tokenizer family (043) → fail fast rather than mis-render.
- Very large preparation job → reuse dataset-service batching, not in-memory blowups.
- Scale: hundreds to tens of thousands of records (medium). Preparation runs as an async job with
  configurable batch sizes, matching the existing dataset-service job pattern. Synchronous preparation
  is not supported.
- Concurrent preparation of the same source dataset → the second request is rejected with a conflict
  (one active preparation per source dataset at a time). A new preparation may start once the prior job
  reaches `ready` or `failed`.
- Empty input (zero records) → job completes as `ready` with `total=0`, not `failed`; the summary makes
  the empty result explicit rather than erroring.

## Requirements

- **FR-034**: The system MUST provide preparation of fine-tuning datasets — prompt→response (SFT) pairs,
  application of the base model's chat template, and (optionally) chosen/rejected preference pairs —
  tracked through the existing dataset governance (spec 005) and consumable directly by a fine-tune
  (044/047).
- **FR-001** (spec-local): A prepared dataset MUST record which chat template / formatting was applied
  and against which base model, so the formatting is reproducible and auditable.
- **FR-002** (spec-local): Preparation MUST validate every record against its declared shape — SFT
  (`instruction`/`response` non-empty, or a well-formed `messages` array with valid roles) or
  preference (`chosen`/`rejected` non-empty) — and report failures using the existing curation
  reporting. On record-level failure, the job MUST skip the offending record and continue processing,
  producing a summary report (`total`, `succeeded`, `failed` counts) with per-record error details.
- **FR-003** (spec-local): Preparation MUST be available without heavy ML deps where possible (chat
  template rendering is text manipulation), with any tokenizer-dependent checks (e.g. token-count or
  tokenizer-family verification) behind the `[finetune]` extra; their absence MUST degrade to a
  warning, not a crash.
- **FR-004** (spec-local): The system MUST expose job status (`preparing | ready | failed`) and a
  summary report (`total`, `succeeded`, `failed` counts with per-record error details) via the
  existing job-status API, so users can monitor async preparation and inspect failures.
- **FR-005** (spec-local): The chat template applied MUST be resolved deterministically in this order:
  (a) an explicitly specified `ChatTemplate`; else (b) the base model's own template, derived from its
  attached tokenizer (per FT-AD-3); else (c) a clearly labeled built-in default template accompanied by
  a warning. The system MUST NOT silently guess a template. Which of (a)/(b)/(c) was used MUST be
  recorded on the prepared dataset (FR-001) for reproducibility.

## Success Criteria

- **SC-001**: A learner turns raw examples into a prompt→response dataset with the base model's chat
  template and fine-tunes on it unchanged.
- **SC-002**: The applied template/formatting and target model are recorded for reproducibility.
- **SC-003**: Preference (chosen/rejected) pairs can be produced and tracked.
- **SC-004 (NMRG)**: Pre-existing tests pass unmodified; base install unaffected.
- **SC-005**: A preparation job with mixed valid/invalid records completes with a summary report
  showing correct `total`/`succeeded`/`failed` counts.
- **SC-006**: When a base model has no chat template, preparation completes using a clearly labeled
  default template and surfaces a warning (never silently guesses); the resolved template choice is
  recorded on the prepared dataset.

## Data Format

### Input (raw examples)

Records supplied by the learner before chat-template rendering. Format is **JSONL** (JSON Lines), one
record per line. Record shapes:

- SFT: `{"instruction": "...", "response": "..."}` (role-based: `{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}` also accepted).
- Preference: `{"chosen": "...", "rejected": "..."}` with optional `{"context": "..."}` field.

### Output (prepared records)

Rendered records stored in the prepared dataset, with the chat template applied and formatting metadata
recorded. Each record stores the chat-template–rendered string plus the original input record for
auditability. Rendering differs by record type:

- **SFT**: the rendered string is the full prompt→response sequence as the model sees it during
  training.
- **Preference**: the shared prompt/`context` is rendered with the template once, and the `chosen` and
  `rejected` completions are each stored against that rendered prompt — yielding a downstream
  `{prompt, chosen, rejected}` triple with consistent formatting (for a future preference-tuning spec).

Format remains JSONL for compatibility with downstream fine-tuning (044/047). Processing is async via
the existing job infrastructure, with configurable batch sizes.

## Key Entities

- **FineTuneDataset**: a prepared, tracked dataset of SFT or preference records with recorded formatting.
  - Lifecycle: `preparing → ready | failed` (aligns with spec 005 dataset governance).
  - References a `ChatTemplate` (by FK) and records the `base_model_ref`.
- **ChatTemplate**: the template applied to render prompts/responses for a given base model. Stored as a
  separate entity (`chat_templates` table) with intrinsic fields: `name`, `template_string`,
  `tokenizer_family`, and `base_model_ref`. Supports future variant/versioned templates.
  - **Relationship to FT-AD-3**: the tokenizer travels with the model (FT-AD-3); the `ChatTemplate`
    entity does not replace it. The model's own template (read from its attached tokenizer) provides the
    default `ChatTemplate` — derived on first use and persisted as a labeled default, so models imported
    before this feature are also covered. Additional rows are explicit variants layered on top. This
    keeps the rendered formatting traceable to the model and avoids silent drift from the model's true
    template.

## Definition of Done

- Raw examples → tracked SFT dataset with chat template applied and recorded; preference pairs
  supported; consumable by 044/047 unchanged; **NMRG (full)**.

## Assumptions

- Raw-corpus curation (005) handles ingestion/cleaning; this spec adds the fine-tuning-specific
  formatting layer on top.
- Preference *tuning* (DPO-style training) is out of scope here; this spec only prepares preference data
  for a future training spec.

## Clarifications

### Session 2026-06-28

- Q: What state lifecycle should a FineTuneDataset go through? → A: `preparing → ready | failed` (matching existing spec 005 governance, simplicity-first).
- Q: How should ChatTemplate metadata be stored relative to FineTuneDataset? → A: Separate `ChatTemplate` entity (`chat_templates` table) with FK reference from FineTuneDataset, to support future template variants/versioning.
- Q: What format should raw instruction examples use as input? → A: JSONL, with SFT records (`instruction`/`response` or `messages` array) and preference records (`chosen`/`rejected`).
- Q: What scale of datasets should preparation handle? → A: Medium (hundreds to tens of thousands of records), async job with configurable batch sizes, matching the existing dataset-service job pattern.
- Q: How should record-level failures be handled? → A: Skip-and-continue with summary report (`total`/`succeeded`/`failed` counts and per-record error details).
