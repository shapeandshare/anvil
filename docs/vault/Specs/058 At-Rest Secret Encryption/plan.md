# Implementation Plan: At-Rest Secret Encryption — Key Ring + KMS Envelope

**Branch**: `058-at-rest-secret-encryption` | **Date**: 2026-06-30 | **Spec**: [[docs/vault/Specs/058%20At-Rest%20Secret%20Encryption/058%20At-Rest%20Secret%20Encryption%20-%20spec.md]]
**Input**: Feature specification from `docs/vault/Specs/058 At-Rest Secret Encryption/spec.md`

## Summary

Replace the current single-key AES-256-GCM secret encryption (spec 042) with a **rotatable, self-describing envelope** scheme. The existing `EncryptionService` in `anvil/services/_shared/encryption.py` encrypts all `user_secrets.encrypted_value` rows with one static master key, making key rotation impossible. This plan:

1. Introduces a **JSON envelope** (`v/alg/kid/n/ct`) with a **key ring** (`current` + optional `previous`), so each row carries the key id (`kid`) that encrypted it.
2. Binds **AAD** (`user_id:key`) to each row, preventing ciphertext replay across rows.
3. Adds a denormalized, indexed **`key_id` column** on `user_secrets` for efficient sweep/expiry queries.
4. Refactors the cipher from a concrete class to an **`EncryptionService` Protocol** in `_shared/`, with `LocalEncryptionService` (file/env key ring) and (Phase 3) `KmsEncryptionService` (KMS envelope in `anvil/_saas/`).
5. Creates a new **`anvil/services/secrets/`** domain housing `SecretRotationService` (rotate → sweep → expire_previous) and moving `UserSecretService` from `model_import/`.
6. Provides an **operator entry point** for triggering rotation with observable steps.

