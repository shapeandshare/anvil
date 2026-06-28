---
title: 028 Concurrent Isolated Instances
type: spec
tags:
  - type/spec
  - domain/operations
  - domain/infrastructure
spec-refs:
  - docs/vault/Specs/028 Concurrent Isolated Instances/
status: draft
created: '2026-06-27'
updated: '2026-06-27'
aliases:
  - 028 Concurrent Isolated Instances
---

# 028 Concurrent Isolated Instances

## Summary

Run multiple stand-alone instances of the full anvil stack concurrently on one host, each as a separate OS process group rooted at its own workspace directory with isolated ports, database, storage, model artifacts, content repository, experiment-tracking store, API key, backups, and logs. Instances are independently targetable by base URL and unaffected by each other's lifecycle. Each instance exposes UI CRUD over its own configuration (persisted in its per-instance database, layered over env + defaults); the experiment-tracking sidecar auto-restarts on relevant changes while boot-critical settings (web port, database location, workspace root) are marked "pending restart" and applied via a documented restart. Instance lifecycle (create/list/start/stop/restart/destroy) is CLI-first for agent automation. Port and workspace collisions are actively prevented, and a write-isolation audit guarantees no persistent write escapes the instance workspace.

## Resolved Decisions

- **Isolation model** → Separate OS processes, one workspace directory each.
- **Restart authority** → Save config to the per-instance DB; auto-restart the tracking sidecar; mark boot-critical settings "pending restart" (no speculative hot-reload).
- **Config persistence** → Per-instance application database (config layered over env + defaults).
- **Management surface** → CLI-first instance lifecycle; per-instance config UI (CRUD on the serving instance).
- **Concurrency safety** → Port collision prevention + workspace/path collision prevention + full write-isolation audit + instance registry/locks.

## Relationship to other specs

- **016 SaaS Architecture** — distinct concern (cloud, multi-user auth via Cognito); this feature is local concurrent stack isolation on a single host.
- **027 Deployment Backup Restore** — reference pattern for ops-UI + CLI parity, atomic operations, and audit logging; backup paths must derive from the instance workspace.
- **024 Unified Interface Local TLS** — per-instance TLS/bindings interact with per-instance ports.

## Artifacts

- [[028 Concurrent Isolated Instances/spec|spec]]

## References

- [[Specs/Specs|Specs]]
