---
title: 059 Local Key Custody Hardening
type: spec
tags:
  - type/spec
  - domain/infrastructure
  - domain/operations
spec-refs:
  - docs/vault/Specs/059 Local Key Custody Hardening/
status: draft
created: '2026-06-29'
updated: '2026-06-29'
aliases:
  - 059 Local Key Custody Hardening
---

# 059 Local Key Custody Hardening

**Deferred / not scheduled.** Follow-up to
[[Specs/058 At-Rest Secret Encryption/058 At-Rest Secret Encryption|spec 058]]: adds **stronger,
opt-in custody options for the local master key** beyond the v1 default (a `0600` key file +
`ANVIL_MASTER_SECRET` env override). Introduces a pluggable **local key provider** with two additional
providers — an **OS keyring** provider (macOS Keychain / Linux Secret Service / Windows Credential
Manager) and a **passphrase-derived** provider (Argon2id KDF, nothing secret stored at rest).

This spec exists so the deferred work is captured with rationale and acceptance criteria; it is **not
on the active roadmap** and should only be activated on a concrete request (e.g. a local user who needs
the master key off plaintext disk, or a regulated single-tenant install).

## Owned

- **FRs**: FR-001..FR-007 (pluggable local key provider; OS-keyring + passphrase providers; headless
  fallback) — see [[059 Local Key Custody Hardening - spec|spec]]

## Dependencies

- [[Specs/058 At-Rest Secret Encryption/058 At-Rest Secret Encryption|058 At-Rest Secret Encryption]] —
  the `EncryptionService` Protocol and `KeyRing` this spec plugs new key sources into
- [[Decisions/ADR-041-simplicity-first-boring-technology|ADR-041]] — keeps these strictly opt-in

## Artifacts

- [[059 Local Key Custody Hardening - spec|spec]]

## References

- [[Specs/Specs|Specs]]
- [[Decisions/ADR-044-at-rest-secret-encryption|ADR-044]]
