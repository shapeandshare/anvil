---
title: 'ADR-044: At-Rest Secret Encryption — Key Ring & KMS Envelope'
type: decision
tags:
  - type/decision
  - domain/architecture
  - domain/infrastructure
  - domain/database
created: '2026-06-29'
updated: '2026-06-29'
status: status/draft
source: agent
aliases:
  - 'ADR-044: At-Rest Secret Encryption — Key Ring & KMS Envelope'
  - ADR-044
related:
  - '[[Decisions/ADR-030-saas-architecture]]'
  - '[[Decisions/ADR-041-simplicity-first-boring-technology]]'
  - '[[Decisions/ADR-032-greenfield-legacy-removal]]'
  - '[[Reference/SaaSArchitectureDecisions]]'
code-refs:
  - anvil/services/_shared/encryption.py
  - anvil/services/model_import/user_secret_service.py
  - anvil/db/models/user_secret.py
  - docs/vault/Specs/058 At-Rest Secret Encryption/
---

# ADR-044: At-Rest Secret Encryption — Key Ring & KMS Envelope

## Status

Draft

Implements [[Specs/058 At-Rest Secret Encryption/058 At-Rest Secret Encryption|spec 058]].

## Context

Per-user secrets (HuggingFace tokens, provider API keys) are stored in `user_secrets` and encrypted at
rest with AES-256-GCM, introduced in [[Specs/042 Model Asset Storage/042 Model Asset Storage|spec 042]].
The cipher is sound, but two design gaps block production use:

1. **No key identifier in the stored value.** The value is a bare `base64(nonce + ciphertext)`. With no
   `kid`, there is no way to know which key encrypted a row, so the master key **can never be rotated**.
2. **No SaaS key-custody story.** Local mode persists the master key to `data/.master_key` (`0600`),
   which does not scale to a multi-tenant hosted deployment.

A recurring instinct is to "use a normal cert/TLS/chain approach." That conflates two layers: TLS/PKI is
**encryption in transit + endpoint identity** (asymmetric), whereas this is **encryption at rest** of
values the same server must both write and later read. Asymmetric/cert-based encryption only helps when
the writer must *not* be able to decrypt (write-only producers) — not the case here. Symmetric AES-256-GCM
at rest is the correct, boring choice ([[Decisions/ADR-041-simplicity-first-boring-technology|ADR-041]]).

The real questions are **where the key lives as we scale** and **how it rotates** — and the system must
keep local mode zero-cloud-dependency (ADR-030) while the SaaS path uses managed AWS primitives.

This decision assumes **greenfield** ([[Decisions/ADR-032-greenfield-legacy-removal|ADR-032]]): no
pre-existing encrypted data or deployments, so there is no legacy format and no migration.

## Decision

Adopt a **self-describing, rotatable envelope** with a **key ring**, and a **mode-aware**
`EncryptionService` (local key file vs. AWS KMS), keeping AES-256-GCM as the data cipher.

1. **Self-describing envelope.** Store `{"v":1,"alg":"aes-256-gcm","kid":<id>,"n":<b64>,"ct":<b64>}`
   instead of a bare blob. `v` versions the scheme (including the AAD construction).
2. **Key ring (`current` / `previous`).** Encrypt with `current`; decrypt by the envelope's `kid`; an
   unknown `kid` is a hard error. This deliberately mirrors the `{current, previous}` dual-key shape
   already defined for the SSE/Redis rotators in [[Specs/037 SaaS Resilience DR/037 SaaS Resilience DR|spec 037]].
3. **AAD bound to row identity.** Use `user_id:key` as AES-GCM AAD so a ciphertext cannot be replayed
   onto a different `(user_id, key)` row.
4. **Denormalized `key_id` column** on `user_secrets` (indexed) so the re-encryption sweep and the
   expiry gate run as `count(...) WHERE key_id = ?` rather than parsing every row.
5. **Rotation = two layers.** KEK rotation (the KMS CMK) is handled by **KMS automatic rotation** with
   **no** data re-encryption; DEK/key rotation promotes `current → previous`, mints a new `current`, and
   a **count-gated** background sweep re-encrypts old rows before `previous` is retired (never on a
   timer alone).
