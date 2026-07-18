# Feature Specification: Config Migration to pydantic-settings

**Feature Branch**: `066-config-pydantic-settings`  
**Created**: 2026-07-18  
**Status**: Draft  
**Priority**: P0  
**Input**: Codebase review finding #066 — `get_config()` returns `dict[str, Any]` instead of using `pydantic-settings` `BaseSettings`, despite `pydantic-settings>=2.14.2` being declared in `pyproject.toml:23`.

## User Scenarios & Testing

### User Story 1 - Type-safe config access (Priority: P1)

A developer accessing application configuration should get type-safe, validated values with IDE autocomplete rather than string-keyed `dict[str, Any]` lookups.

**Why this priority**: Every service and route consumes config. The current flat-dict approach provides no type safety, no validation, and no discoverability. Invalid env var values surface at runtime as cryptic errors.

**Independent Test**: Can instantiate `AppConfig` from env vars, access each setting as a typed attribute, and get a `ValidationError` for invalid values.

**Acceptance Scenarios**:

1. **Given** the environment has `ANVIL_PORT=abc`, **When** `AppConfig()` is instantiated, **Then** a `ValidationError` is raised indicating invalid port value.
2. **Given** the environment has `ANVIL_PORT=9090`, **When** `AppConfig().port` is accessed, **Then** it returns `9090` (int).
3. **Given** no environment variables set, **When** `AppConfig()` is instantiated, **Then** all defaults apply (port=8080, host="127.0.0.1", etc.).
4. **Given** `ANVIL_WORKSPACE_DIR` is set, **When** `AppConfig()` is instantiated, **Then** workspace-derived path defaults are applied with env-var overrides taking highest precedence.

---

### User Story 2 - Backward-compatible migration (Priority: P1)

Existing code that calls `get_config()["port"]` continues to work during a transition period.

**Why this priority**: The config is consumed by dozens of call sites. A breaking change would require simultaneous updates everywhere.

**Independent Test**: Can call both the old `get_config()["port"]` and the new `settings.port` and get the same value.

**Acceptance Scenarios**:

1. **Given** the old `get_config()` function still exists, **When** called with string keys, **Then** it returns values consistent with the new `BaseSettings` instance.
2. **Given** the new `AppConfig` class exists, **When** instantiated, **Then** it respects all existing environment variables (`ANVIL_PORT`, `ANVIL_HOST`, `ANVIL_STATE_DB_PATH`, `ANVIL_LOG_DIR`, `ANVIL_MLFLOW_URI`, `ANVIL_DB_AUTO_MIGRATE`, `ANVIL_STORAGE_BACKEND`, `ANVIL_DEVICE`, `ANVIL_CONTENT_DIR`, `ANVIL_BACKUP_DIR`, `ANVIL_BACKUP_QUOTA_BYTES`, `ANVIL_WORKSPACE_DIR`, and the CORS, rate-limit vars).

### Edge Cases

- What happens when `ANVIL_BACKUP_RETENTION_MAX_COUNT` is empty string (unset)? Should be `None`, not a parse error.
- What happens when `ANVIL_MLFLOW_URI` has a non-standard port? `mlflow_port` should parse correctly.
- What happens in the test environment where `ANVIL_MLFLOW_URI` is set to `sqlite:///:memory:`?

## Requirements

### Functional Requirements

- **FR-001**: System MUST define a `AppConfig(BaseSettings)` class in `anvil/config.py` using `pydantic-settings` `Field(validation_alias=...)` for each config key.
- **FR-002**: System MUST deprecate but retain `get_config()` returning a `dict[str, Any]` for backward compatibility during transition.
- **FR-003**: System MUST support `ANVIL_WORKSPACE_DIR` overlay: when set, `WorkspacePaths` provides path defaults, env vars override.
- **FR-004**: System MUST remove the `_resolved_mlflow_uri` global mutable state by moving MLflow URI resolution into the settings model or a dedicated service.
- **FR-005**: System MUST support `.env` file loading (preserving existing `python-dotenv` integration).
- **FR-006**: All config consumers within the package MUST be migrated from `get_config()["key"]` to `settings.key` pattern, with the old function removed at the end.

### Key Entities

- **AppConfig**: Pydantic `BaseSettings` subclass with all application settings as typed fields
- **WorkspacePaths**: Path derivation for workspace-aware instances (existing, consumed by AppConfig)
- **get_config()**: Legacy function, retained temporarily with deprecation warning

## Success Criteria

### Measurable Outcomes

- **SC-001**: All 30+ existing `get_config()["key"]` call sites migrated to new typed accessor.
- **SC-002**: Invalid env var values produce `ValidationError` at startup, not cryptic runtime errors.
- **SC-003**: `_resolved_mlflow_uri` global mutable state eliminated.
- **SC-004**: `anvil/config.py` line count does not increase (consolidation, not expansion).

## Assumptions

- `pydantic-settings` `Field(validation_alias=...)` is used for env var binding rather than nested models.
- The workspace path overlay logic is preserved in the new model (not dropped).
- Migration of call sites is done incrementally, not all at once — but the spec covers the full migration.
- The test environment's `ANVIL_MLFLOW_URI=sqlite:///:memory:` must continue to work.
