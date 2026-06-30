# Data Model: At-Rest Secret Encryption

**Date**: 2026-06-30 | **Spec**: [[058 At-Rest Secret Encryption - spec]]

## Entity-Relationship Overview

```
┌─────────────────────────────────────────────────────┐
│                   KeyRing                            │
│  ┌──────────────┐  ┌──────────────────┐             │
│  │ current (kid) │  │ previous (kid|None)│            │
│  └──────┬───────┘  └────────┬─────────┘             │
│         │                   │                        │
│         └──────────┬────────┘                        │
│                    ▼                                  │
│         ┌──────────────────┐                         │
│         │  keys: dict[kid] │──► bytes (key material) │
│         └──────────────────┘                         │
└─────────────────────────────────────────────────────┘
         │
         │ references via envelope.kid
         ▼
┌─────────────────────────────────────────────────────────┐
│                    UserSecret                             │
│  id (PK)     user_id (FK†)      key          key_id (NEW)│
│  encrypted_value (envelope JSON)   created_at  updated_at│
│                                                            │
│  UNIQUE(user_id, key)                                      │
│  INDEX(key_id)  ← NEW: efficient sweep/expiry queries      │
└─────────────────────────────────────────────────────────┘
         │
         │ encrypted_value contains:
         ▼
┌──────────────────────────────────────┐
│         EncryptionEnvelope            │
│  v: int       (schema version)       │
│  alg: str     (algorithm enum)       │
│  kid: str     (key id from ring)     │
│  n: str       (base64 nonce)         │
│  ct: str      (base64 ciphertext)    │
│                                       │
│  AAD (not stored): f"{user_id}:{key}" │
└──────────────────────────────────────┘
```

## Entities

### EncryptionEnvelope

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `v` | `int` | Yes | Schema version (currently `1`) |
| `alg` | `str` | Yes | Algorithm identifier from `EncryptionAlgorithm` enum (e.g., `"aes-256-gcm"`) |
| `kid` | `str` | Yes | Key ID — references a key in the active key ring |
| `n` | `str` | Yes | Base64-encoded 96-bit random nonce |
| `ct` | `str` | Yes | Base64-encoded AES-256-GCM ciphertext |

**Location**: `anvil/services/_shared/encryption_envelope.py`
**Model type**: Pydantic `BaseModel`
**Validation rules**:
- `v` must be `1` (future versions added by bumping)
- `alg` must be a member of `EncryptionAlgorithm`
- `n` must decode to exactly 12 bytes (96-bit nonce)
- `n` and `ct` must be valid base64

**Serialization**:
- `to_token() -> str`: JSON-serialized envelope (canonical key order: `v, alg, kid, n, ct`)
- `from_token(token: str) -> EncryptionEnvelope`: Parse JSON, validate fields

### EncryptionAlgorithm (StrEnum)

| Member | Value | Description |
|--------|-------|-------------|
| `AES_256_GCM` | `"aes-256-gcm"` | AES-256 in GCM mode, 96-bit nonce, 128-bit tag |

**Location**: `anvil/services/_shared/encryption_algorithm.py`

### KeyRing

| Field | Type | Description |
|-------|------|-------------|
| `current` | `str` | Key ID of the active encryption key |
| `previous` | `str \| None` | Key ID of the previous key (exists during rotation overlap window) |
| `keys` | `dict[str, bytes]` | Map of key ID → 256-bit key material |

**Location**: `anvil/services/_shared/key_ring.py`
**Persistence**: `data/.key_ring.json` (JSON, `0600` perms)
**Methods**:
- `resolve(kid: str) -> bytes`: Return key material by ID; raise `UnknownKeyIdError` if not found
- `generate() -> str`: Create a new UUID4 key, add to `keys`, return the `kid`
- `save(path: str) -> None`: Persist to JSON file
- `load(path: str) -> KeyRing`: Load from JSON file; auto-generate if not found

**Invariants**:
- `current in keys` always holds
- `previous is None or previous in keys`
- `previous` may equal `current` (single-key state, no rotation active)
- Key material is 32 bytes (256 bits) for AES-256

### EncryptionService (Protocol)

```python
class EncryptionService(Protocol):
    """PEP 544 structural protocol for at-rest secret encryption."""

    def encrypt(self, plaintext: str, aad: bytes) -> str:
        """Encrypt plaintext with AAD, return envelope token.
        
        Returns a JSON-serialized EncryptionEnvelope string.
        """
        ...

    def decrypt(self, token: str, aad: bytes) -> str:
        """Decrypt envelope token with AAD, return plaintext.
        
        Raises:
            InvalidAadError: AAD mismatch
            InvalidCiphertextError: tampered ciphertext
            UnknownKeyIdError: kid not in ring
        """
        ...
```

### LocalEncryptionService

| Dependency | Source |
|------------|--------|
| `key_ring: KeyRing` | `data/.key_ring.json` or `ANVIL_MASTER_SECRET` |
| `encryption_envelope: EncryptionEnvelope` (model) | `encryption_envelope.py` |

