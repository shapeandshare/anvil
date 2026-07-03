---
title: "Session: Unit Test Coverage Burst — Smart Picks to 100% on 5 Modules"
type: session-log
tags:
  - type/session-log
  - domain/tooling
  - status/draft
created: '2026-07-03'
updated: '2026-07-03'
aliases:
  - unit-test-coverage-burst-2026-07-03
status: draft
source: agent
---

# Session: Unit Test Coverage Burst — Smart Picks to 100% on 5 Modules

**Date**: 2026-07-03
**Trigger**: Increase unit test coverage — user request with "Smart picks only" scope.

## Summary

Used the Sisyphus orchestration framework to identify, scope, and execute a targeted coverage burst. Analyzed the full coverage report (`make test` with `--cov-branch`), identified five pure-logic modules with existing test infrastructure as highest-value targets, and delegated expansion tasks to four parallel `deep` sub-agents.

## Modules Brought to 100% (Statement + Branch)

| Module | Before | After | Type |
|--------|--------|-------|------|
| `services/_shared/version_utils.py` | 0% | 100% | **New test file** |
| `storage/local.py` | 25% stmt, ~94% branch | 100% / 100% | Expanded |
| `services/compute/registry.py` | 34% | 100% | Expanded |
| `services/chunking/window_chunker.py` | 14% | 100% | Expanded |
| `services/training/throughput.py` | 27% | 100% | Expanded |

### covered: version_utils.py (new file)

- `read_version()` — happy path, missing version, missing file, commented versions, no-match lines
- `parent_version()` — parent exists, first commit (no parent), version missing in parent
- `classify_increment()` — BREAKING CHANGE→MAJOR, feat→MINOR, fix→PATCH, perf/refactor/chore/docs/ci/test/style/build→NONE, unknown→NONE

### Covered: storage/local.py (expanded from 15→27 tests)

- **Constructor**: explicit `base_path` branch (neither `paths` nor default)
- **Resolve**: deeply nested paths (`a/b/c/.../z.txt`), trailing slash normalization
- **Put/Get**: empty stream, multi-chunk stream reassembly, large file >64KiB exercises multiple `while` loop iterations, nested subdirectory roundtrip
- **Delete**: nested subdirectory, parent directory preserved
- **List**: **covered the one uncovered branch** `p.is_file()` False — listing a directory with subdirectory entries skips them correctly; nested prefix listing; empty existing directory

### Covered: compute/registry.py (expanded from 5→10 tests)

- `_label_for()` — known ComputeBackend values (`auto`→`"Auto"`, `local-cpu`→`"Local (CPU)"`); unknown name returns raw name
- Register overwrite (second call replaces the first)
- Deps passthrough with str, int, list, dict, None
- `reason` field on factory failure (`"failed to initialise"`)

### Covered: chunking/window_chunker.py (expanded FixedSizeWindowChunker tests)

- `overlap=0.0` disjoint non-overlapping windows
- Exact stride boundary (text length is multiple of stride)
- Partial final chunk (text doesn't divide evenly)
- Large overlap (0.9) — stride bottoms at 1
- `block_size=1` with 0 overlap — every char its own chunk
- Long text produces expected chunk count
- Stride bottoms at 1 when `block_size * (1 - overlap) < 1`
- Every chunk ≤ `block_size`

### Covered: training/throughput.py (expanded from 11→17 tests)

- Minimum window (`window=1` — deque retains 1 sample, rates are `None`)
- Zero tokens (`record(0, ...)` — token rate is 0.0)
- Identical timestamps (zero elapsed — all rates are `None`)
- `eta_sec` with step beyond total (clamped to 0)
- Fresh tracker state (creating new tracker == reset)
- Large token counts (`10**9`) don't overflow

## Key Decisions

- **Module selection**: Prioritized pure-logic modules (no DB, no API mocking) with existing test files and known coverage gaps. Avoided modules with heavy mocking requirements (inference, tracking, vault) or routes requiring FastAPI test client setup.
- **Delegation pattern**: Used `task(category="deep", ...)` for each module expansion in parallel, with exhaustive "MUST DO / MUST NOT DO" prompts specifying exact coverage gaps, file paths, and constraints. This allowed 4 modules to be expanded concurrently.
- **TDD compliance**: Each test was written as a characterization test (capturing current behavior) since no source code was modified. This is consistent with the project's legacy-code exemption in the TDD mandate.
- **Parallel execution**: 4 sub-agents ran simultaneously, each independently expanding one test file. The new `test_version_utils.py` test file was written by the orchestrator directly (not delegated) since it was a greenfield creation.

## Files Changed

- `shared/testing.mk` — Added `test_training_throughput.py` and `test_version_utils.py` to `UNIT_BATCH1`
- `tests/unit/services/test_version_utils.py` — **New file** (15 tests, 152 lines)
- `tests/unit/test_local_storage.py` — Expanded from 15→27 tests
- `tests/unit/services/compute/test_registry.py` — Expanded from 5→10 tests
- `tests/unit/services/test_chunking.py` — Expanded `FixedSizeWindowChunker` (+8 tests)
- `tests/unit/services/test_training_throughput.py` — Expanded from 11→17 tests

## Verification

- **1,079 tests pass** (791 batch 1 + 288 batch 2)
- **`make lint`** — clean
- **Coverage**: 5 modules at 100% statement + branch (was average ~20%)
- No source code was modified
