---
title: 064 MLflow Model Catalog - Spec
type: spec
tags:
  - type/spec
created: 2026-07-03
updated: 2026-07-03
---

# Feature Specification: Unified MLflow Model Catalog

**Feature Branch**: `062-mlflow-model-catalog`
**Created**: 2026-07-03
**Status**: Draft
**Input**: User description: "Unified model catalog: MLflow Model Registry as the source of truth for all models (trained, external/imported, merged), per ADR-048. Greenfield — no legacy support, no data migration, no transitional states."

## Clarifications

### Session 2026-07-03

- Q: Does a different revision of the same source become a new version under the same catalog name, or a separate catalog entry? → A: Same catalog name, new version — one logical model per (source type + identifier); each imported revision is a version; `ModelRef` pins the exact version.
- Q: Should LoRA adapters become first-class catalog entries in this feature, or remain attached records under their base model? → A: Attached records for this feature; promoting adapters to first-class catalog entries is deferred to the follow-up spec ([[Specs/065 Adapter Catalog Entries/spec|Spec 065]]). The `adapter` kind remains reserved (per ADR-048) so the follow-up requires no schema change.
- Q: How is a catalog entry's unique name derived? → A: Provider-prefixed deterministic name derived from (source type + sanitized source identifier) — e.g. `hf--TinyLlama--TinyLlama-1.1B-Chat-v1.0`; trained models keep their existing dataset/corpus-derived names; display name is a separate mutable label, never identity.
- Q: What is the expected catalog scale and acceptable listing latency? → A: Catalog listings of up to 100 logical models render within 2 seconds on a local instance.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every model appears in one catalog (Priority: P1)

A user imports a model from HuggingFace and also trains a model from scratch. When they open any model-selection surface — the Models page, the inference playground picker, or the evaluation pickers — both models appear in the same list with consistent information (name, kind, architecture, status), and the user can act on either one (view, play, evaluate) without knowing or caring how it entered the system.

**Why this priority**: This is the defect that motivated the work — imported models are invisible in the inference picker today because two disconnected catalogs exist. A single catalog structurally eliminates the entire class of "model missing from surface X" bugs and is the foundation every other story builds on.

**Independent Test**: Import one external model and train one model; verify both appear in the Models page listing and the inference page picker with correct kind labels, and that selecting either loads it for its supported actions.

**Acceptance Scenarios**:

1. **Given** a fresh instance with one trained model and one fully-downloaded imported model, **When** the user opens the Models page, **Then** both models appear in a single list, each labeled with its kind (trained / external / merged).
2. **Given** the same instance, **When** the user opens the inference playground, **Then** the model picker lists both models, and selecting the runnable imported model enables generation.
3. **Given** a model listing request, **When** the catalog contains models of all kinds, **Then** each entry exposes the same core fields (identity, version, kind, architecture family, tokenizer family, license, runnable status) regardless of origin.

---

### User Story 2 - Import registers the model in the catalog (Priority: P1)

A user imports a model from HuggingFace (or a local path). When the import completes, the model exists as a catalog entry carrying its provenance (source, identifier, revision), architecture metadata, license, and runnability — and it is immediately visible everywhere models are listed. If the catalog cannot be written to, the import does not silently half-complete: it fails with a clear, retryable error.

**Why this priority**: Import is the entry point for external models; if registration is not atomic with import completion, the split-catalog problem reappears. Tied for P1 because Story 1 depends on imported models actually reaching the catalog.

**Independent Test**: Run an import end-to-end and verify the catalog entry exists with full provenance metadata; kill the catalog backend and verify the import fails closed with a retryable job state.

**Acceptance Scenarios**:

1. **Given** a valid import request, **When** the import job completes, **Then** a catalog entry exists tagged with kind=external, source type, source identifier, source revision, architecture family, tokenizer family, license, and runnable status.
2. **Given** the catalog backend is unavailable, **When** an import is attempted, **Then** the import job ends in a failed, retryable state and no partial catalog entry or orphaned local state remains.
3. **Given** a completed import, **When** the user retries the same import (same source, identifier, and revision), **Then** the system reports the existing entry and creates no duplicate.
4. **Given** two concurrent imports of the same source/identifier/revision triple, **When** both jobs run, **Then** exactly one catalog entry results.

---

### User Story 3 - Downstream records follow the model reference (Priority: P2)

A user fine-tunes an imported model (producing an adapter) and evaluates the fine-tuned result against the base model. The adapter records, per-file asset records, download jobs, and evaluation history all reference the model through its catalog identity — so lineage queries ("which adapters exist for this base model?", "what evals compared these two models?") resolve correctly, and these references remain meaningful if the catalog is hosted remotely later.

**Why this priority**: The relational workflow state (adapters, assets, evals) is where the old local-ID coupling lived. It depends on Stories 1–2 existing but is required before the old model table can be removed.

