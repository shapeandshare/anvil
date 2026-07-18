# Context — 078 PEP 563 Annotations Consistency

> Cross-references: `../066-codebase-remediation/data-inventory.md` §7. **CORRECTED SCOPE — see below.**

## Current State (verified — ORIGINAL REVIEW WAS WRONG)

The original review claimed `schemas_dataset.py`, `inference_schemas.py`, `schemas_eval.py` were MISSING `from __future__ import annotations`. **This is incorrect.** Verified:

```bash
grep -L "from __future__ import annotations" anvil/api/v1/schemas_*.py
# → (empty — ALL schema files HAVE it)

grep -c "from __future__ import annotations" anvil/api/v1/inference_schemas.py
# → 1 (HAS it)
```

**The files ACTUALLY missing PEP 563** are non-schema route files:
```bash
grep -L "from __future__ import annotations" anvil/api/v1/*.py
```
Returns:
- `__init__.py` (bare package init — exempt per ownership policy)
- `backup.py`
- `compute.py`
- `config.py`
- `eval.py`
- `eval_datasets.py`
- `experiments.py`
- `health_ops.py`
- `registry.py`
- `router.py`

## Revised Scope

This spec becomes "add `from __future__ import annotations` to route files that lack it" (10 files, minus `__init__.py` = 9 route files), NOT the schema files.

**Full audit across the whole package** (broader scope):
```bash
grep -L "from __future__ import annotations" anvil/**/*.py
```
Run this to find ALL non-conforming files. Exempt: bare `__init__.py` files (they only have docstrings, per Constitution Article VI), migration files, data-only modules.

## Constraint

Per AGENTS.md Principle 10: PEP 563 is mandatory. `from __future__ import annotations` MUST be the first import after the copyright header.

## Gotchas

- `__init__.py` files are exempt (docstring-only per ownership policy).
- Placement: after copyright header comment block, before any other import.
- PEP 563 makes all annotations strings at runtime — Pydantic v2 handles this via `get_type_hints()`, so no behavior change. But verify any code using `typing.get_type_hints()` or runtime annotation introspection still works.
- Some route files use `Annotated[X, Depends(...)]` — these work fine with PEP 563.
- Low risk, mechanical change — good candidate to batch with spec 073 as a "quick wins" PR.
