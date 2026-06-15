---
title: Session — Llama Engine Evolution & Safetensors Export
type: session
tags:
  - type/session
  - domain/core
  - status/complete
created: '2026-06-14T00:00:00.000Z'
updated: '2026-06-14T00:00:00.000Z'
---
# Session: Llama Engine Evolution

**Date**: 2026-06-14
**Feature**: 006-llama-engine-evolution

## What was implemented

- **Core engine evolution** (`anvil/core/engine.py`): Evolved from GPT-2 to Llama architecture:
  - Replaced learned `wpe` position embeddings with half-split RoPE
  - Replaced ReLU `fc1`/`fc2` MLP with SiLU-gated SwiGLU (`gate`/`up`/`down`)
  - Added learned RMSNorm scale parameters (`rms_1`, `rms_2`, `rms_final`)
  - Removed embedding-level norm, added final norm before `lm_head`
  - Added `head_dim` validation (must be even for RoPE)
  - Added old-format detection on model load
- **GPU migration** (`anvil/core/torch_engine.py`): Migrated to match Llama engine (FR-019)
- **Safetensors export** (`anvil/services/export.py`): Primary artifact format with HF-convention tensor names (`model.safetensors` + `config.json` + `tokenizer.json`)
- **Walkthrough updates**: Progression scripts updated to teach modern architecture

## Key decisions

1. **Half-split RoPE** (rotate_half convention): Pairs dim i with dim i + head_dim/2. This matches HuggingFace Llama convention. Interleaved RoPE would silently produce wrong logits on export.
2. **Remove embedding norm**: No corresponding HF tensor exists. Keeping it would break architectural equivalence with exported weights.
3. **SwiGLU intermediate size**: `int(8 * n_embd / 3)` preserves parameter count parity with original 4x ReLU expansion (~8n² total).
4. **GPU consistency**: The GPU→CPU weight bridge requires key compatibility, so `torch_engine.py` was migrated to match — no separate architecture allowed.
5. **Demo model auto-retrain**: On format mismatch, the demo model retrains automatically rather than failing silently.

## Files changed

- `anvil/core/engine.py` (main Llama architecture changes)
- `anvil/core/torch_engine.py` (GPU engine sync)
- `anvil/services/export.py` (safetensors export service)
- `anvil/api/v1/training.py` (export integration)
- `anvil/api/v1/experiments.py` (export integration)
- `anvil/cli.py` (export CLI command)
- `anvil/services/tracking.py` (export hooks)
- `examples/train5.py` (full Llama walkthrough)
- `tests/unit/core/test_engine.py` (edge-case tests added)
- `tests/unit/services/test_export.py` (export tests)
- `docs/vault/Decisions/ADR-007-llama-engine-evolution.md` (this ADR)
