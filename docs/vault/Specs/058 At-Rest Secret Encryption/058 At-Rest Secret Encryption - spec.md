---
title: 058 At-Rest Secret Encryption - spec
type: spec
tags:
  - type/spec
  - domain/database
  - domain/infrastructure
  - domain/architecture
status: draft
spec-refs:
  - docs/vault/Specs/058 At-Rest Secret Encryption/
related:
  - '[[058 At-Rest Secret Encryption]]'
  - '[[042 Model Asset Storage]]'
  - '[[ADR-044-at-rest-secret-encryption]]'
  - '[[Reference/SaaSArchitectureDecisions]]'
created: '2026-06-29'
updated: '2026-06-29'
---

# Feature Specification: At-Rest Secret Encryption — Key Ring + KMS Envelope

**Feature Branch**: `058-at-rest-secret-encryption`
**Created**: 2026-06-29
**Status**: Draft
**Decision**: [[Decisions/ADR-044-at-rest-secret-encryption|ADR-044]]

## Overview

anvil stores per-user credentials (HuggingFace tokens, provider API keys) in the `user_secrets` table,
encrypted at rest with AES-256-GCM ([[Specs/042 Model Asset Storage/042 Model Asset Storage|spec 042]]).
The current scheme has one fatal limitation: the stored value is a bare `base64(nonce + ciphertext)`
with **no key identifier**, so the master key can never be rotated — there is no way to know which key
encrypted a given row.

This feature makes the at-rest scheme **rotatable and mode-aware** while keeping the cipher (AES-256-GCM)
unchanged:

1. A **self-describing JSON envelope** carrying a version, algorithm, and key id (`kid`).
2. A **key ring** (`current` + optional `previous`): encrypt with `current`, decrypt by the envelope's
   `kid`. This reuses the `{current, previous}` shape already defined for the SSE/Redis secret rotators
   in [[Specs/037 SaaS Resilience DR/037 SaaS Resilience DR|spec 037]].
3. **AAD bound to row identity** (`user_id:key`) so a ciphertext cannot be replayed onto a different row.
4. A **background re-encryption sweep** + a count-gated `expire_previous()` to complete a rotation.
5. In SaaS, a **KMS-backed** `EncryptionService` that produces the identical envelope, with the data key
   ring unwrapped via the ECS task **IAM role** — the application stores **no static master key**.

> **Greenfield**: no pre-existing data or deployments. No `v0`/legacy format, no migration, no
> "try-all-keys" fallback. Envelope is `v:1` with a `kid` from the first write.

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-001..FR-008, FR-010..FR-015, FR-020..FR-026, FR-030..FR-031 |
| **Owned decision** | [[ADR-044-at-rest-secret-encryption]] |
| **Supersedes** | The single-key `EncryptionService` from spec 042 (greenfield replace, no migration) |
| **Depends on** | `anvil/services/_shared/` (cipher seam), `anvil/_saas/` isolation (ADR-030), `[aws]` extra for boto3 |
| **In scope** | Local key-ring cipher; rotation mechanics; SaaS KMS envelope cipher; SSM-stored DEK ring |
| **Deferred** | OS-keyring / passphrase local custody → [[059 Local Key Custody Hardening]]; per-tenant/BYOK keys; CloudHSM; HashiCorp Vault Transit |
| **Out of scope** | Infra secrets (SSE signing key, Redis AUTH) — owned by spec 037 / AD-16 |
| **Invariant risk** | **MEDIUM** — touches the at-rest crypto seam and a DB column; mitigated by greenfield (no migration) and TDD |

---

## User Scenarios & Testing

### User Story 1 — Operator Rotates the Master Key Without Data Loss (Priority: P1)

An operator rotates the secret-encryption key. Secrets written before the rotation remain readable
through the overlap window; new writes use the new key; once a background sweep has re-encrypted every
old row, the previous key is retired.

**Why this priority**: Rotation is the entire point — the current scheme cannot do it at all. This is
the MVP slice that removes the blocking limitation.

**Independent Test**: Write secrets, run `rotate()`, confirm old-key rows still decrypt; write new
secrets and confirm they carry the new `kid`; run the sweep; confirm `expire_previous()` succeeds only
after zero rows reference the previous `kid` and old-key decryption then fails.

**Acceptance Scenarios**:

