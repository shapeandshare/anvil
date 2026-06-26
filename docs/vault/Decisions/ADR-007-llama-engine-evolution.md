---
title: 'ADR-007: Llama Engine Evolution — SwiGLU, RoPE, Safetensors Export'
type: decision
tags:
  - type/decision
  - domain/core
  - domain/infrastructure
status: accepted
created: '2026-06-14'
updated: '2026-06-14'
aliases:
  - llama-engine-evolution
source: agent
related:
  - '[[Reference/ProgressiveWalkthroughs]]'
  - '[[Reference/DualBackend]]'
code-refs:
  - anvil/core/engine.py
---
# ADR-007: Llama Engine Evolution

**Date**: 2026-06-14  
**Status**: Accepted  
**Deciders**: anvil contributors  

## Context
The anvil training engine used GPT-2 architecture (ReLU MLP, learned position embeddings, RMSNorm without learned scales). To align with modern decoder-only transformer practices and enable standards-compatible model export, the engine needed to evolve to Llama architecture.

## Decision
We evolved the core engine from GPT-2 to Llama architecture:
1. **SwiGLU MLP**: Replaced ReLU-based fc1/fc2 (4x expansion) with SiLU-gated gate/up/down projections (intermediate_size = int(8 * n_embd/3)) preserving parameter count parity (~8n²)
2. **RoPE**: Replaced learned wpe position embeddings with half-split (rotate_half) Rotary Position Encoding, matching HuggingFace Llama convention (dim i paired with i + head_dim/2)
3. **Learned RMSNorm**: Added learned scale parameters (rms_1, rms_2, rms_final) initialized to 1.0
4. **Norm restructuring**: Removed embedding-level norm (no corresponding HF tensor) and added final norm before lm_head
5. **Safetensors export**: Primary artifact format, generated automatically on training completion, with HF-convention tensor names and standard config
6. **GPU consistency**: torch_engine.py migrated to match (no separate architecture allowed — the GPU→CPU weight bridge requires key compatibility)

## Consequences
- Models can be exported to safetensors and loaded directly by Llama-compatible inference tools
- Walkthroughs updated to teach modern architecture progression
- Old GPT-2 format models are detected and rejected with a clear error
- Demo model auto-retrains on format mismatch
- GPU backend kept in sync (FR-019)

## Alternatives considered
- **Dual-architecture support** (keep GPT-2 alive alongside Llama): Rejected — unnecessary complexity for an educational platform
- **Interleaved/consecutive RoPE**: Rejected — would silently produce wrong logits when exported weights load in HF Llama
- **Keeping embedding-level norm**: Rejected — no corresponding HF tensor; breaks architectural equivalence

## See Also

- [[Decisions/README|Decisions]]