**Technical approach**: AES-256-GCM via `cryptography` (unchanged), self-describing JSON envelope, `current/previous` key ring (matching spec 037's SSE rotator pattern), and for SaaS: KMS `GenerateDataKey`/`Decrypt` once at startup, AES-256-GCM in-process per row.

## Technical Context

**Language/Version**: Python 3.11+ (PEP 604, `StrEnum`, `from __future__ import annotations`)
**Primary Dependencies**: `cryptography` (already transitive dep via mlflow — AES-256-GCM cipher); `boto3` (Phase 3 only, via `[aws]` extra, behind `_saas` boundary)
**Storage**: SQLite (anvil-state.db, WAL mode) via async SQLAlchemy — `user_secrets` table; `LocalFileStore` for key ring persistence (`data/.key_ring.json`, `0600`)
**Testing**: pytest + `moto` (mocked KMS for Phase 3 tests); existing client fixture (in-memory SQLite, httpx.AsyncClient)
**Target Platform**: macOS/Linux (local mode), AWS ECS (SaaS mode)
**Project Type**: web-service + Python library (pip-installable package)
**Performance Goals**: KMS/SSM call once at startup only; AES-256-GCM in-process per-row (hot path, <1ms per enc/dec). Re-encryption sweep is batched background work — no SLA.
**Constraints**:
- **Greenfield**: no pre-existing encrypted data (ADR-032). No `v0`/legacy format. No migration.
- **TDD** (Article IV): rotation, tamper/AAD-mismatch, unknown-`kid`, local↔KMS format-parity tests exist before implementation.
- **`mypy --strict`**: zero type-error suppressions.
- **NumPy docstrings** (ruff convention = numpy).
- **One class per file** (Constitution Art. X, ADR-020).
- **No plaintext/key material in logs** (FR-030).
- **`_saas` import boundary**: KMS crypto lives in `anvil/_saas/`, gated by `[aws]` extra, unimportable in local mode (ADR-030).
- **`anvil/core/` zero-dependency invariant** — no change to core engine.
- **Simplicity First** (ADR-041 / Article XI): envelope + key ring is the simplest rotatable cipher; rejected alternatives recorded in Complexity Tracking.
**Scale/Scope**: Single master key ring per environment; one DEK ring per SaaS environment; per-tenant/BYOK keys deferred. ~100–10k user_secrets rows typical.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity First gate (Article XI — hard MUST)**: Confirm this plan favors
the simplest, most boring solution that meets the requirement:

- [x] **Simplest viable** (§11.1) — AES-256-GCM is unchanged (already in use). The envelope + `current/previous` key ring is the minimal extension that makes rotation possible. No speculative features (BYOK, per-tenant keys, CloudHSM) are added.
- [x] **Boring over novel** (§11.2) — `cryptography` library AES-256-GCM is a mature, widely-used standard. KMS envelope encryption is AWS's recommended pattern for at-rest app-level encryption. No experimental crypto primitives or novel key-management schemes.
- [x] **YAGNI** (§11.3) — Only the features required by FR-001 through FR-031 are built. Per-tenant keys, OS-keyring custody, HashiCorp Vault Transit, CloudHSM are explicitly deferred to future specs (059 and beyond).
- [x] **Reuse first** (§11.4) — The `{current, previous}` dual-key shape reuses the pattern already defined for SSE/Redis secret rotators (spec 037). The `EncryptionService` Protocol becomes the 7th local/SaaS interface per ADR-030's established pattern (FileStore, EventBus, VersionedContentStore, etc.). The existing `cryptography` dependency is used, not replaced.
- [x] **Testable** (§11.6) — All acceptance scenarios have Given/When/Then format. Rotation, tamper/AAD-mismatch, unknown-kid, and local↔KMS format-parity are all testable with mocked KMS (`moto`). The re-encryption sweep is idempotent and verifiable via `count(key_id = ?)` queries.

**Post-design re-evaluation**: ✅ All gates still pass. No new complexity introduced during Phase 1 design. Complexity Tracking table remains accurate.

> Any deviation from the simplest viable solution MUST be recorded in the
> Complexity Tracking table below (§11.5), or this gate fails.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Self-describing envelope (JSON parse per row) | Without `kid` in the stored value, the encrypting key cannot be identified, making rotation impossible | Bare `base64(nonce + ct)` (current) — cannot attribute rows to a key. A separate `key_id` column alone would desync from the encrypted value on copy/restore |
| `{current, previous}` key ring (2 keys instead of 1) | Rotation requires an overlap window where old secrets remain readable under the previous key | Single key with no rotation (current) — cannot rotate at all. Writing all rows atomically on rotation is impossible for large datasets |
| Denormalized `key_id` column + index | Sweep and expiry run as `count WHERE key_id = ?` without parsing every row's envelope JSON | Parsing every envelope to find rows by `kid` — O(n) scan per sweep step, adds latency and complexity |
| `EncryptionService` Protocol + 2 implementations | SaaS mode must avoid storing a static master key; KMS envelope encryption requires a different key-unwrapping path | Single implementation (local-only) — fails SaaS requirement. Direct KMS per-row is KMS-latency/quota-bound |
| SecretRotationService in new `secrets/` domain | Rotation is a bounded-context operation spanning sweep queries, ring mutations, and the god-class wiring | Inline rotation in `UserSecretService` — violates single-responsibility and mixes encryption with key lifecycle management |

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/058 At-Rest Secret Encryption/
├── 058 At-Rest Secret Encryption - spec.md  # Feature specification
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── encryption_service.md   # EncryptionService Protocol contract
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
# Single project — Python package (implicit namespace)
anvil/
├── services/
│   ├── _shared/
│   │   ├── encryption.py              # CANONICAL: EncryptionService Protocol (was concrete class)
│   │   ├── encryption_algorithm.py     # NEW: EncryptionAlgorithm StrEnum
│   │   ├── encryption_envelope.py      # NEW: EncryptionEnvelope Pydantic model
│   │   └── key_ring.py                # NEW: KeyRing (current/previous + keys dict)
│   └── secrets/                       # NEW domain (was model_import/user_secret_service.py)
│       ├── __init__.py                # NEW: bare docstring — domain purpose
│       ├── encryption_service.py      # NEW: LocalEncryptionService (key-ring impl)
│       ├── secret_rotation_service.py # NEW: SecretRotationService
│       ├── user_secret_service.py     # MOVED: from model_import/
│       └── types.py                   # NEW: rotation enums, result types
├── _saas/
│   └── encryption/                    # NEW: SaaS KMS implementation
│       ├── __init__.py                # NEW: bare docstring
│       └── kms_encryption_service.py  # NEW: KmsEncryptionService
├── db/
│   ├── models/
│   │   └── user_secret.py            # MODIFIED: +key_id column
│   └── repositories/
│       └── user_secret_repository.py  # MODIFIED: +count_by_key_id, +iterate_by_key_id
├── _resources/
│   └── migrations/
│       └── versions/
│           └── 008_add_user_secrets_key_id.py  # NEW: add key_id column
└── api/
    └── v1/
        └── user_secrets.py            # MODIFIED: +admin rotation endpoints

tests/
├── unit/
│   ├── services/
│   │   ├── test_encryption.py         # MODIFIED: test Protocol + LocalEncryptionService
│   │   └── secrets/                   # NEW: SecretRotationService tests
│   ├── db/repositories/
│   │   └── test_user_secret_repository.py  # MODIFIED: +count/iterate tests
│   └── models/
│       └── test_encryption_envelope.py     # NEW: envelope round-trip tests
├── e2e/
│   └── test_endpoints.py              # MODIFIED: +admin rotation endpoint tests
└── conftest.py                        # MODIFIED: +in-memory key ring fixture
```

**Structure Decision**: Single project (Python package). All new code follows existing domain-driven package decomposition (Constitution Article X). The `_shared/` types live alongside the encryption protocol. The `secrets/` domain is a new bounded context split from `model_import/` per ADR-044's decision. The `_saas/encryption/` directory follows ADR-030's SaaS isolation pattern.

## Evidence Map (FR → File/Test)

| FR | Primary File(s) | Test File(s) |
|----|-----------------|--------------|
| FR-001 (envelope) | `encryption_envelope.py` | `test_encryption_envelope.py` |
| FR-002 (AES-256-GCM, algorithm enum) | `encryption_algorithm.py`, `encryption_envelope.py` | `test_encryption.py` |
| FR-003 (AAD) | `encryption_service.py` | `test_encryption.py` |
| FR-004 (key ring) | `key_ring.py` | `test_encryption.py` |
| FR-005 (resolve by kid) | `key_ring.py` | `test_encryption.py` |
| FR-006 (key_id column) | `user_secret.py` (model), migration `008_*.py` | `test_user_secret_repository.py` |
| FR-007 (Protocol) | `encryption.py` (Protocol) | `test_encryption.py` |
| FR-008 (auto-generate, ANVIL_MASTER_SECRET) | `key_ring.py` | `test_encryption.py` |
| FR-010 (rotate) | `secret_rotation_service.py` | `test_secret_rotation_service.py` |
| FR-011 (re-encrypt sweep) | `secret_rotation_service.py` | `test_secret_rotation_service.py` |
| FR-012 (expire_previous count-gated) | `secret_rotation_service.py` | `test_secret_rotation_service.py` |
| FR-013 (no timer expire) | `secret_rotation_service.py` | `test_secret_rotation_service.py` |
| FR-014 (structured logs, metrics) | `secret_rotation_service.py` | `test_secret_rotation_service.py` |
| FR-015 (operator entry point) | `user_secrets.py` (API route) | `test_endpoints.py` |
| FR-020 (KMS envelope) | `kms_encryption_service.py` | `test_kms_encryption_service.py` |
| FR-021 (SSM DEK ring) | `kms_encryption_service.py` | `test_kms_encryption_service.py` (via moto) |
| FR-022 (format parity) | `kms_encryption_service.py`, `encryption_service.py` | `test_encryption.py` |
| FR-023 (IAM role, no static key) | `kms_encryption_service.py` | `test_kms_encryption_service.py` |
| FR-024 (KMS auto rotation) | `kms_encryption_service.py` | `test_kms_encryption_service.py` |
| FR-025 (DEK rotation reuses sweep) | `kms_encryption_service.py`, `secret_rotation_service.py` | `test_kms_encryption_service.py` |
| FR-026 (_saas boundary) | `kms_encryption_service.py` | — (lint-gated by _saas boundary) |
| FR-030 (no plaintext in logs) | All services | `test_secret_rotation_service.py` |
| FR-031 (GET returns names only) | `user_secrets.py` (existing) | `test_endpoints.py` (existing) |