**Independent Test**: Fine-tune an imported model, run an evaluation, then list adapters and eval runs for that model via its catalog reference and verify all records resolve.

**Acceptance Scenarios**:

1. **Given** a fine-tuned adapter for an imported base model, **When** the user views the base model's detail page, **Then** the adapter is listed via the model's catalog reference.
2. **Given** an evaluation run comparing a fine-tuned model to its base, **When** the run record is inspected, **Then** both models are referenced by catalog identity (name + version), not by a local numeric ID.
3. **Given** asset download records for an imported model, **When** the model's assets are listed, **Then** per-file state (availability, integrity hash, size) resolves via the model's catalog reference.

---

### User Story 4 - Delete archives, never destroys (Priority: P3)

A user removes a model they no longer need. The model disappears from active listings and its local weight files are cleaned up, but the catalog entry is archived — preserving lineage for any adapters, evaluations, or history that referenced it. Nothing that referenced the model breaks.

**Why this priority**: Correct delete semantics matter for long-term integrity but are exercised far less often than list/import/use flows.

**Independent Test**: Delete an imported model that has an adapter and an eval run; verify it leaves active listings, local assets are removed, and the adapter/eval records still resolve their model references.

**Acceptance Scenarios**:

1. **Given** an imported model with downloaded assets, **When** the user deletes it, **Then** it no longer appears in active model listings and its local asset files are removed.
2. **Given** a deleted model that an evaluation run referenced, **When** the eval run is viewed, **Then** the model reference still resolves (shown as archived), and the eval history remains intact.
3. **Given** any model, **When** deletion is requested, **Then** the catalog entry is archived rather than destroyed, and no renaming of catalog identities ever occurs.

---

### Edge Cases

- What happens when the catalog backend goes down *after* models exist? Listing, import, and model selection fail closed with a clear "catalog unavailable" state; features that do not depend on the catalog (training on datasets, operations, learning content) continue working.
- What happens when an import's metadata resolution succeeds but asset download later fails? The catalog entry exists (metadata-only availability state); the download job is retryable; the entry's availability state reflects reality.
- What happens when two different providers supply a model with the same identifier or display name? Catalog names are provider-prefixed and derived deterministically from (source type + sanitized source identifier), so entries never collide across providers; display names may repeat but identities are unique.
- What happens when a model's provider revision cannot be determined? Import fails with a clear error identifying the missing provenance field (identity requires source type + identifier + revision).
- What happens to in-flight download jobs when their model is deleted? Jobs are cancelled/failed cleanly and their per-file records are removed with the model's operational state.
- What happens when the catalog contains an entry whose local assets were manually removed from disk? The availability state is correctable via re-download; listing does not crash; the play action is gated by actual availability.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST maintain a single model catalog that is the authoritative record of every model's identity, version, kind (trained, external, merged), and descriptive metadata — regardless of how the model entered the system.
- **FR-002**: All model-listing surfaces (Models page, inference picker, evaluation pickers, and their APIs) MUST read exclusively from the single catalog; no surface may query a secondary model store.
- **FR-003**: Every catalog entry MUST carry searchable provenance and capability metadata: kind, source type, source identifier, source revision, architecture family, tokenizer family, license, and runnable status. Bulky configuration payloads MUST be stored alongside the entry as retrievable documents, not as searchable fields.
- **FR-004**: Completing a model import MUST atomically include catalog registration: an import job may only report success after the catalog entry exists; if registration fails, the job MUST end in a failed, retryable state with no orphaned partial state.
- **FR-005**: The system MUST prevent duplicate catalog versions for the same (source type, source identifier, source revision) identity triple, including under concurrent import attempts. A re-import of the same (source type, source identifier) at a *different* revision MUST create a new version under the same catalog name, never a new catalog entry. The duplicate guard MUST be transactional and MUST NOT rely on catalog search as a lock.
- **FR-006**: All operational and relational records (import jobs, download jobs, per-file asset records, fine-tune adapter records, evaluation records) MUST reference models by catalog identity (name + version), and MUST NOT use a workspace-local model table identifier.
- **FR-007**: The system MUST NOT contain the legacy external-model table, its data-access layer, or any endpoint that lists models from it. A single unified listing replaces the dual-track endpoints.
- **FR-008**: Catalog entries MUST be append-only: deletion archives the entry (removing it from active listings and cleaning up local assets) and identity renames MUST NOT occur. Records referencing an archived model MUST continue to resolve.
- **FR-009**: When the catalog backend is unavailable, catalog-dependent features (listing, import, model selection) MUST fail closed with a clear unavailability signal, while features that do not depend on the catalog remain functional.
- **FR-010**: Model import MUST remain provider-neutral: adding a new import provider MUST NOT require changes to the catalog schema or listing surfaces.
- **FR-011**: The inference loading path MUST resolve any runnable catalog entry — trained, external, or merged — routing on the entry's kind, so that a model listed as runnable is actually loadable from its listed surface.
- **FR-012**: Model asset availability (metadata-only, pending, available) MUST be reflected on the catalog entry and MUST gate availability-dependent actions (e.g., play) on every surface consistently.
- **FR-013**: Catalog names for imported models MUST be derived deterministically from (source type + sanitized source identifier) with a provider prefix, requiring no user input at import time. Display names are mutable labels stored as metadata and MUST NOT serve as identity.

