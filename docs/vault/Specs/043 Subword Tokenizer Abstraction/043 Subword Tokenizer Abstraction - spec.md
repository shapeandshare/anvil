---
title: 043 Subword Tokenizer Abstraction - spec
type: spec
tags:
  - type/spec
  - domain/core
  - domain/training
status: draft
spec-refs:
  - docs/vault/Specs/043 Subword Tokenizer Abstraction/
related:
  - '[[043 Subword Tokenizer Abstraction]]'
  - '[[038 Fine-Tuning Arc]]'
  - '[[Reference/FineTuningArchitectureDecisions]]'
created: '2026-06-28'
updated: '2026-06-28'
---

# Feature Specification: Subword Tokenizer Abstraction

**Feature Branch**: `043-subword-tokenizer-abstraction`
**Created**: 2026-06-28
**Status**: Draft
**Parent Spec**: [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc (umbrella)]]

## Overview

The enabling layer for external fine-tuning: a tokenizer abstraction where a model carries its tokenizer
as a first-class artifact, and encode/decode resolves from that attached tokenizer. It holds both
anvil's character-level vocabulary (`anvil/core/vocabulary.py`, `anvil/core/tokenizer.py`) and
HuggingFace subword tokenizers. This is the single hardest assumption the external path breaks —
char-level encoding would destroy a pretrained model's learned representations — so it is isolated here
and depended on by spec 044.

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-014, FR-015, FR-031 (tokenizer serializations) |
| **Owned decisions** | FT-AD-3, FT-AD-11 (tokenizer aspect) |
| **Depends on** | `anvil/core/tokenizer.py`, `anvil/core/vocabulary.py`; `transformers`/`tokenizers` (behind `[finetune]`) for subword |
| **Invariant risk** | **MEDIUM** — touches the tokenization seam used by the existing char-level path; parity must be proven |

---

## User Story

### US — A Model Tokenizes With Its Own Tokenizer (Priority: P1)

Encode/decode for any model resolves from the tokenizer attached to that model — char-level for native
models, subword for imported HF models — with no caller assuming a fixed scheme.

**Independent Test**: Round-trip encode→decode arbitrary text through (a) the char-level tokenizer and
(b) a TinyLlama subword tokenizer via the same abstraction; verify both reproduce the input and that the
existing char-level training/inference paths are unchanged under contract tests.

**Acceptance Scenarios**:

1. **Given** a native model, **When** text is encoded/decoded, **Then** the char-level vocabulary is used
   and behavior matches today exactly.
2. **Given** an imported HF model with a subword tokenizer, **When** text is encoded/decoded, **Then** the
   model's subword tokenizer is used (not char-level).
3. **Given** any model, **When** inference or eval runs, **Then** it dispatches on the recorded tokenizer
   family without special-casing at the call site.

### Edge Cases

- Subword tokenizer files missing for an imported model → fail fast ("download assets first", links 042).
- Unknown tokenizer family → tracked but flagged not-runnable (links 049).
- Char-level vocabulary drift vs a loaded checkpoint → reject mismatched vocab rather than mis-decode.

## Requirements

- **FR-014**: Tokenization MUST be abstracted so a model carries its tokenizer as a first-class artifact;
  encode/decode MUST resolve from the attached tokenizer.
- **FR-015**: The abstraction MUST support both anvil's character-level vocabulary and HuggingFace
  subword tokenizers, and MUST record which family a given model uses for downstream inference/eval.
- **FR-014a**: The existing char-level behavior MUST be provably identical post-abstraction (contract
  tests against the pre-abstraction implementation).
- **FR-015a**: The subword tokenizer implementation MUST live behind the `[finetune]` extra and MUST NOT
  be importable in a base install.
- **FR-031**: The abstraction MUST support, in v1, HF fast tokenizers (`tokenizer.json`) and
  SentencePiece (`tokenizer.model` / `sentencepiece.model`) as used by the Llama family, and MUST record
  the serialization type on the model. Other serializations (e.g. WordPiece-only, GGUF-embedded
  tokenizers) are out of v1 scope and MUST be flagged not-runnable rather than mis-loaded.

## Success Criteria

- **SC-001**: Both tokenizer families round-trip encode/decode correctly through one abstraction.
- **SC-002**: Existing char-level training and inference are byte-for-byte unchanged (contract tests).
- **SC-003**: A model's tokenizer family and serialization type are recorded and drive inference/eval
  dispatch; `tokenizer.json` and SentencePiece both load.
- **SC-004 (NMRG)**: Pre-existing tests pass unmodified; base install imports no subword tokenizer deps.

## Key Entities

- **Tokenizer (abstraction)**: a model-attached tokenizer; char-level (native) or subword (HF).
- **TokenizerFamily**: recorded discriminator (`char` | `subword`) on a model.

## Definition of Done

- Both families round-trip; char-level parity proven by contract tests; tokenizer family recorded and
  dispatched on; **NMRG (full)**.

## Assumptions

- Spec 008's note that the char-level tokenizer is anvil's own format is extended, not replaced.
