---
title: 059 Local Key Custody Hardening - spec
type: spec
tags:
  - type/spec
  - domain/infrastructure
  - domain/operations
status: draft
spec-refs:
  - docs/vault/Specs/059 Local Key Custody Hardening/
related:
  - '[[059 Local Key Custody Hardening]]'
  - '[[058 At-Rest Secret Encryption]]'
  - '[[ADR-044-at-rest-secret-encryption]]'
created: '2026-06-29'
updated: '2026-06-29'
---

# Feature Specification: Local Key Custody Hardening (OS Keyring & Passphrase)

**Feature Branch**: `059-local-key-custody-hardening`
**Created**: 2026-06-29
**Status**: Draft — **Deferred / not scheduled**
**Parent**: [[Specs/058 At-Rest Secret Encryption/058 At-Rest Secret Encryption|058 At-Rest Secret Encryption]]

## Overview

[[Specs/058 At-Rest Secret Encryption/058 At-Rest Secret Encryption|Spec 058]] establishes the local
master key as a `0600` key-ring file with an `ANVIL_MASTER_SECRET` env override. That is the correct,
boring default for v1 — but it leaves the key as plaintext on disk, readable by anyone with filesystem
or root access (and leakable via careless backups).

This feature adds **opt-in, stronger custody for the local master key** behind a pluggable **local key
provider** seam, without changing the envelope, the cipher, or the rotation machinery from spec 058.
Two providers are added beyond the default file provider:

1. **OS keyring provider** — store the key material in the platform secret store (macOS Keychain, Linux
   Secret Service / `libsecret`, Windows Credential Manager) via the `keyring` library.
2. **Passphrase-derived provider** — derive the key from an operator passphrase via **Argon2id**; store
   **nothing** secret at rest (only KDF salt + parameters).

> **Deferred**: This spec is documented for future activation. It is **not** scheduled. Activate only on
> a concrete need (local user wants the key off plaintext disk; regulated single-tenant install).
> Per [[Decisions/ADR-041-simplicity-first-boring-technology|ADR-041]] these providers stay strictly
> opt-in — the file provider remains the default.

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-001..FR-007 |
| **Depends on** | Spec 058 (`EncryptionService` Protocol, `KeyRing`); the `keyring` and `argon2-cffi` libraries (new **optional** extras, not base deps) |
| **In scope** | Pluggable local key provider; OS-keyring provider; passphrase/Argon2id provider; headless/Docker fallback rules; provider selection config |
| **Out of scope** | SaaS/KMS custody (owned by spec 058); the envelope, cipher, AAD, and rotation mechanics (unchanged); TPM / Secure Enclave hardware backing |
| **Status** | **Deferred** — no active roadmap slot |
| **Invariant risk** | **LOW** — additive provider behind an existing seam; default behavior unchanged |

---

## User Scenarios & Testing

### User Story 1 — Operator Stores the Local Key in the OS Keyring (Priority: P1, when activated)

A privacy-conscious local user configures anvil to keep the master key in the OS keyring instead of a
plaintext file, so the key is not readable as a flat file on disk.

**Independent Test**: With the OS-keyring provider selected (and a test keyring backend), boot anvil;
verify no plaintext key file is written, the key is read from the keyring, and encrypt/decrypt round-trips
through the spec-058 `EncryptionService` unchanged.

**Acceptance Scenarios**:

1. **Given** `ANVIL_KEY_PROVIDER=os-keyring`, **When** anvil boots with no existing key, **Then** it
   generates a key, stores it in the OS keyring under a namespaced service/account, and writes **no**
   plaintext key file.
2. **Given** a key already in the OS keyring, **When** anvil boots, **Then** it loads the key from the
   keyring and the `EncryptionService` behaves identically to the file provider.
3. **Given** the OS keyring is unavailable/locked, **When** anvil boots, **Then** it fails fast with an
   actionable message and does **not** silently fall back to a plaintext file.

---

### User Story 2 — Operator Uses a Passphrase, Storing No Key at Rest (Priority: P2, when activated)

A high-security local operator supplies a passphrase at startup; anvil derives the master key and never
persists key material to disk.

**Independent Test**: With the passphrase provider selected, supply a passphrase via the prescribed
non-interactive channel; verify the derived key encrypts/decrypts, only the KDF salt + parameters are
stored, and a wrong passphrase fails to decrypt existing secrets.

**Acceptance Scenarios**:

