---
code-refs:
  - anvil/services/backup/backup_service.py
  - anvil/db/migration.py
created: '2026-06-27'
source: agent
status: draft
tags:
  - type/discovery
  - domain/database
  - status/draft
title: Alembic script_location must be absolute when used outside MigrationService
type: discovery
updated: '2026-06-27'
aliases: Alembic script_location must be absolute when used outside MigrationService
---
When reading the Alembic HEAD revision via `ScriptDirectory` outside of
the `MigrationService` (e.g., from `_get_alembic_head()` in the backup
service), the `alembic.ini` file's relative `script_location =
migrations` does not resolve correctly because the current working
directory may not be the package root.

The fix is to override `script_location` to the absolute path of the
migrations directory when constructing the Alembic Config:

```python
cfg = AlembicConfig(ini_path)
cfg.set_main_option("script_location", abs_migrations_dir)
```

Without this override, `ScriptDirectory.from_config(cfg)` raises
`CommandError: Path doesn't exist: migrations`.

## References

- `anvil/services/backup/backup_service.py` (`_get_alembic_head()`)
- `anvil/db/migration.py` (`_build_config()` — same pattern)
