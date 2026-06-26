---
aliases:
  - 'Session: MLflow get_latest_versions Deprecation Fix'
  - MLflow Deprecation Fix
created: '2026-06-20T00:00:00.000Z'
source: agent
tags:
  - type/session-log
  - domain/mlops
  - domain/inference
title: 'Session: MLflow get_latest_versions Deprecation Fix'
type: session-log
updated: '2026-06-20T00:00:00.000Z'
---
# Session: MLflow `get_latest_versions` Deprecation Fix

**Date**: 2026-06-20
**Status**: Completed

## Summary

Replaced two deprecated `mlflow.tracking.client.MlflowClient.get_latest_versions` calls with `search_model_versions` + sort-by-version, eliminating `FutureWarning` noise at startup.

## Changes

### `anvil/services/tracking/tracking.py:1080-1089`
- Replaced `client.get_latest_versions(name)` with `client.search_model_versions(f"name='{name}'")`
- Added `sorted(..., key=lambda v: int(v.version), reverse=True)` to get the latest version
- The `.version` attribute is a string, so `int()` cast is required for numeric sorting

### `anvil/services/inference/inference.py:194-202`
- Same pattern: `get_latest_versions(model_name)` → `search_model_versions(f"name='{model_name}'")` + sort

### Verification
- `grep` confirms zero remaining `get_latest_versions` calls in the codebase
- `search_model_versions` was already used in 4 other places (consistent pattern)
- The `ModelVersion` object returned by `search_model_versions` has the same interface (`.run_id`, `.version`, etc.) as `get_latest_versions`, so no downstream changes needed

## References
- `anvil/services/tracking/tracking.py:1080-1089`
- `anvil/services/inference/inference.py:194-202`
- `docs/vault/Discoveries/mlflow-get-latest-versions-deprecation.md`

## Related

- [[Discoveries/mlflow-get-latest-versions-deprecation|MLflow get_latest_versions Deprecation]] — discovery note from this session
- [[Reference/MlflowIntegration|MLflow Tracking]] — MLflow integration overview
- [[Decisions/ADR-016-mlflow-primary-lineage|ADR-016: MLflow as Primary Lineage Source of Truth]] — related architecture decision
