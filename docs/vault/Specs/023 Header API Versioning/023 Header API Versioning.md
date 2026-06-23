---
title: 023 Header API Versioning
type: spec
tags:
  - type/spec
  - domain/tooling
spec-refs:
  - docs/vault/Specs/023 Header API Versioning/
status: draft
created: '2026-06-21'
updated: '2026-06-22'
aliases:
  - 023 Header API Versioning
---

# 023 Header API Versioning

## Summary

- Q: Maintain backward compatibility / `/v1/` redirects during the migration? → A: No. Greenfield project (per ADR-032) — no users, no deployments, no released API contract. Remove `/v1/` outright with no alias, redirect, deprecation window, or compatibility layer.

## Artifacts

- [[023 Header API Versioning - spec|spec]]

## References

- [[Specs/Specs|Specs]]
