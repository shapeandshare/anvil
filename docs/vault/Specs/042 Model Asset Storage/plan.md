# Implementation Plan: Model Asset Acquisition & Storage (LakeFS-ready)

**Branch**: `042-model-asset-storage` | **Date**: 2026-06-28 | **Spec**: [[042 Model Asset Storage/042 Model Asset Storage - spec.md]]
**Input**: Feature specification from `docs/vault/Specs/042 Model Asset Storage/042 Model Asset Storage - spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Download and track model assets (weights, tokenizer, config) as managed, content-addressed artifacts — reusing the existing `FileStore` (local) and `VersionedContentStore`/LakeFS (SaaS) storage seam. Downloads are async background jobs with per-asset status tracking, model-level concurrency locking, content-address SHA-256 dedup, and `HF_TOKEN` auth for gated models via a new `UserSecret` model. Accepts safetensors only in v1; rejects unsupported formats fail-closed.

## Technical Context

**Language/Version**: Python 3.11+ (existing repo convention)  
**Primary Dependencies**: FastAPI, async SQLAlchemy + aiosqlite, `safetensors`, `huggingface_hub` (behind `[finetune]` extra), `httpx`, `numpy` — all existing deps; no new runtime deps introduced  
**Storage**: SQLite (app DB, WAL mode), `LocalFileStore` (local), `VersionedContentStore`/LakeFS (SaaS, spec 019/AD-17)  
**Testing**: pytest, httpx `AsyncClient` fixture (clean in-memory SQLite per session), unit tests under `tests/unit/`, e2e under `tests/e2e/`  
**Target Platform**: Linux server / macOS (existing)  
**Project Type**: Python web service (FastAPI) + pip-installable library  
**Performance Goals**: N/A (MVP — correctness over throughput); streaming constraint per FR-010a  
**Constraints**: Must stream large binaries (never full-buffer FR-010a); existing storage seam only (no new storage backend); content-addressed dedup via SHA-256  
**Scale/Scope**: Single-model download at a time per model (model-level lock), cross-model parallelism allowed; SaaS adds per-org throttled pool (max 3)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity First gate (Article XI — hard MUST)**: Confirm this plan favors
the simplest, most boring solution that meets the requirement:

- [x] **Simplest viable** (§11.1) — reuses existing storage seam (`FileStore`/`VersionedContentStore`), existing job infra, existing DB models. No new backends, no new transports.
- [x] **Boring over novel** (§11.2) — all deps are existing; SHA-256 content addressing is the same scheme already used in the data pipeline.
- [x] **YAGNI** (§11.3) — no speculative generality; SAFE tensors only in v1, deferred formats rejected with clear message; no progress SSE channel (polling only).
- [x] **Reuse first** (§11.4) — reuses existing `FileStore`, existing job pattern (training/model-import), existing `RuntimeConfig`-style repo pattern for `UserSecret`.
- [x] **Testable** (§11.6) — all acceptance scenarios (SC-001–SC-005) are testable via the existing `client` fixture + mock storage.

> Any deviation from the simplest viable solution MUST be recorded in the
> Complexity Tracking table below (§11.5), or this gate fails.

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/042 Model Asset Storage/
├── 042 Model Asset Storage - spec.md   # Feature spec (/speckit.specify output)
├── plan.md                             # This file (/speckit.plan command output)
├── research.md                         # Phase 0 output (/speckit.plan command)
├── data-model.md                       # Phase 1 output (/speckit.plan command)
├── quickstart.md                       # Phase 1 output (/speckit.plan command)
├── contracts/                          # Phase 1 output (/speckit.plan command)
└── tasks.md                            # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
anvil/
├── db/
│   ├── models/
│   │   ├── external_model.py           # Existing — add ModelAsset relationship
│   │   ├── model_asset.py              # NEW — ModelAsset ORM model
│   │   └── user_secret.py              # NEW — UserSecret ORM model
│   └── repositories/
│       ├── external_model_repository.py# Existing
│       ├── model_asset_repository.py   # NEW — CRUD for ModelAsset
│       └── user_secret_repository.py   # NEW — CRUD for UserSecret
├── services/
│   ├── model_import/
│   │   ├── hf_source.py                # Existing — add asset download method
│   │   └── model_asset_service.py      # NEW — download orchestration, asset lifecycle
│   └── _shared/
│       └── encryption.py               # NEW — AES encrypt/decrypt for UserSecret (reuse api_key_store.py patterns)
├── api/
│   └── v1/
│       ├── models.py                   # Existing — add asset download endpoint
│       └── dependencies.py             # Existing — add job status polling if needed
└── storage/
    ├── file_store.py                   # Existing — used for local asset storage
    └── versioned_content_store.py      # Existing — used for SaaS asset storage (seam)

tests/
├── unit/
│   ├── services/
│   │   └── test_model_asset_service.py # NEW
│   └── db/
│       └── repositories/
│           ├── test_model_asset_repository.py  # NEW
│           └── test_user_secret_repository.py  # NEW
└── e2e/
    └── test_model_assets.py            # NEW — HTTP endpoint tests
```

**Structure Decision**: Follows existing anvil layered architecture: Repository → Service → API Routes. Domain-aligned sub-packages for model import (adds asset download to `services/model_import/`) and storage seam. New entities (`ModelAsset`, `UserSecret`) follow existing ORM model patterns.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| AES-256-GCM over plaintext | Per-user secrets in DB need encryption (SaaS multi-tenant) | Plaintext + file perms works for local-only; insufficient for SaaS per spec FR-010d |
| Separate `ModelAsset` + `UserSecret` models | Relational integrity, queryability, separate lifecycle | Embedding in `ExternalModel` JSON blob would work for MVP but violates Article X (DDD) and creates migration pain |
| Async job via model-import pattern | GB-scale downloads would timeout sync proxies | Sync download simpler but blocks API worker; violates Article IX (Pit of Success — error on timeout is not acceptable) |
| Use `cryptography` dep (transitive) | Stdlib has no AES-GCM; writing AES from scratch violates §11.2 (boring over novel) | Stdlib-only approach would require custom low-level AES — novel, unproven, and risky |
