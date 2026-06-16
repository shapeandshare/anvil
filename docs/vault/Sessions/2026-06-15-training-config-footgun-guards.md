## Session: Training config footgun guards — live UI warnings, backend validation, engine guards

**Date**: 2026-06-15

### Summary

Added three-layer defense (UI → API → engine) against silent hyperparameter misconfiguration in the training pipeline. Users can no longer silently shoot themselves in the foot with bad n_embd/n_head/block_size/data-source settings.

### Footguns Identified

| Footgun | Impact | Layer caught |
|---------|--------|-------------|
| `n_head > n_embd` | head_dim=0, model produces zeros | UI warning + HTTP 422 |
| `n_embd % n_head ≠ 0` | Attention dimensions silently truncated | UI warning + HTTP 422 |
| head_dim odd | RoPE crash on CPU, wrong output on GPU | UI warning + HTTP 422 + engine ValueError |
| `block_size > corpus chunk_size` | Context slots unused, worse generation | UI warning + startTraining log **← from previous session** |
| Both corpus + dataset selected | Dataset silently takes priority | UI warning + startTraining log |
| No data source selected | Silently uses demo corpus | UI warning + startTraining log |

### Architecture: Three-Layer Defense

1. **UI layer** (training.html JS): Live inline warnings that toggle as the user types — `updateModelStats()` checks n_embd/n_head geometry every keystroke, `handleDataSourceChange()` toggles data conflict/empty warnings. Warnings logged to output pane on start.
2. **API layer** (training.py): Pre-flight HTTP 422 validation rejects bad configs with clear, actionable error messages (including suggested n_head values for divisibility).
3. **Engine layer** (torch_engine.py): Missing `head_dim % 2 != 0` ValueError added to the GPU engine (CPU engine already had it).

### Key Observations

- The autotune logic already avoids all these footguns — the vulnerability was only when users manually override params.
- `head_dim % 2 != 0` check was missing from `TorchLlamaModel.__init__()` while `LlamaModel.__init__()` in engine.py already had it — a gap between the two engine implementations.
- Backend validation returns HTTP 422 with suggested fixes (e.g. "Try n_head=4" when n_embd=20, n_head=6 is entered), making it a teaching moment rather than just an error.

### Files Changed

- `anvil/api/templates/archetypes/training.html` — 3 new warning elements, JS toggles in `updateModelStats()`, `handleDataSourceChange()`, `startTraining()`
- `anvil/api/v1/training.py` — Pre-flight HTTP 422 validation for n_embd/n_head geometry, deduplicated config reads
- `anvil/core/torch_engine.py` — Added missing `head_dim % 2 != 0` ValueError check

### Vault Enrichment

- Created [[Decisions/ADR-013-training-config-footgun-guards]]
- Updated [[Reference/DecisionLog]]