**Location**: `anvil/services/_shared/encryption_service.py`
**Key sources** (priority):
1. `ANVIL_MASTER_SECRET` env var → seeds `current`, popped from env after read (FR-008)
2. `data/.key_ring.json` → load persisted ring
3. Auto-generate new key (first boot)

### KmsEncryptionService

| Dependency | Source |
|------------|--------|
| `boto3 kms_client` | ECS task IAM role credentials |
| `boto3 ssm_client` | ECS task IAM role credentials |
| `DEK ring` | SSM Parameter Store `SecureString` parameter |

**Location**: `anvil/_saas/encryption/kms_encryption_service.py`
**Key sources**:
- SSM Parameter Store `SecureString`: `{"current": "<kid>", "previous": "<kid>|null", "keys": {"<kid>": {"wrapped_dek": "<b64>", "kek_id": "<kms_key_arn>"}}}`
- On boot: `KMS.Decrypt` each wrapped DEK → in-memory `dict[kid, bytes]`
- Hot path: AES-256-GCM in-process (no KMS call per secret)

### UserSecret (ORM Model — Extended)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `int` | PK, autoincrement | Row identifier |
| `user_id` | `String(255)` | NOT NULL | User identity |
| `key` | `String(100)` | NOT NULL | Secret key name (e.g., `hf_token`) |
| `encrypted_value` | `Text` | NOT NULL | JSON-serialized `EncryptionEnvelope` |
| `key_id` | `String(36)` | NOT NULL, INDEXED | Denormalized `kid` from envelope (FR-006) — enables `count WHERE key_id = ?` |
| `created_at` | `DateTime` | NOT NULL | Row creation timestamp |
| `updated_at` | `DateTime` | NOT NULL | Last update timestamp |

**Constraints**: `UNIQUE(user_id, key)` → `uq_user_secrets_user_key`
**Indexes**:
- `ix_user_secrets_key_id` (NEW) — efficient sweep queries

### SecretRotationService

**Location**: `anvil/services/secrets/secret_rotation_service.py`
**Dependencies**:
- `user_secret_repository: UserSecretRepository`
- `encryption_service: EncryptionService` (Protocol)
- `key_ring: KeyRing`

**Methods**:

| Method | Description | State transition |
|--------|-------------|-----------------|
| `rotate()` | Mint new key, promote `current→previous`, persist ring | Ring: `{c} → {c→p, new_c}` |
| `reencrypt_sweep(batch_size=100)` | Re-encrypt rows with `key_id=previous` under `current` | Rows: `kid=p → kid=c` |
| `expire_previous()` | Remove `previous` key from ring (gated by row count) | Ring: `{c, p} → {c}` |
| `rotation_status()` | Return current ring state + row counts per `kid` | Read-only |

**Error types**:
- `RotationInProgressError`: `previous is not None` and `rotate()` called again
- `SweepIncompleteError`: `expire_previous()` called with residual rows
- `UnknownKeyIdError`: envelope `kid` not found in ring

## State Machine

```
                     ┌──────────────┐
                     │  Single-key  │
                     │  (no prev)   │
                     └──────┬───────┘
                            │ rotate()
                            ▼
               ┌────────────────────────┐
               │  Rotation overlap       │
               │  current + previous     │
               │  (sweep may be partial) │
               └──────┬─────────────┬────┘
                      │             │
            sweep()   │             │ expire_previous()
            (residual │             │ (zero rows → success)
             rows >0) │             │
                      ▼             ▼
               ┌──────────┐   ┌──────────────┐
               │ Overlap  │   │  Single-key  │
               │ (cont.)  │   │  (no prev)   │
               └──────────┘   └──────────────┘
```

## Validation Rules

| Rule | Entity | Phase | Description |
|------|--------|-------|-------------|
| Envelope must round-trip | `EncryptionEnvelope` | 1 | `from_token(to_token(e)) == e` |
| Nonce must be 12 bytes | `EncryptionEnvelope` | 1 | Validation on `from_token()` |
| AAD mismatch fails | `LocalEncryptionService` | 1 | Decrypt with wrong AAD raises `InvalidAadError` |
| Tampered ct fails | `LocalEncryptionService` | 1 | GCM authentication tag check raises `InvalidCiphertextError` |
| Unknown kid fails | `KeyRing` | 1 | `resolve(unknown_kid)` raises `UnknownKeyIdError` |
| `previous` only expires at count=0 | `SecretRotationService` | 2 | Gated on `count(key_id=previous) == 0` |
| No timer-based expiry | `SecretRotationService` | 2 | `expire_previous()` never uses time |
| Sweep is idempotent | `SecretRotationService` | 2 | Cursor-based, re-running skips already-rotated rows |
| Format parity (local↔SaaS) | `KmsEncryptionService` | 3 | Same `EncryptionEnvelope` schema and AES-256-GCM cipher; verified via `moto` test |
| No plaintext in logs | All | 1–3 | Only `kid`s, counts, and status strings are logged |
| Key file is `0600` | `KeyRing` | 1 | Enforced on `save()`, validated on `load()` |