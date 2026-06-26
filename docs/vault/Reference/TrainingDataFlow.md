---
title: Training Render Loop & Data Flow
type: reference
tags:
  - type/reference
  - domain/core
created: 2026-06-12T00:00:00.000Z
updated: '2026-06-18'
aliases:
  - render-loop
  - data-flow
  - training-pipeline
related:
  - '[[Reference/InfraParadigms]]'
  - '[[Reference/ProgressiveWalkthroughs]]'
  - '[[Reference/MlflowIntegration]]'
  - '[[Reference/ContentManagementLandscape]]'
---

# Training Render Loop & Data Flow

## Overview

The training pipeline bridges three execution paradigms: async web → sync CPU-bound engine → async streaming back to browser. This document traces the complete path from browser button click to parameter update and back.

## Architecture Diagram

```
┌──────────────┐     POST /v1/training/start     ┌──────────────────┐
│   Browser    │ ──────────────────────────────►  │    FastAPI       │
│  (Jinja2 +   │                                  │   (uvicorn)      │
│   vanilla    │ ◄── SSE /v1/training/stream ──── │                  │
│     JS)      │     event: metrics/loss          │  api/v1/training │
└──────────────┘     event: complete/samples      └────────┬─────────┘
                                                           │
                                              asyncio.create_task()
                                                           │
                                                           ▼
                                              ┌─────────────────────┐
                                              │  TrainingService    │
                                              │  services/training  │
                                              │                     │
                                              │  asyncio.Queue      │
                                              │  (SSE event buffer) │
                                              └──────────┬──────────┘
                                                         │
                                              run_in_executor()
                                              (thread pool)
                                                         │
                                                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Core Engine (sync, zero deps)                     │
│                    anvil/core/engine.py                           │
│                                                                     │
│  train(docs, num_steps, ...)                                        │
│    │                                                                │
│    ├── Tokenize: char-level, BOS sentinel                           │
│    ├── Init LlamaModel (state_dict of Value matrices)                │
│    ├── Init Adam buffers (m, v)                                     │
│    │                                                                │
│    └── STEP LOOP (for step in range(num_steps))                     │
│          │                                                          │
│          ├── Select doc (round-robin)                               │
│          ├── Encode: [BOS, c1, c2, ..., BOS]                       │
│          ├── Init KV cache (per-layer lists)                        │
│          │                                                          │
│          ├── FORWARD PASS (autoregressive over block_size)          │
│          │   │                                                      │
│          │   ├── GPT.forward(token_id, pos_id, keys, values)       │
│          │   │     ├── x = wte[token_id]                           │
│          │   │     │   (NO learned position embedding —            │
│          │   │     │    replaced by RoPE. NO embedding-level       │
│          │   │     │    norm — removed per Llama architecture)     │
│          │   │     │                                                │
│          │   │     └── FOR each layer:                              │
│          │   │           ├── Pre-attn RMSNorm:                    │
│          │   │           │   r = rmsnorm(x) × rms_1               │
│          │   │           │   Q = r · Wq; K = r · Wk; V = r · Wv   │
│          │   │           │   RoPE (half-split): apply to Q and K  │
│          │   │           │   Cache rotated K (not raw K)          │
│          │   │           │   FOR each head:                        │
│          │   │           │     attn = softmax(Q·Kᵀ / √d)          │
│          │   │           │     out  = Σ attn·V                     │
│          │   │           │   x = attn_out · Wo + residual          │
│          │   │           │                                                │
│          │   │           └── SwiGLU MLP:                           │
│          │   │               r = rmsnorm(x) × rms_2               │
│          │   │               gate = SiLU(r · Wgate)                │
│          │   │               up   = r · Wup                       │
│          │   │               x = (gate ⊙ up) · Wdown + residual   │
│          │   │                                                      │
│          │   ├── Final RMSNorm: x = rmsnorm(x) × rms_final        │
│          │   └── logits = x · lm_head                              │
│          │                                                          │
│          ├── softmax(logits) → probs                               │
│          ├── cross_entropy = -log(probs[target])                   │
│          ├── loss = mean(cross_entropies)                          │
│          │                                                          │
│          ├── BACKWARD PASS                                         │
│          │   └── loss.backward()                                   │
│          │       (reverse-mode autograd on Value graph)            │
│          │                                                          │
│          ├── ADAM UPDATE                                           │
│          │   lr_t = lr * (1 - step/num_steps)                     │
│          │   FOR each param:                                       │
│          │     m = β₁·m + (1-β₁)·grad                              │
│          │     v = β₂·v + (1-β₂)·grad²                             │
│          │     m_hat = m / (1-β₁^step)                             │
│          │     v_hat = v / (1-β₂^step)                             │
│          │     param -= lr_t · m_hat / (√v_hat + ε)               │
│          │     grad = 0                                            │
│          │                                                          │
│          └── progress_callback(step, loss.data)                    │
│               │                                                    │
│               │  (called from thread executor)                     │
│               ▼                                                    │
│          asyncio.run_coroutine_threadsafe(                         │
│            queue.put({"event":"metrics",                           │
│                        "data":{"step":s,"loss":l}}),               │
│            loop)                                                   │
│                                                                    │
│    POST-LOOP: Sampling                                             │
│      FOR _ in range(20):                                           │
│        Autoregressive generation with temperature scaling          │
│        token_id = sample(softmax(logits / temperature))            │
│        Until BOS or block_size                                     │
│                                                                    │
│    return model, final_loss, samples, uchars                       │
└─────────────────────────────────────────────────────────────────────┘
```

