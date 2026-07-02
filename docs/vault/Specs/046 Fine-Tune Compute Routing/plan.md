# Implementation Plan: Fine-Tune Compute Routing & Adapter Results

**Branch**: `046-fine-tune-compute-routing` | **Date**: 2026-07-01 | **Spec**: [[046 Fine-Tune Compute Routing - spec.md]]
**Input**: Feature specification from `docs/vault/Specs/046 Fine-Tune Compute Routing/spec.md`

## Summary

Extend the existing compute resolution layer (`anvil/services/compute/`) so fine-tunes are dispatched through a dedicated `resolve_fine_tune()` that selects local vs SaaS by computed `ResourceSpec` (base-model params × method multiplier × quantization) under D4 degraded-mode rules. Add `SAAS`/`SAAS_FINETUNE` enum members, normalize adapter-bearing `ComputeResult` identically across backends, and follow the existing submit-then-poll pattern for SaaS progress tracking. The existing `resolve_backend()` already has a local-only `method in ("lora","qlora")` branch (`resolve.py:111-119`); that branch is refactored to delegate to `resolve_fine_tune()` so there is no duplicate routing path. All non-fine-tune paths of `resolve_backend()` are unchanged (NMRG).

## Technical Context

**Language/Version**: Python 3.11+ (PEP 604, `StrEnum`, `from __future__ import annotations`)
**Primary Dependencies**: No new runtime deps — extends existing FastAPI, async SQLAlchemy, aiosqlite; SaaS backend behind `[finetune]` extra (spec 047)
**Storage**: `LocalFileStore` (local adapters at `data/adapters/`); SQLite (anvil-state.db) for job metadata
**Testing**: pytest + pytest-asyncio (existing); httpx.AsyncClient for e2e
**Target Platform**: Linux/macOS server; SaaS backend (spec 047) handles cloud batch
**Project Type**: pip-installable Python package + FastAPI web service
**Performance Goals**: ResourceSpec computation negligible (<10ms); routing decision <100ms; polling interval 2s (matching existing Modal pattern)
**Constraints**: NMRG — existing `resolve_backend()` non-fine-tune paths unchanged; the lora/qlora branch is refactored to delegate (behavior-preserving for local-only case); `LocalLoraBackend` and existing training pipeline unmodified; no new runtime dependencies
**Scale/Scope**: Single-process web server; SaaS backend handles batch fine-tune compute

### Existing Codebase Analysis (pre-research)

**Existing compute layer** (`anvil/services/compute/`):

- **`resolve.py`** — the public function is `resolve_backend()` (NOT `resolve()`), mapping `compute_backend` strings (auto/local-cpu/local-gpu/modal) to engine+device. It already routes `method in ("lora","qlora")` to a local torch backend at **lines 111-119** — a **local-only gap** (no SaaS option). `resolve_fine_tune()` owns the size-based local-vs-SaaS decision; the lora/qlora branch is refactored to delegate to it (§11.4 — no duplicate routing). Non-fine-tune paths remain unchanged.
- **`ComputeResult`** (`result.py`) — Already supports three shapes: local path (`model`), remote path (`exported_remotely`), adapter path (`adapter_id` + `artifact_uris["adapter_path"]`). This is the normalization target for FR-022b.
- **`ComputeStatus`** (`compute_status.py`) — `SUBMITTED`, `RUNNING`, `COMPLETED`, `FAILED`. Already covers fine-tune lifecycle.
- **`RegistryBackend`** (`registry_backend.py`) — Has `LOCAL_LORA = "local-lora"` registered. New `SAAS_FINETUNE` entry needed.
- **`ComputeBackend`** (`compute_backend.py`) — User-facing enum: `AUTO="auto"`, `LOCAL_CPU="local-cpu"`, `LOCAL_GPU="local-gpu"`, `MODAL="modal"`. There is **no bare `"local"`** and **no `"saas"`** today. New `SAAS="saas"` entry needed. Fine-tune "run locally" is expressed via `local-cpu`/`local-gpu`/`auto`.
- **`ComputeBackendResult`** (`compute_backend_result.py`) — `LOCAL="local"`, `MODAL="modal"`. New `SAAS="saas"` entry needed.
- **`LocalLoraBackend`** (`local_lora_backend.py`) — Existing local fine-tune backend implementing `ComputeBackendProtocol`. Auto-registers as `"local-lora"`. Wraps peft+transformers. Unchanged.
- **`ModalBackend`** (`modal_backend.py`) — Existing remote backend with submit-then-poll pattern (D3). Fine-tune SaaS backend follows the same pattern.
- **`registry.py`** — `register()`, `get_backend()`, `available_backends()`. No changes needed.
- **`protocol.py`** — `ComputeBackendProtocol` with `name`, `is_available()`, `async run()`. This is the interface all backends satisfy.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity First gate (Article XI — hard MUST)**: Confirm this plan favors
the simplest, most boring solution that meets the requirement:

