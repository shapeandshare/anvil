# Session: Training fix — torch_Tensor TYPE_CHECKING bug

**Created**: 2026-06-28
**Updated**: 2026-06-28
**Tags**: `type/session-log`, `domain/training`, `domain/core`

## Summary

Investigated and fixed "Model training fails only demo works" bug. Root cause: `torch_Tensor` hidden behind `TYPE_CHECKING` in `torch_engine.py`.

## Work Done

1. **Investigation**: Traced training flow (CLI → API → TrainingService → compute backend → core engine). Compared with demo path which explicitly uses `local-stdlib`.

2. **Root cause found**: Lazy imports refactoring (`1355777`) moved `torch_Tensor` into `TYPE_CHECKING`. The `cast(torch_Tensor, ...)` call on line 323 fails at runtime.

3. **Fix A** (`torch_engine.py`): Moved `torch_Tensor` import into the runtime `try/except` block.

4. **Fix B** (`training.py`): Added `ComputeStatus.FAILED` check after `backend.run()` so errors surface as SSE `"error"` events instead of silent `"complete"` with null data.

5. **Tests added**: 
   - `tests/unit/core/test_torch_engine.py` — 3 tests verifying runtime import, `torch_available()`, and `train_torch()` execution
   - `tests/unit/services/test_training_phases.py` — `test_backend_failure_emits_error_event` verifying FAILED → error SSE event

6. **Vault enriched**: Discovery note at `Discoveries/torch_Tensor_runtime_import_bug.md`

## Related
- [[Discoveries/torch_Tensor_runtime_import_bug]]