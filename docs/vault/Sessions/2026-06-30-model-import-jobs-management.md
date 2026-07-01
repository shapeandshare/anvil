---
title: Model Import Jobs Management
type: session-log
tags:
  - type/session-log
  - domain/ui
  - domain/architecture
  - domain/registry
created: '2026-06-30'
updated: '2026-06-30'
status: draft
source: agent
aliases: Model Import Jobs Management
---
# Model Import Jobs Management

**Session**: Added a full import jobs management feature to the HuggingFace model browser — list, live polling, error surfacing, retry, and dismiss capabilities for model import jobs.

## What was done

### Root cause fix (two issues found)

1. **CSRF token missing** — The HF browser template's import buttons used raw `fetch()` instead of `window.apiFetch()`. Cookie-authenticated state-changing POST requests require the `X-CSRF-Token` header per the auth middleware (FR-027). The base template provides `window.apiFetch()` which handles this automatically, but `hf_browser.html` wasn't using it. Fixed both import button handlers (curated catalog + search results).

2. **`anvil[finetune]` extra not installed** — The `huggingface_hub` package lives behind the `[finetune]` extra. The running venv didn't have it installed, so all import background jobs failed with `missing_extra`. Fixed via `uv pip install 'anvil[finetune]'`.

### Import Jobs management feature (backend)

**Repository** (`model_import_jobs.py`):
- Added `list_all()` returning all jobs newest-first (mirrors `ExternalModelRepository.get_all()` pattern)

**Service** (`model_import_service.py`):
- `list_jobs()` — delegates to repo
- `retry_import(job_id)` — fetches existing job, re-submits with same source/identifier/revision, returns new job ID; raises `ValueError` if not found

**Routes** (`models.py`):
- `GET /v1/models/import/jobs` — list all jobs with full metadata (JSON)
- `POST /v1/models/import/{job_id}/retry` — 202 + new job_id, fires background resolution

**Page context** (`pages.py`):
- `hf_browser_page` now passes server-rendered `import_jobs` list for first paint

### Import Jobs management feature (frontend)

**Template** (`hf_browser.html`):
- New "Import Jobs" `section-card` between search bar and curated catalog (stagger sequence: 0→1→2→3)
- Server-rendered job rows with status pills (green/red/cyan-pulse/grey), inline error display on failures, "View →" links for complete jobs, "Retry" + "Dismiss" buttons for failed jobs
- Live polling (2s interval) while any job is queued/resolving, stops when all settle
- Retry uses `window.apiFetch` for CSRF compliance; Dismiss is client-side only
- Import buttons now call `fetchJobs()` after successful submission
- S4/S3 UX rules enforced (escaping, CSP nonce, badge\_\_pulse for motion, empty state, semantic elements)

## Files changed
- `anvil/api/templates/hf_browser.html` — new Import Jobs card + JS logic (204 lines)
- `anvil/api/v1/models.py` — two new routes (+67 lines)
- `anvil/api/v1/pages.py` — import_jobs context (+18 lines)
- `anvil/db/repositories/model_import_jobs.py` — list_all() method (+15 lines)
- `anvil/services/model_import/model_import_service.py` — list_jobs() + retry_import() (+40 lines)
- `tests/e2e/test_external_models.py` — 3 new e2e tests (+48 lines)
- `tests/unit/services/test_model_import_service.py` — 3 new unit tests (+48 lines)
- `tests/unit/db/test_model_import_jobs_repo.py` — new repo test file
- `uv.lock` — updated via `uv pip install`

## Related
- Auth middleware: `anvil/api/app.py::auth_middleware` (CSRF enforcement for cookie-authenticated POST)
- Base template: `anvil/api/templates/base.html` (`window.apiFetch` definition)
- Model import service: `anvil/services/model_import/model_import_service.py`
- HfHubSource: `anvil/services/model_import/hf_source.py`