1. **Given** secrets encrypted under key `k1`, **When** `rotate()` runs, **Then** `k1` becomes
   `previous`, a new `k2` becomes `current`, and the existing rows still decrypt via `k1`.
2. **Given** a freshly rotated ring, **When** a new secret is written, **Then** its envelope `kid` is
   `k2` and its `user_secrets.key_id` column equals `k2`.
3. **Given** rows still referencing `k1`, **When** `expire_previous()` is called, **Then** it refuses
   (previous key still in use).
4. **Given** the re-encryption sweep has completed, **When** `expire_previous()` is called, **Then** it
   succeeds, and any token still encrypted under `k1` no longer decrypts.

---

### User Story 2 — Secrets Are Encrypted With a Rotatable, Tamper-Bound Envelope (Priority: P1)

Every stored secret is a self-describing envelope bound to its `(user_id, key)` identity, so it can be
attributed to a key and cannot be moved to another row.

**Why this priority**: The envelope + AAD are the foundation that makes US1 possible; without it nothing
else works.

**Independent Test**: Encrypt a value, inspect the stored token is JSON with `v/alg/kid/n/ct`; decrypt
round-trips; decrypting with a different AAD (`user_id:key`) fails; a tampered `ct` fails.

**Acceptance Scenarios**:

1. **Given** a plaintext secret for `(alice, hf_token)`, **When** encrypted, **Then** the stored value is
   a JSON envelope `{"v":1,"alg":"aes-256-gcm","kid":...,"n":...,"ct":...}`.
2. **Given** a valid envelope for `(alice, hf_token)`, **When** decrypted with AAD `bob:hf_token`,
   **Then** decryption fails (authentication error).
3. **Given** a valid envelope, **When** any byte of `ct` is flipped, **Then** decryption raises.
4. **Given** an envelope whose `kid` is not in the ring, **When** decrypted, **Then** it raises a clear
   "unknown key id" error (never a silent wrong-key attempt).

---

### User Story 3 — SaaS Encrypts via KMS Without Storing a Master Key (Priority: P2)

In SaaS mode the application encrypts secrets using data keys derived from a KMS CMK. The plaintext data
keys live only in process memory; the CMK never leaves KMS; the app holds no static key on disk or in
config.

**Why this priority**: Required for the hosted product, but local mode (US1/US2) is independently
shippable first.

**Independent Test**: With a mocked KMS (`moto`), load the DEK ring (one KMS `Decrypt` per DEK),
encrypt/decrypt round-trip, and confirm a row encrypted by the **local** service decrypts under the
**KMS** service and vice-versa (identical envelope format).

**Acceptance Scenarios**:

1. **Given** a KMS CMK and a DEK ring in SSM, **When** the app boots, **Then** it unwraps `current` and
   `previous` DEKs into memory via the task IAM role and holds no plaintext key on disk.
2. **Given** the KMS service is active, **When** a secret is encrypted, **Then** the produced envelope is
   byte-format-compatible with the local service (same `v/alg` schema; `kid` resolves in the DEK ring).
3. **Given** the CMK has KMS automatic rotation enabled, **When** the CMK rotates, **Then** existing rows
   decrypt unchanged with **no** row re-encryption (KMS retains prior backing material).
4. **Given** a DEK rotation, **When** triggered, **Then** it reuses the US1 sweep + `expire_previous()`
   machinery unchanged.

### Edge Cases

- Unknown `kid` in a stored envelope → raise an explicit "unknown key id" error; never fall back to
  trying every key.
- `expire_previous()` requested while sweep is incomplete → refuse with the residual count; never expire
  on a timer alone.
- KMS unavailable at boot (SaaS) → fail fast and loud; do not start serving with no decrypt capability.
- AAD scheme change in the future → bump envelope `v`; `v` selects the AAD construction so old and new
  never collide.
- Crash mid-sweep → sweep is idempotent and resumable by `key_id`; re-running completes the rotation.
- Plaintext/key material in logs → forbidden; only counts and `kid`s may be logged.

## Requirements

### Envelope & Local Key Ring (Phase 1)

- **FR-001**: Stored secret values MUST be a self-describing JSON envelope with fields `v` (schema
  version, int), `alg` (algorithm enum), `kid` (key id, str), `n` (base64 nonce), `ct` (base64
  ciphertext). The envelope MUST round-trip losslessly to/from the `user_secrets.encrypted_value` text.
