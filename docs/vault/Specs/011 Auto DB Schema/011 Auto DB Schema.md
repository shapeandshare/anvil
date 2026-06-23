---
title: 011 Auto DB Schema
type: spec
tags:
  - type/spec
  - domain/vault
spec-refs:
  - docs/vault/Specs/011 Auto DB Schema/
status: draft
created: '2026-06-18'
updated: '2026-06-22'
aliases:
  - 011 Auto DB Schema
---

# 011 Auto DB Schema

## Summary

A developer clones the repo, installs dependencies, and runs `anvil` (the web server) without first running `make setup`. The database file doesn't exist yet. The app should detect this, create the database, and apply all pending Alembic migrations so the server starts successfully.

## Artifacts

- [[011 Auto DB Schema - data-model|data-model]]
- [[011 Auto DB Schema - plan|plan]]
- [[011 Auto DB Schema - quickstart|quickstart]]
- [[011 Auto DB Schema - research|research]]
- [[011 Auto DB Schema - spec|spec]]
- [[011 Auto DB Schema - tasks|tasks]]

## References

- [[Specs/Specs|Specs]]
