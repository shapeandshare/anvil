# Compute Routing Contract

**Feature**: 046 Fine-Tune Compute Routing
**Last Updated**: 2026-07-01
**Status**: Draft

## Interface: `resolve_fine_tune()`

```python
def resolve_fine_tune(config: dict[str, Any]) -> dict[str, Any]:
    """Resolve fine-tune compute backend by ResourceSpec.

    Parameters
    ----------
    config : dict
        Configuration with keys:
        - ``method`` : str — ``"full"`` | ``"lora"`` | ``"qlora"``
        - ``base_model_ref`` : str — base model identifier
        - ``compute_backend`` : str — ``"auto"`` | ``"local-cpu"`` |
        ``"local-gpu"`` | ``"saas"`` (optional, defaults to ``"auto"``).
        Note: there is NO bare ``"local"`` value; local execution is
        ``local-cpu``/``local-gpu``/``auto``.

    Returns
    -------
    dict
        Resolved configuration with keys:
        - ``"engine"`` : TrainingEngine — ``"torch"``
        - ``"device"`` : DeviceType — auto-detected device
        - ``"backend"`` : ComputeBackendResult — ``"local"`` | ``"saas"``

    Raises
    ------
    ComputeBackendUnavailable
        If explicit backend selection cannot be honored.
    """
```

## Routing Logic

```
Input: config dict
1. Extract method, base_model_ref, compute_backend from config
2. Compute ResourceSpec:
   - Resolve base_model params from model registry/metadata
   - Apply method multiplier (full=2×, lora=1.2×, qlora=0.6×)
   - Add overhead (0.5 GB)
   - Compare vs available host memory (GPU VRAM or system RAM)
3. Apply D4 semantics:
   - auto + fits local → local (local-lora backend)
   - auto + over local + SaaS configured → saas (SaaS backend, spec 047)
   - auto + over local + SaaS NOT configured → guidance message
   - local-cpu / local-gpu + fits local → local
   - local-cpu / local-gpu + over local → raise ComputeBackendUnavailable
   - saas + SaaS configured → saas
   - saas + SaaS NOT configured → raise ComputeBackendUnavailable
4. Return resolved config dict
```

## Integration with `resolve_backend()`

`resolve_backend()` (the existing public resolver, `resolve.py:111-119`) already contains a
`method in ("lora","qlora")` branch that routes fine-tunes to a local torch backend only. That branch
MUST be refactored to **delegate** to `resolve_fine_tune()` so there is a single routing path
(Constitution §11.4 — no duplicate logic). All non-fine-tune paths of `resolve_backend()` are unchanged.

## Normalized Output (ComputeResult)

All fine-tune `ComputeResult` objects follow the adapter shape regardless of backend:

```json
{
  "status": "completed",
  "adapter_id": "run_42",
  "artifact_uris": {
    "adapter_path": "/path/to/adapter/"
  },
  "backend": "local",
  "engine": "torch"
}
```

## Enums

```python
class ComputeBackend(StrEnum):
    AUTO = "auto"        # existing
    LOCAL_CPU = "local-cpu"  # existing
    LOCAL_GPU = "local-gpu"  # existing
    MODAL = "modal"      # existing
    SAAS = "saas"        # NEW

class ComputeBackendResult(StrEnum):
    LOCAL = "local"      # existing
    MODAL = "modal"      # existing
    SAAS = "saas"        # NEW

class RegistryBackend(StrEnum):
    LOCAL_STDLIB = "local-stdlib"    # existing
    LOCAL_TORCH = "local-torch"      # existing
    LOCAL_LORA = "local-lora"        # existing
    MODAL = "modal"                  # existing
    SAAS_FINETUNE = "saas-finetune"  # NEW
```

## NMRG Guarantee

The existing `resolve_backend()` function signature and behavior are unchanged.
No existing tests break. No existing API routes or user-facing behavior changes.