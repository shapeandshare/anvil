# Context — 079 Exception Hierarchy Unification

> Cross-references: `../066-codebase-remediation/data-inventory.md` §8, `shared-decisions.md` Decision 4.

## Current State (verified inventory)

Server-side exceptions with mixed bases (to unify under `AnvilServiceError`):
| Class | Base | File:Line |
|-------|------|-----------|
| `SafetensorsExportError` | `Exception` | `services/training/safetensors_export_error.py:13` |
| `RemotePollError` | `Exception` | `services/compute/remote_poll_error.py:14` |
| `RemoteSubmissionError` | `Exception` | `services/compute/remote_submission_error.py:13` |
| `DuplicateDownloadError` | `Exception` | `services/model_import/model_asset_service.py:43` |
| `ModelAssetAlreadyAvailableError` | `Exception` | `services/model_import/model_asset_service.py:47` |
| `ModelNotFoundError` | `Exception` | `services/model_import/model_asset_service.py:51` |
| `ModelRefNotFoundError` | `Exception` | `services/model_import/model_asset_service.py:55` |
| `TokenizerLoadError` | `Exception` | `services/_shared/tokenizer_load_error.py:15` |
| `ModelSourceError` | `Exception` | `services/_shared/import_types.py:52` (already structured) |
| `CatalogUnavailableError` | `RuntimeError` | `services/catalog/catalog_unavailable_error.py:9` |
| `MigrationError` | `RuntimeError` | `db/migration_error.py:13` |

Re-verify: `grep -rn "class \w\+\(Error\|Exception\)(" anvil --include="*.py"`

## Keep As-Is

- **Encryption errors** (`services/_shared/encryption_errors.py:17-37`) — cohesive group inheriting `KeyError`/`ValueError`/`RuntimeError`. If unified, use MULTIPLE inheritance (`class UnknownKeyIdError(AnvilServiceError, KeyError)`) to preserve `isinstance(e, KeyError)` checks.
- **Control-flow** (`DivergenceError`, `StopRequested`) — NOT API-facing, leave outside hierarchy.
- **Client SDK** (`anvil/client/_shared/` — `ApiError` + 6 subclasses) — already well-structured, DO NOT TOUCH.

## Reference Patterns (already in codebase)

`ApiError` (`client/_shared/api_error.py:16-36`):
```python
class ApiError(Exception):
    def __init__(self, status_code: int | None, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)
```
`ModelSourceError` (`services/_shared/import_types.py:67-71`) — already has `code`/`message`/`source`:
```python
def __init__(self, code: str, message: str, source: str) -> None:
    self.code = code
    self.message = message
    self.source = source
    super().__init__(f"[{code}] {message} (source={source})")
```

## Decision Reference

`shared-decisions.md` Decision 4: define `AnvilServiceError(Exception)` in `anvil/services/_shared/service_error.py` with `code: str`, `message: str`, `details: dict | None`. Consumed by spec 072's error handler.

## Gotchas

- The change is ADDITIVE — existing `except Exception`/`except RuntimeError` handlers still catch unified exceptions.
- `catch` sites that specifically do `except RuntimeError` for `CatalogUnavailableError`/`MigrationError` — if you switch their base from `RuntimeError` to `AnvilServiceError`, those catches break. Either keep `RuntimeError` via multiple inheritance OR audit the catch sites first: `grep -rn "except RuntimeError" anvil/`.
- `_shared/` bare `__init__.py` — the new module is `service_error.py` (docstring + class), imported directly.
- Spec 072 depends on this — do 079 first.