- **FR-002**: Encryption MUST use AES-256-GCM with a fresh 96-bit random nonce per operation. `alg` MUST
  be drawn from an `EncryptionAlgorithm` `StrEnum` (`aes-256-gcm`), never a magic string.
- **FR-003**: Encryption MUST bind Additional Authenticated Data (AAD) to the row identity as
  `f"{user_id}:{key}"`. Decryption MUST supply the same AAD; a mismatch MUST fail authentication. The
  AAD construction is versioned by the envelope `v` field.
- **FR-004**: A **key ring** MUST hold a `current` key id and an optional `previous` key id, plus the key
  material for each. Encryption MUST always use `current`.
- **FR-005**: Decryption MUST resolve the key by the envelope's `kid`. An unknown `kid` MUST raise an
  explicit error (no try-all-keys behavior).
- **FR-006**: `user_secrets` MUST carry a denormalized, indexed `key_id` column recording the `kid` used
  for that row, enabling efficient `count`/`iterate` queries by key id. It is set on every write to
  `ring.current`.
- **FR-007**: The cipher MUST be exposed as an `EncryptionService` **Protocol** in
  `anvil/services/_shared/`, with `LocalEncryptionService` (file/env key ring) and (Phase 3)
  `KmsEncryptionService` (in `anvil/_saas/`) as the two implementations — the 7th local/SaaS interface
  alongside `FileStore`, `EventBus`, etc. (ADR-030).
- **FR-008**: There MUST be **no** legacy/`v0` format and **no** migration path (greenfield). The local
  ring MUST auto-generate a single `current` key on first boot, persisted `0600`; `ANVIL_MASTER_SECRET`,
  if set, seeds `current` and is popped from the environment after read.

### Rotation Mechanics (Phase 2)

- **FR-010**: A `SecretRotationService.rotate()` operation MUST mint a new key, promote the existing
  `current` to `previous`, set the new key as `current`, and persist the ring atomically.
- **FR-011**: A re-encryption sweep MUST walk rows whose `key_id == previous`, decrypt each (by its own
  `kid`) and re-encrypt under `current` (updating `encrypted_value` and `key_id`). The sweep MUST be
  batched, idempotent, and resumable.
- **FR-012**: `expire_previous()` MUST succeed only when `count(key_id == previous) == 0` (and, in SaaS,
  all serving nodes have reloaded the ring). Otherwise it MUST refuse and report the residual count.
- **FR-013**: `previous` MUST NOT be expired on a timer alone — expiry is gated solely on the residual
  row count (FR-012).
- **FR-014**: Rotation operations (`rotate`, sweep progress, `expire_previous`) MUST emit structured logs
  and a `rows_by_key_id` metric. Logs MUST NOT contain plaintext or key material.
- **FR-015**: Rotation MUST be triggerable via an operator/admin entry point (CLI or admin route),
  running `rotate → sweep → expire_previous` as observable steps.

### SaaS KMS Envelope (Phase 3)

- **FR-020**: In SaaS mode, `KmsEncryptionService` MUST use KMS envelope encryption: a small **DEK ring**
  of `{kid → plaintext_dek}` is unwrapped once at startup via KMS `Decrypt`, held only in process memory,
  and used for local AES-256-GCM per row. The hot path MUST NOT call KMS per secret operation.
- **FR-021**: The DEK ring config (`{current, previous, keys:{kid:{wrapped_dek, kek_id}}}`) MUST be
  stored in **AWS SSM Parameter Store** as a `SecureString`. (Secrets Manager is an acceptable
  alternative only if its rotation hooks are needed; default is SSM for cost.)
- **FR-022**: The KMS service MUST produce envelopes **byte-format-identical** to the local service
  (same `v`/`alg` schema; `kid` resolves in the active ring), so rows are portable across modes.
- **FR-023**: The application MUST authenticate to KMS via its ECS task **IAM role** (workload identity);
  it MUST NOT store a static master key on disk or in config in SaaS mode.
- **FR-024**: KEK rotation MUST be handled by **KMS automatic key rotation** on the CMK, requiring **no**
  row or DEK re-encryption.
- **FR-025**: DEK rotation (minting a new data key, promoting `current`/`previous`, writing the ring back
  to SSM) MUST reuse the Phase 2 sweep + `expire_previous()` machinery unchanged.
