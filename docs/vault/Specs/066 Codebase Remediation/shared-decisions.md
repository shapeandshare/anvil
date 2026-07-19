# Shared Decisions — Codebase Remediation Suite (066–080)

**Purpose**: Some remediation specs share cross-cutting decisions that MUST be made once and applied consistently across all affected specs. This document records those decisions so that independent implementers do not diverge. Resolve each decision BEFORE starting the dependent specs.

---

## Decision 1 — API Response Envelope Convention

**Affects**: 067 (response_model), 072 (error format), and every route file.

**The problem**: Three inconsistent envelope patterns exist today:
- `{"data": ..., "error": None}` — datasets, corpora, content
- Direct dict — training, experiments, eval
- Flat status dict — health, config

**Options**:
- **Option A — Direct Pydantic models (RECOMMENDED)**: Each route returns a typed Pydantic model directly (the `eval.py` pattern). Errors use HTTP status codes + a standard `ErrorResponse` body. This is idiomatic FastAPI, gives clean OpenAPI docs, and is already proven in `eval.py`.
- **Option B — Wrapper envelope**: All responses wrapped in `{"data": T, "error": ErrorResponse | None}`. Requires a generic `Envelope[T]` model.

**RECOMMENDATION**: **Option A** — direct Pydantic models. Rationale: `eval.py` already demonstrates it; it is the FastAPI-idiomatic approach; Constitution Article XI (Simplicity First / boring technology) favors the standard framework pattern over a custom envelope. The wrapper envelope adds a generic layer with no present consumer benefit (YAGNI).

**DECISION**: _[To be confirmed by implementer/owner before starting 067]_ — default to Option A unless the frontend explicitly depends on the `{data, error}` shape. **Action**: grep the frontend JS (`anvil/api/static/`) for `.data` / `.error` response access to confirm no breakage before committing to Option A.

---

## Decision 2 — Service Dependency Injection Mechanism

**Affects**: 069 (route DI), 071 (service DI injection), 068 (asyncio fix depends on 071).

**The problem**: Routes use module-level singletons; services create dependencies inline. Two DI layers need a consistent mechanism.

**Options**:
- **Option A — Workbench-centric (RECOMMENDED)**: All services obtained via `AnvilWorkbench` properties (already the established pattern per Constitution Article VII). Route-level `Depends()` functions in `deps.py` are thin wrappers that return `workbench.<service>`. Service-to-service deps are wired in the workbench property accessors.
- **Option B — Independent FastAPI providers**: Each service gets its own `get_<service>()` provider function independent of the workbench.

**RECOMMENDATION**: **Option A** — workbench-centric. Rationale: Constitution Article VII mandates the God Class as the single service entry point. Adding parallel provider functions would create "a second way to do the same thing" (Principle 13, reject-worthy). Route convenience deps should delegate to the workbench.

**DECISION**: **Option A**. Route-level dependencies like `get_training_service()` MUST delegate to `AnvilWorkbench` (obtained via `get_workbench`). Service constructors accept optional dependency params (default `None` → lazy-create) for backward compatibility, and the workbench wires them explicitly.

---

## Decision 3 — Backward-Compatibility Strategy for config Migration

**Affects**: 083 (config pydantic-settings).

**The problem**: 40 `get_config()` references across 18 files (25 use subscript `["key"]`). A big-bang migration risks breakage.

**Options**:
- **Option A — Dual-run transition (RECOMMENDED)**: Introduce `AppConfig(BaseSettings)`. Reimplement `get_config()` to return `AppConfig().model_dump()` (or a dict view) so existing call sites keep working. Migrate call sites incrementally. Remove `get_config()` in the final step of the spec.
- **Option B — Big-bang**: Replace `get_config()` and update all 25 call sites in one commit.

**RECOMMENDATION**: **Option A** — dual-run. Rationale: enables incremental, testable migration (TDD-friendly), reduces blast radius per commit.

**DECISION**: **Option A**. `get_config()` becomes a thin compatibility shim over `AppConfig` and is removed only after all call sites are migrated (final task of spec 083).

---

## Decision 4 — Exception Base Class Location & Scope

**Affects**: 079 (exception hierarchy), 072 (error format consumes it).

**Options**:
- **Option A (RECOMMENDED)**: Define `AnvilServiceError(Exception)` in `anvil/services/_shared/service_error.py` (bare module, per `__init__.py` ownership policy). Carries `code: str`, `message: str`, `details: dict | None`.
- **Option B**: Top-level `anvil/exceptions.py`.

**RECOMMENDATION**: **Option A** — `_shared/` co-location. Rationale: service errors belong with cross-domain shared types; `_shared/` already hosts `encryption_errors.py`, `tokenizer_load_error.py`, etc.

**DECISION**: **Option A**. Control-flow exceptions (`StopRequested`, `DivergenceError`) stay OUTSIDE the hierarchy (not API-facing). Client SDK `ApiError` hierarchy is untouched.

---

## Decision 5 — Migration Numbering for DB Indexes

**Affects**: 080 (FK indexes).

**Context**: Latest Alembic migration is `014_add_download_job_source_columns.py`.

**DECISION**: New migration MUST be `015_add_fk_indexes.py` (next sequential number). Verify no other in-flight migration claims 015 before creating. Use Alembic autogenerate as a starting point, then hand-verify the index names match the spec.

---

## Global Constraints (apply to ALL specs)

1. **TDD mandatory** (Constitution Article IV): every change starts with a failing test. See each spec's `tasks.md` for the Red-Green-Refactor sequence.
2. **Coverage ratchet** (Article IV): `fail_under` may only increase. Do NOT let any spec's changes drop coverage.
3. **Simplicity First** (Article XI): reuse existing patterns; no speculative abstraction; record any complexity in the plan's Complexity Tracking table.
4. **No lazy imports** (Principle 14): imports at top of file (except the three documented exceptions).
5. **Relative imports only** (Principle 7): within `anvil/`, use `from .module import X`.
6. **Enums over magic strings** (Principle 11): new fixed-value sets use `StrEnum`.
7. **mypy --strict**: zero new errors. No `# type: ignore` without a code, no `cast()` abuse.
8. **Gates**: `make lint`, `make typecheck`, `make test`, `make vault-audit` must all pass before any spec is considered done.
