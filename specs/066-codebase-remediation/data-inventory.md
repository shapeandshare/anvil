# Data Inventory — Verified Ground-Truth (as of 2026-07-18)

**Purpose**: Exact, grepped inventories of every anti-pattern occurrence. This is the "cold-start" data so a future implementer does not need to re-investigate. All line numbers are as of the branch state on 2026-07-18 — **re-verify with the provided grep commands before editing**, as line numbers drift.

---

## 1. `get_config()` call sites (spec 066)

**Total**: 40 references across 18 files; 25 use subscript access `get_config()["key"]`.

**Re-verify**: `grep -rn "get_config()" anvil --include="*.py"`

**Subscript call sites to migrate** (excluding docstrings):
| File | Line | Key |
|------|------|-----|
| `anvil/supervisor/supervisor.py` | 29 | `log_dir` |
| `anvil/supervisor/supervisor.py` | 135 | `log_dir` |
| `anvil/config.py` | 66 | `mlflow_uri` |
| `anvil/config.py` | 93 | `mlflow_port` |
| `anvil/services/content/local_versioned_content_store.py` | 82 | `content_dir` |
| `anvil/services/content/advisory_service.py` | 239 | `content_dir` |
| `anvil/api/v1/_environment.py` | 107 | `mlflow_port` |
| `anvil/api/v1/experiments.py` | 99, 355, 518, 604, 769 | `mlflow_uri` (×5) |
| `anvil/api/v1/health_ops.py` | 126, 175, 185, 323, 433 | `mlflow_port`/`mlflow_disable_local` (×5) |
| `anvil/db/migration.py` | 403 | `state_db_path` |
| `anvil/workbench.py` | 404 | `content_dir` |
| `anvil/db/session.py` | 66 | `state_db_path` |

**Also uses `get_config()` (non-subscript)**: `anvil/cli.py` (3), `anvil/services/backup/cli.py` (2), `anvil/supervisor/services.py` (1), `anvil/services/backup/backup_service.py` (1), `anvil/services/runtime_config/runtime_config_service.py` (1), `anvil/services/tracking/tracking.py` (1), `anvil/api/app.py` (1), `anvil/api/v1/learning.py` (1).

**Config keys** (from `anvil/config.py:186-213`): `port`, `host`, `state_db_path`, `log_dir`, `mlflow_uri`, `mlflow_port`, `mlflow_backend_store_uri`, `mlflow_disable_local`, `db_auto_migrate`, `storage_backend`, `device`, `content_dir`, `backup_dir`, `backup_quota_bytes`, `backup_quota_warn_fraction`, `backup_retention_max_count`, `backup_retention_max_age_days`, `workspace_root`.

**Global mutable state to remove**: `_resolved_mlflow_uri` (`config.py:35`), set via `set_resolved_mlflow_uri()` (`config.py:38-50`), read via `get_mlflow_uri()` (`config.py:53-67`).

---

## 2. Route response_model coverage (spec 067)

**Verified**: 6 `response_model=` usages vs **221 total route decorators** in `anvil/api/v1/`.
(Note: the original review said "23 route files"; the actual route *count* is 221 endpoints. Only `eval.py` uses response models.)

**Re-verify**: 
- `grep -rn "response_model" anvil/api/v1/ | wc -l`
- `grep -rn "@router\.\(get\|post\|put\|delete\|patch\)" anvil/api/v1/ | wc -l`

**Reference implementation**: `anvil/api/v1/eval.py` — uses `EvaluationRunResponse` etc. Study this file for the target pattern.

---

## 3. `asyncio.run()` blocking calls (spec 068)

**Verified**: 3 occurrences, all in `anvil/services/training/training.py`:
| Line | Context |
|------|---------|
| 336 | `_load_docs` dataset branch → `asyncio.run(_load())` |
| 353 | `_load_docs` default-corpus branch → `asyncio.run(_load_default())` |
| 430 | (third occurrence — verify context) |

**Re-verify**: `grep -rn "asyncio.run(" anvil/services/training/`

