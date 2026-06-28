---
title: 028 SaaS Abstraction Framework - spec
type: spec
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/028 SaaS Abstraction Framework/
related:
  - '[[028 SaaS Abstraction Framework]]'
created: '2026-06-27'
updated: '2026-06-27'
---

# Feature Specification: SaaS Abstraction Framework

**Feature Branch**: `028-saas-abstraction-framework`
**Created**: 2026-06-27
**Status**: Draft

## User Scenarios & Testing

### User Story 4 — Local User Runs anvil Unchanged (Priority: P1)

A local user installs anvil via pip, runs `anvil serve`, and all existing functionality works exactly as before. No SaaS code is loaded, no cloud dependencies are required.

**Why this priority**: The local mode is the existing product. Breaking it for existing users is unacceptable. This feature carries the HIGHEST local-mode risk because it refactors existing local code behind new interfaces.

**Independent Test**: Run `pip install anvil && anvil serve` and verify the web UI at localhost:8080 works with all existing features (corpus upload, training, SSE, model export).

**Acceptance Scenarios**:
1. **Given** a clean Python environment, **When** the user runs `pip install anvil`, **Then** no `boto3`, `redis-py`, or other cloud SDKs are installed.
2. **Given** a local install, **When** the user runs `anvil serve`, **Then** SQLite is used, MLflow runs as a subprocess, training runs in-process, and no cloud services are contacted.
3. **Given** the refactored local implementations, **When** existing tests run, **Then** all pre-existing tests pass without modification (SC-007).

### User Story 5 — SaaS Developer Runs Full Stack Locally (Priority: P2)

A developer clones the repo and runs `docker compose up` to start PostgreSQL, Redis, MinIO, MLflow, and the anvil web service with hot-reload. They can make changes to the code and see them reflected immediately.

**Why this priority**: Developer velocity directly impacts how fast SaaS features ship.

**Acceptance Scenarios**:
1. **Given** the developer runs `docker compose up`, **When** all containers are healthy, **Then** the anvil web UI is available at localhost:8080.
2. **Given** the docker compose stack is running, **When** the developer starts a training job, **Then** compute runs in-process (not Batch), writing results to the local MinIO and PostgreSQL containers.

### Edge Cases

- What happens in local mode when `ANVIL_MODE=saas` is not set? Local mode runs the `anvil.api.app:app` entrypoint, which has no import path to `anvil/_saas/` — SaaS modules are never loaded and no cloud service is contacted (FR-011, FR-011a).
- What happens if the local entrypoint is launched with `ANVIL_MODE=saas` (or the SaaS entrypoint with mode unset/local)? The factory detects the entrypoint/mode mismatch and **fails fast** with a clear error — it does not reinterpret or silently switch (FR-011b).
- What happens if `ANVIL_MODE=saas` but a required cloud variable (e.g., `DATABASE_URL`) is missing? The SaaS factory fails fast at startup listing the missing variables, before wiring any implementation — it never falls back to SQLite/local (FR-011c).
- What happens when an interface implementation swap changes behavior? Contract tests (T016) running against both local and SaaS implementations guarantee parity — a regression in a local implementation is caught by the same contract test that validates the SaaS implementation.

## Requirements

### Functional Requirements

- **FR-011**: System MUST NOT load any SaaS-only code (`boto3`, `redis-py`) in local mode. The local entrypoint module (`anvil/api/app.py`) MUST have no static import path to `anvil/_saas/`, so import isolation is structurally guaranteed (not merely runtime-checked).
- **FR-011a**: Mode selection MUST use two layers: (1) the **entrypoint module** is the primary switch — local launches `anvil.api.app:app`, SaaS launches `anvil._saas.app:app`; (2) the `ANVIL_MODE` env var is an explicit guard and config selector. Mode MUST be explicit and is NEVER auto-detected.
- **FR-011b**: Each app factory MUST validate `ANVIL_MODE` matches its module on startup and **fail fast** on mismatch (e.g., local entrypoint started with `ANVIL_MODE=saas`, or vice versa). No silent reinterpretation.
- **FR-011c**: When `ANVIL_MODE=saas`, the SaaS factory MUST validate that all required cloud configuration (`DATABASE_URL`, `REDIS_URL`, `S3_DATA_BUCKET`, `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`, `MLFLOW_TRACKING_URI`) is present BEFORE wiring implementations, and fail fast listing any missing variables. It MUST NEVER silently fall back to local implementations.
- **FR-001**: System MUST use Amazon Cognito User Pools as the sole authentication provider for SaaS mode — no custom auth code (no password hashing, no JWT issuance, no token storage in the application).
- **FR-016**: The core abstraction interfaces (`FileStore`, `EventBus`, `JobQueue`, `ComputeBackend`, `LogsReader`, and `VersionedContentStore`) MUST be defined with local implementations alongside them and SaaS implementations in `anvil/_saas/implementations/`. Blob/runtime interfaces live in `anvil/storage/`; the `VersionedContentStore` content-repository interface lives in `anvil/services/content/` (spec 016). `VersionedContentStore` is the versioned content-repository substrate: local mode uses a pure-Python, content-addressed implementation (no external service); SaaS mode uses a LakeFS-backed implementation behind the same interface (see the "Content Repository (versioned)" requirement group below and AD-17).

