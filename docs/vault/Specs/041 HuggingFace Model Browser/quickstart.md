# Quickstart: HuggingFace Model Browser

**Feature**: 041 | **Role**: Developer implementing the HF Browser

## Implementation Steps

### 1. Create the curated catalog YAML

Create `anvil/data/curated-models.yaml` with initial entries (TinyLlama-class models). Add `"data/curated-models.yaml"` to `[tool.setuptools.package-data]` in `pyproject.toml`.

### 2. Add Pydantic models

Create `anvil/services/inference/model_browser_types.py` with `CatalogEntry`, `ResourceEnvelope`, `CuratedCatalog`, and `RunnableArchitecture`.

### 3. Build the service

Create `anvil/services/inference/model_browser.py` with `ModelBrowserService`:
- `load_catalog()` → parse YAML → validate with Pydantic → cache in memory
- `check_eligibility(entry, detected_device)` → pure function comparing envelope against host
- `get_allow_list()` → return the `RunnableArchitecture` enum values

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

Add to `anvil/api/v1/pages.py`:
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
- Curated catalog cards with eligibility badges
- Detail panel on card selection
- Graceful offline messaging when HF API unavailable

### 8. Register in auth + nav

- Add `"/v1/hf-browser"` to `PAGE_PREFIXES` in `anvil/api/auth.py`
- Add nav link in `anvil/api/templates/base.html`

### 9. Write tests

- Unit: `tests/unit/services/inference/test_model_browser.py` — catalog parsing, eligibility
- Unit: `tests/unit/services/inference/test_model_browser_types.py` — Pydantic validation
- E2E: `tests/e2e/test_hf_browser.py` — page renders 200, search API returns correct JSON

### 10. Import action

Wire the "Import" button to call `workbench.model_import` (spec 040) — this delegates entirely to the existing import flow.

## Key Files

| File | Action |
|------|--------|
| `anvil/data/curated-models.yaml` | Create |
| `pyproject.toml` | Add `"data/curated-models.yaml"` to package-data |
| `anvil/services/inference/model_browser_types.py` | Create (Pydantic models) |
| `anvil/services/inference/model_browser.py` | Create (service) |
| `anvil/services/inference_hub/hub_client.py` | Create (HF client) |
| `anvil/services/inference_hub/__init__.py` | Create (bare, docstring-only) |
| `anvil/workbench.py` | Edit (add service property) |
| `anvil/api/v1/pages.py` | Edit (add route) |
| `anvil/api/templates/hf_browser.html` | Create (Jinja2 template) |
| `anvil/api/auth.py` | Edit (add to PAGE_PREFIXES) |
| `anvil/api/templates/base.html` | Edit (add nav link) |