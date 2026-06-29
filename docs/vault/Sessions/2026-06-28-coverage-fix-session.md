---
title: 'Session Log: 2026-06-28 Coverage Fix — 10-Item Test Coverage Burst'
type: session-log
tags:
  - type/session-log
  - domain/tooling
  - domain/training
  - domain/vault
status: draft
created: '2026-06-28'
updated: '2026-06-28'
aliases:
  - coverage-fix-2026-06-28
source: agent
---

# Session Log: 2026-06-28 — Coverage Fix: 10-Item Test Coverage Burst

## Summary

Addressed 10 prioritized coverage gaps across the codebase, raising overall
coverage from 22% to 25% (+443 uncovered statements converted). Work was
delegated in parallel to 10 subagents, each owning one item.

## Items addressed

| # | Priority | Area | What changed |
|---|----------|------|-------------|
| 1 | P1 | Client SDK imports | Fixed 14 broken import paths in 4 test files — unblocks `anvil/client/` from 0% |
| 2 | P1 | test_warm_start collision | Renamed file to resolve pytest module collision |

| 3 | P2 | CLI test failures | Corrected 21+ mock patch targets (local-binding vs source-module bug) — 44 CLI tests pass |
| 4 | P2 | GPU coverage | New `test_gpu.py` with 8 mock-based scenarios — `gpu.py` 21% → 90%+ |
| 5 | P2 | Supervisor services | Full MLflowService lifecycle tests + SIGKILL fallback test — `services.py` coverage boosted |
| 6 | P3 | API route tests | 3 new test files (34 tests) covering training validation, experiment detail, registry detail |
| 7 | P3 | Inference service | Extended tests for attention truncation, multi-token sampling, model params, load_model paths |

| 8 | P3 | Tracking service | Fixed 6 failing tests, extended FakeMlflowClient with 7 methods, added 6 new tests |
| 9 | P3 | Workbench properties | New `test_workbench_properties.py` (21 tests) — `workbench.py` 38% → 89% |
| 10 | P4 | Vault service | Fixed 8 pre-existing test failures (2 source bugs), 4 new test files (60 tests) — 272→343 passing |

## Source bugs discovered and fixed

- [[Discoveries/stripped-vs-line-indent-type-checking-bug|Stripped-vs-Line Indent Bug in TYPE_CHECKING Detection]]:
  `check_relative_imports.py` and `check_guarded_imports.py` used `line.strip()`
  to check indentation, losing the whitespace needed to detect TYPE_CHECKING blocks.
  Also fixed `_in_triple_quoted` single-line docstring handling.

## Key results

- Coverage: 22% → **25.39%**
- 14 modified + 11 new files
- ~1,042 lines added
- All 6 failing tracking tests fixed (now 33/33 passing)
- All 8 failing vault tests fixed (now 343/343 passing)
- All 44 CLI tests passing (was 21 failures)
- pre-existing failures: torch_engine (optional dep)