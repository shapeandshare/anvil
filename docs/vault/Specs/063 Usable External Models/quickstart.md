# Quickstart: Using an Imported External Model

## Flow

```text
1. Import a model from HuggingFace
   → hf_browser page
   → click "Import" on a runnable model
   → wait for import job to complete

2. Download its weights
   → click "View →" on the import job
   → model detail page shows "Download Weights" button
   → click it, wait for download to complete
   → badge turns green "available"

3. Run inference (Play)
   → Play button appears on model detail page
   → opens playground with locally loaded model
   → generation works offline

4. Fine-tune from it
   → Continue Training button appears
   → opens training page with model as base
   → full warm-start or LoRA/QLoRA using local weights
```

## Key Files

| File | Purpose |
|------|---------|
| `anvil/services/inference/inference.py` | `load_model()` external model path + local-first adapter compose |
| `anvil/services/model_import/model_asset_service.py` | Download to HF-standard layout |
| `anvil/services/training/training_run_service.py` | Warm-start validation (works automatically after inference change) |
| `anvil/api/templates/archetypes/model_detail.html` | Download button + external detail + Play/Train affordances |
| `tests/e2e/test_external_models.py` | Full import → download → inference → train e2e |
| `tests/unit/services/test_inference.py` | Unit tests for local load + fallback paths |

## Verification (after implementation)

```bash
# Full e2e test
make test

# Specific tests
pytest tests/e2e/test_external_models.py -v
pytest tests/unit/services/test_inference.py -v -k "external"

# Manual verification
make run
# Visit hf_browser, import a model, download, play, train
```