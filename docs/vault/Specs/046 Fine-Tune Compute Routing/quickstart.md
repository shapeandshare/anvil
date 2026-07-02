# Quickstart: Fine-Tune Compute Routing

## What you need to know

This feature adds compute routing for fine-tune jobs. It does NOT change native training, the existing `LocalLoraBackend`, or any user-facing workflow.

## What changed

### New function: `resolve_fine_tune()` in `resolve.py`

```python
from anvil.services.compute.resolve import resolve_fine_tune

result = resolve_fine_tune({
    "method": "lora",
    "base_model_ref": "tinyllama-1.1b",
    "compute_backend": "auto",
})
# Returns: {"engine": "torch", "device": "cuda", "backend": "local"}
```

### New enum members

```python
ComputeBackend.SAAS       # "saas" — user-facing selection
ComputeBackendResult.SAAS # "saas" — stored in ComputeResult
RegistryBackend.SAAS_FINETUNE  # "saas-finetune" — registry key
```

### How routing works

> Note: `compute_backend` uses the existing `ComputeBackend` vocabulary plus the new `saas`. There is
> **no bare `"local"`** value — local execution is `local-cpu`/`local-gpu`/`auto`.

| `compute_backend` | Fits local? | SaaS configured? | Result |
|-------------------|-------------|------------------|--------|
| `auto` | Yes | — | Routes to local backend |
| `auto` | No | Yes | Routes to SaaS backend |
| `auto` | No | No | Reports gap with guidance |
| `local-cpu` / `local-gpu` | Yes | — | Routes to local backend |
| `local-cpu` / `local-gpu` | No | — | Raises `ComputeBackendUnavailable` |
| `saas` | — | Yes | Routes to SaaS backend |
| `saas` | — | No | Raises `ComputeBackendUnavailable` |

### ResourceSpec formula

```
VRAM = base_params_in_billions * method_multiplier * quantization_factor + 0.5 GB overhead

full:  2.0×
lora:  1.2×
qlora: 0.6×
```

### What DID change in `resolve_backend()`

- The existing `method in ("lora","qlora")` branch (`resolve.py:111-119`) is refactored to **delegate**
  to `resolve_fine_tune()` — behavior-preserving for the local-only case, but now size-aware. No second
  parallel routing path (§11.4).

### What did NOT change

- `resolve_backend()` — all non-fine-tune paths unchanged (NMRG)
- `LocalLoraBackend` — unchanged (NMRG)
- `ComputeResult` — unchanged (already supports adapter shape)
- `ComputeStatus` — unchanged
- `registry.py` — unchanged
- `protocol.py` — unchanged
- `ModalBackend` — unchanged

## Testing

### Unit tests

```bash
pytest tests/unit/services/compute/test_resolve.py -k "fine_tune" -v
```

Test cases:
- `test_resolve_finetune_fits_local_auto` — small model routes to local
- `test_resolve_finetune_over_local_auto_saas` — large model routes to SaaS
- `test_resolve_finetune_over_local_auto_no_saas` — guidance message
- `test_resolve_finetune_explicit_local_over_limit` — raises `ComputeBackendUnavailable`
- `test_resolve_finetune_explicit_saas_not_configured` — raises `ComputeBackendUnavailable`
- `test_resolve_finetune_nmrg_existing` — `resolve_backend()` unchanged

### e2e tests

```bash
pytest tests/e2e/test_finetune_routing.py -v
```

## Dependencies

- No new runtime dependencies
- All additions are within `anvil/services/compute/`
- SaaS backend implementation is in spec 047