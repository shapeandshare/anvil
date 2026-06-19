---
title: Learning Content Enrichment Implementation
type: session
tags:
- type/session-log
created: 2026-06-13
updated: '2026-06-18'
---

# Session: Learning Content Enrichment

Implements 7 new learning features for anvil: autograd backprop visualization, progressive code stubs (train1/train3/train4), cross-entropy loss deep-dive, model parameter anatomy, Adam optimizer interactive lesson, FAQ section, and residual connections & RMSNorm explanations.

## What was built

- **3 backend endpoints**: backward-graph (computation graph with gradients), loss-breakdown (per-token cross-entropy), model-params (parameter anatomy)
- **4 interactive widgets**: AutogradWidget (canvas computation graph), LossWidget (per-token loss bars), ParamsWidget (parameter breakdown), AdamWidget (optimizer state curves)
- **3 progressive scripts**: train1.py (MLP + manual gradients), train3.py (single-head attention), train4.py (multi-head GPT)
- **5 new lessons**: Autograd, Loss, Parameters, Adam, FAQ (static accordion)
- **Enriched attention lesson**: 2 new steps for residual connections and RMSNorm
- **Adam optimizer state capture**: optimizer_state_callback in engine.py + SSE event in TrainingService
- **16 tests**: 6 unit tests + 10 e2e endpoint tests covering all new endpoints, demo fallback (FR-019), and OOV handling (FR-020)

## Key files created/modified

(Full task list available in the session feature branch.)

## Design decisions

- Computation graph visualization uses existing forward_graph() traversal augmented with .grad and _local_grads
- Widgets follow existing pattern (constructor takes container, _render() builds HTML, _fetch() calls API)
- Demo model fallback ensures widgets work without training
- Adam optimizer state captured via callback (Option B — real logged data)
