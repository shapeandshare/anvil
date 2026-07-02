---
title: 2026-07-01 spec-046-implementation
type: session-log
tags:
  - type/session-log
  - domain/training
  - domain/operations
status: draft
source: agent
aliases: 2026-07-01 spec-046-implementation
created: '2026-07-01'
updated: '2026-07-01'
---

# Session: 046 Fine-Tune Compute Routing — implementation

## Summary

Implemented spec 046 Fine-Tune Compute Routing: enum additions, `resolve_fine_tune()` function, lora/qlora delegation refactor, and comprehensive tests.

## Key Decisions

- **`resolve_fine_tune()` vocabulary**: Uses existing `ComputeBackend` enum values (`auto`, `local-cpu`, `local-gpu`) plus the new `SAAS`. There is no bare `"local"` value — "run locally" is `local-cpu`/`local-gpu`/`auto`.
- **Delegation pattern**: The existing `resolve_backend()` lora/qlora branch (lines 111-119) was refactored to delegate to `resolve_fine_tune()`, avoiding duplicate routing logic (§11.4).
- **SaaS sizing formula**: `VRAM = base_params * method_mult + 0.5 GB overhead` where full=2×, lora=1.2×, qlora=0.6×.
- **Host memory detection**: CUDA VRAM queried via `torch.cuda.get_device_properties`; MPS defaults to 8 GB; CPU defaults to 4 GB.

## Files Changed

- `anvil/services/compute/compute_backend.py` — added `SAAS = "saas"`
- `anvil/services/compute/compute_backend_result.py` — added `SAAS = "saas"`
- `anvil/services/compute/registry_backend.py` — added `SAAS_FINETUNE = "saas-finetune"`
- `anvil/services/compute/resolve.py` — added `resolve_fine_tune()`, `_saas_configured()`, `_estimate_host_memory_gb()`, `_parse_model_params()`; refactored lora/qlora branch to delegate
- `tests/unit/services/compute/test_resolve.py` — added 7 test cases for `resolve_fine_tune()`
- `tests/e2e/test_finetune_routing.py` — added 2 e2e routing tests

## Compliance

- **Tests**: 70 passed (68 unit + 2 e2e), coverage 26.79% (above 23% threshold)
- **Lint**: ruff/black/isort all pass
- **NMRG**: Existing `resolve_backend()` non-fine-tune paths unchanged
- **SaaS backend**: Not implemented (owned by spec 047); `_saas_configured()` returns `False` as placeholder

## Post-implementation review fixes

An Oracle + explore review found real bugs in the first-pass implementation, since fixed:

- **`backend=False` sentinel removed** — `auto` + over-local + no-SaaS now silently falls back to local (correct D4); `resolve_fine_tune()` always returns a valid `ComputeBackendResult`.
- **NMRG regression fixed** — explicit `local-cpu`/`local-gpu` no longer raises on size; it always routes local, preserving pre-046 unconditional-local behavior for LoRA/QLoRA. Only explicit `saas`-unconfigured raises.
- **FR-022a reconciled** — QLoRA multiplier (0.6×) folds quantization in; no separate quantization factor. Constants extracted to `_METHOD_MEMORY_MULTIPLIER`.
- **`_parse_model_params` hardened** — boundary-aware regex (`llama-2-13b-chat` → 13, not 2).
- **Tests strengthened** — removed tautological assertions; added exact-boundary sizing test, sentinel-guard test, model-ref parsing edge cases, and `resolve_backend()` lora/qlora NMRG regression tests. 28 resolve tests pass (was 10); 87 compute+training tests pass.

## Known gap deferred (out of 046 scope)

LoRA/QLoRA jobs route to `"local-torch"` not `"local-lora"` because `training.py:528`
remaps `LOCAL` → `"local-{engine}"`. Pre-dates 046 (spec-044 lora branch). Documented
in [[Discoveries/lora-routes-to-local-torch-not-local-lora]].

## Related

- [[Specs/046 Fine-Tune Compute Routing/046 Fine-Tune Compute Routing - spec.md]]
- [[Discoveries/lora-routes-to-local-torch-not-local-lora]]
