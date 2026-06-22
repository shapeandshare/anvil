---
title: Learning Arc — Platform Lessons Expansion
type: session-log
tags:
  - type/session-log
  - domain/content
  - domain/governance
  - domain/tracking
  - domain/training
created: '2026-06-21'
updated: '2026-06-21'
status: draft
aliases: Learning Arc — Platform Lessons Expansion
source: agent
---
# Learning Arc — Platform Lessons Expansion

**Session**: A review found the learning arc (`anvil/api/v1/learning.py`) covered the model/engine fundamentals from the ground up, but left five platform-layer subsystems with no lesson. This session added rigorous, code-accurate lessons for all five, closing the gap between "understand the LLM" and "understand the whole anvil system".

## What was done

Added five new lessons to the `LEARNING_ARC` (and `LEARNING_ARC_LESSONS` index list), each a text-only `*_STEPS` constant rendered through the existing `archetypes/concept.html` carousel (same pattern as the Export and Cloud Compute lessons — no JS widget required):

| Lesson | Route | Source of truth |
|--------|-------|-----------------|
| Chunking Strategies | `/v1/learn/chunking` | `anvil/services/chunking/` |
| Content Versioning | `/v1/learn/content-versioning` | `anvil/services/content/`, [[Decisions/ADR-033-content-repository-substrate]] |
| Experiment Tracking | `/v1/learn/experiment-tracking` | `anvil/services/tracking/tracking.py`, [[Decisions/ADR-016-mlflow-primary-lineage]], [[Decisions/ADR-009-mlflow-pyfunc-model-compliance]] |
| Data Governance | `/v1/learn/governance` | `anvil/services/governance/`, [[Decisions/ADR-023-responsible-data-governance]] |
| Memory & Divergence | `/v1/learn/memory-divergence` | `anvil/services/training/memory_estimator.py`, `throughput.py` |

Supporting changes:

- **Route handlers** — five new `*_concept_page` handlers in `learning.py`, mirroring the existing 13.
- **Glossary** — 14 new `GLOSSARY_TERMS` entries (Chunker, Overlap, Content Blob, Manifest, VersionRef, Weight Replication, MLflow Run, Model Registry, Fire-and-Forget, Provenance, Acceptable-Use Gate, Audit Chain, Memory Estimate, Divergence).
- **Cross-links** — wired the new lessons into workspace pages via `related_lessons(...)` in `anvil/api/v1/pages.py`: experiments→experiment-tracking, operations→memory-divergence, datasets→chunking+governance, content→content-versioning+governance.
- **Tests** — six new e2e render-smoke tests in `tests/e2e/api/test_pages.py` (five lesson routes + extended `test_learn_index` to assert all five appear in the index).

## Accuracy method

Content facts were extracted by read-only exploration of the live code (not from memory) before any prose was written. Key verified facts:

- Window chunk stride is `max(1, int(block_size * (1 - overlap)))`; overlap range is the half-open `[0.0, 1.0)`.
- Content blobs and manifests are both SHA-256-addressed; weight replication is `factor = max(1, round(weight))` (integer replication, not sampling).
- `TrackingService` is fire-and-forget (sets `_degraded`, silently no-ops) — the deliberate opposite of `AuditService`, which raises on write failure.
- Audit chain genesis `prev_hash` is 64 zeros; `verify_chain()` returns `ChainVerifyResult(valid, break_at_sequence, entries_checked)`.
- Memory estimate: weights + gradients + Adam (2x params) + KV cache in FP32, with `peak = total * 2`; OOM flagged above 90% of available memory.
- Divergence: `classify_divergence(loss)` → `DivergenceReason.LOSS_NAN` / `LOSS_INF`; raises `DivergenceError` and emits a `divergence` SSE event.

## Verification

- `ruff check` on changed files: **pass** (fixed initial RUF001 ambiguous `×` → `x`).
- `black` / `isort` on changed files: **pass** (after black normalization).
- `tests/e2e/api/test_pages.py`: **all pass** (5 new + extended index).
- One pre-existing failure (`test_related_lessons.py::test_training_page_renders_related_lessons_row`, a 303 auth redirect) confirmed via `git stash` to be unrelated to this work.
- `mypy --strict`: no new errors introduced; new handlers follow the existing untyped FastAPI-handler baseline.

## Follow-up: Animated concept widgets (same session)

The text-only lessons were upgraded with signature animated visualizations so each "pops", matching the engine lessons' widget pattern. Five new vanilla-JS widgets were added under `anvil/api/static/js/widgets/`, each modeled on the existing `cloud-compute.js` contract (IIFE, ES5, `_token()` design-token theming, Play/Step/Reset, `prefers-reduced-motion`):

| Widget | Signature animation |
|--------|---------------------|
| `chunking.js` | A window box glides across a text strip by the real `max(1, round(block_size·(1-overlap)))` stride; captured chunks drop in as chips. Strategy + overlap toggles. |
| `content-versioning.js` | SHA-256 hashes scramble-then-settle; two identical files merge (dedup); weight fan-out (`max(1, round(weight))`); manifest → version chain → MLflow lineage. |
| `governance.js` | Audit blocks chain in; tampering a past block cascades a downstream break to red; Verify reports VALID/BROKEN as text + color. |
| `experiment-tracking.js` | An SVG loss sparkline draws left→right with a live ticking readout; params/artifacts/registry phases illuminate; an "MLflow offline" toggle shows the fire-and-forget degrade. |
| `memory-divergence.js` | A stacked memory bar builds segment-by-segment (weights/gradients/Adam 2x/KV) with a 2x-headroom ghost and OOM status; a Spike-LR button drives the loss curve to NaN and halts with a DivergenceError banner. |

Wiring: `concept.html` gained the five `<script>` includes and `WIDGET_CLASSES` registry entries (and finally wired the previously-orphaned `cloud-compute.js`); each new lesson's first `*_STEPS` entry got a `"widget"` key so the carousel mounts the widget.

### Design-system / UX compliance (S4/S3 hard gates)

- All controls are `<button>` with `aria-label`; clickable diagram nodes use `role="button"` + `tabindex` + Enter/Space keydown. No `<div>`/`<span>` click handlers.
- `:focus-visible` styles present; no `outline: none` without replacement.
- Animations use `transform`/`opacity` only — no `transition: all`; every widget honors `prefers-reduced-motion` by jumping to the end state (no information lost).
- State never signaled by color alone — every red/green/orange is paired with a text label. Numeric readouts use `tabular-nums`. Theming is 100% via `tokens.css` custom properties (no hardcoded hex except token fallbacks). No unicode `×` in source (RUF001).

### Verification

- `node --check` on all 5 widgets: **valid JS**.
- `scripts/ci/ux_lint.py` on the widgets: **clean (`✓`)**. The one S4 it flags (`concept.html:45 {{ step.body | safe }}`) is **pre-existing** (unchanged in git HEAD; `data-fundamentals.html` carries the identical baseline) — lesson bodies are author-controlled trusted strings.
- `tests/e2e/api/test_pages.py`: **33 pass**, including new `data-widget="…"` mount assertions on all five lessons.
- `ruff` / `black` on changed Python: **pass**.

## Notes / follow-ups

- The repo-wide lint/typecheck baseline carries pre-existing failures in untouched files (`tests/unit/test_supervisor.py` docstrings; missing return annotations across all route handlers; the `concept.html` `|safe` S4) — out of scope for this change.
- Widgets are illustrative (hardcoded sample data), not wired to live backend endpoints — appropriate for these platform concepts which have no per-model data to drive them.