### Key Entities

- **Catalog Entry**: The authoritative record of a logical model — one entry per (source type + source identifier) for external models, with the unique name derived deterministically as provider prefix + sanitized identifier, carrying one or more **versions** (one per imported source revision). Each version records kind (trained / external / merged), provenance (source type, identifier, revision), capability metadata (architecture family, tokenizer family, license, runnable status), availability state, and lifecycle state (active / archived). Lives in the catalog; never renamed or hard-deleted.
- **Model Reference (ModelRef)**: The canonical way any other record points at a model — the pair (catalog name, version). Replaces workspace-local numeric model IDs everywhere.
- **Import Job**: Operational record of a model import — provider, identity triple, state machine (queued → resolving → complete/failed), and the transactional duplicate guard. References its resulting Catalog Entry by ModelRef on success.
- **Download Job / Asset Record**: Operational records of weight/config/tokenizer downloads — per-file integrity (hash, size), progress, and availability state — keyed by ModelRef.
- **Adapter Record**: A fine-tune product (e.g., LoRA adapter) tied to its base model by ModelRef, with training parameters and merge state.
- **Evaluation Record**: A comparison run referencing the evaluated model and base model by ModelRef, with metric deltas and sample outputs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of models present in the system (imported, trained, or merged) appear in every model-listing surface; zero surfaces show a partial catalog.
- **SC-002**: A user can import a model and, upon import completion, find and select it in the inference picker without any intermediate manual step.
- **SC-003**: Repeating an identical import (same source, identifier, revision) — sequentially or concurrently — never yields more than one catalog entry (0 duplicates across the test suite's concurrency scenarios).
- **SC-004**: After deleting a model that has dependent records (adapters, evaluations), 100% of those records still resolve their model references, and the deleted model appears in no active listing.
- **SC-005**: When the catalog backend is stopped, catalog-dependent pages show an explicit unavailability state within one page load, and at least the training, operations, and learning surfaces remain fully functional.
- **SC-006**: The codebase contains zero references to the legacy external-model table or its identifiers (verifiable by static search), and the retired dual-track listing endpoint returns no route.
- **SC-007**: Adding a hypothetical new import provider requires zero changes to listing surfaces or catalog schema (verified by the provider abstraction's contract tests).
- **SC-008**: A catalog listing of up to 100 logical models renders within 2 seconds on a local instance (measured on a 2023+ MacBook Pro M2 or equivalent Linux workstation), on every model-listing surface.

## Assumptions

- All instances are new after this change: no existing deployment's data needs migrating, no dual-write or transitional compatibility layer is built, and the legacy external-model storage is removed outright (per ADR-032 and explicit stakeholder direction).
- The catalog backend ships with the product as a supervised sidecar locally and is expected to be a managed, highly-available service in the SaaS deployment; therefore "catalog unavailable" is an acceptable hard-failure mode for catalog-dependent features (per ADR-048).
- The existing provider abstraction (HuggingFace, local path) is retained as-is; provider expansion is out of scope for this feature beyond preserving the abstraction's neutrality.
- Adapters do not appear in the catalog or model pickers in this feature: they remain attached records under their base model (base model detail page, adapter-aware inference/eval options). Only *merged* adapter results enter the catalog, as `merged` models. First-class adapter catalog entries are specified separately in Spec 065.
- Weight/asset files remain on the existing local file storage (LakeFS in SaaS per specs 042/047); the catalog stores metadata and references, not weights.
- The transactional duplicate guard remains in the application's local database, which is retained for operational workflow state (jobs, per-file assets, adapters, evals).
- No new runtime dependencies are introduced; the existing catalog client library already in the product is sufficient.
- Archived catalog entries remain queryable for lineage indefinitely; storage cost of archived metadata is negligible.
- Expected scale is a single-user local workbench: typically dozens of logical models, with 100 as the tested ceiling (see SC-008); the catalog is not expected to serve multi-tenant-scale listings in this feature.

## See Also

- [[Decisions/ADR-048-mlflow-model-catalog-source-of-truth|ADR-048]] — the architecture decision this spec implements
- [[Decisions/ADR-016-mlflow-primary-lineage|ADR-016]] — precedent: MLflow as source of truth for experiments/trained models
- [[Decisions/ADR-032-greenfield-legacy-removal|ADR-032]] — greenfield mandate (no migration)
- [[Specs/063 Usable External Models/spec|Spec 063]] — external model local loading (layout this spec builds on)
- [[Specs/065 Adapter Catalog Entries/spec|Spec 065]] — follow-up: adapters as first-class catalog entries
