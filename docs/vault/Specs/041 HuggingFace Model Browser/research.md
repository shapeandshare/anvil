# Research: HuggingFace Model Browser & Curated Catalog

**Feature**: 041 HuggingFace Model Browser | **Date**: 2026-06-28

## Catalog File Location

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| `anvil/data/curated-models.yaml` | Follows existing pattern — `anvil/data/` already contains bundled data (`demo/`, `provenance.json`) and is declared in `pyproject.toml` package-data | `anvil/_resources/` (holds Alembic config only — wrong semantics); `anvil/api/static/` (static assets meant for browser); standalone file at repo root (not bundled in wheel) |

**Implementation note**: Add `"data/curated-models.yaml"` to `[tool.setuptools.package-data]` in `pyproject.toml`. No structural changes needed.

## Page Structure & Routing

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| Standalone page at `/v1/hf-browser`, route in `anvil/api/v1/pages.py` | All standalone HTML page routes live in `pages.py` following the existing pattern (`/training-page`, `/datasets-page`, etc.) | Sub-tab on models page (mixed concerns); modal (limited UX for browsing) |

**Registration checklist**:
1. Add `@router.get("/hf-browser", response_class=HTMLResponse)` to `anvil/api/v1/pages.py`
2. Create `anvil/api/templates/hf_browser.html` extending `base.html`
3. Add nav entry in `anvil/api/templates/base.html` `<nav class="nav-bar__tabs">`
4. Add `"/v1/hf-browser"` to `PAGE_PREFIXES` tuple in `anvil/api/auth.py`

## Template Pattern

| Decision | Rationale |
|----------|-----------|
| Extend `base.html` with `{% block content %}` | All existing standalone pages follow this pattern. Use `{% block extra_css %}` for archetypes CSS if needed. |

## Service Architecture

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| `ModelBrowserService` in `anvil/services/inference/` with lazy property on `AnvilWorkbench` | Follows the established service wiring pattern (Article VII). `inference/` domain sub-package already exists and is semantically correct. | New top-level `anvil/services/model_browser/` — 12+ peer modules threshold not met; domain belongs in `inference` |

**Wiring pattern** (per existing convention — note: NO `self.compute.device`, that property does not exist):
```python
# anvil/workbench.py
self._model_browser: ModelBrowserService | None = None

@property
def model_browser(self) -> ModelBrowserService:
    if self._model_browser is None:
        self._model_browser = ModelBrowserService()  # loads bundled YAML; calls detect_gpu()/psutil internally
    return self._model_browser
```

**Correction (post-review)**: `anvil/services/compute/resolve.py` only returns a `DeviceType` (cpu/cuda/mps) — NOT RAM/VRAM quantities. Resource detection for eligibility uses `detect_gpu()` (`anvil/gpu.py`, returns `GpuInfo` with `memory_total_gb`) and `psutil.virtual_memory()` (psutil is a core dependency). There is no `workbench.compute` property.

Note: `AnvilWorkbench` is NOT created at startup — it's created **per-request** by `get_workbench()` dependency (`anvil/api/deps.py`). Each request gets a fresh `AsyncSession` and workbench instance.

## HF Hub Client Isolation

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| HF Hub client wrapper in `anvil/services/inference_hub/` behind `[finetune]` extra | Base install must NOT import `huggingface_hub` (Article IX — Pit of Success). The separate `inference_hub/` domain sub-package ensures clean import boundary. | Inline in `inference/` (violates import isolation — `huggingface_hub` import would fail in base install); lazy import in model browser (works but mixes concerns) |

**Lazy import pattern** (within `inference_hub/hub_client.py`):
```python
class HubClient:
    def __init__(self, token: str | None = None) -> None:
        from huggingface_hub import HfApi  # safe: guarded behind [finetune] extra
        self._api = HfApi(token=token)
```

## Model Architecture Allow-List

| Decision | Rationale |
|----------|-----------|
| **Reuse** spec 040's existing `_ALLOWED_ARCHITECTURES`, `_ACCEPTED_FORMATS`, and `RunnableStatus` | Constitution Article XI §11.4 (Reuse First). These already exist in `anvil/services/model_import/model_import_service.py` and `anvil/services/_shared/runnable_status.py`. Defining a parallel `RunnableArchitecture` enum would be a duplicate source of truth (reject-worthy). |

## Eligibility Computation

| Decision | Rationale |
|----------|-----------|
| Pure function `check_eligibility(envelope, gpu, ram_total_gb)` using `detect_gpu()` (`anvil/gpu.py`) + `psutil` | `anvil/services/compute/resolve.py` returns only a device *type*, not quantities. `detect_gpu()` returns `GpuInfo.memory_total_gb`; `psutil.virtual_memory()` gives RAM (psutil is core). Pure function is trivially unit-testable (Article IV). MPS VRAM is a unified-RAM proxy (best-effort). |

## Auto-Import Entry Point

| Decision | Rationale |
|----------|-----------|
| Import button calls existing `POST /v1/models/import` (spec 040); service API is `workbench.model_imports.submit_import(source, identifier, *, revision, name)` | The import flow + route are already implemented. **Correction**: property is `model_imports` (plural), method is `submit_import` (not `create_job`), and there is NO `architecture` argument — it is auto-derived from the model config. No new import endpoint is added. |

## Dependency Table

| Dependency | Where Declared | Why |
|-----------|---------------|-----|
| `huggingface_hub` | `[finetune]` extra (existing) | HF Hub API client — `HfApi.list_models()`, `HfApi.model_info()` |
| `PyYAML` | **Must be ADDED to core deps** | Parse `curated-models.yaml`. **Correction**: currently only a transitive dep (via mlflow et al.), NOT declared in `pyproject.toml`. Must be promoted to `[project.dependencies]` (FR-007b). |
| `psutil` | Core deps (existing, line 28) | System RAM detection for eligibility |
| `Pydantic` | Core deps (existing) | `CatalogEntry`, `ResourceEnvelope` validation models |
| `detect_gpu()` | Existing module `anvil/gpu.py` | GPU backend + VRAM detection for eligibility |

## HF Hub API Rate Limiting

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| Local TTL-based cache: 5-15 min for search, 30-60 min for model details; rely on `huggingface_hub` built-in retry | Library auto-retries 429 with exact reset time via `http_backoff` (since v1.2.0). Anonymous: 500 req/5min (1.67/s); Authenticated: 1000 req/5min (3.33/s). **Passing `HF_TOKEN` is the #1 way to avoid rate limits.** | Complex cache invalidation (unnecessary — model metadata changes infrequently); no caching (risk of 429 during rapid browsing) |

**Key numbers**:
- Anonymous limit: 500 requests per 5-minute window (per IP)
- Free authenticated (with `HF_TOKEN`): 1,000 requests per 5-minute window
- Library retry behavior: on 429, parses `RateLimit` headers, waits exact `reset_in_seconds` + 1s, retries up to 5 times
- After retries exhausted: raises `HfHubHTTPError` with user-friendly message including remaining time
- Recommended TTLs: `list_models()` → 5 min, `model_info()` → 30 min

**Implementation**: Simple in-memory TTL cache in `HubClient` wrapper. No persistent cache needed.