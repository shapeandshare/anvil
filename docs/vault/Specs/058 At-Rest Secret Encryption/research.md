# Research: At-Rest Secret Encryption — Key Ring + KMS Envelope

**Date**: 2026-06-30 | **Spec**: [[058 At-Rest Secret Encryption - spec]]

## Overview

All technical context was **Clear** from the spec and ADR-044 — no NEEDS CLARIFICATION items existed. This research.md records the design decisions validated during exploration of the existing codebase.

## Key Decisions

### Decision 1: Protocol Pattern — Structural (PEP 544) over ABC

- **Decision**: Use `typing.Protocol` (PEP 544 structural typing) for `EncryptionService`, not `abc.ABC`.
- **Rationale**: The codebase uses both patterns. `FileStore` and `VersionedContentStore` use ABC, while `ComputeBackendProtocol` and `ModelSource` use structural Protocol. The structural pattern is preferred here because:
  - No shared base implementation needed — `LocalEncryptionService` and `KmsEncryptionService` share zero code beyond the method signatures.
  - `KmsEncryptionService` lives behind the `_saas` import boundary and should not inherit from a `_shared` base class that would bring unnecessary coupling.
  - The `ComputeBackendProtocol` pattern is the most recent and aligns with ADR-030's interface-seam pattern.
- **Alternatives considered**: ABC-based Protocol (rejected — adds coupling across the `_saas` boundary).

### Decision 2: Key Ring Persistence Format

- **Decision**: `data/.key_ring.json` with `0600` permissions, JSON format containing `{"current": "<kid>", "previous": "<kid>|null", "keys": {"<kid>": "<hex_key>", ...}}`.
- **Rationale**: JSON is human-readable for debugging, trivially parseable, and the file is single-writer (only the local encryption service touches it). Hex encoding avoids binary-in-JSON issues.
- **Alternatives considered**: Binary format (rejected — harder to debug); SQLite (overkill for a single small file); environment variables only (not persistent across restarts).

### Decision 3: Key ID Format

- **Decision**: Use RFC 4122 UUID4 strings as key IDs (`kid`).
- **Rationale**: Universally unique, no collision risk in concurrent rotations, identifiable at a glance, fits in the JSON envelope and the indexed `key_id` column without length concerns.
- **Alternatives considered**: Sequential integers (rejected — collision risk in multi-process scenarios); timestamp-based (rejected — information leak).

### Decision 4: Sweep Batching

- **Decision**: Re-encryption sweep processes rows in batches of 100, using `key_id = ? AND id > ? ORDER BY id` for resumable cursor-based iteration.
- **Rationale**: 100 rows per batch keeps each transaction small (<100ms) and the cursor-based pagination means crash mid-sweep resumes from the last processed row without double-counting.
- **Alternatives considered**: Time-based windows (rejected — rows may have unbounded age); offset-based pagination (rejected — unstable under concurrent writes).

### Decision 5: Migration Strategy for `key_id` Column

- **Decision**: Add the column via a new Alembic migration (`008_add_user_secrets_key_id.py`). Since this is greenfield (no existing data), set a default of `""` (empty string — will be populated on first write). The column is `NOT NULL` with a deferred default — for greenfield, no rows exist so the constraint is trivially satisfied.
- **Rationale**: The simplest approach for greenfield deployment. No backfill needed.
- **Alternatives considered**: Nullable column (rejected — `NOT NULL` with indexed column is simpler for query semantics); backfill script (unnecessary — no data).

### Decision 6: `UserSecretService` Relocation

- **Decision**: Move `UserSecretService` from `anvil/services/model_import/` to `anvil/services/secrets/` in the same commit as the new domain creation (Constitution §10.9 exception: structural + behavioral combined since both are new code paths).
- **Rationale**: Secrets are a distinct bounded context that spans model-import and inference use. Keeping `UserSecretService` in `model_import/` creates an unnatural dependency. Moving it aligns with ADR-022 (Domain-Driven Package Decomposition) and ADR-044's location decision.
- **Impact**: `AnvilWorkbench` import path changes from `model_import.user_secret_service` to `secrets.user_secret_service`. All consumers (`ModelImportService`, `ModelAssetService`) update imports.

