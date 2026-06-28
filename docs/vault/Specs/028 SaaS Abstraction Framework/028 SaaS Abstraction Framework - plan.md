---
title: 028 SaaS Abstraction Framework - plan
type: plan
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/028 SaaS Abstraction Framework/
related:
  - '[[028 SaaS Abstraction Framework]]'
created: '2026-06-27'
updated: '2026-06-27'
---

# Implementation Plan: SaaS Abstraction Framework

**Branch**: `028-saas-abstraction-framework` | **Date**: 2026-06-27 | **Spec**: docs/vault/Specs/028 SaaS Abstraction Framework/spec.md
**Input**: Feature specification from `docs/vault/Specs/028 SaaS Abstraction Framework/spec.md`

## Summary

Establish the multi-mode abstraction layer for anvil. Four core interfaces (`FileStore`, `EventBus`, `JobQueue`, `ComputeBackend`) decouple business logic from infrastructure. Existing local implementations are refactored to sit behind these interfaces. The `ANVIL_MODE` env var + entrypoint selector wires the correct implementations at startup with fail-fast guards. Package skeletons (`anvil/_saas/`, `anvil/deploy/`), CDK app skeleton, docker-compose stub, and `[aws]` optional extras complete the foundation. This feature carries the highest local-mode risk of all SaaS features — every existing local code path is touched.

## Phasing

Phases map 1:1 to tasks.md and the acceptance gates G1–G2 in spec.md.

### Phase 1 — Setup

Package structure, `[aws]` extras, CDK app skeleton, docker-compose stub. **Gate G1.**

### Phase 2 — Foundational Abstractions

FileStore / EventBus / JobQueue (+ ResourceSpec) / ComputeBackend interfaces + local implementations + `ANVIL_MODE` selector + contract tests. **Gate G2.**

## Constitution Check

*GATE: Must pass before Phase 1. Re-check after Phase 2.*

### Article I — Zero-Dependency Core
- `anvil/core/` is untouched. ✓

### Article IV — TDD Mandatory
- Tests must be written before or alongside all new code.
- SaaS abstractions (FileStore, EventBus, JobQueue, ComputeBackend) each get contract tests.

### Article VI — `__init__.py` Ownership Policy
- `anvil/_saas/` is a new authoritative level — gets bare docstring-only `__init__.py`. ✓
- `anvil/_saas/implementations/` sub-package — same treatment. ✓
- `anvil/storage/` is the new home for interfaces — gets bare `__init__.py`. ✓
- `packages/infra/` is outside the Python package — no `__init__.py`. ✓

### Article VII — Layered Architecture
- The compute worker (`_saas/compute_worker.py`) is introduced as a stub — it does NOT go through `AnvilWorkbench` god class. **This is a justified exception**: the compute pod is a separate process that only runs `anvil/core` + I/O.

### Article IX — Pit of Success
- Local mode unchanged: `pip install anvil && anvil serve` works without any env vars. ✓
- If `ANVIL_MODE=saas` is set but cloud services aren't reachable, the app errors clearly rather than silently degrading. ✓

### Article X — Domain-Driven Package Decomposition
- `anvil/_saas/` follows underscore-prefixed convention for internal infrastructure. ✓
- `anvil/storage/` follows singular naming (contains abstraction interfaces). ✓
- Max 2 levels of sub-packaging. ✓

### Additional Constraints
- **Pydantic BaseModel**: `ResourceSpec` uses Pydantic BaseModel. ✓
- **One class per file**: FileStore interface, EventBus interface, etc. each get their own file. ✓
- **No type-error suppression**: `mypy --strict` applies to all new code. ✓
- **Lean dependencies**: `boto3`, `redis`, `aws-jwt-verify` go in `[project.optional-dependencies]` under `aws` extra. ✓

### Gate Evaluation

**Gate 1: Article VII exception (compute worker bypasses God Class)** — PASS. Justification documented above. The compute worker is a separate process, not a web-layer component.

**Gate 2: New cloud dependencies not in base package** — PASS. All cloud SDKs are optional extras.

**Gate 3: Local mode unchanged** — PASS. Zero behavioral changes to existing `make run` / `anvil serve`. Contract tests (T016) guarantee parity.

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/028 SaaS Abstraction Framework/
├── 028 SaaS Abstraction Framework.md       # Index note
├── spec.md                                  # Feature specification
├── plan.md                                  # This file
├── research.md                              # Research findings
├── data-model.md                            # ResourceSpec + interface definitions
├── quickstart.md                            # Developer quickstart
├── contracts/                               # Abstraction interface stubs
│   ├── filestore.py
│   ├── event_bus.py
│   ├── job_queue.py
│   └── compute_backend.py
└── tasks.md                                 # Task decomposition
```

### Source Code (repository root)

```text
# SaaS-specific code — only loaded in ANVIL_MODE=saas
anvil/_saas/
├── __init__.py                # Package docstring
└── implementations/
    └── __init__.py

# Abstraction interfaces (shared, no cloud deps)
anvil/storage/
├── __init__.py                # Package docstring
├── filestore.py               # FileStore interface (abstract)
├── local.py                   # LocalFileStore (existing, moved behind interface)
├── event_bus.py               # EventBus interface (abstract)
├── in_process_event_bus.py    # InProcessEventBus (local)
├── job_queue.py               # JobQueue interface (abstract) + ResourceSpec
├── in_process_job_queue.py    # InProcessJobQueue (local)
├── compute_backend.py         # ComputeBackend interface (abstract)
├── logs.py                    # LogsReader interface (abstract)
└── local_logs.py              # LocalLogsReader (file-based, existing)

# Deploy CLI (installed with anvil[aws] extra)
anvil/deploy/
├── __init__.py
├── command.py                 # Placeholder stub
└── cloudformation.py          # Placeholder stub

# Mode selector + config
anvil/config.py                # ANVIL_MODE selector, guard, cloud-config validation

# CDK infrastructure (TypeScript, dev only)
packages/infra/
├── bin/anvil.ts               # CDK app entrypoint (skeleton)
└── package.json

# Docker compose for local SaaS emulation
docker-compose.yml              # PostgreSQL, Redis, MinIO stubs (root)
```

## Complexity Tracking

| Item | Justification |
|------|---------------|
| Article VII exception — compute worker bypasses God Class | The compute worker is a standalone process in a Batch pod running only `anvil/core` + I/O. Not a web-tier component. |
| New cloud dependencies (`boto3`, `redis`, `aws-jwt-verify`) | Optional `[aws]` extras only; never installed or imported in local mode (Gate G1/G2 enforces). |
| Four interfaces instead of one general "pluggable storage" | Each interface maps to a distinct infrastructure concern with different lifecycle semantics (file I/O, pub/sub messaging, async job dispatch, compute execution). Combining them would violate the Single Responsibility Principle and make contract testing harder. |

## Dependency Changes

### New optional extras (pyproject.toml)

```toml
[project.optional-dependencies]
aws = [
    "boto3>=1.35",
    "redis>=5.0",
    "aws-jwt-verify>=4.0",
]
```

| Audience | Install | Gets |
|----------|---------|------|
| Local user | `pip install anvil` | Core only, zero cloud/monitoring deps |
| Operator deploying (CLI only) | `pip install anvil[aws]` | boto3/redis/jwt for `anvil deploy`, no monitoring |