**Note**: The original review mentioned only 1 occurrence; there are **3**. All must be converted to async.

---

## 4. Module-level service singletons & mutable state (specs 069, 074)

**Verified** in `anvil/api/v1/`:
| File | Line | Declaration | Spec |
|------|------|-------------|------|
| `training.py` | 126 | `svc = TrainingService()` | 069 |
| `training.py` | 127 | `tracking_svc = TrackingService()` | 069 |
| `training.py` | 128 | `_tasks: dict[int, asyncio.Task[Any]] = {}` | 074 |
| `corpora.py` | 54 | `tracking_svc = TrackingService()` | 069 |
| `eval_datasets.py` | 21 | `_tracking_svc = TrackingService()` | 069 |
| `inference.py` | 33 | `_svc = InferenceService()` | 069 |
| `content.py` | 60 | `_injection_queue: asyncio.Queue[...] = asyncio.Queue(maxsize=128)` | 074 |
| `fine_tune_datasets.py` | 42 | `_tasks: dict[int, asyncio.Task[Any]] = {}` | 074 |

**Also**: `experiments.py` creates `TrackingService()` inline in 5 route handlers (lines 99, 355, 518, 604, 769 — same lines as the mlflow_uri usage) — spec 069/070.

**Re-verify**: `grep -rn "TrackingService()\|InferenceService()\|TrainingService()\|_tasks\|_injection_queue" anvil/api/v1/`

---

## 5. Services creating services inline (spec 071)

**Verified**:
| File | Line | Creates |
|------|------|---------|
| `anvil/services/evaluation/evaluation_service.py` | 517-518 | `InferenceService()`, `TrackingService()` |
| `anvil/services/inference/inference.py` | 414, 734, 1251 | `TrackingService()` (×3) |
| `anvil/services/inference/demo_model_provider.py` | 90, 213, 219, 240, 260, 410, 540, 546 | Various (Tracking, Demo, Corpus, Training) |
| `anvil/services/training/training.py` | 333, 343, 344 | `DatasetService`, `CorpusService`, `DemoBootstrapService` |
| `anvil/services/training/training_run_service.py` | 397 | `InferenceService()` |
| `anvil/services/demo/demo_bootstrap.py` | 92, 109, 110 | `DemoBootstrapService`, `CorpusService`, `DatasetService` |

**Re-verify**: `grep -rn "TrackingService()\|InferenceService()\|TrainingService()\|DatasetService(\|CorpusService(\|DemoBootstrapService(" anvil/services/`

**Note**: `demo_model_provider.py` and `demo_bootstrap.py` are heavy offenders not fully covered in the original review — include them in the injection scope.

---

## 6. Pydantic schema `extra="forbid"` gaps (spec 073)

**`schemas_content.py`**: 0 models have `extra="forbid"`. 15 models total (line refs):
- Request bodies (need `extra="forbid"`): `ContentCorpusCreate` (22), `SessionOpenBody` (138), `CompositionSpecItem` (222), `FreezeVersionBody` (237), `TagBody` (257), `LockBody` (269), `RevertBody` (311), `ImportStart` (323).
- Response models (need `extra="ignore"` or leave default): `ContentCorpusOut` (60), `ContentVersionOut` (102), `SessionOut` (153), `AcceptOut` (183), `ValidationReportOut` (207), `LockOut` (284), `ImportJobOut` (341).

**`schemas_dataset.py`**: 0 models have `extra="forbid"`. 8 models (all request bodies): `CreateDatasetBody` (18), `UpdateDatasetBody` (33), `ImportBody` (48), `FilterBody` (63), `ReplaceBody` (78), `UpdateSampleBody` (96), `CloneDatasetBody` (108), `CreateFromCorpusBody` (123).

**Re-verify**: `grep -c 'extra="forbid"' anvil/api/v1/schemas_content.py anvil/api/v1/schemas_dataset.py`

---

## 7. PEP 563 annotations gaps (spec 078)

