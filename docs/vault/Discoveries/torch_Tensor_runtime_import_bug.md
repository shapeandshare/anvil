# torch_Tensor Hidden Behind TYPE_CHECKING

**Created**: 2026-06-28
**Updated**: 2026-06-28
**Status**: draft
**Tags**: `type/discovery`, `domain/core`, `domain/training`

## Summary

The lazy imports refactoring (commit `1355777`) moved `from torch import Tensor as torch_Tensor` inside an `if TYPE_CHECKING:` guard in `anvil/core/torch_engine.py`. This broke the torch compute backend at runtime because `torch_Tensor` is used in `cast(torch_Tensor, ...)` on line 323 — a runtime function call, not an annotation.

## Impact

Every training attempt that resolved to `local-torch` backend (via `auto` detection on machines with CUDA or MPS) would crash with:

```
NameError: name 'torch_Tensor' is not defined
```

The error was silently swallowed by `LocalTorchBackend.run()` which catches exceptions and returns `ComputeResult(status=FAILED)` — but `TrainingService.start_training()` then blindly emitted a `"complete"` SSE event with `final_loss=None`, making it appear as a silent success in the Web UI.

## Fix

1. **torch_engine.py**: Moved `torch_Tensor` import from `TYPE_CHECKING` into the `try/except ImportError` block where torch is actually imported at runtime. The other two aliases (`torch_device`, `torch_Parameter`) stayed under `TYPE_CHECKING` — they are annotation-only (PEP 563 deferred).

2. **training.py**: Added a `ComputeResult.status == FAILED` check after `backend.run()` returns. Now emits `"error"` SSE event with the backend's `error_message` instead of silently emitting `"complete"`.

## Lesson

When using the `TYPE_CHECKING` guard pattern, verify that every `TYPE_CHECKING`-guarded symbol is truly annotation-only and will never be evaluated at runtime. `cast()` arguments are always evaluated — they're not annotations. The `from __future__ import annotations` (PEP 563) only defers annotation evaluation, not `cast()` arguments.