# Context — 067 Add response_model to All Routes

> Cross-references: `../066-codebase-remediation/data-inventory.md` §2, `shared-decisions.md` Decision 1.

## Current State (verified)

- **221 route decorators** in `anvil/api/v1/` (`@router.get/post/put/delete/patch`).
- **Only 6 `response_model=` usages** — all in `eval.py`.
- Most routes return `dict[str, Any]` or `dict`.

Re-verify:
```bash
grep -rn "response_model" anvil/api/v1/ | wc -l          # → 6
grep -rEn "@router\.(get|post|put|delete|patch)" anvil/api/v1/ | wc -l   # → 221
```

## Reference Implementation

`anvil/api/v1/eval.py` — study the response model pattern:
```python
async def get_evaluation_run(...) -> EvaluationRunResponse:
    return EvaluationRunResponse(run_id=run.id, model_id=..., ...)
```
Response models are defined in `schemas_eval.py`.

## Decision Reference

Per `shared-decisions.md` Decision 1: **Option A — direct Pydantic models** (RECOMMENDED). Before committing, grep `anvil/api/static/` JS for `.data`/`.error` access to confirm the frontend does not depend on the `{data, error}` wrapper. If it does, either keep the wrapper for those endpoints or update the JS.

## Scope Notes

- **Exempt** (no `response_model=`): SSE streaming (`/training/stream/{run_id}`, `/sse/eval/{run_id}`), `FileResponse` downloads, HTML page routes (`response_class=HTMLResponse`), `/v1/health`.
- 221 routes is large — this is the biggest spec. Consider splitting into per-domain sub-PRs (training, datasets, experiments, corpora, etc.) even within the single feature branch.
- Coordinate with 072 (error format) and 073 (extra="forbid") — do those first so response/request models are consistent.

## Gotchas

- Some routes currently return the `{data, error}` wrapper. Migrating to direct models changes the response shape — this is a breaking API change. Verify no external consumers depend on the wrapper (the client SDK in `anvil/client/` is the main consumer — check `anvil/client/_shared/` deserialization).
- Reuse response models across routes where the shape is identical (avoid duplication — Principle 13).
- `experiments.py` responses are complex (enriched experiment detail) — coordinate with spec 070 which extracts that logic; the response model should mirror the extracted service's return type.