## SSE Streaming Bridge

The critical bridge between sync training and async web:

```
Thread Executor (sync core)           asyncio Event Loop
┌────────────────────┐              ┌──────────────────────┐
│ train()            │              │ TrainingService      │
│   progress_cb() ───┼──run_coro──►│   queue.put(msg)     │
│                    │              │                      │
│                    │              │ FastAPI SSE endpoint  │
│                    │              │   queue.get() ───────► Browser
└────────────────────┘              └──────────────────────┘
```

Key properties:
- `run_coroutine_threadsafe()` is the only safe way to inject into an asyncio.Queue from another thread
- SSE keeps connection alive with 30s timeout + heartbeat keepalive
- Queue consumer breaks on `complete` or `error` events

## Completion & Persistence

After training finishes, `on_complete` fires:

1. **MLflow Tracking** (`TrackingService`):
   - `set_tag()` — `anvil.status=finished`, `anvil.final_loss`, dataset/corpus metadata tags
   - `log_params()` — capture config hyperparameters as MLflow params
   - `log_metrics()` — final loss, device, elapsed_sec
   - `log_model()` — upload model.json + samples.txt as artifacts
   - On success: `register_source_model()` — create/update MLflow Model Registry version
   - On error: `fail_run()` + `set_tag("anvil.status", "failed")`
2. **Disk**: Save `data/models/experiment_{id}.json` for local inference fallback
3. **SSE**: Send `complete` event with final loss + device
4. **Browser**: Enable inference on the trained model

> **Note**: The old `ExperimentRepository` path is removed. Experiment state (status, run metadata) is stored entirely as MLflow tags and params — there is no local DB `experiments` table (see [[Decisions/ADR-016-mlflow-primary-lineage|ADR-016]]).

## Inference Flow

```
POST /v1/inference/sample  {model_id, version, temperature, num_samples}
  │
  ├── InferenceService.load_model(model_id, version)
  │     ├── Phase 1: Try local data/models/experiment_{id}.json
  │     └── Phase 2: Fall back to MLflow artifact download
  │                   (MlflowClient.download_artifacts)
  ├── Reconstruct LlamaModel with saved hyperparams + state_dict
  │
  └── Autoregressive sampling (same as post-training loop)
        token = BOS
        for pos in range(block_size):
          logits = LlamaModel.forward(token, pos, keys, values)
          token = sample(softmax(logits / temperature))
          if token == BOS: break
```

## Key Properties

| Property | Implementation |
|----------|---------------|
| **Determinism** | `random.seed(42)` at train start; model init uses fixed std |
| **Zero deps** | Core engine imports only `random` and `math` |
| **RoPE** | Rotary Position Encoding via precomputed cos/sin tables — applied per-head, half-split (rotate_half) convention, replaces learned `wpe` |
| **SwiGLU** | SiLU-gated gated MLP — `(SiLU(x·Wgate) ⊙ x·Wup)·Wdown` — replaces ReLU `fc1`/`fc2` |
| **Learned RMSNorm** | Per-layer `rms_1`/`rms_2` + final `rms_final` scale vectors, initialized to 1.0, applied elementwise after RMSNorm computation |
| **No embedding norm** | Embedding-level RMSNorm removed — Llama architecture has no corresponding tensor; norm occurs only at pre-attn, pre-MLP, and pre-output positions |
| **Character-level** | No BPE/WordPiece — sorted unique chars + BOS sentinel |
| **KV cache** | Per-layer lists appended each forward step (no recompute). Keys are rotated by RoPE BEFORE caching (one rotation per position — never double-rotated). Values are not rotated |
| **Autograd** | Reverse-mode AD via Value graph (micrograd pattern) |
| **Adam** | Plain Adam (not AdamW — no weight decay) with bias correction + linear LR decay |
| **No batching** | Processes one token position at a time (educational simplicity) |
| **Architecture** | Llama-style: RoPE (half-split), SwiGLU MLP, learned RMSNorm, final norm |

## See Also

- [[Glossary]] — Value, RMSNorm, KV cache, Adam definitions
- [[ArchitectureOverview]] — High-level system architecture and layer discipline
- [[DualBackend]] — CPU vs GPU training bridge
- [[Hyperparameters]] — Hyperparameter interaction guide
- [[Decisions/ADR-002-sync-core-async-bridge|ADR-002: Sync Core / Async Bridge]]
