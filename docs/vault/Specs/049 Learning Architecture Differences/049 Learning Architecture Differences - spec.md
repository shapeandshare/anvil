---
title: 049 Learning Architecture Differences - spec
type: spec
tags:
  - type/spec
  - domain/content
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
| **Owned FRs** | FR-025 (sole), FR-025a (sole), FR-026 *architecture aspect* (shared with 048 — concepts aspect), FR-032 *allow-list lesson/rationale* (shared with 041/042/043 — publish/detect aspects) |
| **Owned decisions** | FT-AD-9 (shared with 044), FT-AD-10 *architecture-differences page* (shared with 048 — concepts pages), FT-AD-11 *allow-list teaching/rationale aspect* (shared with 041/042/043 — publish/fail-closed aspects) |
| **Depends on** | Existing learning content system; conceptually pairs with 048; cross-links 041 |
| **Invariant risk** | **NONE** — content + UI only |

---

## Clarifications

### Session 2026-06-28

- Q: What page format should the architecture-differences module use? → A: Single page with expandable/collapsible sections (accordion pattern). Each architecture dimension (tokenization, attention, parameters, context, allow-list) gets its own collapsible section, keeping all content on one URL for self-paced exploration.
- Q: Where should cross-links from 041 eligibility flags land within the module? → A: Link directly to the allow-list section via anchor ID. The user's intent ("why can't I run this?") is best served by landing on the allow-list explanation, with the other accordion sections available for further exploration.

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
  - **UX**: The module MUST use a single-page layout with expandable/collapsible sections (accordion
    pattern), one per architecture dimension (tokenization, attention, parameters, context, allow-list),
    enabling self-paced exploration without page navigation.
- **FR-026 (architecture aspect — shared with 048)**: This spec MUST deliver the architecture-differences
  facet of the "each shippable capability ships with its learning content" requirement (FT-AD-10). The
  conceptual facet (what fine-tuning is, LoRA, fine-tune vs prompt vs RAG) is owned by spec 048; this spec
  owns the architecture-differences page that frames the catalog/eligibility features (041) and the external
  engine (044). Together 048 + 049 satisfy FR-026 for the pedagogy track.
- **FR-025a**: The module MUST cross-link from the catalog's not-eligible/unknown-architecture flags so
  the limitation is always one click from its explanation.
  - **UX**: Cross-links from 041 eligibility flags MUST land on the module's allow-list section via
    anchor ID, delivering the user directly to the explanation most relevant to their intent.
- **FR-032 (lesson/rationale aspect — shared with 041/042/043)**: The module MUST present and explain the
  concrete runnable **architecture allow-list** (v1: `LlamaForCausalLM`) and the accepted weight format
  (v1: `safetensors` only) — teaching *why* the boundary exists (tokenizer/weight-format/architecture
  differences) and what "track-but-not-run" means — so the allow-list **published by 041** (which owns the
  publish/surface aspect of FR-032; detection/acquisition aspects in 042/043) is paired with its rationale.
  The taught values MUST stay consistent with the single source of truth in code
  (`_ALLOWED_ARCHITECTURES` / `_ACCEPTED_FORMATS` in `anvil/services/model_import/model_import_service.py`).
  It MUST also frame GGUF as a deferred, planned type (FT-AD-11; specs 050–052) rather than an unsupported
  dead end.

## Success Criteria

- **SC-001**: The module explains architecture differences and implications without claiming exhaustive
  execution support.
- **SC-002**: It is cross-linked from the catalog eligibility flags (041). *Cross-spec dependency*: this
  module provides the anchor target (`#allow-list`, FR-025a); the **emitting** link from a `track_only`
  catalog entry is added in the 041 model-detail UI (see tasks.md T016). SC-002 is satisfied only when
  both sides land.
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