- [x] **Simplest viable** (§11.1) — The approach extends existing `resolve.py` with a single new function (`resolve_fine_tune()`), reuses `ComputeResult` (already supports adapters), and follows the existing Modal submit-then-poll pattern. No new infrastructure.
- [x] **Boring over novel** (§11.2) — No novel dependencies or patterns. Reuses the existing string-key registry, `ComputeBackendProtocol`, and `ComputeResult`. The SaaS sizing formula (full=2×, lora=1.2×, qlora=0.6×) is a well-established heuristic.
- [x] **YAGNI** (§11.3) — No speculative generality. `resolve_fine_tune()` handles only the current requirement (FR-022). SaaS job persistence, retry, and failover are deferred to spec 047 per explicit scope boundary.
- [x] **Reuse first** (§11.4) — Reuses `registry.py`, `ComputeBackendProtocol`, `ComputeResult`, `ComputeStatus`, existing submit-then-poll pattern from `ModalBackend`. Critically, the existing `resolve_backend()` lora/qlora branch is refactored to **delegate** to `resolve_fine_tune()` — it does NOT create a second parallel routing path.
- [x] **Testable** (§11.6) — All routing logic is a pure function (`dict → dict/raise`). `ComputeResult` normalization is assertable. SaaS polling can be tested with an injected fake backend. Pattern identical to existing Modal tests.

> No deviations from simplest viable — Complexity Tracking table is empty.

**Additional gates**:

| Article/Gate | Status | Notes |
|-------------|--------|-------|
| Article I (Zero-Dependency Core) | ✅ Pass | Fine-tune routing touches `services/compute/` only; core engine unchanged |
| Article IV (TDD Mandatory) | ✅ Pass | Tests written before implementation per spec-kit flow |
| Article V (Async-First) | ✅ Pass | Backend `run()` is async; polling follows existing async pattern |
| Article VI (`__init__.py` Ownership) | ✅ Pass | No new package levels introduced |
| Article VII (Layered Architecture) | ✅ Pass | Routing lives in services layer; no DB leaks to routes |
| Article IX (Pit of Success) | ✅ Pass | Auto falls back to local when SaaS not configured |
| Article X (Domain Decomposition) | ✅ Pass | All additions within existing `services/compute/` domain |
| No type-error suppression | ✅ Pass | `mypy --strict` compatible by design |
| Pydantic BaseModel over dataclass | ✅ Pass | `ComputeResult` is already a `BaseModel` |
| One class per file | ✅ Pass | New files each contain one class |

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/046 Fine-Tune Compute Routing/
├── spec.md                    # Feature specification (symlink to canonical file)
├── plan.md                    # This file
├── research.md                # Phase 0 — codebase research findings
├── data-model.md              # Phase 1 — entity definitions
├── quickstart.md              # Phase 1 — developer quickstart
├── contracts/                 # Phase 1 — interface contracts
│   └── compute-routing.md     #   resolve_fine_tune() contract
└── tasks.md                   # Phase 2 — task breakdown (created by /speckit.tasks)
```

### Source Code (repo root — files to create/modify)

```text
# Files to CREATE:
anvil/services/compute/
├── compute_backend_result.py  # MODIFY: add SAAS enum member
├── compute_backend.py         # MODIFY: add SAAS enum member
├── registry_backend.py        # MODIFY: add SAAS_FINETUNE enum member
└── resolve.py                 # MODIFY: add resolve_fine_tune()

