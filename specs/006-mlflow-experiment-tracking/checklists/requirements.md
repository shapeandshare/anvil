# Specification Quality Checklist: MLflow Experiment & Data Lifecycle Tracking

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-06-13
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- The source request was a deeply technical, implementation-oriented MLflow integration brief
  (specific API signatures, module paths, `mlflow.*` calls). The spec deliberately translates
  this into technology-agnostic, user-facing requirements: the WHAT/WHY of provenance, consistent
  tracking destination, metrics, lifecycle integrity, and capability-gated evaluation sets — while
  the HOW (MLflow API surface) is reserved for the planning phase.
- Codebase verification resolved the request's stated "highest-value question": the corpus is
  training/source data, so it is modeled as per-run lineage (documented as an Assumption), avoiding
  a [NEEDS CLARIFICATION] marker.
- Codebase verification also corrected a key premise in the source request: the trainer is
  stdlib/custom, not HuggingFace/Transformers — so transformer-flavor autologging requirements were
  intentionally excluded and replaced with a custom-artifact guardrail (FR-025).
- All items pass. Spec is ready for `/speckit.clarify` (optional) or `/speckit.plan`.

### Post-review codebase-fact corrections (2026-06-13)

A critical review verified the spec's factual premises against the actual codebase and the two external libraries it depends on. Corrections applied:

- **Registry dual-write claim corrected** (spec Context + rebase note): MLflow auto-registers on **every** completed run (`anvil-experiment-{id}`); the **local** registry is written **only** via the manual `POST /v1/registry/models` endpoint — they are NOT both written on every run. The dual-system contradiction is **latent**, not unconditional. Consolidation work (FR-019/027) is unchanged.
- **MPS utilization mechanism corrected** (research R9, data-model B5, plan, tasks T043/T044): `psutil`/`torch.mps` cannot provide GPU utilization (torch.mps is memory-only); utilization comes from `ioreg`/IOKit `AGXAccelerator → PerformanceStatistics` (no `sudo`, no new dep). `powermetrics` rejected (requires `sudo`).
- **`mlflow.genai` managed datasets confirmed** available on self-hosted **SQLite/SQL-backed** OSS MLflow 3.x (NOT Databricks-only; NOT FileStore-compatible) — validating US6 as first-class and reinforcing R2's HTTP-server-over-SQLite destination.
- **Orphan-reconciliation liveness wording corrected** (FR-028): no PID/heartbeat tracking exists; single-process assumption made explicit; multi-instance concurrency out of scope.
- **Dependency-resolution pre-check added** (task T002a) for the `mlflow>=3.1,<4` bump against `pydantic<3`/`torch`/`alembic`.
- **Stale "error clearly" goal corrected** (tasks Phase 4) to graceful degradation per Article IX / FR-009.
