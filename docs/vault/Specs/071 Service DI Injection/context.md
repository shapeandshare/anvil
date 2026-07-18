# Context — 071 Inject Cross-Service Dependencies

> Cross-references: `../066-codebase-remediation/data-inventory.md` §5, `shared-decisions.md` Decision 2. **Blocks spec 068.**

## Current State (verified — MORE offenders than original review)

Services creating services inline:
| File | Line | Creates |
|------|------|---------|
| `services/evaluation/evaluation_service.py` | 517-518 | `InferenceService()`, `TrackingService()` |
| `services/inference/inference.py` | 414, 734, 1251 | `TrackingService()` (×3) |
| `services/inference/demo_model_provider.py` | 90, 213, 219, 240, 260, 410, 540, 546 | Tracking/Demo/Corpus/Training |
| `services/training/training.py` | 333, 343, 344 | Dataset/Corpus/DemoBootstrap |
| `services/training/training_run_service.py` | 397 | `InferenceService()` |
| `services/demo/demo_bootstrap.py` | 92, 109, 110 | DemoBootstrap/Corpus/Dataset |

Re-verify: `grep -rn "TrackingService()\|InferenceService()\|TrainingService()\|DatasetService(\|CorpusService(\|DemoBootstrapService(" anvil/services/`

## Reference Pattern

`AnvilWorkbench` already wires deps in property accessors, e.g. `workbench.py:221-230`:
```python
@property
def evaluation(self) -> EvaluationService:
    if self._evaluation is None:
        self._evaluation = EvaluationService(
            session=self._session, inference=self.inference, tracking=self.tracking,
        )
    return self._evaluation
```
This is the target — but `EvaluationService.__init__` still creates its own services at lines 517-518 in some code path. Verify whether those are fallbacks or a separate method.

## Approach

For each service, add optional constructor params with `None` defaults that lazy-create (backward compat), then update the workbench to pass explicit instances:
```python
def __init__(self, ..., tracking: TrackingService | None = None) -> None:
    self._tracking = tracking or TrackingService()
```
Then internal methods use `self._tracking` instead of `TrackingService()`.

## Decision Reference

Per `shared-decisions.md` Decision 2: workbench-centric wiring. The `None`-default-lazy-create pattern preserves backward compatibility for direct instantiation (tests, CLI).

## Gotchas

- `demo_model_provider.py` has module-level functions (not a class) that create services — these are called from the app warmup thread. Refactor to accept services as params, or keep as a documented exception if they're genuinely standalone bootstrap utilities.
- `demo_bootstrap.py:109-110` creates services in `__init__` from repos it already holds — this is arguably acceptable (it owns those services). Evaluate case-by-case.
- Watch for circular deps: `InferenceService` needing `TrackingService` and vice versa. The layered architecture should prevent this — if a cycle appears, it signals a design issue to escalate.
- No new event loops — this pairs with spec 068.