# Files CREATED by spec 047 (SaaS backend — referenced, not built here):
#   anvil/services/compute/saas_finetune_backend.py  (SaaSBackend)

# Files UNCHANGED (NMRG):
#   anvil/services/compute/local_lora_backend.py
#   anvil/services/compute/registry.py
#   anvil/services/compute/result.py
#   anvil/services/compute/compute_status.py
#   anvil/services/compute/protocol.py
#   anvil/services/compute/modal_backend.py

# Tests:
tests/unit/services/compute/
└── test_resolve.py            # MODIFY: add resolve_fine_tune() tests
tests/e2e/
└── test_finetune_routing.py   # CREATE: e2e routing tests
```

**Structure Decision**: Single project (pip package). All additions are within the existing `anvil/services/compute/` domain sub-package. No new package levels.

## Complexity Tracking

> No Constitution Check violations. Complexity Tracking table is empty.
> The chosen approach is the simplest viable for all requirements.

## Phase 0: Research Findings

All unknowns are resolved via direct codebase analysis (see Technical Context above). The following design decisions are confirmed:

| Decision | Choice | Rationale |
|----------|--------|-----------|
| `resolve_fine_tune()` scope | New function in `resolve.py`; existing lora/qlora branch delegates to it | Fills the local-only gap in `resolve_backend()`; non-fine-tune paths unchanged (NMRG FR-022); no duplicate routing (§11.4) |
| ResourceSpec formula | VRAM = base_params × method_mult × quant_factor + overhead | Industry-standard heuristic (QLoRA paper) |
| SaaS progress tracking | Internal poll in `SaaSBackend.run()`, matching Modal D3 pattern | No new status endpoint needed (FR-022c) |
| SaaS mid-job failure | Report as `ComputeResult` error, no retry | Out of scope for 046; owned by 047 |
| D4 semantics | Per ADR-015: auto silently falls back, explicit unavailable raises | No new failure semantics needed |
| Adapter result normalization | Already supported by `ComputeResult.adapter_id` + `artifact_uris["adapter_path"]` | FR-022b satisfied by existing code |

No NEEDS CLARIFICATION remain.

## Source Files to Create/Modify

### 1. `anvil/services/compute/compute_backend.py` — MODIFY
Add `SAAS = "saas"` enum member to `ComputeBackend`.

### 2. `anvil/services/compute/compute_backend_result.py` — MODIFY
Add `SAAS = "saas"` enum member to `ComputeBackendResult`.

### 3. `anvil/services/compute/registry_backend.py` — MODIFY
Add `SAAS_FINETUNE = "saas-finetune"` enum member to `RegistryBackend`.

### 4. `anvil/services/compute/resolve.py` — MODIFY
Add `resolve_fine_tune()` function that:
- Accepts `config` dict (with `method`, `base_model_ref`, `compute_backend`)
- Computes `ResourceSpec` via VRAM formula
- Applies D4 rules (user-facing `compute_backend` values — NO bare `"local"`):
  - `auto`: local if fits envelope, SaaS if too large and SaaS configured, guidance if SaaS not configured
  - `local-cpu`/`local-gpu`: local; raises `ComputeBackendUnavailable` if too large
  - `saas`: SaaS; raises `ComputeBackendUnavailable` if SaaS not configured
- Returns resolved `dict` with `engine`, `device`, `backend` keys

**Also refactor** the existing `method in ("lora","qlora")` branch at `resolve.py:111-119` to delegate to `resolve_fine_tune()` (behavior-preserving for the local-only case) so no duplicate routing logic exists (§11.4).

### 5. `tests/unit/services/compute/test_resolve.py` — MODIFY
Add test cases for `resolve_fine_tune()`:
- Fits local auto → local
- Over-local auto with SaaS → saas
- Over-local auto without SaaS → gap guidance
- Explicit local over-local → `ComputeBackendUnavailable`
- Explicit saas without SaaS → `ComputeBackendUnavailable`
- Full/lora/qlora sizing differences
- NMRG: existing `resolve_backend()` tests still pass

### 6. `tests/e2e/test_finetune_routing.py` — CREATE
e2e test that submits a fine-tune and verifies:
- Routing produces the correct backend
- `ComputeResult` carries normalized adapter shape regardless of backend