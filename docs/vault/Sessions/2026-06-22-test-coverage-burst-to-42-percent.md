---
aliases:
  - Test coverage burst to 42% — parallel sub-agent test generation
created: '2026-06-22'
source: agent
tags:
  - type/session-log
  - domain/tooling
title: Test coverage burst to 42% — parallel sub-agent test generation
type: session-log
updated: '2026-06-22'
---
# Test Coverage Burst to 42%

**Date:** 2026-06-22

## Summary

Increased unit test coverage from **22.72% → 42%** by spinning off 7 parallel sub-agents to add tests across under-covered areas. Coverage now comfortably exceeds the 23% threshold. 846 tests passing, 0 failures.

## What Changed

### Methodology

Used Sisyphus's orchestration mode: decomposed the coverage gap into 7 independent work units and delegated each to a `category="unspecified-high"` sub-agent running in parallel. Each agent received:
- Explicit file paths and coverage targets
- Existing test patterns and conventions
- MUST DO / MUST NOT DO constraints

After all agents completed (3 succeeded, 4 partially completed), a cleanup pass fixed 11 test bugs introduced by the sub-agents (6 CLI failures, 4 demo_bootstrap failures, 1 inference failure).

### Production Bug Fix

- **`anvil/cli.py:_load_docs()`**: `import asyncio` was scoped inside the `if corpus_id is not None:` branch. Python's compiler treats any name assigned in a function body as a local throughout the function, so `asyncio.run(_load_default())` on the else branch raised `UnboundLocalError`. Moved `import asyncio` to the top of the function body.

### Files Added (10 new files)

| File | Lines | Area |
|------|-------|------|
| `tests/unit/services/content/test_corpus_service.py` | 456 | Content services |
| `tests/unit/services/content/test_import_service.py` | 235 | Content services |
| `tests/unit/services/content/test_ingestion_service.py` | 677 | Content services |
| `tests/unit/services/content/test_validation_service.py` | 646 | Content services |
| `tests/unit/services/test_demo_bootstrap.py` | 548 | Demo bootstrap |
| `tests/unit/services/test_vault_connectivity.py` | 210 | Vault services |
| `tests/unit/services/test_vault_hygiene.py` | 364 | Vault services |
| `tests/unit/services/test_vault_scoring.py` | 177 | Vault services |
| `tests/unit/services/test_vault_structural.py` | 182 | Vault services |
| `tests/unit/services/test_vault_topology.py` | 143 | Vault services |

### Files Modified (5 existing)

| File | Lines Added | Area |
|------|-------------|------|
| `tests/unit/core/test_engine.py` | +573 | Core engine |
| `tests/unit/services/test_export.py` | +116 | Model export |
| `tests/unit/services/test_inference.py` | +237 | Inference |
| `tests/unit/services/test_memory_estimator.py` | +149 | Memory estimation |
| `tests/unit/test_cli.py` | +918 | CLI entry points |

### Coverage Gains by Module

| Module | Before | After |
|--------|--------|-------|
| cli.py | 0% | ~40% |
| services/training/export.py | 0% | ~40% |
| services/training/memory_estimator.py | 30% | ~70% |
| services/inference/inference.py | 5% | ~35% |
| services/vault/hygiene.py | 0% | ~50% |
| services/vault/structural.py | 0% | ~25% |
| services/vault/connectivity.py | 0% | ~25% |
| services/vault/scoring.py | 0% | ~50% |
| services/vault/topology.py | 0% | ~40% |
| services/content/corpus_service.py | 0% | ~60% |
| services/content/ingestion_service.py | 0% | ~25% |
| services/content/validation_service.py | 0% | ~25% |
| services/content/import_service.py | 0% | ~25% |
| **Overall** | **22.72%** | **42.00%** |

## Key Discoveries

1. **MagicMock `id` attribute**: `id` is a built-in Mock method. `MagicMock(id=1, ...)` does NOT set `id` as an attribute — it gets shadowed. Use `types.SimpleNamespace` instead for data-only objects with an `id` field. Found while debugging `test_list_corpora` (`TypeError: unsupported format string passed to MagicMock.__format__`).
2. **`import asyncio` scoping**: Python treats any name assigned anywhere in a function body (even inside `if`/`for` blocks) as a local variable throughout the entire function. `import asyncio` inside a conditional branch makes `asyncio` unbound in other branches.
3. **Sub-agent test quality**: Autonomous test-writing agents produce many tests but often introduce subtle bugs (wrong assertions, missing fixtures, mock configuration errors). Budget 15-20% overhead for review and fix-up after parallel delegation.
4. **Inference test performance**: Tests that train real models (`train(docs, num_steps=20, ...)`) take ~5 minutes for 31 tests. These need to be run separately from the fast unit test batch to avoid timeouts.

## Related Artifacts

- PR #150 — https://github.com/shapeandshare/anvil/pull/150