- **FR-026**: All SaaS crypto code MUST live under `anvil/_saas/`, depend on boto3 only via the `[aws]`
  extra, and MUST NOT be importable in local mode (enforced by the existing `_saas` lint boundary).

### Cross-Cutting Safety

- **FR-030**: Plaintext secret values and key material MUST NEVER be written to logs, error messages, or
  the GET API. Only key ids, counts, and status may be logged.
- **FR-031**: The `GET /v1/user/secrets` endpoint MUST continue to return key **names only**, never
  decrypted values (preserved from spec 042).

## Success Criteria

- **SC-001**: An operator completes a full key rotation (rotate → sweep → expire) with zero secret loss
  and zero downtime in local mode.
- **SC-002**: Every stored secret is a `v:1` envelope carrying a `kid`; a tampered ciphertext or a
  mismatched `(user_id, key)` AAD fails to decrypt.
- **SC-003**: A row encrypted by the local service decrypts under the KMS service and vice-versa
  (format parity), verified with mocked KMS.
- **SC-004**: In SaaS, the application starts with no static master key present on disk/config; the only
  stored material is the KMS-wrapped DEK ring in SSM.
- **SC-005**: KMS CMK automatic rotation occurs with no row re-encryption and no decrypt failures.
- **SC-006 (NMRG)**: Local-mode encryption uses no cloud dependencies in a base install; the `anvil/core/`
  zero-dependency invariant and the `_saas` import boundary are preserved.

## Key Entities

- **EncryptionEnvelope** (`anvil/services/_shared/encryption_envelope.py`): Pydantic model `v, alg, kid,
  n, ct` with `to_token()` / `from_token()` (base64+JSON), strict validation.
- **EncryptionAlgorithm** (`StrEnum`): `AES_256_GCM = "aes-256-gcm"`.
- **KeyRing** (`anvil/services/_shared/key_ring.py`): `current`, `previous`, `keys: dict[str, bytes]`;
  load/generate/persist (`0600`); resolve-by-`kid`.
- **EncryptionService** (Protocol): `encrypt(plaintext: str, aad: bytes) -> str`,
  `decrypt(token: str, aad: bytes) -> str`.
- **LocalEncryptionService**: file/env key-ring implementation (local mode).
- **KmsEncryptionService** (`anvil/_saas/encryption/`): KMS envelope implementation (SaaS mode).
- **SecretRotationService** (new `anvil/services/secrets/` domain): `rotate()`, `reencrypt_sweep()`,
  `expire_previous()`.
- **UserSecret** (extended): adds the indexed `key_id` column (FR-006).

## Definition of Done

- Self-describing `v:1` envelope with `kid` and `user_id:key` AAD; `current`/`previous` key ring;
  `LocalEncryptionService` behind the `EncryptionService` Protocol; `key_id` column; rotation
  (`rotate → sweep → expire_previous`) count-gated and observable; SaaS `KmsEncryptionService` with a
  KMS-unwrapped DEK ring in SSM, IAM-authenticated, format-compatible with local; KMS auto-rotation
  needs no re-encryption; new `anvil/services/secrets/` domain houses the rotation service; **NMRG
  (full)**, TDD, mypy --strict, NumPy docstrings, one-class-per-file.

## Assumptions

- Greenfield: no encrypted data or deployments exist; the spec-042 single-key cipher is replaced
  outright, not migrated.
- The three-mode architecture (ADR-030) and the `anvil/_saas/` isolation + `[aws]` extra are in place.
- AES-256-GCM via the `cryptography` library remains the cipher (already a transitive dependency).
- SaaS runs on AWS with KMS and SSM Parameter Store available to the task IAM role.
- Infra-secret rotation (SSE signing key, Redis AUTH) is owned elsewhere (spec 037 / AD-16) and only
  donates its `{current, previous}` pattern for consistency.

## Phasing

| Phase | Slice | Effort | Depends on |
|-------|-------|--------|------------|
| 1 | Self-describing envelope + local key-ring cipher + `key_id` column + AAD | Small–Medium | — |
| 2 | Rotation mechanics (rotate / sweep / count-gated expire) | Medium | Phase 1 |
| 3 | SaaS KMS envelope cipher + SSM DEK ring + IAM identity | Medium | Phases 1–2 |
