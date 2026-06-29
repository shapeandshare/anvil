# Implementation Plan: HuggingFace Model Browser & Curated Catalog

**Branch**: `041-huggingface-model-browser` | **Date**: 2026-06-28 | **Spec**: `docs/vault/Specs/041 HuggingFace Model Browser/spec.md`
**Input**: Feature specification from `docs/vault/Specs/041-huggingface-model-browser/spec.md`

## Summary

Build an in-app HuggingFace view at `/v1/hf-browser` to search, browse, and inspect model cards. The view is fronted by a curated YAML-based catalog of very small models (TinyLlama-class) with per-backend resource envelopes. Each model shows a local-eligibility badge computed against the running host's detected resources. One-click import feeds the registry (spec 040). Live search uses the `huggingface_hub` library (behind `[finetune]` extra, token optional) with a local cache layer.

## Technical Context

**Language/Version**: Python 3.11+ (PEP 604, `StrEnum`, `from __future__ import annotations`)
**Primary Dependencies**: FastAPI + Jinja2 (existing), PyYAML (existing), `huggingface_hub` (behind `[finetune]` extra), Pydantic (existing)
**Storage**: In-repo YAML file (`curated-models.yaml`) bundled with the Python package; in-memory cache for HF API results with configurable TTL
**Testing**: pytest + httpx.AsyncClient (existing fixtures); unit tests for catalog loading/parsing/eligibility; e2e HTTP test for page render
**Target Platform**: macOS/Linux (web browser)
**Project Type**: web-service (part of anvil monolith)
**Performance Goals**: Page load < 500ms (catalog from static YAML); live search results within 2s with loading spinner; eligibility badge computation < 50ms
**Constraints**: Offline-capable catalog; `huggingface_hub` only behind `[finetune]` extra (base install must not import it); no-token HF API rate limits must be respected with local caching
**Scale/Scope**: Single-user/local deployment; < 50 curated catalog entries; HF API search for thousands of results (paginated)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Article I — Zero-Dependency Core**: Not applicable — this feature does not touch `anvil/core/`.

**Article IV — TDD Mandatory**: All catalog parsing, eligibility computation, and API wrapper code MUST have tests written before implementation. E2E test for the page render required.

**Article V — Async-First**: The new route handler MUST be async. Catalog loading from YAML at startup is sync (one-time). HF API calls via `huggingface_hub` are sync — wrap in `asyncio.to_thread()` or use the library's async client if available.

**Article VI — `__init__.py` Ownership Policy**: If a new domain sub-package is created under `anvil/services/`, it MUST have a bare, docstring-only `__init__.py`. Data-only directories (for the YAML catalog) MUST NOT.

**Article VII — Layered Architecture**: 
- Catalog service in appropriate domain sub-package
- Service exposed through `AnvilWorkbench` god class
- Route handler calls god class method
- No direct file/YAML I/O in route handler

**Article VIII — iOS-Grade Polish**: The HF Browser page MUST follow the design system (`docs/ux-rules.md`, `anvil/api/static/css/tokens.css`). Loading/empty/error states MUST be styled consistently with the existing page patterns.

**Article IX — Pit of Success**: 
- Base install (`pip install anvil`) must NOT import `huggingface_hub`
- When `[finetune]` extra is installed but HF Hub API is unreachable, the curated catalog MUST still render with an appropriate offline notice
- Live search degrades gracefully with a user-visible message

**Article XI — Simplicity First (hard MUST)**:

| Check | Status |
|-------|--------|
| **§11.1 Simplest viable** | YAML file + Pydantic model is the simplest approach for a static catalog with validation |
| **§11.2 Boring over novel** | Using existing `huggingface_hub` (already adopted behind `[finetune]`) + existing Jinja2/FastAPI patterns. No new or experimental dependencies. |
| **§11.3 YAGNI** | No config knobs without consumers. Allow-list is a hardcoded set for v1 — not a config file. |
| **§11.4 Reuse first** | Reusing existing FastAPI route pattern, Jinja2 template inheritance, Pydantic models, PyYAML, and `AnvilWorkbench` god class pattern. |
| **§11.6 Testable** | Catalog parsing (YAML → Pydantic) is trivially unit-testable. Eligibility computation is pure function. E2E test with `httpx.AsyncClient`. |

