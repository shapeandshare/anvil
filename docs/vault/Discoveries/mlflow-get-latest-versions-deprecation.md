---
aliases:
  - MLflow get_latest_versions Deprecation
  - mlflow-get-latest-versions-deprecation
code-refs:
  - 'anvil/services/tracking/tracking.py:1080-1089'
  - 'anvil/services/inference/inference.py:194-202'
created: '2026-06-20'
session: 2026-06-20-mlflow-deprecation-fix
source: agent
status: draft
tags:
  - type/discovery
  - domain/mlops
  - status/draft
title: MLflow get_latest_versions Deprecation
type: discovery
updated: '2026-06-20'
---
## MLflow `get_latest_versions` Deprecation

`mlflow.tracking.client.MlflowClient.get_latest_versions` has been deprecated since MLflow 2.9.0 and produces a `FutureWarning` at startup. The replacement is `search_model_versions` with a `name='...'` filter string, followed by sorting descending on `int(v.version)`.

### The migration pattern

```python
# Before (deprecated):
latest_versions = client.get_latest_versions(model_name)
latest = latest_versions[0]

# After:
all_versions = client.search_model_versions(f"name='{model_name}'")
sorted_versions = sorted(all_versions, key=lambda v: int(v.version), reverse=True)
latest = sorted_versions[0]
```

`search_model_versions` returns an iterable of `ModelVersion` objects (same type as `get_latest_versions`), so `.run_id`, `.version`, etc. are all available identically. The `.version` attribute is a string, hence the `int()` cast for numeric sorting.

### Files changed

- `anvil/services/tracking/tracking.py:1080-1089` — `_list_registered_models` (or similar method iterating registered models)
- `anvil/services/inference/inference.py:194-202` — `_resolve_run_artifacts` (or similar method resolving latest model version)

### Why not `get_model_version_by_alias`?

The codebase already uses `search_model_versions` in 4 other places (`tracking.py:1105`, `registry.py:194`, `registry.py:292`, migration script). Using `search_model_versions` + sort is consistent with the existing pattern and avoids introducing a new API surface. Aliases are not used anywhere in the project.
