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
| **Owned FRs** | FR-034 (+ spec-local FR-001..FR-003) |
| **Owned decisions** | reuses FT-AD-3 (tokenizer/chat template), FT-AD-5 (governance/storage) |
| **Depends on** | 005 (dataset curation), datasets service; 043 (tokenizer/chat template); 040 (base model whose template is applied) |
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
- Malformed/empty examples → validated and reported per the existing curation rules (005).
- Mismatched template vs tokenizer family (043) → fail fast rather than mis-render.
- Very large preparation job → reuse dataset-service batching, not in-memory blowups.

## Requirements

- **FR-034**: The system MUST provide preparation of fine-tuning datasets — prompt→response (SFT) pairs,
  application of the base model's chat template, and (optionally) chosen/rejected preference pairs —
  tracked through the existing dataset governance (spec 005) and consumable directly by a fine-tune
  (044/047).
- **FR-001** (spec-local): A prepared dataset MUST record which chat template / formatting was applied
  and against which base model, so the formatting is reproducible and auditable.
- **FR-002** (spec-local): Preparation MUST validate records (non-empty prompt and response, role
  structure) and report failures using the existing curation reporting.
- **FR-003** (spec-local): Preparation MUST be available without heavy ML deps where possible (template
  rendering is text), with any tokenizer-dependent checks behind the `[finetune]` extra.

## Success Criteria

- **SC-001**: A learner turns raw examples into a prompt→response dataset with the base model's chat
  template and fine-tunes on it unchanged.
- **SC-002**: The applied template/formatting and target model are recorded for reproducibility.
- **SC-003**: Preference (chosen/rejected) pairs can be produced and tracked.
- **SC-004 (NMRG)**: Pre-existing tests pass unmodified; base install unaffected.

## Key Entities

- **FineTuneDataset**: a prepared, tracked dataset of SFT or preference records with recorded formatting.
- **ChatTemplate**: the template applied to render prompts/responses for a given base model.

## Definition of Done

- Raw examples → tracked SFT dataset with chat template applied and recorded; preference pairs
  supported; consumable by 044/047 unchanged; **NMRG (full)**.

## Assumptions

- Raw-corpus curation (005) handles ingestion/cleaning; this spec adds the fine-tuning-specific
  formatting layer on top.
- Preference *tuning* (DPO-style training) is out of scope here; this spec only prepares preference data
  for a future training spec.