**Files WITH `from __future__ import annotations`** (8): `schemas_governance.py`, `schemas_corpus.py`, `schemas_fine_tune_datasets.py`, `schemas_eval.py`, `schemas_misc.py`, `schemas_dataset.py`, `schemas_teach.py`, `schemas_content.py`.

**CORRECTION**: The earlier review claimed `schemas_dataset.py`, `inference_schemas.py`, `schemas_eval.py` were MISSING the import. Re-grep shows `schemas_dataset.py` and `schemas_eval.py` DO have it. **Only `inference_schemas.py` needs verification** — it did not appear in the `schemas_*.py` glob (different filename). Check `inference_schemas.py` explicitly.

**Re-verify**: `grep -L "from __future__ import annotations" anvil/api/v1/*.py` (lists files WITHOUT it).

**Action for implementer**: Run the `grep -L` command above across ALL `anvil/api/v1/*.py` and `anvil/**/*.py` to get the true list. The scope is "any file missing it", not a fixed list.

---

## 8. Exception hierarchy (spec 079)

**Server-side exceptions (need unification under `AnvilServiceError`)**:
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
| `ModelSourceError` | `Exception` | `services/_shared/import_types.py:52` (already has `code`, `message`, `source`) |
| `CatalogUnavailableError` | `RuntimeError` | `services/catalog/catalog_unavailable_error.py:9` |
| `MigrationError` | `RuntimeError` | `db/migration_error.py:13` |

**Keep as-is (cohesive group, multiple inheritance if unified)**: encryption errors in `services/_shared/encryption_errors.py:17-37` (inherit `KeyError`/`ValueError`/`RuntimeError`).

**Keep OUTSIDE hierarchy (control-flow, not API-facing)**: `DivergenceError` (`services/training/divergence_error.py:16`), `StopRequested`.

**Client SDK — DO NOT TOUCH**: `ApiError` + 6 subclasses in `anvil/client/_shared/` (already well-structured; see `api_error.py` as the reference pattern).

**Reference pattern for structured exception** (`api_error.py:16-36`):
```python
class ApiError(Exception):
    def __init__(self, status_code: int | None, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)
```
And `ModelSourceError` (`import_types.py:67-71`):
```python
def __init__(self, code: str, message: str, source: str) -> None:
    self.code = code
    self.message = message
    self.source = source
    super().__init__(f"[{code}] {message} (source={source})")
```

---

## 9. session.py cleanup targets (spec 077)

**`cast()` calls** (`anvil/db/session.py`): lines 89, 91, 128, 129.
**`assert` statements**: lines 101, 137.
**Module-level bootstrap at import**: line 86 (`_bootstrap_engine()`).

**Re-verify**: `grep -n "cast(\|assert \|_bootstrap_engine()" anvil/db/session.py`

---

## 10. Coverage threshold (spec 075)

**Current `fail_under`**: `23` (`pyproject.toml:203`).
**Docs claim actual**: ~41% (AGENTS.md, ARCHITECTURE.md).

**ACTION REQUIRED**: No venv present in this environment — the actual coverage was NOT measured during spec creation. The implementer MUST run:
```bash
make setup    # if venv missing
make test     # produces TOTAL coverage line
```
Then set `fail_under` to the measured integer (floor). Do NOT guess.

---

## 11. Reference implementations (study these)

| Pattern | Reference file | Why |
|---------|---------------|-----|
| Response models on routes | `anvil/api/v1/eval.py` | Only route file doing it right |
| BaseSettings config | `anvil/client/_shared/server_config.py` | Uses `field_validator`, `from_env()` factory |
| Exception hierarchy | `anvil/client/_shared/api_error.py` | Clean base + subclasses |
| Structured exception fields | `anvil/services/_shared/import_types.py:52` | `code`/`message`/`source` |
| Plugin registry (DI) | `anvil/services/compute/registry.py` | Factory + injection pattern |
| Repository pattern | `anvil/db/repositories/datasets.py` | Clean async repo |
| DI dependency | `anvil/api/deps.py` | `get_workbench()`, `get_db_session()` |
