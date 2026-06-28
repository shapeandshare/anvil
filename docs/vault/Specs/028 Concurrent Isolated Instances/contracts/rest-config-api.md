# Contract: Configuration REST API

Per-instance config CRUD (FR-010–FR-017, US2/US3). New router `anvil/api/v1/config.py` (`router = APIRouter()`), included in `router.py`; DTOs in `schemas.py`. Auth via existing middleware (page/API auth model unchanged). Mutations are CSRF-aware (client uses `window.apiFetch`). Each endpoint targets the **serving instance's own** config; never another instance's.

All routes operate through `RuntimeConfigService` (DB-backed, non-cached) for editable settings and the boot snapshot in `app.state` for pending-restart computation.

## `GET /v1/config`

List every configurable setting with effective value + provenance (FR-010).

**200** → `{ "settings": [ConfigSettingOut, ...], "pending_restart": [<key>, ...] }`

`ConfigSettingOut` (Pydantic): `key: str`, `value: str`, `source: "default"|"env"|"override"`, `apply_class: "boot_critical"|"mlflow_restart"|"applies_live"`, `pending_restart: bool`, `editable: bool`.

## `GET /v1/config/{key}`

Single setting. **200** → `ConfigSettingOut`. **404** if unknown key.

## `PUT /v1/config/{key}`

Create/update an override (FR-011, FR-013, FR-014).

**Body** `UpdateConfigBody`: `{ "value": <string> }`
**Behavior**: validate type/range; for ports/workspace validate against the registry for collisions; persist override (boot-critical → boot file pending; non-boot → `runtime_config` table). If `apply_class == mlflow_restart` → auto-restart the MLflow sidecar and report applied (FR-016). If `boot_critical` → mark pending_restart (FR-017). Audit `CONFIG_SET`.
**200** → `{ "key", "value", "applied": bool, "pending_restart": bool, "mlflow_restarted": bool }`
**400** → `{ "detail": { "error": "<specific validation message>" } }` (e.g. invalid port, port in use by `<instance>`, workspace collision). No partial persistence.

## `POST /v1/config/{key}/reset`

Remove the override → fall back to env/default (FR-012). Audit `CONFIG_RESET`.
**200** → `ConfigSettingOut` (now showing `source` = `env`/`default`). **404** if no override exists.

## `GET /v1/config/pending-restart`

Summary of all settings whose saved value differs from the startup snapshot (FR-017, research.md D).
**200** → `{ "pending": [ { "key", "current_value", "saved_value" } ], "action_required": "Restart the instance to apply." }`

## Error model

Reuses the existing `HTTPException(status_code, detail=...)` convention. `409` for busy/conflict (e.g. MLflow restart in progress), `400` for validation, `404` for unknown key/override. Mutations never apply on validation failure.