6. **Two implementations behind one Protocol** (the 7th local/SaaS seam, per ADR-030):
   - **Local** — `LocalEncryptionService`, file/env key ring (`data/.master_keyring.json`, `0600`;
     `ANVIL_MASTER_SECRET` override). OS-keyring / passphrase custody is **deferred** to
     [[Specs/059 Local Key Custody Hardening/059 Local Key Custody Hardening|spec 059]].
   - **SaaS** — `KmsEncryptionService` in `anvil/_saas/`: KMS envelope encryption (`GenerateDataKey`),
     a small DEK ring unwrapped once at startup into memory, AES-256-GCM locally per row. The DEK ring
     config is stored in **SSM Parameter Store SecureString** (Secrets Manager only if rotation hooks
     are later required). The app authenticates to KMS via its **ECS task IAM role** — **no static
     master key is stored by the application**.
7. **Rotation service location.** A new `anvil/services/secrets/` domain owns `SecretRotationService`
   (and `UserSecretService` moves here from `model_import/`), since secrets are a bounded context that
   already spans model-import and inference use ([[Decisions/ADR-022-domain-driven-package-decomposition|ADR-022]]).

### Explicitly rejected / deferred

| Option | Disposition | Reason |
|--------|-------------|--------|
| TLS / cert / PKI as the at-rest store | Rejected | Wrong layer; asymmetric buys nothing when the server reads its own secrets |
| Per-user AWS Secrets Manager entries | Rejected | ~$0.40/secret/mo + ops scale poorly across many users; no benefit |
| Direct KMS encrypt/decrypt per secret | Acceptable stepping stone only | Every read becomes KMS-latency/quota-bound; envelope + in-memory DEK is preferred |
| HashiCorp Vault Transit | Deferred | Strong but you must operate Vault (HA/unseal/upgrade) — not "boring/managed" for an AWS-only v1 |
| CloudHSM | Deferred | Compliance-grade, expensive, overkill for v1 |
| Per-tenant / BYOK keys | Deferred | One shared DEK ring per environment for v1; revisit on a real BYOK/isolation/crypto-erasure requirement |
| OS-keyring / passphrase local custody | Deferred | Tracked in [[059 Local Key Custody Hardening]] |

## Consequences

### Positive

- The master key becomes **rotatable** — the current scheme cannot rotate at all.
- SaaS holds **no static master key**; the root key never leaves the KMS HSM, and access is governed by
  IAM + a KMS key policy with CloudTrail audit.
- One KMS call at startup (not per read) keeps the hot path fast while still rooting trust in KMS.
- Row format is identical across local and SaaS, so secrets are portable and testable without AWS.
- AAD binding closes a ciphertext-substitution gap within the database.

### Negative

- More moving parts than a single key file: an envelope, a key ring, a rotation service, and (SaaS) a
  DEK ring + SSM parameter + KMS key policy. Justified by the rotation requirement (Complexity Tracking).
- Moving `UserSecretService` into a new `secrets/` domain is churn (acceptable greenfield).
- A future AAD-scheme change requires an envelope `v` bump and a re-encryption sweep.

### Neutral

- The cipher (AES-256-GCM via `cryptography`) is unchanged; no new runtime dependency in local mode.
- `anvil/core/` zero-dependency and the `anvil/_saas/` import boundary are preserved.

## Compliance

- **Merge review** verifies: envelope carries `v/alg/kid`; AAD is `user_id:key`; `key_id` column exists
  and is indexed; no plaintext/key material in logs; SaaS crypto lives under `anvil/_saas/` behind `[aws]`.
- **TDD** (Article IV): rotation (rotate/sweep/expire), tamper/AAD-mismatch, unknown-`kid`, and
  local↔KMS format-parity tests exist before implementation; mocked KMS via `moto`.
- **Simplicity gate** (ADR-041): the rejected simpler alternatives (per-secret Secrets Manager; direct
  KMS per op) are recorded above and in the plan's Complexity Tracking table.
- **Greenfield** (ADR-032): no `v0`/legacy read path or migration is added.

## See Also

- [[Specs/058 At-Rest Secret Encryption/058 At-Rest Secret Encryption|Spec 058 — At-Rest Secret Encryption]]
- [[Specs/059 Local Key Custody Hardening/059 Local Key Custody Hardening|Spec 059 — Local Key Custody Hardening (deferred)]]
- [[Decisions/README|Decisions]]
