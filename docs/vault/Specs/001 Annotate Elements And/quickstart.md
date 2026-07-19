# Quickstart: Visual Feedback Annotation

## Implementation Order

Follow this order to implement the feature incrementally:

### Step 1: Data Layer

1. **Add enums** — Create `FeedbackStatus` in `anvil/db/models/feedback_status.py` and `AnnotationType` in `anvil/db/models/annotation_type.py` (following the `teaching_session_status.py` pattern — DB enums live in the DB layer)
2. **Create DB model** — `anvil/db/models/feedback_report.py` with `FeedbackReport` and `FeedbackAnnotation` ORM models
3. **Write migration** — Hand-write `anvil/_resources/migrations/versions/015_add_feedback_reports.py` following the `011_add_teaching_sessions.py` pattern (migrations auto-apply at startup via `ANVIL_DB_AUTO_MIGRATE`; there is no `make db-revision` target)
4. **Add WorkspacePaths property** — Add `feedback_dir` to `anvil/workspace/workspace_paths.py`
5. **Create repository** — `anvil/db/repositories/feedback_repository.py` with `FeedbackRepository`

### Step 2: Service Layer

6. **Create feedback service** — `anvil/services/feedback/feedback_service.py` with `FeedbackService`:
   - `submit_report()` — store screenshots via LocalFileStore, create DB records
   - `list_reports()` — paginated list with status filter
   - `get_report()` — single report with annotations
   - `update_status()` — transition between open/in_progress/resolved
   - `delete_report()` — remove files + DB record
   - `batch_delete()` — remove multiple reports
   - `export_report()` — return structured JSON for agent consumption

### Step 3: API Layer

7. **Create API routes** — `anvil/api/v1/feedback.py` with all feedback endpoints
8. **Add route to router** — Register routes in the FastAPI router
9. **Add feedback page route** — Add `feedback_page()` to `anvil/api/v1/pages.py`

### Step 4: Frontend

9a. **Vendor library** — Download the `html-to-image` IIFE/UMD build (v1.11.11) into `anvil/api/static/js/lib/html-to-image.js` (mandatory: CSP blocks CDN scripts on app routes)
10. **Create CSS** — `anvil/api/static/css/feedback.css` for annotation overlay styles
11. **Create JS** — `anvil/api/static/js/annotation.js` with `AnnotationCanvas` class:
    - Screenshot capture via vendored `html-to-image`
    - Canvas initialization with DPR scaling
    - Drawing tools (element click, circle, freehand)
    - Annotation management (add/edit/delete/reorder)
    - Submit flow (POST to `/v1/feedback`)
12. **Create feedback template** — `anvil/api/templates/feedback.html`
13. **Create annotation toolbar partial** — `anvil/api/templates/partials/annotation-toolbar.html`
14. **Modify base.html** — Add Feedback nav tab and annotation.js script

### Step 5: Tests

15. **Unit tests** — `tests/unit/services/test_feedback_service.py`:
    - CRUD operations
    - Status transitions
    - Validation rules
    - File storage interactions
16. **E2E tests** — `tests/e2e/test_feedback.py`:
    - Submit report via API
    - List/filter reports
    - Export report as JSON
    - Delete report (single and batch)
    - Browser test: annotation mode flow (with Playwright)

## Commands

```bash
# Run unit tests for this feature
python -m pytest tests/unit/services/test_feedback_service.py -v

# Run e2e tests for this feature
python -m pytest tests/e2e/test_feedback.py -v

# Run all tests
make test

# Type check
make typecheck

# Lint
make lint
```

## Key Reference Files

| Purpose | File |
|---------|------|
| Canvas pattern | `anvil/api/static/js/chart.js` (LossChart) |
| Existing service pattern | `anvil/services/datasets/datasets.py` |
| Existing repository pattern | `anvil/db/repositories/datasets.py` |
| Existing DB model with storage path | `anvil/db/models/model_asset.py` |
| Page template pattern | `anvil/api/templates/operations.html` |
| Base template (nav + script loading) | `anvil/api/templates/base.html` |
| Route handler pattern | `anvil/api/v1/pages.py` |
| CSS token reference | `anvil/api/static/css/tokens.css` |
| Modal component reference | `anvil/api/static/css/components.css` (lines 512-676) |
