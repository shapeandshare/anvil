# Quickstart: Visual Feedback Annotation

## Implementation Order

Follow this order to implement the feature incrementally:

### Step 1: Data Layer

1. **Add enums** — Create `FeedbackStatus` and `AnnotationType` `StrEnum` classes in `anvil/services/feedback/`
2. **Create DB model** — `anvil/db/models/feedback_report.py` with `FeedbackReport` and `FeedbackAnnotation` ORM models
3. **Add Alembic migration** — `make db-revision` to create `feedback_reports` and `feedback_annotations` tables
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

10. **Create CSS** — `anvil/api/static/css/feedback.css` for annotation overlay styles
11. **Create JS** — `anvil/api/static/js/annotation.js` with `AnnotationCanvas` class:
    - Screenshot capture via `html-to-image`
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

# Create Alembic migration
make db-revision msg="add feedback reports and annotations tables"

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
