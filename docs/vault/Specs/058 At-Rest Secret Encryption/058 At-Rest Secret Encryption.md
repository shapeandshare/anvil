---
title: 058 At-Rest Secret Encryption
type: spec
tags:
  - type/spec
  - domain/database
  - domain/infrastructure
  - domain/architecture
spec-refs:
  - docs/vault/Specs/058 At-Rest Secret Encryption/
status: draft
created: '2026-06-29'
updated: '2026-06-29'
aliases:
  - 058 At-Rest Secret Encryption
---

# 058 At-Rest Secret Encryption

Hardens per-user secret encryption (the `user_secrets` table) into a **rotatable, self-describing,
mode-aware** scheme. Replaces the current single-key, format-less AES-256-GCM blob with a versioned
JSON envelope carrying a key id (`kid`), a `current`/`previous` **key ring**, AAD bound to row identity,
and a background re-encryption sweep. In SaaS mode the same envelope is produced by a **KMS-backed
envelope-encryption** service (DEK ring unwrapped via the ECS task IAM role), so no static master key
is ever stored by the application.

> **Greenfield assumption**: no pre-existing encrypted data or deployments. There is **no `v0`/legacy
> read path and no data migration** — the envelope ships at `v:1` with a `kid` from day one
> (consistent with [[Decisions/ADR-032-greenfield-legacy-removal|ADR-032]]).

## Owned

- **FRs**: FR-001..FR-008 (envelope + local key ring), FR-010..FR-015 (rotation),
  FR-020..FR-026 (SaaS KMS envelope), FR-030..FR-031 (cross-cutting safety)
- **Decision**: [[Decisions/ADR-044-at-rest-secret-encryption|ADR-044]]

## Dependencies

- [[Specs/042 Model Asset Storage/042 Model Asset Storage|042 Model Asset Storage]] — introduced
  `UserSecret` + the original `EncryptionService` this spec supersedes
- [[Decisions/ADR-030-saas-architecture|ADR-030]] / [[Reference/SaaSArchitectureDecisions|SaaS
  Architecture Decisions (AD-1..AD-17)]] — three-mode model; `anvil/_saas/` isolation; `[aws]` extra
- [[Specs/037 SaaS Resilience DR/037 SaaS Resilience DR|037 SaaS Resilience DR]] — the existing
  dual-key `{current, previous}` rotation pattern this spec reuses for consistency
- [[Decisions/ADR-041-simplicity-first-boring-technology|ADR-041]] — Simplicity First gate

## Deferred to a follow-up spec

- [[Specs/059 Local Key Custody Hardening/059 Local Key Custody Hardening|059 Local Key Custody
  Hardening]] — OS-keyring and passphrase-derived local key custody (opt-in, not scheduled)

## Artifacts

- [[058 At-Rest Secret Encryption - spec|spec]]

## References

- [[Specs/Specs|Specs]]
- [[Decisions/README|Decisions]]
