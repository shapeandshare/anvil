---
aliases:
  - 'Session: Demo Data Bootstrap Guard'
  - demo-data-bootstrap-guard
created: '2026-06-19'
source: agent
status: draft
tags:
  - type/session-log
  - domain/architecture
  - domain/tooling
  - domain/ui
title: 'Session: Demo Data Bootstrap Guard Implementation'
type: session-log
updated: '2026-06-19'
---
# Session: Demo Data Bootstrap Guard

**Date**: 2026-06-19
**Trigger**: Ensure demo data bootstraps only on first startup of a fresh environment, with optional re-trigger from the ops menu.

## What was done

### 1. Specified feature (specify → clarify → plan → tasks → analyze → implement)

- Full Spec Kit flow: `/speckit.specify` → `/speckit.clarify` (1 question answered) → `/speckit.plan` → `/speckit.tasks` → `/speckit.analyze` (4 findings resolved) → `/speckit.implement`.
- 13 implementation tasks across 5 phases (foundational → US1 → US2 → US3 → polish).

### 2. Implemented changes

**Foundation**: Added `count_by_origin()` method to both `CorpusRepository` and `DatasetRepository` — enables origin-based first-run detection without a new table.

**User Story 1 (P1 — Lifespan guard)**:
- Modified `anvil/api/app.py` lifespan handler to check `count_by_origin("bundled")` before calling `bootstrap_all()`. If bundled data exists, logs debug and skips. If not, proceeds with full bootstrap.
- The warmup thread (FR-007) is unaffected — it runs in a separate daemon thread after the guard.

**User Story 2 (P2 — Ops menu re-trigger)**:
- New `POST /v1/demo/bootstrap` endpoint in `anvil/api/v1/health_ops.py` with server-side `asyncio.Lock` returning HTTP 409 on contention (FR-009).
- New "↻ Re-bootstrap Demo" button in the System Actions section of `operations.html` with `ops.rebootstrapDemo()` JS handler following the existing toast pattern.

**User Story 3 (P3 — CLI consistency)**:
- Modified `anvil/cli.py` `bootstrap_datasets_main()` to call `bootstrap_all()` first, then conditionally print the banner only if entities were created.

**Testing**: 3 new tests (`test_count_by_origin`, `test_guard_skips`, `test_rebootstrap`, `test_cli_banner`). Also fixed 6 pre-existing tests that had stale monkeypatch paths from the DDD restructure (012) and were blocked by missing provenance manifest — added `_svc_with_provenance()` helper and `PROVENANCE_MANIFEST` fixture constant.

**Quality gates**: ruff clean on all changed files, 11/11 tests pass, coverage 26.28% (exceeds 23% threshold).

### 3. Vault enrichment

- Wrote this session log.
- Wrote discovery note about provenance manifest monkeypatch technique.

## Key decisions

| Decision | Rationale |
|----------|-----------|
| First-run detection via `origin="bundled"` count query | Existing schema field already marks demo entities; no new table needed |
| Two-layer FR-009 concurrency (client debounce + server asyncio.Lock) | Spec originally said "or debouncing"; clarified to both for defense-in-depth |
| Re-trigger is not a hard reset | Delete-and-reimport is out of scope; users delete entities individually |
| Provenance manifest monkeypatch via `_provenance_manifest` attribute | The manifest is loaded from package resources (not DEMO_DIR), so tests needed direct injection |

## Discoveries

- The provenance manifest `_provenance_manifest` is loaded from `_resources.files("anvil")` (installed package), not from `DEMO_DIR`. Test fixtures that mock `DEMO_DIR` also need to inject the manifest directly.
- The provenance lookup strips `.txt` suffix from relative paths before key lookup: `key = rel.removesuffix(".txt")`. Manifest keys should NOT include `.txt`.
- Several existing tests (`test_bootstrap.py`) had stale `anvil.services.demo_bootstrap` monkeypatch paths from before the 012 DDD restructure — the module moved to `anvil.services.demo.demo_bootstrap`.

## Related

- [[Specs/015 Demo Data Bootstrap/015 Demo Data Bootstrap|015 Demo Data Bootstrap]] — feature specification
- [[Decisions/ADR-011-name-based-demo-bootstrap-idempotency|ADR-011: Name-Based Demo Bootstrap Idempotency]] — architecture decision record
- [[Reference/ArchitectureOverview|Architecture]] — startup lifecycle and service architecture context