1. **Given** `ANVIL_KEY_PROVIDER=passphrase` and a supplied passphrase, **When** anvil boots, **Then**
   it derives the key via Argon2id, persists only salt + KDF parameters, and stores no key material.
2. **Given** secrets written under a passphrase-derived key, **When** anvil restarts with the same
   passphrase, **Then** the secrets decrypt; **When** restarted with a wrong passphrase, **Then**
   decryption fails cleanly (authentication error), not a crash.
3. **Given** no passphrase is supplied in a non-interactive/headless context, **When** anvil boots,
   **Then** it fails fast with guidance (passphrase provider is unsuitable for unattended restart).

### Edge Cases

- Headless / Docker / CI with no OS keyring backend → the file provider remains default; OS-keyring and
  passphrase providers fail fast with clear guidance rather than degrading silently.
- Lost passphrase → secrets are unrecoverable by design; the provider docs MUST state this explicitly.
- Switching providers on an existing install → requires a spec-058 rotation (re-encrypt under a key
  sourced from the new provider); there is no implicit cross-provider key import.
- `keyring` selecting an insecure/plaintext backend (e.g. `keyrings.alt`) → MUST be detected and
  refused; only OS-backed secure backends are acceptable.

## Requirements

- **FR-001**: The local key material source MUST be abstracted behind a **`LocalKeyProvider`** seam that
  supplies/persists key material for the spec-058 `KeyRing`, without altering the `EncryptionService`
  Protocol, the envelope, the AAD, or the rotation machinery.
- **FR-002**: The provider MUST be selectable via `ANVIL_KEY_PROVIDER` (`file` | `os-keyring` |
  `passphrase`), defaulting to `file` (the spec-058 default). Unknown values MUST fail fast.
- **FR-003**: An **OS-keyring provider** MUST store/retrieve key material via the `keyring` library under
  a namespaced service/account, write no plaintext key file, and refuse insecure/plaintext `keyring`
  backends.
- **FR-004**: A **passphrase provider** MUST derive the key via **Argon2id** with per-install random
  salt, persist only salt + KDF parameters (never key material), and accept the passphrase through a
  defined non-interactive channel (env/secret-file), never an unconditional interactive prompt.
- **FR-005**: Non-default providers MUST **fail fast** when their backing store is unavailable (locked
  keyring, missing passphrase, headless context) and MUST NOT silently fall back to a plaintext file.
- **FR-006**: `keyring` and `argon2-cffi` MUST be **optional extras** (e.g. `anvil[keyring]`), never base
  dependencies; local mode with the default file provider MUST require no new dependency
  ([[Decisions/ADR-041-simplicity-first-boring-technology|ADR-041]], Article I).
- **FR-007**: Switching providers on an existing install MUST be performed via a spec-058 key rotation
  (re-encrypt under a key from the new provider); no implicit cross-provider key migration is provided.

## Success Criteria

- **SC-001**: With the OS-keyring provider, no plaintext key file exists on disk and encrypt/decrypt
  behaves identically to the file provider.
- **SC-002**: With the passphrase provider, only KDF salt + parameters are stored; correct passphrase
  decrypts, wrong passphrase fails cleanly.
- **SC-003**: All non-default providers fail fast (no silent plaintext fallback) when their store is
  unavailable.
- **SC-004 (NMRG)**: The default file provider is unchanged; a base install needs no new dependency.

## Key Entities

- **LocalKeyProvider** (Protocol): supplies/persists key material for the spec-058 `KeyRing`.
- **FileKeyProvider**: the spec-058 default (`0600` key-ring file; `ANVIL_MASTER_SECRET` override).
- **OsKeyringKeyProvider**: `keyring`-backed provider with secure-backend enforcement.
- **PassphraseKeyProvider**: Argon2id-derived provider; stores salt + KDF params only.

## Assumptions

- Built on spec 058's `EncryptionService` / `KeyRing` seam; this spec adds only key *sources*.
- The default (file) provider remains correct and sufficient for the common local case; these are
  hardening options for users who explicitly want them.
- SaaS custody is unaffected — KMS (spec 058) is the SaaS path; these providers are local-only.

## Activation Note

This spec is **deferred**. Activate by scheduling it as a feature slice (e.g. `/speckit.plan` +
`/speckit.tasks` against `059-local-key-custody-hardening`) only when a concrete user/compliance need
appears. Until then it is a captured intention, not committed work.
