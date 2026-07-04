---
title: 065 Adapter Catalog Entries - Spec
type: spec
tags:
  - type/spec
created: 2026-07-03
updated: 2026-07-03
---

# Feature Specification: Adapters as First-Class Catalog Entries

**Feature Branch**: *(not yet started — backlog follow-up to Spec 064)*
**Created**: 2026-07-03
**Status**: Draft (deferred; depends on Spec 064)
**Input**: User description: "Promote LoRA fine-tune adapters to first-class entries in the unified model catalog (kind=adapter), so they appear in model listings and pickers and are directly selectable for inference and evaluation — deferred from Spec 064 Clarification Q2."

## Overview

Spec 064 unifies all *models* (trained, external, merged) in a single
catalog, but keeps fine-tune adapters as attached records visible only
on their base model's detail page. This follow-up promotes adapters to
first-class catalog entries so users can discover, select, and act on a
fine-tuned adapter the same way they act on any model — without first
navigating to its base model. The `adapter` kind is already reserved in
the catalog's kind vocabulary (ADR-047), so no catalog schema change is
required.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Adapters appear in the catalog (Priority: P1)

A user fine-tunes an imported base model, producing an adapter. The
adapter appears in the Models page listing and in the inference and
evaluation pickers as its own entry, labeled kind=adapter and showing
its base-model lineage — selectable exactly like any other model.

**Why this priority**: Discoverability is the point of the feature —
today a user must remember which base model an adapter belongs to and
navigate there first.

**Independent Test**: Fine-tune a base model, then verify the adapter
appears in the Models listing and inference picker with kind=adapter
and a resolvable base-model reference.

**Acceptance Scenarios**:

1. **Given** a completed fine-tune run producing an adapter, **When**
   the user opens the Models page, **Then** the adapter appears as a
   catalog entry with kind=adapter, its own identity, and a visible
   link to its base model.
2. **Given** the same instance, **When** the user opens the inference
   picker, **Then** the adapter is listed and selecting it runs
   generation with the adapter composed on its base model — without the
   user separately selecting the base.
3. **Given** an adapter catalog entry, **When** its base model's assets
   are unavailable, **Then** the adapter's runnable/availability state
   reflects that (an adapter is only runnable when its base is).

---

### User Story 2 - Adapter lineage and evaluation flow through the catalog (Priority: P2)

A user evaluates an adapter against its base model by selecting the
adapter directly from a picker. The evaluation record references the
adapter's catalog identity, and lineage queries ("all adapters of base
X", "base model of adapter Y") resolve through catalog metadata alone.

**Why this priority**: Builds on Story 1's entries to remove the
adapter-specific special-casing in eval flows.

**Independent Test**: Start an evaluation by selecting an adapter
entry; verify the eval record references the adapter's catalog
identity and the comparison base is inferred from lineage.

**Acceptance Scenarios**:

1. **Given** an adapter catalog entry, **When** the user starts an
   evaluation from it, **Then** the base model is pre-resolved from the
   adapter's lineage metadata and the eval record references both by
   catalog identity.
2. **Given** a base model with multiple adapters, **When** the user
   filters the catalog by lineage to that base, **Then** all its
   adapters are returned.

---

### User Story 3 - Adapter lifecycle matches catalog semantics (Priority: P3)

Deleting an adapter archives its catalog entry (append-only, no
renames), removes its local adapter files, and leaves evaluation
history resolvable. Merging an adapter continues to produce a `merged`
catalog entry linked to both the adapter and the base.

**Independent Test**: Delete an adapter with eval history; verify
archive semantics. Merge an adapter; verify the merged entry links to
adapter + base lineage.

**Acceptance Scenarios**:

1. **Given** an adapter with evaluation history, **When** it is
   deleted, **Then** its entry is archived, local adapter files are
   removed, and eval records still resolve.
2. **Given** an adapter, **When** it is merged into its base, **Then**
   the resulting `merged` catalog entry carries lineage references to
   both the adapter entry and the base entry.

---

### Edge Cases

- What happens when an adapter's base model is archived? The adapter
  remains listed but is marked not runnable, with the reason surfaced.
- What happens to adapter entries when a fine-tune run fails? No
  catalog entry is created; only completed adapters are registered.
- What happens if the catalog backend is down when a fine-tune
  completes? Same fail-closed contract as Spec 064 imports: the run's
  registration step fails retryably; no orphaned entry.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Completed fine-tune adapters MUST be registered as
  catalog entries with kind=adapter, carrying lineage metadata that
  resolves their base model's catalog identity.
- **FR-002**: All model-listing surfaces MUST include adapter entries,
  visually distinguished by kind, with base-model lineage displayed.
- **FR-003**: Selecting an adapter for inference or evaluation MUST
  resolve and compose its base model automatically; users MUST NOT
  need to select the base separately.
- **FR-004**: An adapter entry's runnable/availability state MUST be
  derived from both its own assets and its base model's availability.
- **FR-005**: Adapter registration MUST follow Spec 064's atomicity
  contract: the producing run reports success only after the catalog
  entry exists; failures are retryable with no orphaned state.
- **FR-006**: Adapter deletion MUST follow Spec 064's archive
  semantics (append-only, no renames, dependent records resolve).
- **FR-007**: Merge operations MUST link the resulting merged entry to
  both the adapter entry and base entry via lineage metadata.

### Key Entities

- **Adapter Catalog Entry**: A catalog entry (kind=adapter) whose
  versioning follows its producing runs; carries lineage (base
  ModelRef), fine-tune parameters summary, and availability state.
- **Lineage Reference**: Catalog metadata resolving adapter → base and
  merged → (adapter, base) relationships.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of completed adapters appear in every model-listing
  surface with kind=adapter and resolvable base lineage.
- **SC-002**: A user can go from a completed fine-tune to generating
  text with the adapter using only picker selection (zero manual
  base-model navigation steps).
- **SC-003**: Lineage queries (adapters-of-base, base-of-adapter)
  resolve via catalog metadata alone in 100% of test scenarios.
- **SC-004**: Deleting an adapter never breaks referencing records
  (100% of eval references resolve post-archive).

## Assumptions

- Spec 064 (unified MLflow model catalog, ModelRef references,
  archive semantics, fail-closed contract) is fully implemented; this
  feature builds directly on its catalog service and reserved
  `adapter` kind — no catalog schema change is needed.
- The adapter files themselves remain in local/asset storage; the
  catalog stores metadata and lineage only.
- Adapter records retained in the operational database by Spec 064
  continue to exist for workflow state; this feature adds the catalog
  projection, it does not move per-run training state into the catalog.

## See Also

- [[Specs/064 MLflow Model Catalog/spec|Spec 064]] — prerequisite: unified model catalog (this spec was deferred from its Clarification Q2)
- [[Decisions/ADR-047-mlflow-model-catalog-source-of-truth|ADR-047]] — catalog architecture decision (reserves the `adapter` kind)