## Acceptance Criteria — Local-Mode Regression Gate (LMRG)

Because this feature carries the **HIGHEST local-mode risk** (it refactors existing local code paths behind new interfaces), the Definition of Done is anchored by the full Local-Mode Regression Gate:

```bash
make test            # all pre-existing tests pass UNMODIFIED (SC-007)
make lint            # zero new lint errors
make typecheck       # mypy --strict clean; no SaaS imports leaking into non-SaaS modules
pip install .        # clean install
anvil serve          # boots; UI at :8080 works end-to-end (upload → train → SSE → export)
```

Plus the **import-isolation assertion** (cheap, run in CI on every feature):

```bash
# No SaaS module is reachable from the local entrypoint, and no cloud SDK is importable
# in a base (no-extras) install.
python - <<'PY'
import importlib, sys
import anvil.api.app          # local entrypoint must import with zero cloud deps
for forbidden in ("boto3", "redis", "aws_jwt_verify", "opentelemetry", "prometheus_client"):
    assert forbidden not in sys.modules, f"{forbidden} loaded by local entrypoint"
print("import isolation OK")
PY
```

Additionally, the refactored `LocalFileStore` / `InProcessEventBus` / `InProcessJobQueue` produce **identical observable behavior** to pre-refactor. Contract tests (T016) run against the local implementations to guarantee parity.

`ANVIL_MODE=saas` with the local entrypoint **fails fast** with a clear error (FR-011b) — never silently degrades.

## Success Criteria

- **SC-006**: Local mode (`pip install anvil && anvil serve`) has zero SaaS dependencies and no behavioral changes from the pre-SaaS version.
- **SC-007**: All existing local-mode tests pass without modification after the abstraction layer is introduced.

## Acceptance Gates

### Gate G1 — Setup

| ID | Criterion | Verification | Pass Condition |
|----|-----------|--------------|----------------|
| G1.1 | `anvil/_saas/` package exists and is never imported in local mode | `python -c "import anvil"` with import tracing | No `anvil._saas` module loaded |
| G1.2 | `boto3`, `redis`, `aws-jwt-verify` are optional extras only | `pip install anvil` in clean venv, then `pip list` | None of the SaaS deps present |
| G1.3 | CDK app synthesizes | `cd packages/infra && cdk synth` | Exit 0, templates produced |

### Gate G2 — Foundational

| ID | Criterion | Verification | Pass Condition |
|----|-----------|--------------|----------------|
| G2.1 | All 4 abstraction interfaces defined with full type signatures | `mypy --strict anvil/storage/` | Zero errors |
| G2.2 | Local implementations satisfy interfaces | Contract tests in `tests/contract/` | All pass |
| G2.3 | Local mode unchanged — existing suite passes | `make test` | 100% pass, coverage ≥ baseline |
| G2.4 | `ANVIL_MODE` selector wires correct implementations | Unit test asserting local vs saas wiring | Both modes wire correctly |
| G2.5 | Entrypoint/mode mismatch fails fast | Unit test: local factory with `ANVIL_MODE=saas` and vice versa | Raises clear error, no silent switch |
| G2.6 | SaaS factory fails fast on missing cloud config | Unit test: `ANVIL_MODE=saas` with `DATABASE_URL` unset | Raises listing missing vars, no local fallback |

## Assumptions

- Local mode uses SQLite, in-process MLflow, local filesystem, and in-process compute — unchanged from current behavior.
- The same `anvil` Python package serves both local and SaaS modes. The mode is selected by the `ANVIL_MODE` environment variable at deploy time and is never auto-detected.
- No changes to `anvil/core/` — the training engine remains zero-dependency.
- Existing compute backends (`local-stdlib`, `local-torch`, `modal`) continue to work in local mode.
- The base package installs zero cloud dependencies. All cloud SDKs (`boto3`, `redis`, `aws-jwt-verify`) live in the `[aws]` optional extra.
- A single SaaS container image (web + compute worker, selected by entrypoint per AD-10) is published to a public registry.