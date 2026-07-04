---
title: 'ADR-047: Shared Environment Snapshot Extraction — Reusable Health/About Page Data'
type: decision
tags:
  - type/decision
  - domain/operations
status: draft
code-refs:
  - anvil/api/v1/_environment.py
  - anvil/api/v1/health_ops.py
  - anvil/api/v1/pages.py
  - anvil/services/training/training.py
  - anvil/services/training/training_run_service.py
created: '2026-07-04'
updated: '2026-07-04'
aliases:
  - ADR-047
  - environment-snapshot-extraction
source: 'About page enrichment session'
---

# ADR-047: Shared Environment Snapshot Extraction — Reusable Health/About Page Data

## Status

Draft

## Context

`GET /v1/health/detailed` (`anvil/api/v1/health_ops.py`) already computed a rich
system snapshot inline: CPU/memory/disk via `psutil`, GPU via `detect_gpu()`,
database connectivity via `MigrationService`, MLflow reachability via a raw
socket probe, and MLflow tracking status via `workbench.tracking.tracking_status`.

The `/v1/about` page (`anvil/api/v1/pages.py`) only passed a `licenses` sequence
to its template. The user requested enriching the About page with exactly this
class of environment/system data, plus fields the health endpoint didn't have:
git commit hash, Python version, and cross-domain asset counts (datasets,
corpora, external models, training runs).

Two options were considered:

1. **Duplicate the probing logic** inline in `about_page()` — fast to write,
   but guarantees drift the first time GPU detection or DB-health logic
   changes (the exact anti-pattern flagged in ADR-045 for training lifecycle
   duplication).
2. **Extract a shared async helper** consumed by both routes.

## Decision

Extract `_collect_environment_snapshot(workbench)` into a new module
`anvil/api/v1/_environment.py`. It owns:

- `_get_git_commit_hash()` — `git rev-parse --short HEAD` from the repo root,
  gracefully degrading to `"unknown"` on `OSError` / `CalledProcessError` /
  `TimeoutExpired` (covers the pip-installed-wheel-with-no-`.git` case).
- The psutil/GPU/DB/MLflow/tracking probing logic, moved verbatim from
  `health_detailed()`.
- New fields: `commit_hash`, `python_version` (via `platform.python_version()`),
  and `asset_counts` (datasets/corpora via `Repository.get_all()` + `len()`;
  external models via `ExternalModelRepository.get_all()`; training runs via
  a new `run_count` property added to `TrainingService`/`TrainingRunService`,
  exposing the existing monotonically-increasing `_running` counter — no new
  persistence layer, per Simplicity First / YAGNI).

`health_detailed()` was refactored to call the shared helper and layer its
own JSON-specific fields (`errors` on GPU, `error` on db/mlflow) on top,
preserving its exact pre-existing response shape (verified: all 39 existing
`tests/unit/api/v1/test_health_ops.py` tests pass unmodified).

One deviation from a strict `float | None` GPU-memory contract: the About
page template renders `gpu.memory_total_gb - gpu.memory_available_gb`
arithmetic, which raises `TypeError` on `None`. The shared helper normalizes
missing GPU memory to `0.0` for both consumers rather than pushing `None`-
handling into the template (template already guards on `gpu.available`
separately for the "No GPU detected" case).

## Consequences

**Easier:**
- Any future consumer of environment/system snapshot data (CLI status
  command, a future `/v1/status` widget, etc.) calls one function instead of
  re-deriving psutil/GPU/DB/MLflow probing.
- `TrainingService.run_count` / `TrainingRunService.run_count` are now public,
  reusable properties — available to any future dashboard needing a training
  activity count without touching MLflow.

**Harder:**
- `_environment.py` is a new small module outside the `services/` layer
  (it lives in `api/v1/` since both consumers are routes in that package) —
  slightly bends the strict Repository → Service → God Class → Routes
  layering, but avoids a heavier service-layer abstraction for what is
  fundamentally read-only route-level data aggregation shared by two GET
  endpoints in the same package.
- `training_runs` asset count is an in-memory, per-process counter (resets on
  restart) rather than a persisted total — accepted as sufficient for a
  glanceable About-page stat; MLflow-backed run search was explicitly
  rejected as unjustified complexity for this use case.

**Not changed:**
- `GET /v1/health/detailed` response shape — byte-for-byte compatible.
- No new runtime dependencies (`psutil`, `subprocess`, `platform` already used).

## Compliance

- `tests/unit/api/v1/test_health_ops.py` (39 tests) must continue to pass
  unmodified — verifies `health_detailed()` backward compatibility.
- `tests/unit/test_about_helpers.py` covers `_get_git_commit_hash()` including
  the `.git`-missing fallback path.
- `tests/e2e/test_about_page.py` covers `GET /v1/about` rendering the full
  environment contract end-to-end.

## See Also

- [[Decisions/README|Decisions]]
- [[Decisions/ADR-045-training-lifecycle-extraction|ADR-045: Training Lifecycle Extraction]] — same "extract shared helper to avoid duplication" pattern, applied to a sibling problem.
- [[Sessions/2026-07-04-about-page-environment-enrichment|Session: About Page Environment & Stats Enrichment]]
