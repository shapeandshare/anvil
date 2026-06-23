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

## Artifacts

- [[024 Unified Interface Local TLS - spec|spec]]

## References

- [[Specs/Specs|Specs]]