> Any deviation from the simplest viable solution MUST be recorded in the Complexity Tracking table below (§11.5), or this gate fails.

### Post-Design Re-Evaluation (Phase 1 complete)

All constitutional gates verified after Phase 1 design:

| Article | Verdict | Notes |
|---------|---------|-------|
| Article I — Zero-Dependency Core | ✅ **Pass** | Does not touch `anvil/core/` |
| Article IV — TDD Mandatory | ✅ **Pass** | All data model types trivially testable; eligibility is pure function |
| Article V — Async-First | ✅ **Pass** | Route handler async; catalog load is sync one-time; `hub_client` wraps sync HF calls |
| Article VI — `__init__.py` Policy | ✅ **Pass** | `inference_hub/` gets bare docstring-only `__init__.py`; `data/` is data-only — no init |
| Article VII — Layered Architecture | ✅ **Pass** | `ModelBrowserService` → `AnvilWorkbench` property → route handler via `Depends(get_workbench)` |
| Article VIII — iOS-Grade Polish | ✅ **Pass** | Follows design system; template extends `base.html` |
| Article IX — Pit of Success | ✅ **Pass** | `huggingface_hub` guarded behind `[finetune]` extra; catalog renders offline; search degrades gracefully |
| Article XI — Simplicity First | ✅ **Pass** | No complexity deviations recorded; all choices are simplest viable |
| Article X — Domain-Driven | ✅ **Pass** | `inference_hub/` domain sub-package is justified (separates finetune-only code); <12 peer modules |
| Additional — No lazy imports | ✅ **Pass** | Only `huggingface_hub` import is lazy via `import-placement:allow` (optional extra guard) |
| Additional — Pydantic over dataclass | ✅ **Pass** | All new models use `BaseModel` |
| Additional — One class per file | ✅ **Pass** | Types file may hold multiple tightly-coupled model classes (exception permitted) |

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/041 HuggingFace Model Browser/
├── plan.md              # This file
├── spec.md              # Feature specification (input)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── api-browser.md   # /v1/hf-browser page + search API contract
│   ├── api-import.md    # POST /v1/hf-browser/import contract
│   └── catalog-format.md # YAML schema
└── tasks.md             # Phase 2 output
```

### Source Code (anvil package)

```text
anvil/
├── data/
│   └── curated-models.yaml       # Bundled catalog (in wheel via package-data)
├── services/
│   ├── inference/                # Existing domain sub-package (model browser lives here)
│   │   ├── __init__.py
│   │   ├── model_browser.py      # Catalog loading, eligibility, HF search wrapper
│   │   └── model_browser_types.py # Pydantic models: CatalogEntry, ResourceEnvelope, RunnableArchitecture
│   └── inference_hub/            # [NEW] HF Hub integration (behind [finetune] extra)
│       ├── __init__.py
│       └── hub_client.py         # huggingface_hub wrapper with TTL caching
├── api/
│   ├── v1/
│   │   ├── hf_browser.py         # Route: /v1/hf-browser (page GET)
│   │   └── hf_browser_api.py     # Route: /v1/hf-browser/search (JSON API)
│   └── templates/
│       └── hf_browser.html       # Jinja2 page template
└── supervisor/
    └── ...                       # No change

tests/
├── unit/services/inference/
│   ├── test_model_browser.py     # Catalog loading, eligibility
│   └── test_model_browser_types.py # Pydantic model validation
└── e2e/
    └── test_hf_browser.py        # Page render, search API
```

**Structure Decision**: Option 2 (web application — single project). New service code goes into the existing `anvil/services/inference/` domain sub-package since the model browser is tightly coupled to inference. The HF Hub client wrapper goes into a new `anvil/services/inference_hub/` sub-package to maintain separation between finetune-only and base-install code paths (Article IX).

## Complexity Tracking

> No complexity deviations identified at this time. All approaches are the simplest viable.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |