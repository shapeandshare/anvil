---
title: Data Flow Analysis Session — 2026-06-12
type: session
tags: [type/session, domain/core]
created: 2026-06-12
updated: 2026-06-12
---

# Session: Render Loop & Data Flow Analysis

## Summary
Deep analysis of the training render loop and end-to-end data flow — tracing the path from browser button click through FastAPI, TrainingService, core engine (autograd + GPT forward/backward), SSE streaming, persistence, and inference. Vault enriched with documentation of the full pipeline.

## Discoveries

### Architecture
- **Sync core + async SSE bridge** is the central architectural pattern: `train()` runs in `run_in_executor`, events bridge via `run_coroutine_threadsafe` into `asyncio.Queue`. This pattern is now documented as [[Decisions/ADR-002-sync-core-async-bridge|ADR-002]].

### Training Loop (the "render")
- The forward pass is autoregressive over `block_size` — one token at a time, no batching (educational simplicity)
- KV cache is per-layer `list.append()` — unbounded growth per forward pass (fine for small block_size)
- RMSNorm is applied at three points per layer: input, pre-attention (after residual), pre-MLP (after residual)
- Loss is mean over per-token cross-entropies, then `.backward()` propagates through the entire unrolled computation graph
- AdamW includes bias correction and linear LR decay — full implementation despite small model scale

### Autograd (Value)
- 69 lines of Python implementing full reverse-mode automatic differentiation
- `_local_grads` stores the partial derivative of output w.r.t. each child at computation time
- `backward()` does topological sort then chain rule accumulation: `child.grad += local_grad * parent.grad`
- No gradient checkpointing or mixed precision — not needed for educational sizes

### Tokenization
- Character-level: `sorted(set("".join(docs)))` — no BPE, no subword
- BOS sentinel = `len(uchars)` — always the last index in the vocabulary
- Encode: `[BOS, idx(c1), idx(c2), ..., BOS]`

### Data Flow
- Complete trace documented in [[TrainingDataFlow]]
- SSE is pure push — server initiates all communication after the initial subscribe
- MLflow runs as a managed subprocess; training logs metrics to it via REST API

### Code Patterns
- The `Tokenizier` class at `anvil/core/tokenizer.py` exists but is NOT used by `train()` — the engine embeds its own inline tokenization in the loop
- `softmax` is reimplemented three times across the codebase — once in engine.py, once in api/v1/router.py (for inference)

## Artifacts Created / Updated
- `docs/vault/Reference/TrainingDataFlow.md` — full data flow documentation
- `docs/vault/Decisions/ADR-002-sync-core-async-bridge.md` — architecture decision record
- `docs/vault/Sessions/2026-06-12-data-flow-analysis.md` — this session log
- `docs/vault/Reference/Glossary.md` — updated with core engine terms
- `docs/vault/Reference/DecisionLog.md` — updated with ADR-002 entry
- `docs/vault/index.md` — updated timestamp

## Open Questions
- The `Tokenizer` class at `anvil/core/tokenizer.py` is dead code (not imported by engine.py) — should be removed or integrated into the train() function
- softmax is duplicated (engine.py + api/v1/router.py) — should be a shared utility
- The `stop_training` endpoint returns 200 but does nothing — actual cancellation would require thread-safe signaling