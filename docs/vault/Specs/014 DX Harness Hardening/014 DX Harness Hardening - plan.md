---
title: 014 DX Harness Hardening - plan
type: plan
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/014 DX Harness Hardening/
related:
  - '[[014 DX Harness Hardening]]'
created: ~
updated: ~
---
# Implementation Plan: Developer & Agent Experience Hardening

**Branch**: `014-dx-harness-hardening` | **Date**: 2026-06-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/docs/vault/Specs/014 DX Harness Hardening/spec.md`

## Summary

Close the gap between anvil's *declared* discipline and its *enforced* discipline. The feature has four workstreams, ordered by priority:

1. **Enforcement (P1)** — Wire the already-existing local quality gates (`make lint`, `make typecheck`, `make test` + coverage, `make vault-audit`) into an automated check that runs on every pull request and on non-main branches, blocks merge into the protected default branch on failure (fail-closed), reports the specific failing gate, and exempts only version-only bump PRs via a fast file-scope guard.
2. **Consistency & honesty (P2)** — Reconcile contradictory/aspirational governance: amend the `TYPE_CHECKING` ban to a conditional-allow rule (keep 2 ORM models, refactor `inference.py`); replace the unenforceable "100% coverage" with a ratcheting baseline; renumber the three colliding ADR numbers (008/010/016) and fix inbound links; add ADR-uniqueness + guarded-import auditing. Every amendment is recorded as a dated ADR + constitution version bump.
3. **Onboarding (P3)** — Add an authoritative `ARCHITECTURE.md`, expand `CONTRIBUTING.md`, add a human-readable ADR index, and trim per-change history out of `AGENTS.md` into the changelog.
4. **Structural architecture (P4)** — Consolidate `AnvilWorkbench` so all services route through it (FR-018), and decompose the 1958-line `anvil/api/v1/router.py` into cohesive per-area modules (FR-019). Each refactor lands as its own behavior-free change (Constitution §10.9).

**Technical approach**: No new runtime dependencies. Reuse existing `make`/`shared/*.mk` targets and `scripts/ci/vault_audit.py`. Add one GitHub Actions CI workflow plus small, unit-tested helper scripts (bump-scope guard, ADR-uniqueness check, guarded-import check). Governance changes are documentation + ADRs. Structural refactors are mechanical moves verified by the unchanged test suite.

## Technical Context

**Language/Version**: Python 3.11+ (helper scripts, refactors); YAML (GitHub Actions); Markdown (governance/docs); POSIX sh + GNU make (gate orchestration, existing `shared/*.mk`)
**Primary Dependencies**: Existing dev tooling only — `ruff`, `black`, `isort`, `pylint`, `mypy` (strict), `pytest` + `pytest-cov`, `commitizen`, `uv`; GitHub Actions (`actions/checkout@v4`, `astral-sh/setup-uv` or `actions/setup-python@v5`); existing `scripts/ci/vault_audit.py` + `graph_health/`. **No new runtime or dev dependency is required.**
**Storage**: N/A — no new persistence. (Coverage baseline stored as a config value in `pyproject.toml`; gate config stored in workflow YAML.)
**Testing**: `pytest` (existing suite, 64 files) for new helper scripts and refactor verification; CI workflow validated by triggering deliberate-failure and happy-path PRs.
**Target Platform**: GitHub-hosted CI runners (`ubuntu-latest`) for automation; local dev on macOS/Linux for gate parity.
**Project Type**: Existing pip-installable Python package with FastAPI web layer (layered: Repository → Service → God Class → Routes/CLI).
**Performance Goals**: Full gate suite completes in a reasonable CI window (target < ~10 min on `ubuntu-latest`); fast bump-scope guard completes in < ~1 min so release automation is not materially slowed.
**Constraints**: Fail-closed gating; zero behavioral delta for each structural refactor (test suite identical before/after); no new dependencies; each governance amendment requires an ADR + constitution version bump.
**Scale/Scope**: ~127 `anvil/` modules, 64 test files, ~100 vault notes / 24 ADR files; single repository; single protected branch (`main`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against `.specify/memory/constitution.md` v1.6.0.

| Article | Relevance | Status |
|---|---|---|
| I — Zero-Dependency Core | No changes to `anvil/core/`; no deps added | ✅ Pass |
| II — Educational Clarity | Unaffected | ✅ Pass |
| III — Seeded Reproducibility | Unaffected | ✅ Pass |
| IV — TDD Mandatory / 100% coverage | **Amended** — "100%" becomes a ratcheting baseline + phased goal. New helper scripts are developed test-first. | ⚠️ Amendment (see below) |
| V — Async-First | Unaffected (helper scripts are sync tooling, not web/db/service layer) | ✅ Pass |
| VI — `__init__.py` Ownership | New modules from the router split MUST get bare docstring-only `__init__.py` at authoritative levels | ✅ Pass (compliance required) |
| VII — Layered Architecture / God Class | FR-018 brings code **into** compliance (all services via `AnvilWorkbench`) | ✅ Pass (improves compliance) |
| VIII — iOS-Grade Polish | Unaffected (no UI behavior change; route split is behavior-free) | ✅ Pass |
| IX — Pit of Success | Unaffected | ✅ Pass |
| X — Domain-Driven Decomposition | Router split MUST follow domain boundaries + §10.9 (structural-only commit, zero behavioral delta) | ✅ Pass (compliance required) |
| Additional: `TYPE_CHECKING` forbidden | **Amended** — becomes conditional-allow with exception discipline (FR-021/FR-022) | ⚠️ Amendment (see below) |
| Additional: No type-error suppression | Reconcile existing `mypy` module-level `ignore_errors` overrides (`tracking`, `mlflow_inputs`) under FR-008 — justify via ADR or remove | ⚠️ Reconciliation required |
| Additional: One class per file | Router split MUST keep one class per file | ✅ Pass (compliance required) |
| Additional: Pydantic BaseModel | Any new structured types use `BaseModel` | ✅ Pass (compliance required) |
| Workflow: Spec Kit + merge gates | This feature **creates** the merge-gate enforcement the constitution already mandates | ✅ Pass (fulfills intent) |

**Gate result: PASS.** The two ⚠️ amendments (Article IV coverage target; `TYPE_CHECKING` ban) are **not violations** — they are sanctioned governance amendments performed *through* the constitution's own Governance process (ADR + version bump + recorded rationale). They are tracked in Complexity Tracking below.

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/014 DX Harness Hardening/
├── plan.md              # This file
├── spec.md              # Feature spec (with Clarifications)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (conceptual entities)
├── quickstart.md        # Phase 1 output (contributor experience)
├── contracts/           # Phase 1 output (gate + governance invariants)
│   ├── ci-gates.md
│   └── governance-invariants.md
└── checklists/
    └── requirements.md  # From /speckit.specify
```

### Source Code (repository root)

```text
.github/workflows/
├── ci.yml               # NEW — required gate suite on pull_request + non-main push
├── auto-bump.yml        # EXISTING — reconcile with required-check gating
└── release.yml          # EXISTING — reconcile with required-check gating

scripts/ci/
├── vault_audit.py       # EXISTING — reused as a gate; gains ADR-uniqueness check
├── check_adr_unique.py  # NEW — detect duplicate ADR identifiers (or folded into vault_audit)
└── check_guarded_imports.py  # NEW — flag TYPE_CHECKING symbols used in runtime code

shared/
└── testing.mk / python.mk / vault.mk  # EXISTING — gate targets, reused unchanged

pyproject.toml           # MODIFY — coverage fail_under set to ratcheting baseline

anvil/
├── cli.py               # MODIFY (P4) — relocate/expand AnvilWorkbench to expose all services
├── workbench.py         # NEW (P4, optional) — house the god class outside the CLI entrypoint
└── api/v1/
    ├── router.py        # MODIFY (P4) — reduce to a thin aggregator
    └── <new per-area modules>.py  # NEW (P4) — extracted route groups (one concern each)

anvil/db/models/
├── corpus.py            # KEEP guarded import (documented cycle exception)
└── corpus_file.py       # KEEP guarded import (documented cycle exception)

anvil/services/inference/
└── inference.py         # MODIFY (P2) — plain top-level import of Value; drop local re-import

.specify/memory/constitution.md  # MODIFY — amend Art IV coverage + TYPE_CHECKING rule; version bump

docs/vault/Decisions/
├── ADR-0NN-coverage-ratcheting-baseline.md     # NEW
├── ADR-0NN-type-checking-conditional-allow.md  # NEW
├── ADR-0NN-ci-merge-gate-enforcement.md        # NEW
├── ADR-0NN-adr-renumbering-and-uniqueness.md   # NEW
├── README.md            # NEW — human-readable ADR index
└── <renamed duplicate ADRs>  # 008/010/016 collisions renumbered + redirect stubs

ARCHITECTURE.md          # NEW — authoritative architecture/onboarding doc
CONTRIBUTING.md          # MODIFY — expand for onboarding
AGENTS.md                # MODIFY — trim per-change history into CHANGELOG.md
```

**Structure Decision**: This is an existing single-package layered project; no new top-level project structure is introduced. Changes are surgical: one new CI workflow, a small number of unit-tested helper scripts under `scripts/ci/`, governance/doc edits, and two isolated behavior-free refactors under `anvil/`. The router split introduces new modules under `anvil/api/v1/` following the existing domain-decomposition and one-class-per-file conventions.

## Complexity Tracking

> The two items below are **constitutional amendments**, not unjustified violations. They are listed because the Constitution Check flagged them and the Governance article requires explicit, recorded justification.

| Amendment | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Article IV: "100% coverage" → ratcheting baseline + phased goal | The stated 100% is unenforced and untrue (~41% actual); an impossible gate trains contributors/agents to ignore gates. A true, ratcheting baseline is enforceable today and improves monotonically. | Keeping "100%" and writing tests to reach it now would balloon scope far beyond DX hardening and block all merges until met. Deleting the standard entirely abandons the quality goal. |
| `TYPE_CHECKING` ban → conditional-allow + exception discipline | The ban contradicts the agent guide and working code; the ORM bidirectional-relationship cycle has no rule-compliant alternative (string-ref ban, one-class-per-file, `mypy --strict` each foreclose the alternatives). | Blanket ban would force violating one-class-per-file (co-location) or the string-ref ban. Blanket allow would re-permit the removable `inference.py` anti-pattern. The narrow conditional rule is the minimal honest reconciliation. |
| Reconcile `mypy` `ignore_errors` overrides (`tracking`, `mlflow_inputs`) | FR-008 forbids rules the code knowingly violates; module-level error suppression is such a case. | Leaving them silently contradicts "no type-error suppression"; this must be either justified in an ADR (3rd-party stub gaps) or removed. Tracked under P2. |
