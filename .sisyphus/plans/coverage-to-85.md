# Plan: Test Coverage from 25% → 85%

**Current**: 25.33% (1701/6715 lines covered)
**Target**: >85% (~5708/6715 lines covered)
**Method**: Iterative batches, each batch adds tests for a domain area, run suite, fix regressions, bump `fail_under`.

## Strategy

1. **Consolidate fixtures first** — Create shared fixtures in `tests/unit/conftest.py` so all unit tests use consistent in-memory DB sessions. This prevents fixture duplication across the ~15 test files that currently inline DB setup.
2. **Parallel delegation** — Each batch spawns subagents in parallel, each responsible for one module's test coverage.
3. **Ratchet upward** — After each batch, update `fail_under` in `pyproject.toml` to the new minimum.
4. **Fix bugs as found** — If a test reveals a bug, fix it before moving on.

## Batch 0: Fixture Consolidation

**Files to modify**: `tests/conftest.py` (root), create `tests/unit/conftest.py`

**Goal**: One `in_memory_session` fixture that ALL repository & service tests share:
- Creates tables, yields AsyncSession, drops tables (pattern already in root conftest)
- Move boilerplate setup out of individual test files (e.g., `test_corpus_repository.py` has inline `db_session` fixture — consolidate)

**New shared fixtures in `tests/unit/conftest.py`**:
- `in_memory_session` — async in-memory SQLite session with table create/drop lifecycle
- Optional: `in_memory_session_no_create` for tests that create their own schema
- Move duplicate `db_session` fixtures from test files to use this

## Batch 1: 0%-Coverage Modules

### 1a. `anvil/db/repositories/training_configs.py` (100 lines, 0%)
- **File**: `tests/unit/db/test_training_config_repository.py`
- **Tests**: CRUD operations (get, get_all, add, delete)
- **Pattern**: Follow `test_corpus_repository.py` — use `in_memory_session`, create `TrainingConfig` instances

### 1b. `anvil/services/governance/governance_service.py` (291 lines, 0%)
- **File**: `tests/unit/services/governance/test_governance_service.py`
- **Fixtures needed**: Mock `LicenseRepository` + `AuditService` (or use `in_memory_session` + real repos)
- **Tests**: 
  - `list_licenses()` — with & without own-content sentinel
  - `seed_catalog()` — idempotent seeding
  - `evaluate_submission()` — all rejection paths (no source, no license, no affirmation, empty/unparseable), and acceptance path with license resolution & own-content
  - `assign_provenance()` — Dataset vs Corpus branches, TypeError for unsupported type
  - `get_provenance()` — dataset target, corpus target, not-found
  - `validate_bundled()` — no license, own-content, approved license

### 1c. `anvil/services/governance/gate_decision.py` (32 lines, 0%)
- **Test in test_governance_service.py**: GateDecision model construction and field defaults

### 1d. `anvil/services/governance/provenance_view.py` (32 lines, 0%)
- **Test in test_governance_service.py**: ProvenanceView defaults

### 1e. `anvil/services/tracking/mlflow_inputs.py` (177 lines, 0%)
- **File**: `tests/unit/services/test_mlflow_inputs.py` (expand existing)
- **Tests**:
  - `content_digest()` static method
  - `resolve_dataset()` — found, not-found (ValueError), empty dataset, with samples
  - `resolve_corpus()` — found, not-found (ValueError), empty directory
  - Mocks: Patch `DatasetRepository`, `CorpusRepository`, file I/O

### 1f. `anvil/services/training/safetensors_export_error.py` (2 lines, 0%)
- **Test**: Just construct the exception — pattern: `SafetensorsExportError("msg")` in test_export.py

## Batch 2: Storage, Supervisor, CLI

### 2a. `anvil/storage/local.py` (156 lines, 32%)
- **File**: `tests/unit/test_local_storage.py`
- **Tests**: 
  - `_resolve()` path resolution + parent directory creation
  - `put()` + `get()` round-trip with bytes
  - `put()` cleanup on failure
  - `delete()` — existing file, non-existent file (idempotent)
  - `list()` — existing dir, non-existent dir
  - `FileInfo` fields

### 2b. `anvil/storage/interface.py` (80 lines, 100%) + `file_info.py` (2 lines, 100%)
- Already covered — skip.

### 2c. `anvil/supervisor/supervisor.py` (224 lines, 25%)
- **File**: `tests/unit/test_supervisor.py`
- **Tests**:
  - `write_pid()` + `read_pid()` — round-trip
  - `kill_pid_file()` — with signal, nonexistent pid, ProcessLookupError
  - `ProcessSupervisor.start()` + `stop()` + `status()` + `stop_all()` + `is_running()`
  - Edge case: duplicate start, stop on nonexistent

### 2d. `anvil/supervisor/services.py` (191 lines, 18%)
- **File**: `tests/unit/test_supervisor_services.py` (expand existing)
  - Actually there's already `tests/unit/test_supervisor_services.py`. Check what's there.
- **Tests**:
  - `MLflowService` initialization (paths, config)
  - `_free_port()` — lsof success, lsof not found, no PIDs found
  - `start()` — normal, already running
  - `stop()` — normal, timeout → SIGKILL, not running
  - `is_running` property, `tracking_uri` property

