---
title: 'Session: Domain-Driven Package Decomposition'
type: session-log
tags:
  - type/session-log
  - domain/architecture
  - domain/governance
created: '2026-06-19'
updated: '2026-06-19'
aliases:
  - 'Session: Domain-Driven Package Decomposition'
  - domain-driven-decomposition
source: agent
status: draft
---
# Session: Domain-Driven Package Decomposition

**Date**: 2026-06-19
**Trigger**: User identified that `anvil/services/` had grown to ~29 flat `.py` modules and asked
  for best-practice recommendations. Followed by request to encode Domain-Driven Package
  Decomposition into the constitution alongside one-class-per-file and `__init__.py` rules.

## What was done

### 1. Analyzed module density

| Package | Flat modules | Verdict |
|---------|:-:|---------|
| `anvil/services/` | 29 | 🚩 Exceeds any reasonable threshold |
| `anvil/db/` | 5 | Manageable |
| `anvil/api/` | 2 | Fine |
| `anvil/core/` | 5 | Fine |
| `anvil/storage/` | 2 | Fine |
| `anvil/supervisor/` | 2 | Fine |

Root cause: one-class-per-file produces 2–3 support files (result type, error class, value object)
per service module, all dumped at the parent level.

### 2. Created Constitution Article X

New article with 9 sections:

- **§10.1** — 12-module domain threshold (MUST evaluate)
- **§10.2** — Tightly-coupled types co-locate with their service
- **§10.3** — Cross-domain types go in `_shared/`
- **§10.4** — Naming: plural nouns for domains, underscore-prefixed for internal
- **§10.5** — Nesting limit: max 2 levels from parent root
- **§10.6** — Pairing with Article VI (`__init__.py` Ownership Policy)
- **§10.7** — Pairing with one-class-per-file rule
- **§10.8** — Import discipline in a DDD structure
- **§10.9** — Refactoring discipline (structural-only commits)

Constitution bumped from v1.5.0 to **v1.6.0**.

### 3. Created ADR-022

Filed as [[Decisions/ADR-022-domain-driven-package-decomposition|ADR-022]] with full rationale,
consequences, and compliance rules.

### 4. Updated AGENTS.md

- New agent behavioral principle #8 (Domain-Driven Package Decomposition)
- Architecture Rules bullet referencing Article X
- Project structure diagram updated to show DDD sub-packages
- Renumbered Async Throughout → #9, Forward References → #10

### 5. Executed services/ restructure (65 files)

Moved all 29 flat modules into 6 domain sub-packages:

| Domain | Files | Source modules |
|--------|:-----:|----------------|
| `datasets/` | 12 | corpora, corpus_loader, corpus_load_result, corpus_scan_result, datasets, dataset_import, import_result, parsed_sample, dataset_curation, curation_result, metrics_result, dataset_export |
| `training/` | 5 | training, stop_requested, export, safetensors_export_error, memory_estimator |
| `tracking/` | 6 | tracking, mlflow_capabilities, mlflow_inputs, mps_metrics_collector, mps_sampler_thread, experiments |
| `inference/` | 3 | inference, loaded_model, demo_model_provider |
| `demo/` | 2 | demo_bootstrap, bootstrap_result |
| `_shared/` | 1 | capability_unavailable |

Import rewrites performed across:
- **8 api/v1/*.py files** — updated `...services.X` → `...services.domain.X`
- **6 services/*.py files** — cross-domain imports (`.compute` → `..compute`, `.corpora` → `..datasets.corpora`)
- **1 cli.py** — `from .services.training` → `from .services.training.training`
- **~40 test files** — absolute `anvil.services.X` → `anvil.services.domain.X`
- **1 example** (`train5.py`) — export path updated

### 6. Verified

- All 37 service modules import at new paths
- 85 structural-adjacent tests pass (0 failures)
- 0 old-path imports remain in source, tests, or examples
- Pre-existing enum migration changes (011) are interleaved but unrelated

## Files changed

```
Modified:
  .specify/memory/constitution.md        # Article X + v1.6.0
  AGENTS.md                              # Principle #8, structure diagram, renumbering,
                                         # Recent Changes + Active Technologies
  anvil/api/app.py                       # 3 lazy import paths
  anvil/api/v1/corpora.py                # import path rewrites
  anvil/api/v1/datasets.py               # import path rewrites
  anvil/api/v1/eval.py                   # import path rewrites
  anvil/api/v1/eval_datasets.py          # import path rewrites
  anvil/api/v1/experiments.py            # import path rewrites
  anvil/api/v1/inference.py              # import path rewrites
  anvil/api/v1/registry.py               # import path rewrites
  anvil/api/v1/router.py                 # import path rewrites
  anvil/api/v1/training.py               # import path rewrites
  anvil/cli.py                           # import path rewrites
  anvil/services/datasets/*.py           # moved + import rewrites (12 files)
  anvil/services/training/*.py           # moved + import rewrites (5 files)
  anvil/services/tracking/*.py           # moved + import rewrites (6 files)
  anvil/services/inference/*.py          # moved + import rewrites (3 files)
  anvil/services/demo/*.py              # moved + import rewrites (2 files)
  anvil/services/_shared/*.py           # moved + import rewrites (1 file)
  examples/train5.py                     # import path rewrite
  docs/vault/Reference/ProgressiveWalkthroughs.md  # import path fix
  tests/ (40 files)                      # import path rewrites

Created:
  docs/vault/Decisions/ADR-022-domain-driven-package-decomposition.md
  docs/vault/Sessions/2026-06-19-domain-driven-decomposition.md
  anvil/services/datasets/__init__.py
  anvil/services/training/__init__.py
  anvil/services/tracking/__init__.py
  anvil/services/inference/__init__.py
  anvil/services/demo/__init__.py
  anvil/services/_shared/__init__.py
```

## Key insight

The one-class-per-file rule creates the shallowness problem, and DDD sub-packaging
is the natural cure. Tightly-coupled result/error types are single-class files —
they're easy to move into domain directories because they have no sub-dependencies.
The pairing is synergistic, not conflicting.

## Tags

- type/session-log
- domain/architecture
- domain/governance
- status/draft
