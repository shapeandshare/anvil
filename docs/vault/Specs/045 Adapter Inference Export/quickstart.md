# Quickstart — Adapter Inference, Merge & Export

## Key Files

| File | Purpose |
|------|---------|
| `anvil/services/compute/result.py` | Add `adapter_id` field to `ComputeResult` |
| `anvil/services/training/merge_service.py` | Non-destructive merge + lineage registration |
| `anvil/services/inference/inference.py` | Actual PeftModel composition in `load_model()` |

## Implementation Order

1. **ComputeResult adapter shape** — Add `adapter_id: str | None = None` field
2. **AdapterMergeService non-destructive** — Stop deleting adapter files; stop premature `mark_merged`; add lineage registration
3. **InferenceService composition** — Use `PeftModel.from_pretrained()` in `load_model()` when adapter_id is provided
4. **Merge+export atomicity** — Write to temp dir + atomic rename
5. **Tests** — Unit tests for each change; e2e test for full flow
6. **Agent context update**

## Test Plan

| Test | What it covers |
|------|----------------|
| `test_adapter_inference` | Load base + adapter, generate, verify output differs from base-only |
| `test_merge_export` | Merge adapter, verify standalone artifact, verify lineage tags |
| `test_merge_atomic_failure` | Simulate failure mid-merge, verify no partial artifact |
| `test_compute_result_adapter_shape` | ComputeResult with `adapter_id` serializes/deserializes correctly |
| `test_merge_preserves_adapter` | Adapter files still exist after merge |
