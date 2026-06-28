---
title: >-
  Session: Reverse-Proxy Registry Consolidation — Spec 056, ADR-037
  Integration & Cross-Spec Cleanup
type: session-log
tags:
  - type/session-log
  - domain/architecture
  - domain/infrastructure
  - domain/operations
created: '2026-06-28'
updated: '2026-06-28'
aliases:
  - >-
    Session: Reverse-Proxy Registry Consolidation
  - reverse-proxy-registry-consolidation
status: draft
source: agent
---

# Session: Reverse-Proxy Registry Consolidation — Spec 056, ADR-037 Integration & Cross-Spec Cleanup

**Date**: 2026-06-28
**Trigger**: Audit of ADR-035 (MLflow reverse proxy) found it superseded by ADR-037
(generic single-origin front door), yet 3 specs (020, 024, 036) independently re-specified
the same proxy mechanism, and ADR-035 was still cited as binding. Also discovered a hard
conflict between Spec 012 (mandates publishing MLflow port 5001) and Spec 024 (mandates
loopback-only, port unpublished).

## What was done

### 1. Spec inventory and cross-spec coverage mapping

Three parallel explore agents produced:
- A complete inventory of all 55 specs (all `draft`, most without implementation)
- A cross-spec coverage matrix for every proxy/TLS/MLflow requirement
- A codebase implementation-state audit confirming the proxy is 100% on paper (MLflow
  still launches `--host 0.0.0.0 --allowed-hosts "*"`, port 5001 published, no proxy
  route or TLS infrastructure, only dead-code CSRF-exempt prefix)

### 2. New foundational spec: 056 Reverse-Proxy Registry & Single-Origin Front Door

Authored three files:
- `docs/vault/Specs/056 Reverse-Proxy Registry/056 Reverse-Proxy Registry.md` — overview
- `docs/vault/Specs/056 Reverse-Proxy Registry/056 Reverse-Proxy Registry - spec.md` — 13 FRs,
  7 SCs, 3 user stories, full edge case treatment
- `docs/vault/Specs/056 Reverse-Proxy Registry/056 Reverse-Proxy Registry - tasks.md` — 13 tasks
  across 4 phases (registry core → auth/CSRF → MLflow as first upstream → validation)

Spec 056 owns the proxy-registry half of ADR-037; TLS remains in Spec 024.

### 3. Consumer specs re-pointed

| Spec | Change |
|------|--------|
| 020 OWASP Remediation | FR-004 retained as security requirement; T009/T009t marked superseded by 056 |
| 036 SaaS Observability | Phase 5 split — generic mechanism tasks superseded by 056; kept SaaS layers only (Cognito, org_id, Cloud Map) |
| 024 Unified Interface Local TLS | FR-001/002/003 marked owned by 056; 024 keeps TLS half; SC-005 deferred to 056 |
| 023 Header API Versioning | Proxy path move references 056 FR-013 (single mount-prefix constant) |

### 4. ADR hygiene

- Fixed ADR-035 body `## Status` from `proposed` to `superseded` with a banner linking
  to ADR-037 + Spec 056
- Updated `code-refs` on ADR-035 to include Spec 056
- Updated Decisions README row for ADR-035

### 5. Conflict resolution: Spec 012 vs Spec 024 port publishing

Amended Spec 012 artifacts:
- FR-008 in `spec.md` — port 5001 publish clause marked superseded
- `contracts/compose.md` R-C2 — marked superseded; banner at top of contract
- `contracts/dockerfile.md` R-D4 — `EXPOSE 8080 5001` → `EXPOSE 8080` only

All three defer to Spec 024/056 as the governing architecture (ADR-037).

### 6. Vault MOC registration

Added Spec 056 entry + new reverse-proxy consolidation section to `Specs.md`.

## Discoveries

- The `domain/learning` tag is not in the controlled tag vocabulary (`docs/vault/_meta/tags.md`)
  but is used by 4 specs (038, 048, 049, 055) — a pre-existing audit failure.
- ADR-035's body `## Status` said `proposed` while its frontmatter said `superseded` —
  contradictory statuses across two locations in the same file.
- `get_mlflow_browser_uri` in `anvil/config.py` still returns a bare `http://host:5001` despite
  the CSRF-exempt prefix `/v1/mlflow-proxy` being in `anvil/api/auth.py` as dead code — the
  design intent was partially committed without the implementation.

## References

- [[Specs/056 Reverse-Proxy Registry/056 Reverse-Proxy Registry|056 Reverse-Proxy Registry]]
- [[Decisions/ADR-035-mlflow-reverse-proxy|ADR-035]]
- [[Decisions/ADR-037-unified-interface-local-tls|ADR-037]]
- [[Specs/020 OWASP Remediation/020 OWASP Remediation|020 OWASP Remediation]]
- [[Specs/036 SaaS Observability MLflow Proxy/036 SaaS Observability MLflow Proxy|036]]
- [[Specs/024 Unified Interface Local TLS/024 Unified Interface Local TLS|024]]
- [[Specs/023 Header API Versioning/023 Header API Versioning|023]]
- [[Specs/012 Pip Installable Package/012 Pip Installable Package|012]]