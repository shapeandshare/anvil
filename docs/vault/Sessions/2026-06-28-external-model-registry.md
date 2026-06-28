---
title: 040 External Model Registry — Implementation
type: session-log
tags:
  - type/session-log
  - domain/training
  - domain/tracking
  - spec/040
status: reviewed
source: agent
created: '2026-06-28'
updated: '2026-06-28'
aliases: 040 External Model Registry Implementation
related:
  - '[[040 External Model Registry]]'
  - '[[038 Fine-Tuning Arc]]'
  - '[[Reference/FineTuningArchitectureDecisions]]'
---

# Session: 040 External Model Registry — Implementation

**Date**: 2026-06-28  
**Feature**: 040 External Model Registry & Import Paradigm  
**Branch**: `040-external-model-registry`  

## Summary

Implemented the full spec 040: source-agnostic ModelSource abstraction,
async job-based import orchestration, database schema, CLI, REST API,
and SDK client for importing external models as tracked metadata entries.

## Key Discoveries

### `import` is a Python reserved keyword
A package named `import/` is illegal — `from ..import.x import Y` is a
syntax error. The domain sub-package was named `model_import/` instead.

### No `[finetune]` extra existed
Assumed `huggingface_hub` behind a `[finetune]` extra, but verification
confirmed only `gpu`, `compute`, `vault-health`, and `dev` extras exist.
The extra was created as part of this feature.

### No native ORM model registry
Spec 003's "model registry" is entirely MLflow-based. There are zero
native ORM tables for registered models. Migration 001 confirms
`registered_models` / `model_versions` tables were created but later
dropped. ExternalModel is a new first-class ORM entity.

### ImportJob name collision
An `ImportJob` model already exists (`anvil/db/models/content_import_job.py`)
for the content-repository domain. Renamed to `ModelImportJob` to avoid
class name collision.

### Workbench has a legacy duplicate in CLI
`anvil/cli.py` defines a separate, minimal `AnvilWorkbench` class that
only wraps TrainingService. The real workbench is in `anvil/workbench.py`.
CLI commands use `AsyncSessionLocal()` directly, not the real workbench.

### Model registration via `models/__init__.py` is a no-op
`anvil/db/registry.py` does `from . import models` claiming it registers
models, but `models/__init__.py` is docstring-only. Models register via
transitive imports through repositories. Added explicit imports.

### Idempotency must check resolved revision_sha
The FR-006a idempotency requirement (same source+identifier+revision)
cannot be checked before metadata resolution because the resolved
`revision_sha` may differ from the user-requested `revision` (e.g.
symbolic `main` → concrete SHA, or local → `"local"`). Dedup moved to
`run_import` after resolution.

## Session Activity

1. Updated `feature.json` to point to spec 040
2. Created feature branch `040-external-model-registry`
3. Ran `/speckit.clarify` — resolved 5 ambiguities (idempotency, delivery
   surfaces, HF auth, async jobs, error classification)
4. Ran `/speckit.plan` — generated plan, research, data-model, contracts,
   and quickstart artifacts
5. Ran `/speckit.tasks` — generated 32 implementation tasks across 4 phases
6. Performed critical review — discovered 7 codebase-truth errors (package
   naming, finetune extra, ImportJob collision, session scoping, model
   registration, API Depends pattern, huggingface_hub version range)
7. Ran `/speckit.implement` — implemented all 32 tasks
8. Second critical review — found and fixed idempotency bug, copy-paste
   revision error, false completion claim for test_hf_source.py, mypy errors

## Vault Changes

- [[040 External Model Registry]] — spec note updated with clarifications
- [[040 External Model Registry - spec]] — spec updated with FR-005b/c/d
- Sessions/2026-06-28-external-model-registry — this session log

## Links

- [[Specs/040 External Model Registry/spec.md]]
- [[Specs/040 External Model Registry/plan.md]]
- [[Specs/040 External Model Registry/tasks.md]]
- [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc (umbrella)]]