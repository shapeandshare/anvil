---
aliases:
  - 'Dataset Deletion Orphans File Artifacts'
code-refs:
  - anvil/services/datasets/datasets.py
created: '2026-06-19'
source: agent
status: draft
tags:
  - type/discovery
  - domain/database
title: Dataset Deletion Orphans File Artifacts
type: discovery
updated: '2026-06-19'
---
# Discovery: Dataset Deletion Orphans File Artifacts

## What was found

`DatasetService.delete_dataset()` in `anvil/services/datasets/datasets.py` drops the database row but **never calls `LocalFileStore.delete()`** for the dataset's stored sample artifacts. After deletion, orphaned files remain under `data/datasets/{dataset_id}/`.

## Impact

- Storage waste: orphaned artifacts accumulate but are never garbage-collected.
- Data-leak risk: deleted datasets' content persists on disk.
- Violates FR-021/SC-005 (zero orphaned artifacts after deletion).

## Resolution

Feature `010-responsible-data-governance` closes this gap: `DatasetService.delete_dataset()` now enumerates `Sample.file_path` artifacts and deletes them via `LocalFileStore.delete()` before dropping rows.

## References
- [[Discoveries/Discoveries|Discoveries]]

- `anvil/services/datasets/datasets.py` — `delete_dataset()` method
- `docs/vault/Specs/013 Responsible Data Governance/spec.md` — FR-021, SC-005
- `docs/vault/Specs/013 Responsible Data Governance/tasks.md` — T060, T051
