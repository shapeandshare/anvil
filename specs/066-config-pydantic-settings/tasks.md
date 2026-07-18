# Tasks — 066 Config Migration to pydantic-settings

**TDD order (Red → Green → Refactor). Each task: write the failing test FIRST.**

## Phase 0 — Setup
- [ ] T001 Re-verify current state: run `grep -rn 'get_config()' anvil --include="*.py"` and confirm the call-site inventory in `context.md` still matches. Note any drift.
- [ ] T002 Confirm Decision 3 (dual-run) with owner. Check `anvil/api/static/` for any frontend dependency on config shape (none expected — config is server-side).

## Phase 1 — AppConfig model (Red-Green-Refactor)
- [ ] T010 **[Red]** Write `tests/unit/test_config.py::test_appconfig_defaults` — asserts `AppConfig()` yields port=8080, host="127.0.0.1", etc. with no env set. Confirm it FAILS (AppConfig doesn't exist).
- [ ] T011 **[Red]** Write `test_appconfig_env_override` — `ANVIL_PORT=9090` → `AppConfig().port == 9090`.
- [ ] T012 **[Red]** Write `test_appconfig_invalid_port_raises` — `ANVIL_PORT=abc` → `ValidationError`.
- [ ] T013 **[Red]** Write `test_appconfig_workspace_overlay` — `ANVIL_WORKSPACE_DIR` set → workspace path defaults applied, env overrides win.
- [ ] T014 **[Red]** Write `test_appconfig_mlflow_port_derived` — `mlflow_port` derived from `mlflow_uri`.
- [ ] T015 **[Red]** Write `test_appconfig_retention_empty_is_none` — empty `ANVIL_BACKUP_RETENTION_MAX_COUNT` → `None`.
- [ ] T020 **[Green]** Implement `AppConfig(BaseSettings)` in `anvil/config.py` with all 18 fields, validators, computed `mlflow_port`, workspace overlay. Make T010-T015 pass.
- [ ] T021 **[Refactor]** Extract workspace-overlay logic into a clean helper; ensure `mypy --strict` passes.

## Phase 2 — Backward-compat shim
- [ ] T030 **[Red]** Write `test_get_config_shim_matches_appconfig` — `get_config()["port"] == AppConfig().port` for all keys.
- [ ] T031 **[Green]** Reimplement `get_config()` as a shim returning `AppConfig().model_dump()` (or dict view). Keep `@lru_cache` semantics. Make T030 pass.
- [ ] T032 Verify all existing tests still pass: `make test`.

## Phase 3 — Remove global mutable state (FR-004)
- [ ] T040 **[Red]** Write a test for MLflow URI resolution that does not depend on `_resolved_mlflow_uri` global.
- [ ] T041 **[Green]** Replace `_resolved_mlflow_uri` + `set_resolved_mlflow_uri()` + `get_mlflow_uri()` with app-state storage or a `MLflowUriResolver` service. Update the supervisor caller.
- [ ] T042 Verify supervisor integration still works (the supervisor sets the resolved URI after MLflow starts).

## Phase 4 — Migrate call sites (incremental)
- [ ] T050 Migrate `anvil/db/session.py:66`, `anvil/db/migration.py:403` (state_db_path) to `AppConfig`.
- [ ] T051 Migrate `anvil/api/v1/experiments.py` (5×), `health_ops.py` (5×), `_environment.py` (mlflow keys).
- [ ] T052 Migrate `anvil/services/content/*` (content_dir ×2), `anvil/workbench.py:404`.
- [ ] T053 Migrate `anvil/supervisor/supervisor.py` (log_dir ×2), remaining call sites.
- [ ] T054 After ALL call sites migrated, remove the `get_config()` shim (FR-006).

## Phase 5 — Gates
- [ ] T060 `make lint && make typecheck && make test && make vault-audit` all green.
- [ ] T061 Confirm SC-004: `anvil/config.py` line count did not increase.

## Verification (Success Criteria)
- SC-001: zero `get_config()["..."]` call sites remain (`grep` returns nothing).
- SC-002: invalid env var → `ValidationError` at startup.
- SC-003: `_resolved_mlflow_uri` global removed.
- SC-004: config.py line count ≤ original.
