# Research: Demo Data Bootstrap Guard

**Date**: 2026-06-19 | **Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md)

## Unknowns Resolved

### 1. First-Run Detection Strategy

- **Decision**: Query database for existing entities with `origin="bundled"` (Corpus and Dataset models)
- **Rationale**: Both Corpus and Dataset ORM models have an `origin` column (`String(20)`, default `"user"`). Demo entities are created with `origin=DataOrigin.BUNDLED.value` = `"bundled"`. A simple `SELECT count(*) FROM corpora WHERE origin='bundled'` or equivalent is the cleanest detection method. No new table needed.
- **Alternatives considered**:
  - Dedicated `bootstrap_metadata` table — rejected; adds unnecessary schema complexity when `origin` field already serves the purpose
  - Name-prefix check (entities starting with `"Demo - "`) — rejected; fragile, could match user-created entities

### 2. Repository Query Methods

- **Decision**: Add `count_by_origin(origin: str) -> int` to both `CorpusRepository` and `DatasetRepository`
- **Rationale**: Follows existing Repository pattern. Keeps DB queries behind the repository layer rather than inline SQL in the lifespan handler. The method is simple: `select(func.count()).where(model.origin == origin)`.
- **Alternatives considered**: Inline `select()` in the lifespan handler — rejected; violates Article VII (Layered Architecture)

### 3. Ops Menu Re-trigger API Design

- **Decision**: `POST /v1/demo/bootstrap` returning `BootstrapResult` as JSON dict
- **Rationale**: Follows existing ops page pattern (`POST /v1/services/restart-all` returns `{"status": "ok", ...}`)
- **Contract**: See [contracts/rebootstrap-api.md](contracts/rebootstrap-api.md)

### 4. JS Handler Pattern

- **Decision**: Add `ops.rebootstrapDemo()` following the `restartAll` pattern exactly
- **Rationale**: All existing ops actions use the same pattern: `setBtnLoading` → `fetch(POST)` → toast success/error → `setBtnLoading(false)`
- **Details**: Button id `btn-rebootstrap-demo`; toast shows counts from `BootstrapResult`

### 5. CLI Banner Behavior

- **Decision**: Only print "Bootstrapping demo data..." banner when `bootstrap.corpora_created > 0 or bootstrap.datasets_created > 0`
- **Rationale**: Matches the startup handler pattern in `app.py`. The startup handler only logs creation when something was actually created.
- **Note**: `--verbose` flag is parsed but unused. Will be left as-is since the spec says CLI changes are for consistency, not new features (P3 priority).

### 6. Bootstrap Failure Handling

- **Decision**: Follow existing best-effort pattern in `app.py` (try/except, `pass` on failure)
- **Rationale**: Article IX — Pit of Success. Startup must not crash if bootstrap fails.
- **Details**: The existing lifespan handler already catches all exceptions. The guard query itself is lightweight and unlikely to fail.

### 7. Ops Button Error State

- **Decision**: Red toast on API failure (following existing `restartAll` pattern with `catch(e)`)
- **Rationale**: Confirmed in `/speckit.clarify` session — user chose Option A (existing toast pattern)

## Technology Choices

| Tech | Decision | Rationale |
|------|----------|-----------|
| FastAPI | Existing — no change | New endpoint uses existing patterns |
| SQLAlchemy | Existing — no change | Repository query methods use existing async session |
| Jinja2 | Existing — no change | Template edits follow existing patterns |
| Inline JS | Existing — no change | ops.html already uses inline `<script>` with IIFE |
| No new deps | Confirmed | Feature uses only existing project dependencies |

## Dependencies

No new pip dependencies. Changes are entirely within the existing codebase.

## Integration Points

| Integration | File | Nature of Change |
|-------------|------|-----------------|
| Lifespan handler | `anvil/api/app.py` | Add guard check before `bootstrap_all()` call |
| API endpoint | `anvil/api/v1/health_ops.py` | New `POST /v1/demo/bootstrap` route |
| Ops template | `anvil/api/templates/operations.html` | New button in System Actions + JS handler |
| CLI command | `anvil/cli.py` | Conditional banner in `bootstrap_datasets_main()` |