# Research: Fine-Tune Compute Routing

**Feature**: 046 Fine-Tune Compute Routing
**Date**: 2026-07-01
**Method**: Direct codebase analysis of `anvil/services/compute/`

## Research Questions

### Q1: How does `resolve.py` currently work?

**Findings**: The public function is `resolve_backend()` (NOT `resolve()`), mapping user-facing `compute_backend` strings (`auto`, `local-cpu`, `local-gpu`, `modal`) to resolved `engine` + `device` + `backend`. Lines **111-119** currently route `method in ("lora","qlora")` to the local torch backend **only** — a local-only gap with no SaaS option. Fine-tune SaaS routing goes in a new `resolve_fine_tune()`, and the existing lora/qlora branch is refactored to delegate to it (no duplicate routing path, §11.4). Non-fine-tune paths of `resolve_backend()` remain unchanged.

**Files read**: `anvil/services/compute/resolve.py` (186 lines)

### Q2: Does `ComputeResult` already support adapter-bearing results?

**Findings**: Yes. `ComputeResult` supports three shapes:
- Local path: `model` field holds in-process `LlamaModel`
- Remote path: `exported_remotely=True`, `artifact_uris` carry MLflow run IDs
- Adapter path: `adapter_id` field + `artifact_uris["adapter_path"]` for LoRA adapter weights

FR-022b (normalize identically across backends) is satisfied by the existing model — no structural changes needed.

**Files read**: `anvil/services/compute/result.py` (133 lines)

### Q3: How do backends register and what's the registry pattern?

**Findings**: String-key registry via `registry.py`. Backends call `register(name, factory)` at module import time. Consumers use `get_backend(name, **deps)` or `available_backends()`. No ABCs — structural typing via `ComputeBackendProtocol`.

Existing registrations: `local-stdlib`, `local-torch`, `local-lora`, `modal`.

**Files read**: `anvil/services/compute/registry.py`, `registry_backend.py`, `compute_backend.py`

### Q4: How does the Modal backend handle remote job status?

**Findings**: Modal uses submit-then-poll (D3). Key implementation:
- `remote_fn.spawn(docs, config)` → gets `call` with `object_id`
- `progress_callback(-1, 0.0)` signals "submitted"
- Every 2 seconds: `call.get_status()` → checks `"success"`/`"failed"`/`"error"`
- Cancellation: `call.cancel()` on `stop_check()` → returns `ComputeResult(FAILED)`

This is the exact pattern SaaS fine-tune backend should follow (FR-022c).

**Files read**: `anvil/services/compute/modal_backend.py` (341 lines)

### Q5: What enums need new members?

| Enum | File | New Member Needed |
|------|------|-------------------|
| `ComputeBackend` | `compute_backend.py` | `SAAS = "saas"` |
| `ComputeBackendResult` | `compute_backend_result.py` | `SAAS = "saas"` |
| `RegistryBackend` | `registry_backend.py` | `SAAS_FINETUNE = "saas-finetune"` |

### Q6: Existing LoRA/QLoRA fine-tune backend details?

**Findings**: `LocalLoraBackend` (570 lines) is already auto-registered as `"local-lora"`. It:
- Checks `peft`/`torch` availability; falls back to synthetic loop
- Supports LoRA and QLoRA (4-bit via bitsandbytes)
- Runs in `run_in_executor` to avoid blocking the event loop
- Returns `ComputeResult` with `artifact_uris={"adapter_path": str(adapter_path)}`
- Unchanged by this spec

**Files read**: `anvil/services/compute/local_lora_backend.py` (570 lines)

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| New `resolve_fine_tune()` function | Yes — in existing `resolve.py`; existing lora/qlora branch delegates to it | Fills the local-only gap; keeps `resolve_backend()` non-fine-tune paths unchanged (NMRG); avoids a duplicate routing path (§11.4) |
| ResourceSpec formula | VRAM = params × method_mult × quant_factor + overhead | Full=2×, LoRA=1.2×, QLoRA=0.6× — industry standard heuristic |
| SaaS progress tracking | Internal poll inside `SaaSBackend.run()` | Matches existing Modal D3 pattern; no new endpoint (FR-022c) |
| SaaS mid-job failure | Report as `ComputeResult` error | Out of scope for 046; owned by 047 |
| D4 semantics | Per ADR-015 | Auto falls back; explicit unavailable raises `ComputeBackendUnavailable` |
| Adapter result normalization | Already supported by `ComputeResult` | No structural changes needed |
| SaaS backend implementation | Not in this spec | Owned by spec 047 |

## Alternatives Rejected

| Alternative | Rejected Because |
|-------------|-----------------|
| Put all size-based routing logic inline in `resolve_backend()` | Would bloat the general training resolver with fine-tune-specific SaaS/ResourceSpec logic and risk regressing non-fine-tune paths; a focused `resolve_fine_tune()` (delegated to from the lora/qlora branch) is cleaner and keeps NMRG for non-fine-tune paths |
| Persist job state for retry (Option C) | Violates scope boundary (047 owns SaaS pipeline); adds distributed-systems complexity (ADR-015 Phase 2 deferral) |
| External status endpoint for SaaS progress | No consumer need identified; existing SSE stream carries progress via orchestrator |
| SSE at backend level | Backend doesn't own transport; SSE is the orchestrator's concern |
| Hardcoded parameter-count threshold for "too large" | Not method-aware — would route all full fine-tunes to SaaS even if they fit locally |
| Empirical probe (try loading model) | Non-deterministic; OOM depends on current system state; can't test reliably