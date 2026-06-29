# Quickstart: HuggingFace Model Browser

**Feature**: 041 | **Role**: Developer implementing the HF Browser

## Implementation Steps

### 1. Create the curated catalog YAML

Create `anvil/data/curated-models.yaml` with initial entries (TinyLlama-class models). Add `"data/curated-models.yaml"` to `[tool.setuptools.package-data]` in `pyproject.toml`.

### 0. Declare PyYAML

Add `pyyaml>=6,<7` to `[project.dependencies]` in `pyproject.toml` (currently only transitive).

### 2. Add Pydantic models

Create `anvil/services/inference/model_browser_types.py` with `CatalogEntry`, `ResourceEnvelope`, `CuratedCatalog`. **Reuse** spec 040's `_ALLOWED_ARCHITECTURES`, `_ACCEPTED_FORMATS`, and `RunnableStatus` — do not define a new architecture enum.

### 3. Build the service

Create `anvil/services/inference/model_browser.py` with `ModelBrowserService`:
- `load_catalog()` → parse YAML (PyYAML) → validate with Pydantic → cache in memory
- `check_eligibility(envelope, gpu, ram_total_gb)` → pure function (RAM always; VRAM only if GPU present; MPS best-effort)
- gathers detection inputs via `detect_gpu()` (`anvil/gpu.py`) + `psutil.virtual_memory()`
- `runnable_status(entry)` → compare against imported `_ALLOWED_ARCHITECTURES` → `RunnableStatus`

### 4. Build the HF Hub client (behind `[finetune]`)

Create `anvil/services/inference_hub/hub_client.py` with `HubClient`:
- `search_models(query)` → wrapped `HfApi.list_models()` with 5-min TTL cache
- `get_model_info(hf_id)` → wrapped `HfApi.model_info()` with 30-min TTL cache
- Lazy import of `huggingface_hub` (guarded behind `[finetune]` extra)

### 5. Wire into the god class

Add to `anvil/workbench.py`:
- Private slot `self._model_browser: ModelBrowserService | None = None`
- `@property def model_browser(self) -> ModelBrowserService`

### 6. Create the route

Add a page route to `anvil/api/v1/pages.py` and a search JSON route to a new `anvil/api/v1/hf_browser_api.py` (register it in `router.py`):
```python
@router.get("/hf-browser", response_class=HTMLResponse)
async def hf_browser_page(
    request: Request,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> HTMLResponse:
    # ...
```

### 7. Create the template

Create `anvil/api/templates/hf_browser.html` extending `base.html`, with:
- Search bar for live HF Hub search
- Curated catalog cards with eligibility badges (computed against host RAM/VRAM)
- Detail panel on card selection; "Import" button POSTs to the existing `/v1/models/import`
- Lesson-049 link only when available (graceful omission otherwise)
- Graceful offline messaging when HF API unavailable

### 8. Register in auth + nav

- Add `"/v1/hf-browser"` to `PAGE_PREFIXES` in `anvil/api/auth.py`
- Add nav link in `anvil/api/templates/base.html`

### 9. Write tests

- Unit: `tests/unit/services/inference/test_model_browser.py` — catalog parsing, eligibility
- Unit: `tests/unit/services/inference/test_model_browser_types.py` — Pydantic validation
- E2E: `tests/e2e/test_hf_browser.py` — page renders 200, search API returns correct JSON

### 10. Import action

Wire the "Import" button to issue a client-side `POST /v1/models/import` with `{source:"huggingface", identifier:<hf_id>}` (the existing spec 040 route — service property is `workbench.model_imports.submit_import(...)`). No architecture is passed; the import service derives it.

## Key Files

| File | Action |
|------|--------|
| `anvil/data/curated-models.yaml` | Create |
| `pyproject.toml` | Add `"data/curated-models.yaml"` to package-data; add `pyyaml` to core deps |
| `anvil/services/inference/model_browser_types.py` | Create (Pydantic models) |
| `anvil/services/inference/model_browser.py` | Create (service) |
| `anvil/services/inference_hub/hub_client.py` | Create (HF client) |
| `anvil/services/inference_hub/__init__.py` | Create (bare, docstring-only) |
| `anvil/workbench.py` | Edit (add service property) |
| `anvil/api/v1/pages.py` | Edit (add route) |
| `anvil/api/templates/hf_browser.html` | Create (Jinja2 template) |
| `anvil/api/auth.py` | Edit (add to PAGE_PREFIXES) |
| `anvil/api/templates/base.html` | Edit (add nav link) |