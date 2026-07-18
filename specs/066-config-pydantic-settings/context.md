# Context — 066 Config Migration to pydantic-settings

> Cold-start handoff context. Cross-references: `../066-codebase-remediation/data-inventory.md` §1, `../066-codebase-remediation/shared-decisions.md` Decision 3.

## Current State (quoted)

`anvil/config.py:121-213` — the offending function:
```python
@lru_cache
def get_config() -> dict[str, Any]:
    ...
    return {
        "port": int(os.getenv("ANVIL_PORT", "8080")),
        "host": os.getenv("ANVIL_HOST", "127.0.0.1"),
        "state_db_path": os.getenv("ANVIL_STATE_DB_PATH") or _ws_state_db,
        "log_dir": os.getenv("ANVIL_LOG_DIR", _ws_log_dir),
        "mlflow_uri": default_mlflow_uri,
        "mlflow_port": _parse_port_from_uri(default_mlflow_uri),
        "mlflow_backend_store_uri": _ws_mlflow_backend,
        "mlflow_disable_local": mlflow_disable_local,
        "db_auto_migrate": os.getenv("ANVIL_DB_AUTO_MIGRATE", "true").lower() in (...),
        "storage_backend": os.getenv("ANVIL_STORAGE_BACKEND", "local"),
        "device": os.getenv("ANVIL_DEVICE", ""),
        "content_dir": os.getenv("ANVIL_CONTENT_DIR", _ws_content_dir),
        "backup_dir": os.getenv("ANVIL_BACKUP_DIR", _ws_backup_dir),
        "backup_quota_bytes": int(os.getenv("ANVIL_BACKUP_QUOTA_BYTES", str(10 * 1024**3))),
        "backup_quota_warn_fraction": float(os.getenv("ANVIL_BACKUP_QUOTA_WARN", "0.8")),
        "backup_retention_max_count": (int(v) if (v := os.getenv("ANVIL_BACKUP_RETENTION_MAX_COUNT")) else None),
        "backup_retention_max_age_days": (int(v) if (v := os.getenv("ANVIL_BACKUP_RETENTION_MAX_AGE_DAYS")) else None),
        "workspace_root": str(wp.root) if wp else "",
    }
```

Global mutable state (`config.py:35-67`):
```python
_resolved_mlflow_uri: str | None = None
def set_resolved_mlflow_uri(uri: str) -> None: ...   # called by supervisor
def get_mlflow_uri() -> str: ...                       # reads _resolved_mlflow_uri then falls back
```

## Reference Implementation

`anvil/client/_shared/server_config.py` — a working `BaseModel` + `field_validator` + `from_env()` factory pattern. Study lines 19-80. Adapt to `BaseSettings` (pydantic-settings) with `env_prefix="ANVIL_"` or per-field `validation_alias`.

## Call Sites to Migrate

18 config keys; 25 subscript call sites across 12 files + 15 non-subscript. Full table in `data-inventory.md §1`. Re-verify before editing:
```bash
grep -rn 'get_config()\[' anvil --include="*.py"
```

## Key Constraints

- **Workspace overlay** (`config.py:106-118, 171-184`): when `ANVIL_WORKSPACE_DIR` set, `WorkspacePaths` provides path defaults; env vars still win. This precedence MUST be preserved in `AppConfig`.
- **`.env` loading**: `load_dotenv()` at `config.py:30` — `pydantic-settings` `SettingsConfigDict(env_file=".env")` replaces this.
- **`@lru_cache`**: current caching behavior — `BaseSettings` instances are cheap; use a module-level cached singleton or `@lru_cache` on a factory.
- **Test env**: `tests/conftest.py:22` sets `ANVIL_MLFLOW_URI=sqlite:///:memory:` — must still resolve.

## Decision Reference

Per `shared-decisions.md` Decision 3: **dual-run transition**. `get_config()` becomes a shim over `AppConfig().model_dump()` so existing subscript call sites keep working; migrate incrementally; remove `get_config()` last.

## Gotchas

- `mlflow_port` is DERIVED from `mlflow_uri` via `_parse_port_from_uri()` (`config.py:97-103`) — model this as a computed field (`@computed_field` or `@property`).
- `backup_retention_max_count`/`max_age_days` use walrus-empty-string → `None` semantics. Model with `int | None` and a validator that maps `""` → `None`.
- `_resolved_mlflow_uri` is set at runtime by the supervisor AFTER startup — cannot be a static settings field. Move to app state or a small dedicated `MLflowUriResolver` (see FR-004).
