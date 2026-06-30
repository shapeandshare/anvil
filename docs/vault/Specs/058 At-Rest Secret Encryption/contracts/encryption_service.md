# EncryptionService Protocol Contract

**Date**: 2026-06-30 | **Spec**: [[058 At-Rest Secret Encryption - spec]]

## Overview

The `EncryptionService` Protocol defines the interface for at-rest secret encryption in anvil. It has two implementations:

1. `LocalEncryptionService` — file/env key ring (local mode)
2. `KmsEncryptionService` — KMS envelope encryption with SSM-stored DEK ring (SaaS mode)

Both implementations produce **byte-format-identical** `EncryptionEnvelope` tokens, ensuring secrets are portable across modes.

## Interface

### `encrypt(plaintext: str, aad: bytes) -> str`

Encrypt a plaintext secret with AAD binding.

| Parameter | Type | Description |
|-----------|------|-------------|
| `plaintext` | `str` | UTF-8 encoded secret value to encrypt |
| `aad` | `bytes` | Additional Authenticated Data — callers MUST supply `f"{user_id}:{key}".encode()` |

**Returns**: `str` — JSON-serialized `EncryptionEnvelope`:
```json
{"v":1,"alg":"aes-256-gcm","kid":"<uuid4>","n":"<base64-nonce>","ct":"<base64-ciphertext>"}
```

**Raises**: No exceptions on valid input (encryption always succeeds with correct key material).

### `decrypt(token: str, aad: bytes) -> str`

Decrypt an envelope token back to plaintext.

| Parameter | Type | Description |
|-----------|------|-------------|
| `token` | `str` | JSON-serialized `EncryptionEnvelope` |
| `aad` | `bytes` | Additional Authenticated Data — MUST match the AAD used during encryption |

**Returns**: `str` — Decrypted plaintext.

**Raises**:

| Exception | When | Example scenario |
|-----------|------|-----------------|
| `InvalidAadError` | AAD mismatch | Decrypting `alice:hf_token` with AAD `bob:hf_token` |
| `InvalidCiphertextError` | Tampered ciphertext or auth tag | Any byte of `ct` flipped in storage |
| `UnknownKeyIdError` | Envelope `kid` not found in active key ring | Ring was rotated and `previous` expired since the row was written |
| `InvalidEnvelopeError` | Token is malformed JSON or fails validation | Corrupted DB value, schema version mismatch |

### Auxiliary

The `EncryptionService` Protocol type is defined in `anvil/services/_shared/encryption.py`. Implementations are not required to inherit from it — PEP 544 structural subtyping applies: any class with matching `encrypt(self, plaintext: str, aad: bytes) -> str` and `decrypt(self, token: str, aad: bytes) -> str` method signatures satisfies the protocol.

## Data Formats

### EncryptionEnvelope (JSON)

```json
{
    "v": 1,
    "alg": "aes-256-gcm",
    "kid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "n": "ABC123...==",
    "ct": "XYZ789...=="
}
```

| Field | Type | Constraints |
|-------|------|-------------|
| `v` | `int` | Schema version — currently `1`. Future AAD scheme changes bump this to route decoding. |
| `alg` | `str` | Algorithm identifier — MUST be a member of `EncryptionAlgorithm` StrEnum (`"aes-256-gcm"`) |
| `kid` | `str` | UUID4 string — identifies the key that encrypted this value |
| `n` | `str` | Base64-encoded 96-bit (12-byte) random nonce |
| `ct` | `str` | Base64-encoded AES-256-GCM output (ciphertext + 128-bit GCM tag) |

### Key Ring (JSON, persisted to `data/.key_ring.json`)

Local mode only:

```json
{
    "current": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "previous": "fedcba09-8765-4321-abcd-ef0987654321",
    "keys": {
        "a1b2c3d4-e5f6-7890-abcd-ef1234567890": "hex-encoded-32-byte-key-material...",
        "fedcba09-8765-4321-abcd-ef0987654321": "hex-encoded-32-byte-key-material..."
    }
}
```

### DEK Ring (SSM Parameter Store SecureString, SaaS mode)

```json
{
    "current": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "previous": null,
    "keys": {
        "a1b2c3d4-e5f6-7890-abcd-ef1234567890": {
            "wrapped_dek": "base64-encoded-ciphertext-blob-from-KMS-GenerateDataKey",
            "kek_id": "arn:aws:kms:us-east-1:123456789012:key/mrk-1234abcd..."
        }
    }
}
```

## State Machine

### Implementation resolution

```
AnvilWorkbench
  │
  ├── MODE="local" ──→ LocalEncryptionService(key_ring=KeyRing.load())
  │
  └── MODE="saas"  ──→ KmsEncryptionService(
                          kms_client=boto3.client("kms"),
                          ssm_client=boto3.client("ssm"),
                          dek_ring_ssm_path="/anvil/{env}/dek-ring"
                        )
```

### Rotation lifecycle

```
                    ┌───────────────┐
                    │  Single-key   │ previous=None
                    └───────┬───────┘
                            │ rotate()
                            ▼
┌───────────────────────────────────────────┐
│              Rotation Overlap              │
│  current=k2, previous=k1, keys={k1, k2}   │
│  New writes → k2                           │
│  Existing rows still at k1 → readable     │
└──────────┬────────────────────┬───────────┘
           │                    │
    reencrypt_sweep()    expire_previous()
    (idempotent,         (gated: count
     resumable)          rows at k1 == 0)
           │                    │
           ▼                    ▼
    ┌───────────┐       ┌───────────────┐
    │ In-progress│       │  Single-key   │
    │ (cont.)   │       │  current=k2   │
    └───────────┘       │  previous=None│
                        └───────────────┘
```

## Security Properties

- **Confidentiality**: AES-256-GCM with unique random nonce per encryption
- **Integrity**: GCM authentication tag covers ciphertext + AAD
- **Anti-replay**: AAD `user_id:key` binds ciphertext to row identity
- **Key attribution**: Every envelope carries `kid` identifying the encrypting key
- **Rotation safety**: Overlap window preserves readability of old rows; count-gated expiry prevents premature key retirement
- **No plaintext leak**: FR-030 — plaintext value and key material never appear in logs, error messages, or API responses