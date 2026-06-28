---
title: 'Session: RestoreEngine — derive managed_dirs from extracted content'
type: session-log
tags:
  - type/session-log
  - domain/operations
created: '2026-06-27'
updated: '2026-06-27'
status: draft
source: agent
aliases:
  - restore-engine-managed-dirs-fix
---

# Session: RestoreEngine — derive managed_dirs from extracted content

**Date**: 2026-06-27
**Trigger**: Backup restore through the Ops UI fails with `[Errno 2] No such file or directory: 'data/backups/.restore-tmp/.../data'`.

## What was done

### Root cause — hardcoded `managed_dirs`

`RestoreEngine.execute()` used `managed_dirs = ["data", "mlruns"]` at two locations (lines 102, 119), with a comment claiming "Determine managed roots from restore_tmp structure" — but it never actually inspected the extracted content. When a backup archive didn't contain files under `data/` (e.g., empty subdirectories, or the archive was structured differently), the swap step tried to `os.rename()` a non-existent source directory, crashing with `ENOENT`.

### Fix — derive from actual extracted directories

- `managed_dirs` is now built from `restore_tmp.iterdir()`, filtering for directories. This adapts to whatever the archive actually contains.
- Added an early return with a clear error message when the extracted archive contains zero root directories (previously would crash).
- Replaced `Path.rename()` → `shutil.move()` for cross-filesystem safety (fallback to copy+delete).
- Rollback path (`except` block) also derives `managed_dirs` dynamically from restore_tmp (guarded by `exists()`).

### Files changed

- `anvil/services/backup/restore_engine.py` — removed `managed_dirs = ["data", "mlruns"]` hardcoding, added dynamic directory enumeration.

## Related

- [[2026-06-27-backup-restore-ui-fixes-and-async-debt]]
- [[2026-06-27-backup-ui-csp-fixes]]
- [[ADR-040-deployment-backup-restore]]