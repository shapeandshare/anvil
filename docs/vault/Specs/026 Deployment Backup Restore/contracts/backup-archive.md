# Contract: Backup Archive Format & Manifest

**Feature**: 026-deployment-backup-restore | **Phase**: 1

Defines the on-disk contract for a backup archive so it is stable, verifiable, and forward-compatible. Producers: `anvil/services/backup/archive_writer.py`. Consumers: `archive_reader.py`, `restore_engine.py`, and the Verify action.

---

## 1. Archive File

- **Format**: gzip-compressed POSIX tar (`.tar.gz`), created via stdlib `tarfile` (mode `w:gz`).
- **Filename**: `backup-<backup_id>.tar.gz` where `backup_id = <UTC timestamp compact>-<6-char random hex>`, e.g. `backup-20260621T143000Z-a1b2c3.tar.gz`.
- **Location**: `<backup_dir>/` (default `data/backups/`).
- **Immutability**: written atomically — assembled in `<backup_dir>/.tmp/<backup_id>.tar.gz.part`, then `os.replace`d to the final name. Never modified after creation (FR-022). A reader MUST treat archives as read-only.
- **Temp/partial cleanup**: `.tmp/` is swept on service init and on any failure (FR-013).

---

## 2. Archive Member Layout

```text
manifest.json          # MUST be the first member; UTF-8 JSON
data/anvil-state.db     # single merged SQLite file (no -wal/-shm)
data/models/**          # model artifacts (recursively)
data/datasets/**        # dataset files
data/storage/**         # blob store
data/content/**         # content repository blobs
mlruns/mlflow.db        # MLflow backend SQLite (merged)
mlruns/**               # MLflow artifacts
```

- All member paths are **relative**, forward-slash, rooted at the archive top. No absolute paths, no `..` components (enforced on read — reject archives containing path traversal).
- Empty managed directories are represented by their directory entry so structure is preserved on restore.
- A managed root that does not exist at backup time is simply absent from the archive (not an error).

---

## 3. `manifest.json` Schema

Serialized `BackupManifest` (see data-model.md §3). Example:

```json
{
  "manifest_version": 1,
  "backup_id": "20260621T143000Z-a1b2c3",
  "created_at": "2026-06-21T14:30:00Z",
  "operation_type": "backup",
  "deployment_version": "1.7.0",
  "schema_revision": "002",
  "total_uncompressed_bytes": 901234567,
  "entries": [
    { "path": "data/anvil-state.db", "sha256": "9f86d0…", "size": 104857600 },
    { "path": "mlruns/mlflow.db",   "sha256": "2c26b4…", "size": 2097152 },
    { "path": "data/models/run-12/model.safetensors", "sha256": "…", "size": 524288 }
  ]
}
```

**Rules**:
- `entries` covers **every regular file** in the archive **except** `manifest.json` itself.
- `path` values match archive member names exactly.
- `sha256` is the hex digest of the uncompressed file bytes.
- `manifest_version` gates forward compatibility: a reader encountering a higher `manifest_version` than it supports MUST refuse and report a clear message (do not guess).

---

## 4. Integrity & Verification

- **Top-level manifest checksum**: `manifest_sha256` = SHA-256 of the exact `manifest.json` bytes, stored in the `backup_operations` DB row at creation. Detects manifest tampering independent of the archive.
- **Verify (FR-025)**: stream each archive member, recompute SHA-256, compare to the matching `entries[i].sha256`.
  - All match → `VerifyResult.valid = true`.
  - Any mismatch, missing entry, or extra unlisted file → `valid = false`, offending paths in `mismatched`, and the backup's `status` transitions to `corrupted` (FR-026).
- **Restore-time verification (FR-024)**: the same per-file check runs against the **extracted temp copy** BEFORE any live file is swapped. Failure aborts the restore with the live deployment untouched.

---

## 5. Compatibility Check Inputs (FR-023)

On restore, `restore_engine` compares:
- `manifest.schema_revision` vs the running deployment's current Alembic head → primary signal.
- `manifest.deployment_version` vs `anvil.__version__` → secondary/informational.

Mapping to `SchemaCompatibility`:
| Condition | Result |
|---|---|
| schema_revision == current head | `OK` |
| schema_revision == current head, version differs | `WARN` |
| schema_revision != current head | `BLOCKED` |

`BLOCKED` ⇒ API `409`, CLI exit `7`, wizard shows red gate and disables "Start Restore".

---

## 6. Forward-Compatibility Guarantees

- `manifest_version` is the single evolution knob. New optional fields MAY be added at `manifest_version` 1 if readers ignore unknown fields (Pydantic models for the manifest use `extra="ignore"` for reads of newer-but-compatible manifests).
- Adding a new managed root in a future version: older readers will still restore the roots they know; the new root would simply be ignored by an old reader. New writers MUST list it in `entries`.
- The archive container format (`tar.gz`) is fixed for v1.