### 2e. `anvil/cli.py` (check coverage)
- Expand `tests/unit/test_cli.py` with any uncovered CLI functions beyond `db_main`

## Batch 3: Datasets Services

### 3a. `anvil/services/datasets/dataset_import.py` (163 lines, 15%)
- **File**: `tests/unit/services/test_dataset_import.py`... wait, there's already `tests/unit/test_dataset_import.py`
- Expand existing to cover import service methods

### 3b. `anvil/services/datasets/dataset_curation.py` (147 lines, 16%)
- Expand `tests/unit/test_dataset_curation.py`

### 3c. `anvil/services/datasets/dataset_export.py` (36 lines, 36%)
- Expand `tests/unit/test_dataset_export.py`

### 3d. `anvil/services/datasets/corpora.py` (74 lines, 32%)
- **File**: `tests/unit/services/test_corpus_service.py` — expand coverage for CorpusService methods

### 3e. `anvil/services/datasets/corpus_loader.py` (97 lines, 22%)
- **File**: `tests/unit/services/test_corpus_loader.py` — expand

## Batch 4: Inference & Demo Services

### 4a. `anvil/services/inference/inference.py` (374 lines, 7%)
- **File**: `tests/unit/services/test_inference.py` (172 lines exist) — expand
- **Focus**: Ensure all methods have coverage for happy paths and error paths

### 4b. `anvil/services/inference/demo_model_provider.py` (186 lines, 12%)
- Expand existing tests

### 4c. `anvil/services/demo/demo_bootstrap.py` (156 lines, 29%)
- Expand `tests/test_bootstrap.py`

## Batch 5: Tracking & Training Services

### 5a. `anvil/services/tracking/tracking.py` (414 lines, 13%)
- **File**: `tests/unit/services/test_tracking_service.py` (495 lines exist) — expand
- Focus on uncovered methods

### 5b. `anvil/services/training/training.py` (133 lines, 23%)
- Expand `tests/unit/services/test_training_phases.py` or create focused tests

### 5c. `anvil/services/training/export.py` (86 lines, 17%)
- Expand `tests/unit/services/test_export.py`

### 5d. `anvil/services/training/memory_estimator.py` (100 lines, 35%)
- Expand `tests/unit/services/test_memory_estimator.py`

### 5e. `anvil/services/tracking/mps_metrics_collector.py` (38 lines, 34%)
- Expand `tests/unit/services/test_metrics_collectors.py`

### 5f. `anvil/services/tracking/mlflow_capabilities.py` (12 lines, 25%)
- Expand `tests/unit/services/test_mlflow_capabilities.py`

## Batch 6: Compute & Chunking

### 6a. `anvil/services/compute/registry.py` (28 lines, 39%)
- Expand `tests/unit/services/compute/test_registry.py`

### 6b. `anvil/services/compute/resolve.py` (49 lines, 22%)
- Expand `tests/unit/services/compute/test_resolve.py`

### 6c. `anvil/services/compute/local_stdlib_backend.py` (36 lines, 50%)
- Expand `tests/unit/services/compute/test_local_backend.py`

### 6d. `anvil/services/compute/modal_backend.py` (87 lines, 28%)
- Expand `tests/unit/services/compute/test_modal_backend.py`

### 6e. `anvil/services/chunking/window_chunker.py` (20 lines, 20%) + `file_chunker.py` (6 lines, 50%) + `line_chunker.py` (4 lines, 75%)
- Expand `tests/unit/services/test_chunking.py`

### 6f. `anvil/db/repositories/` remaining low-coverage repositories
- `audit_events.py` repo, `curation.py` repo, `datasets.py` repo, `import_source_repository.py`, `licenses.py` repo

## Batch 7: API Routes & Workbench

### 7a. `anvil/workbench.py` (101 lines, 53%)
- Expand workbench tests for uncovered accessors

### 7b. `anvil/api/v1/` routes — expand API route tests

### 7c. `anvil/gpu.py` (68 lines, 24%)
- Tests for GPU detection and device handling

## Verification

After each batch:
1. Run `pytest tests/ -v --cov=anvil --cov-report=term-missing --ignore=tests/system -x`
2. Fix any test failures (pre-existing or from new tests)
3. Update `fail_under` in `pyproject.toml` to current coverage percentage
4. Fix any bugs found during testing
5. Clean diagnostics with `lsp_diagnostics` on changed files
6. Mark batch complete, move to next

## Consolidation Rules

- **No fixture duplication**: All shared fixtures go in `tests/unit/conftest.py` or `tests/conftest.py`
- **No `db_session` inline fixtures**: Centralize to `in_memory_session` in conftest
- **Use mocks for external services**: MLflow, Modal, network calls
- **Use real SQLite for repos**: In-memory SQLite via async engine for all repository tests
- **Follow existing pattern**: Look at `test_audit_service.py` and `test_corpus_repository.py` for style guide
- **Prefer property-based assertions**: Not just "doesn't crash" — assert return values, side effects, error messages
- **Fix bugs as found**: Don't paper over them — fix root cause