# Context — 076 Split InferenceService

> Cross-references: `../066-codebase-remediation/data-inventory.md` §5. Coordinate with spec 071 (DI).

## Current State (verified)

`anvil/services/inference/inference.py` — **2028 lines** (the review said 1400+; actual is larger). Responsibilities observed:
- HF↔anvil key mapping (`_hf_to_anvil_key`, `_STATIC_HF_MAP`, `_LAYER_SUB_MAP` — lines 59-120)
- Model loading (from catalog, ref, MLflow) — creates `TrackingService()` at 414, 734, 1251
- Tokenization, embeddings, attention
- Sampling / generation
- Loss / logits
- PEForm/transformers optional-dep handling (lines 44-56)

Re-verify size: `wc -l anvil/services/inference/inference.py`

## Existing Sub-Modules

`anvil/services/inference/` already contains: `loaded_model.py`, `tokenizer_factory.py`, `transformers_tokenizer_adapter.py`, `demo_model_provider.py`, `model_browser.py`. So the package is already partially decomposed — the god class is `inference.py` itself.

## Consumers (do not break)

```bash
grep -rn "InferenceService" anvil/ tests/
```
Known consumers: routes (`inference.py`, `training.py`), `TrainingRunService`, `EvaluationService`, `TeachingService`, `_pyfunc_model.py`. The facade must preserve the public API.

## Suggested Decomposition (implementer may adjust)

- **ModelLoadingService** — load_model, catalog/ref/MLflow resolution, HF key mapping, warmup.
- **TokenizationService** — tokenize, embeddings, attention.
- **SamplingService** — generate, sampling distributions, top-k/top-p.
- **LossService** — loss, logits, probabilities.
- **InferenceService** — facade delegating to the above (keeps public API).

## Approach

1. Characterize: capture current public method signatures + a few golden outputs.
2. Extract one concern at a time, moving methods + private helpers into a new service class.
3. Facade delegates; inject sub-services (spec 071 pattern).
4. Keep behavior identical.

## Gotchas

- This is the highest-effort spec (3-5 days). Do it LAST among the service specs, after 071 (DI) so sub-services are injectable.
- Shared state: is there a cached loaded model on the instance? If so, decide where it lives (facade or a shared context passed to sub-services).
- The `_call_or_400` route wrapper (in route `inference.py`) calls facade methods — unaffected if the facade API is stable.
- Optional-dep flags (`_PEFT_AVAILABLE`, `_TRANSFORMERS_AVAILABLE`) move with the model-loading concern.
