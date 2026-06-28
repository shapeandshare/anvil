---
title: 049 Learning Architecture Differences - spec
type: spec
tags:
  - type/spec
  - domain/learning
  - domain/ui
status: draft
spec-refs:
  - docs/vault/Specs/049 Learning Architecture Differences/
related:
  - '[[049 Learning Architecture Differences]]'
  - '[[038 Fine-Tuning Arc]]'
  - '[[Reference/FineTuningArchitectureDecisions]]'
created: '2026-06-28'
updated: '2026-06-28'
---

# Feature Specification: Learning Arc — Architecture Differences

**Feature Branch**: `049-learning-architecture-differences`
**Created**: 2026-06-28
**Status**: Draft
**Parent Spec**: [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc (umbrella)]]

## Overview

Turns a scoping limitation into a teaching moment: an explorable module explaining how model
architectures differ — tokenization, attention variants, parameter scaling, context length — and what
those differences imply for fine-tuning. It explicitly frames that anvil **executes a limited
architecture set** (its char-level mini-Llama plus the curated catalog families) while teaching the
broader landscape (FT-AD-9). Cross-linked from the catalog's "not eligible / unknown architecture"
flags (041).

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-025, FR-026 (architecture aspect), FR-032 (allow-list lesson) |
| **Owned decisions** | FT-AD-9, FT-AD-10, FT-AD-11 (allow-list aspect) |
| **Depends on** | Existing learning content system; conceptually pairs with 048; cross-links 041 |
| **Invariant risk** | **NONE** — content + UI only |

---

## User Story

### US — Learner Understands How Architectures Differ (Priority: P1)

A learner explores how anvil's char-level mini-Llama compares with TinyLlama-class and larger families,
and grasps why anvil supports some but not all architectures.

**Independent Test**: Open the architecture-differences module; verify it explains tokenization,
attention/parameter/context differences and their fine-tuning implications, and explicitly states
anvil's limited execution scope without claiming exhaustive support.

**Acceptance Scenarios**:

1. **Given** the module, **When** the learner explores it, **Then** it explains tokenization, attention
   variants, parameter scaling, and context length, and what each implies for fine-tuning.
2. **Given** the scope framing, **When** the learner reads it, **Then** it is clear anvil executes a
   limited architecture set while teaching the broader landscape.
3. **Given** a catalog model flagged "not eligible / unknown architecture" (041), **When** the learner
   follows the flag, **Then** it links into this module for explanation.

### Edge Cases

- New families added to the catalog later → the module's framing accommodates additions without implying
  exhaustive coverage.
- Learner expects anvil to run any architecture → the page sets accurate expectations up front.

## Requirements

- **FR-025**: The learning arc MUST include an architecture-differences module explaining tokenization,
  attention/parameter/context differences and their fine-tuning implications, explicitly scoping that
  anvil executes a limited architecture set while teaching the broader landscape.
- **FR-026 (architecture)**: This spec provides the architecture-differences learning content paired with
  the catalog/eligibility features (041) and the external engine (044).
- **FR-025a**: The module MUST cross-link from the catalog's not-eligible/unknown-architecture flags so
  the limitation is always one click from its explanation.
- **FR-032**: The module MUST present and explain the concrete runnable **architecture allow-list** (v1:
  `LlamaForCausalLM`) and the accepted weight format (safetensors) — teaching *why* the boundary exists
  (tokenizer/weight-format/architecture differences) and what "track-but-not-run" means — so the
  published allow-list (surfaced in 041) is paired with its rationale. It MUST also frame GGUF as a
  deferred, planned type (FT-AD-11; specs 050–052) rather than an unsupported dead end.

## Success Criteria

- **SC-001**: The module explains architecture differences and implications without claiming exhaustive
  execution support.
- **SC-002**: It is cross-linked from the catalog eligibility flags (041).
- **SC-003**: It contrasts anvil's char-level mini-Llama with TinyLlama-class and larger families.
- **SC-004**: The runnable allow-list and accepted format are explained with rationale, and GGUF is
  framed as deferred/planned (not a dead end).
- **SC-005 (NMRG)**: Pre-existing tests pass unmodified; content-only change.

## Key Entities

- **LearningModule (architecture)**: explorable unit on architecture differences within the learning arc.

## Definition of Done

- Module explains differences + implications with accurate scope framing; cross-linked from 041
  eligibility flags; **NMRG (full)**.

## Assumptions

- Conceptual/decision pages (what fine-tuning is, LoRA, fine-tune vs prompt vs RAG) are owned by spec
  048; this spec owns the architecture-differences module.
