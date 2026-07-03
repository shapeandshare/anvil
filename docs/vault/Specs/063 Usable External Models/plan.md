# Implementation Plan: Usable External Models

**Branch**: `063-usable-external-models` | **Date**: 2026-07-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `docs/vault/Specs/063 Usable External Models/spec.md`

## Summary

Make imported HuggingFace external models first-class citizens in anvil. Currently, imported models' downloaded assets sit unused — every load path fetches from HF Hub. This plan adds a canonical HF-standard storage layout, a bare external model inference path, local-first asset resolution for all consumers (adapter, training, evaluation), and UI affordances (Play, Training) when assets are available. Three user stories: run locally (P1), fine-tune from local weights (P2), reuse local weights everywhere (P3).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, async SQLAlchemy (existing); `transformers`/`peft`/`torch` (existing `[finetune]` extra); `huggingface_hub` (existing `[finetune]` extra); stdlib `pathlib`, `tempfile`
**Storage**: SQLite (anvil-state.db, WAL) via async SQLAlchemy; LocalFileStore at `data/models/{model_id}/hf/` for assets
**Testing**: pytest, pytest-asyncio, httpx (existing e2e fixtures)
**Target Platform**: Linux/macOS server
**Project Type**: Python package + FastAPI web service
**Performance Goals**: Model load from local assets should complete in a fraction of the time of a network fetch (no specific SLA — load observability via structured logging will track this).
**Constraints**: New storage layout at `models/{model_id}/hf/` with canonical filenames (per Q1 clarify). `from_pretrained(local_dir)` requires `[finetune]` extra — must degrade gracefully when absent. Existing sha256-keyed layout (`assets/{sha256}/`) is **not** migrated or removed in this feature.
**Scale/Scope**: Single-host local storage; remote/SaaS routing out of scope.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity First gate (Article XI — hard MUST)**: Confirm this plan favors the simplest, most boring solution that meets the requirement:

- [x] **Simplest viable** (§11.1) — Canonical HF directory layout (`from_pretrained(local_dir)`) is the simplest path to make assets loadable. No custom loaders, no symlink farms, no manifest-based resolution.
- [x] **Boring over novel** (§11.2) — Using `from_pretrained()` which is the existing, mature HF loading mechanism. Adding a new code path in `load_model()` that branches on external model ID is the same pattern used for experiment artifacts and MLflow resolution.
- [x] **YAGNI** (§11.3) — No speculative generality. The local-load branch handles only runnable models. No plugin system, no configurable storage backends.
- [x] **Reuse first** (§11.4) — Reuses existing `_hf_state_dict_to_anvil_format()` conversion helper, existing `_compose_adapter_with_repo()` for adapter composition, existing `ExternalModelRepository` for DB lookups, existing `ModelAssetService` for download. The only new code is the resolution branch in `load_model()` and the storage layout change in the download service.
- [x] **Testable** (§11.6) — Each path (local load, network fallback, graceful degradation) is independently testable via the existing `e2e` fixtures with in-memory SQLite and mocked `from_pretrained`.

> No deviations from simplest viable solution. Complexity Tracking table is empty.

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/063 Usable External Models/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── rest-api.md      # API contract changes
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
# Existing files modified (no new top-level directories):
anvil/
├── api/
│   ├── templates/
│   │   └── archetypes/
│   │       └── model_detail.html    # ALREADY MODIFIED: download button + external detail
│   └── v1/
│       └── models.py                # download/import/asset endpoints (existing)
├── services/
│   ├── inference/
│   │   └── inference.py             # NEW: external model load branch in load_model()
│   ├── model_import/
│   │   ├── model_asset_service.py   # MODIFY: store to hf/ layout instead of sha256 keyed
│   │   └── hf_source.py            # MAYBE: helper for materializing HF dir
│   └── training/
│       └── training_run_service.py  # MODIFY: validate warm-start from external model
├── db/
│   └── repositories/
│       └── external_models.py       # MODIFY: may need asset layout helper
└── workbench.py                     # MODIFY: wire external model loader if needed

tests/
├── e2e/
│   └── test_external_models.py      # NEW e2e: import → download → inference → train
├── unit/
│   ├── services/
│   │   └── test_inference.py        # NEW: test local load + fallback paths
│   └── api/
│       └── v1/
│           └── test_models.py       # NEW: test layout changes in download
```

**Structure Decision**: The existing project structure is sufficient. No new packages or sub-packages needed — changes are within existing files and one new resolution branch in the inference service.

## Complexity Tracking

No complexity deviations. The simplest viable approach is chosen throughout.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |