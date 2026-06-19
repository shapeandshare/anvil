# Contract: Packaging (wheel contents & pyproject)

**Feature**: `009-pip-installable-package`

Defines what the built wheel MUST contain and how `pyproject.toml` MUST be configured. Verifiable by inspecting the `.whl` and a clean install.

## pyproject.toml requirements

- `[project] requires-python = ">=3.11"` retained (drives FR-006 fail-fast).
- `[project] version` is the single source of truth for the artifact version (FR-015).
- `[project.dependencies]` lists every base runtime dependency; torch/nvidia-ml-py remain in `[project.optional-dependencies] gpu`; modal in `compute` (FR-002, FR-014).
- `[project.scripts]` MUST NOT contain `anvil-migrate-registry` (phantom — Decision 8). All remaining entry points MUST map to existing functions.
- `[tool.setuptools.package-data]` MUST declare (relative to `anvil/`):
  - `_resources/alembic.ini`
  - `_resources/migrations/*.py`, `_resources/migrations/*.mako`, `_resources/migrations/scripts/*.py`, `_resources/migrations/versions/*.py`
  - `data/demo/**/*.txt`, `data/demo/**/*.md`
  - `api/static/**/*`, `api/templates/**/*`
- `[tool.ruff] per-file-ignores` and `[tool.coverage.run] omit` referring to repo-root `migrations/**` MUST be updated to the new in-package path (or removed) so migrations are linted/covered consistently with policy.

## Wheel content contract (verify via `python -m zipfile -l anvil-*.whl` or `unzip -l`)

The wheel MUST contain, at minimum:

```
anvil/__init__.py
anvil/_resources/alembic.ini
anvil/_resources/migrations/env.py
anvil/_resources/migrations/script.py.mako
anvil/_resources/migrations/versions/001_initial.py
... (ALL version files incl. 12a4027155f0_merge_002b_and_006_heads.py)
anvil/data/demo/medium/alice/...           # at least the default demo corpus
anvil/api/static/...                        # css/js assets
anvil/api/templates/...                     # jinja templates
anvil-<version>.dist-info/METADATA          # lists base deps; Requires-Python: >=3.11
```

The wheel MUST NOT contain torch, nvidia-ml-py, or modal as install requirements of the base distribution.

## Acceptance checks

| ID | Check | Maps to |
|----|-------|---------|
| PKG-1 | `python -m build --wheel` produces exactly one `anvil-*.whl` without error | FR-001, SC-001 |
| PKG-2 | Wheel listing shows alembic.ini, all migration versions, demo content, static, templates | FR-003, SC-003 |
| PKG-3 | `dist-info/METADATA` lists all base deps and `Requires-Python: >=3.11` | FR-002, FR-006 |
| PKG-4 | Base install in clean venv does NOT install torch | FR-014, SC-009 |
| PKG-5 | `anvil-migrate-registry` absent from entry points; every other script importable | FR-007 |
