---
title: 024 Unified Interface Local TLS
type: spec
tags:
  - type/spec
  - domain/vault
spec-refs:
  - docs/vault/Specs/024 Unified Interface Local TLS/
status: draft
created: '2026-06-21'
updated: '2026-06-22'
aliases:
  - 024 Unified Interface Local TLS
---

# 024 Unified Interface Local TLS

## Summary

- Q: How should TLS work locally without external binaries (Caddy/nginx/mkcert)? → A: uvicorn serves HTTPS using a self-signed certificate auto-generated on first run via the `cryptography` library (already in the dependency tree). Pure pip-install. Browser trust prompt is accepted for local-first; an opt-in trust path may be documented later.

## Scope split (2026-06-28)

[[Decisions/ADR-037-unified-interface-local-tls|ADR-037]] has two halves. This spec
(024) now owns ONLY the **local TLS** half — self-signed cert generation, uvicorn
HTTPS, scheme-awareness, and the `ANVIL_TLS` toggle. The **single-origin reverse-proxy
registry** half (FR-001/FR-002/FR-003 below — generic registry, loopback-only
upstreams, MLflow proxy) is now OWNED by
[[Specs/056 Reverse-Proxy Registry/056 Reverse-Proxy Registry|Spec 056 — Reverse-Proxy Registry]].
024 consumes 056's scheme-aware unified-origin URL behavior (FR-006) and cross-references
it; 024 does not implement the proxy itself.

## Artifacts

- [[024 Unified Interface Local TLS - spec|spec]]

## References

- [[Decisions/ADR-037-unified-interface-local-tls|ADR-037 — Unified Single-Origin Interface]]
- [[Specs/056 Reverse-Proxy Registry/056 Reverse-Proxy Registry|056 Reverse-Proxy Registry]] (proxy half of ADR-037)
- [[Specs/Specs|Specs]]
