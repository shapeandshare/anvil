---
title: ADR-005 — Source-keyed model registry consolidation
type: decision
tags:
- type/decision
- domain/registry
created: 2026-06-13
updated: 2026-06-13
aliases:
- ADR-005 — Source-keyed model registry consolidation
source: agent
code-refs:
- anvil/services/tracking/tracking_service.py
- anvil/db/models/registry.py
- anvil/api/v1/registry.py
---

# ADR-005: Source-keyed model registry consolidation

**Status**: Accepted

## Context

Two parallel model-record systems existed: MLflow auto-registered per-run as `anvil-experiment-{id}` (one throwaway model per run), and local `RegisteredModel`/`ModelVersion` DB tables written via manual `POST /v1/registry/models`. This created registry pollution and potential contradictions.

## Decision

- Single source of truth: the MLflow Model Registry
- Registered model name = stable per-source key based on immutable DB id: `dataset-<id>`, `corpus-<id>`, `default-source`
- Auto-register every successful run as a new version under the source's registered model
- Failed/interrupted runs create zero versions
- Local `RegisteredModel`/`ModelVersion` tables: deprecated (no new writes), retained for read-only access; migration path via `migrate_local_registry_to_mlflow`

## Consequences

- 1 source → 1 registered model → N versions (clean versioning story)
- Renaming a dataset/corpus does not fork its registered model (id-based key)
- Registry is inspectable through standard MLflow UI