### Decision 7: KMS Mocking Strategy

- **Decision**: Use `moto`'s `mock_kms` for Phase 3 tests, with `moto` added to `[tool.pytest.ini_options]` test-only deps.
- **Rationale**: `moto` is the standard AWS mock library for Python and is already used elsewhere in the project. It provides in-memory KMS with `create_key`, `generate_data_key`, `decrypt` — exactly what's needed for format-parity tests.
- **Alternatives considered**: Manual mocking with `unittest.mock` (rejected — fragile, doesn't test real KMS API shapes); LocalStack (rejected — heavy, Docker dependency for unit tests).

## Dependencies

| Dependency | Version | Purpose | When |
|------------|---------|---------|------|
| `cryptography` | existing (transitive via mlflow) | AES-256-GCM cipher | All modes |
| `boto3` | existing (via `[aws]` extra) | KMS + SSM Parameter Store APIs | SaaS only |
| `moto` | test only | KMS/SSM mocking in tests | Test |

## Architecture Patterns Discovered

### Existing Protocol Pattern (for local/SaaS service pairs)

The codebase establishes a consistent pattern for service pairs across the local/SaaS boundary:

1. **Protocol definition** in `anvil/services/_shared/` (or domain `_shared/`) — lightweight `typing.Protocol` with method signatures only.
2. **Local implementation** in the same domain — concrete class with file/env-variant logic.
3. **SaaS implementation** in `anvil/_saas/` — behind `[aws]` extra, isolated by the `_saas` lint boundary, using AWS primitives.
4. **Runtime selection** in `AnvilWorkbench` — conditional instantiation based on `MODE` (ADR-030).

This is followed by `FileStore`, `VersionedContentStore`, `ComputeBackendProtocol`, and `ModelSource`. `EncryptionService` (spec 058) becomes the 7th instance.

### Existing Cipher Seam (being replaced)

**File**: `anvil/services/_shared/encryption.py`
**Current**: Concrete `EncryptionService` class with `encrypt(plaintext)` and `decrypt(token)`.
**Key source**: `ANVIL_MASTER_SECRET` env var → `data/.master_key` file → auto-generate.
**Format**: `base64(nonce_12_bytes + gcm_ciphertext)` — **no key id, no envelope, no AAD**.
**Replaced by**: `LocalEncryptionService` with envelope + key ring + AAD (this spec).

### Alembic Migration Pattern

- **Location**: `anvil/_resources/migrations/versions/`
- **Naming**: `{revision:03d}_{description}.py` (e.g., `006_add_model_assets_asset_download_jobs.py`)
- **Chain**: `001 → 002 → 003 → 004 → 005 → 006 → 007` (HEAD is 007)
- **Next revision**: `008`
- **Async env**: `anvil/_resources/migrations/env.py` uses `anvil.db.base.Base` and `anvil.db.registry.get_expected_tables()` to auto-register all models.
- **Auto-apply**: `MigrationService.ensure_migrated()` at startup, controlled by `ANVIL_DB_AUTO_MIGRATE` (default: `true`).

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Concurrent rotation triggers | Low | Data loss | `rotate()` checks `previous is None` — if a rotation is already in progress, refuse |
| KMS IAM misconfiguration in SaaS | Medium | Boot failure | Fail fast on KMS `Decrypt` failure at startup — never serve with no decrypt capability |
| Envelope format drift between local and SaaS | Low | Secret portability broken | Single `EncryptionEnvelope` model shared by both implementations; format-parity test enforces round-trip equivalence |
| Plaintext leak in exception traceback | Medium | Secret exposure | All `encrypt()`/`decrypt()` catch `Exception`, log `kid` + status only, re-raise with a generic error message |
| Key file permissions too permissive | Low | Local key exposure | `0o600` enforced on write; validated in `__post_init__` of key ring load |
