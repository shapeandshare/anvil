---
title: 056 Reverse-Proxy Registry
type: spec
tags:
  - type/spec
  - domain/architecture
  - domain/infrastructure
  - domain/operations
spec-refs:
  - docs/vault/Specs/056 Reverse-Proxy Registry/
status: draft
created: '2026-06-28'
updated: '2026-06-28'
aliases:
  - 056 Reverse-Proxy Registry
  - Reverse-Proxy Registry & Single-Origin Front Door
  - Single-Origin Front Door
---

# 056 Reverse-Proxy Registry & Single-Origin Front Door

## Summary

The single foundational owner of the **reverse-proxy layer**: a registry of mounted upstream services exposed under sub-paths of one authenticated origin. This generalizes the one-off MLflow proxy (ADR-035) into the reusable registry mandated by ADR-037, and becomes the single home for the proxy mechanism that specs 020, 024, and 036 previously each re-specified.

- **Generic proxy registry** — an in-process FastAPI `httpx.AsyncClient` reverse proxy keyed by mount prefix; new upstreams register without bespoke per-service wiring (ADR-037 FR-003).
- **MLflow as first registered upstream** — `/v1/mlflow-proxy/{path:path}` forwarding to a loopback/private MLflow launched with `--static-prefix`; port `5001` no longer published. This is the concrete remediation for OWASP A05-001 / A07 (spec 020 FR-004).
- **Single origin** — secondary services bind loopback-only with unpublished ports; the app is the sole externally reachable endpoint, under the app's auth middleware.
- **Mode-aware, shared code** — local and SaaS share one front-door + registry; only configuration differs (loopback upstream + self-signed TLS locally vs Cloud Map upstream + edge TLS in SaaS). TLS itself is owned by spec 024.

## Key decisions

- **Owns the proxy mechanism** previously triple-specified in 020 (T009), 036 (FR-057a–g), and 024 (FR-003). Those specs now reference 056 rather than restating the mechanism.
- **Supersedes ADR-035** in spirit: ADR-035 (one-off MLflow proxy) is superseded by ADR-037 (generic single-origin front door); 056 is the implementation spec for ADR-037's proxy-registry half. TLS (the other half of ADR-037) stays in spec 024.
- **CSRF exemption** for the proxy prefix is preserved (already present as dead code in `anvil/api/auth.py`) and activated once the route exists.
- **Resolves the 012-vs-024 port conflict**: MLflow port `5001` MUST NOT be published; 056 is the governing architecture, spec 012's Docker contracts defer to it.

## Implementation status

**Spec status:** ⏳ waiting — not yet started. The codebase currently ships only a dead-code CSRF-exempt prefix (`/v1/mlflow-proxy` in `anvil/api/auth.py`) with no route behind it; MLflow still launches `--host 0.0.0.0 --allowed-hosts "*"` and port `5001` is still published in `compose.yaml`.

## Open items

- Exact registry API shape (decorator vs explicit `register_upstream()` call) — finalized in plan.
- Whether the proxy prefix de-versions to `/mlflow-proxy/` now or after spec 023 lands (ADR-036).
- Per-instance proxy/port interaction with spec 028 (Concurrent Isolated Instances).

## References

- [[056 Reverse-Proxy Registry - spec|spec]]
- [[056 Reverse-Proxy Registry - tasks|tasks]]
- [[Decisions/ADR-037-unified-interface-local-tls|ADR-037 — Unified Single-Origin Interface]]
- [[Decisions/ADR-035-mlflow-reverse-proxy|ADR-035 — MLflow Reverse Proxy (superseded)]]
- [[Specs/020 OWASP Remediation/020 OWASP Remediation|020 OWASP Remediation]] (FR-004 consumer)
- [[Specs/024 Unified Interface Local TLS/024 Unified Interface Local TLS|024 Unified Interface Local TLS]] (TLS half of ADR-037)
- [[Specs/036 SaaS Observability MLflow Proxy/036 SaaS Observability MLflow Proxy|036 SaaS Observability MLflow Proxy]] (SaaS consumer)
- [[Specs/Specs|Specs]]
