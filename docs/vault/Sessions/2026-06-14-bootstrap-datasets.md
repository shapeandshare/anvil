---
title: Bootstrap Demo Datasets Implementation
type: session
aliases:
  - 2026-06-14 Bootstrap Datasets
  - Bootstrap Demo Datasets Session
source: agent
tags:
- type/session-log
created: '2026-06-14T00:00:00.000Z'
updated: '2026-06-18'
---
# Session: Bootstrap Demo Datasets

**Date**: 2026-06-14
**Feature**: 001-bootstrap-datasets

## What was implemented

- **Demo data** (`data/demo/`): 13 files across 3 sizes (small/medium/large) × 4 domains (names, code, prose, structured records) — all public-domain or permissively-licensed
- **DemoBootstrapService** (`anvil/services/demo_bootstrap.py`): New service that walks `data/demo/`, discovers subdirectories (corpora) and `.txt` files (datasets), imports them via existing ingestion pipelines
- **Training fallback replacement**: Removed external `names.txt` download in both `cli.py` and `training.py` — replaced with default demo corpus lookup
- **Inference demo model** (`inference.py`): Replaced hardcoded 8-line `DEMO_CORPUS` with DB-backed lookup + 3-line fallback
- **CLI command**: `anvil bootstrap-datasets` with `--dry-run` and `--verbose` flags
- **Deletion warning**: `DELETE /datasets/{id}` returns HTTP 409 for demo datasets unless `force=true`
- **Auto-bootstrap**: Both on app startup (`app.py` lifespan) and in `make setup`
- **30 test cases** across 3 test files

## Key decisions

1. **Corpus primary, dataset secondary**: Directory-based corpora are the primary demo data format; `.txt` file uploads are secondary. This aligns with the corpus ingestion pipeline being the more common path.
2. **Name-based idempotency**: Bootstrap checks by entity name (`"Demo - {size}/{name}"`) to avoid duplicates. Simpler than content hashing and works with existing DB unique constraints.
3. **Deletion with warning**: Demo datasets can be deleted with a warning (not blocked). `force=true` bypasses. After deletion, re-bootstrap recreates them since the name is now free.
4. **`!data/demo/` in `.gitignore`**: Added exclusion so demo source files are tracked while runtime data (`data/datasets/`, `data/models/`) remains ignored.
5. **Pit of Success**: Auto-bootstrap on startup means users who run `make setup && make run` get demo data without any manual step. Training fallback gives a clear error message if bootstrap hasn't run.

## Files created

- `data/demo/**` (13 demo data files)
- `anvil/services/demo_bootstrap.py` (DemoBootstrapService)
- `specs/009-bootstrap-datasets/**` (12 spec/plan/task artifacts)
- `tests/test_bootstrap.py` (7 test cases)
- `tests/services/test_training.py` (3 test cases)
- `tests/test_api/test_datasets_routes.py` (5 test cases)

## Files modified

- `.gitignore` — added `!data/demo/` exclusion
- `pyproject.toml` — added `anvil-bootstrap-datasets` entry point
- `shared/database.mk` — added bootstrap to `make setup`
- `anvil/cli.py` — added `bootstrap_datasets_main()`, replaced training fallback, updated help text
- `anvil/services/training.py` — replaced `names.txt` download with demo corpus lookup
- `anvil/services/inference.py` — replaced `DEMO_CORPUS` with DB-backed + fallback
- `anvil/api/app.py` — added auto-bootstrap on startup
- `anvil/api/v1/datasets.py` — added deletion warning
- `anvil/db/repositories/corpora.py` — added `get_by_name()`
- `anvil/db/repositories/datasets.py` — added `get_by_name()`
- `AGENTS.md` — updated active technologies
