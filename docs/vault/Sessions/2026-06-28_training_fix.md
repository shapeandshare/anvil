# Session: Training fix — torch_Tensor TYPE_CHECKING bug + Solar Flare pulsing flash CSS fix

**Created**: 2026-06-28
**Updated**: 2026-06-28
**Tags**: `type/session-log`, `domain/training`, `domain/core`, `domain/ui`

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

---

## Session: Solar Flare pulsing flash CSS fix

**Segment**: 2026-06-28 (afternoon)

### Summary

Fixed Solar Flare theme's `flare-burst` pulsing flash animation being invisible. Root cause: CSS initial `--flare: 0` made all keyframes compute to opacity 0; animation started invisible before JS could override.

### Work Done

1. **Investigation**: Traced `--flare` CSS variable flow from initial CSS value (`0`) through JS override (`0.5`) to keyframe computation. Identified timing race: CSS loads asynchronously before body JS, animation starts with `--flare: 0`, and `calc(var(...))` in `@keyframes` doesn't reliably re-evaluate mid-animation.

2. **Fix**: Changed `--flare: 0` → `--flare: 0.5` in `solarflare.css` line 33. Matches the JS baseline that `solarFlareMapping` already sets, ensuring animation is visible from cycle 1.

3. **Vault enriched**: Updated [[Discoveries/solarflare-training-baseline-lift]] with CSS gap documentation.

### Files changed
- `anvil/api/static/css/themes/solarflare.css` — initial `--flare` value from 0 to 0.5