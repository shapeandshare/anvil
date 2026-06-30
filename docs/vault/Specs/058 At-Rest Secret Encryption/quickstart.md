# Quickstart: At-Rest Secret Encryption

**Date**: 2026-06-30 | **Branch**: `058-at-rest-secret-encryption`

## What This Feature Does

Replaces the single-key AES-256-GCM secret encryption with a **rotatable, self-describing envelope** scheme. This is purely an **internal architecture change** — the user-visible API (GET/POST/DELETE secrets) is unchanged.

## For Developers

### No manual migration steps

This is a **greenfield** deployment. No existing encrypted data exists. The Alembic migration adds the `key_id` column to `user_secrets` — auto-applied on next `make run` via the existing `MigrationService`.

### Running locally

```bash
make setup    # installs deps (cryptography is already transitive)
make run      # starts web UI + MLflow; auto-migrates DB
```

The key ring file (`data/.key_ring.json`, `0600`) is auto-generated on first boot with a single key. No manual configuration needed.

### Key rotation (operator entry point)

```bash
# Trigger a full rotation cycle:
curl -X POST http://localhost:8080/v1/admin/secrets/rotate
# → {"status":"accepted","kid":"<new-uuid>"}

# Check status:
curl http://localhost:8080/v1/admin/secrets/rotation-status
# → {"current":"<kid>","previous":"<kid>|null","rows_by_kid":{"<kid>":42}}

# Trigger re-encryption sweep:
curl -X POST http://localhost:8080/v1/admin/secrets/sweep
# → {"rows_processed":42}

# Expire previous key (only succeeds when 0 rows reference it):
curl -X POST http://localhost:8080/v1/admin/secrets/expire-previous
# → {"status":"ok","expired_kid":"<previous-kid>"}
```

### Running tests

```bash
make test    # includes all new encryption + rotation tests
```

## For Reviewers

### Key files to review

| File | Purpose |
|------|---------|
| `anvil/services/_shared/encryption_envelope.py` | Pydantic model for the JSON envelope |
| `anvil/services/_shared/encryption_algorithm.py` | `EncryptionAlgorithm` StrEnum |
| `anvil/services/_shared/key_ring.py` | Key ring (current/previous + keys dict) |
| `anvil/services/_shared/encryption.py` | `EncryptionService` Protocol |
| `anvil/services/_shared/encryption_service.py` | `LocalEncryptionService` implementation |
| `anvil/services/secrets/user_secret_service.py` | Moved from `model_import/` |
| `anvil/services/secrets/secret_rotation_service.py` | Rotation, sweep, expire |
| `anvil/db/models/user_secret.py` | +`key_id` column |
| `anvil/_resources/migrations/versions/008_add_user_secrets_key_id.py` | Migration |
| `anvil/_saas/encryption/kms_encryption_service.py` (Phase 3) | KMS envelope implementation |
| `anvil/api/v1/user_secrets.py` | +admin rotation endpoints |

### Verification checklist

- [ ] Envelope round-trips: `decrypt(encrypt("hello", aad), aad) == "hello"`
- [ ] AAD mismatch fails: `decrypt(encrypt("hello", aad_alice), aad_bob)` raises
- [ ] Tampered ciphertext fails: flip a byte in `ct`, decrypt raises
- [ ] Unknown `kid` raises explicit error — no silent try-all-keys
- [ ] `rotate()` promotes `current→previous`, mints new key
- [ ] `expire_previous()` refuses when residual rows exist
- [ ] `expire_previous()` succeeds after sweep completes
- [ ] `reencrypt_sweep()` is idempotent (re-running same batch is safe)
- [ ] Plaintext never appears in logs (FR-030)
- [ ] `mypy --strict` passes on all changed files
- [ ] `make lint` and `make test` pass

## For Ops

### Local mode key file

- **Location**: `data/.key_ring.json`
- **Permissions**: `0600` (owner read/write only)
- **Override**: `ANVIL_MASTER_SECRET` env var seeds the current key and is popped from env after read
- **Backup**: The key ring is NOT backed up with the database — it must be restored separately. Include `data/.key_ring.json` in disaster recovery procedures.

### SaaS mode

- **DEK ring**: SSM Parameter Store `SecureString` at path `/anvil/{env}/dek-ring`
- **KMS CMK**: Customer-managed key with automatic rotation enabled
- **IAM**: ECS task role requires `kms:Decrypt`, `kms:GenerateDataKey`, and `ssm:GetParameter` permissions
- **Boot order**: The application will not start serving if KMS `Decrypt` fails at startup (fail-fast)
- **Rotation**: CMK auto-rotation needs no action. DEK rotation uses the same operator API above.