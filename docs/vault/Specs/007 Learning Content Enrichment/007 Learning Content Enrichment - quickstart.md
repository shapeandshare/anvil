---
title: 007 Learning Content Enrichment - quickstart
type: quickstart
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/007 Learning Content Enrichment/
related:
  - '[[007 Learning Content Enrichment]]'
created: ~
updated: ~
---
# Quickstart: Learning Content Enrichment Implementation

**Date**: 2026-06-13 | **Plan**: [plan.md](plan.md)

## Implementation Order

### Sprint 1: Backend Foundation (P0)

```
Day 1 — Backend endpoints + Progressive scripts
  ├── Add `backward_graph()` to InferenceService (inference.py: +25 lines)
  │   ├── Run forward on input text, compute loss, call loss.backward()
  │   └── Traverse Value graph capturing .data, .grad, .local_grads
  │
  ├── Add `loss_breakdown()` to InferenceService (inference.py: +20 lines)
  │   ├── Tokenize input, forward pass per position
  │   └── Compute per-token cross-entropy + average + random baseline
  │
  ├── Add `model_params()` to InferenceService (inference.py: +20 lines)
  │   ├── Iterate state_dict, extract shape/params per matrix
  │   └── Categorize into embedding/attention/mlp/output groups
  │
  ├── Add routes in api/v1/inference.py (+15 lines)
  │   ├── POST /v1/inference/backward-graph
  │   ├── POST /v1/inference/loss-breakdown
  │   └── GET /v1/inference/model-params
  │
  ├── Implement train1.py (MLP + manual gradients, ~80 lines)
  │   ├── 2-layer MLP: input -> hidden (ReLU) -> output
  │   ├── Numerical gradients via finite differences
  │   ├── Analytic gradients via chain rule by hand
  │   ├── Verify they match (assert within tolerance)
  │   └── Train with SGD, print loss
  │
  ├── Implement train3.py (single-head attention, ~100 lines)
  │   ├── Position embeddings + causal self-attention (1 head)
  │   ├── RMSNorm + residual connections
  │   └── Train with SGD, print loss
  │
  └── Implement train4.py (multi-head GPT, ~80 lines)
      ├── Multi-head attention (n_head heads)
      ├── Single transformer layer loop
      └── Train with SGD, print loss
```

### Sprint 2: Lesson Pages + Widgets (P0-P1)

```
Day 2-3 — Autograd lesson + Loss lesson
  ├── AutogradWidget (static/js/widgets/autograd.js, ~200 lines)
  │   ├── Canvas-based computation graph renderer
  │   ├── Node rendering with data + grad + local_grads overlay
  │   └── Color-coded by op type (green=input, blue=add, orange=mul, etc.)
  │
  ├── Autograd lesson steps (router.py: 5 steps)
  │   1. "What is autograd?" — Value class wraps scalars
  │   2. "Building the graph" — every operation tracks children
  │   3. "Topological sort" — ordering nodes for backward pass
  │   4. "Chain rule in action" — gradients flow backward
  │   5. "Gradient accumulation" — branching paths sum
  │
  ├── LossWidget (static/js/widgets/loss.js, ~150 lines)
  │   ├── Per-token bar chart with loss values
  │   ├── Random-guess baseline indicator line
  │   └── Average loss display
  │
  └── Loss lesson steps (router.py: 5 steps)
      1. "What is loss?" — measuring prediction error
      2. "Cross-entropy" — -log(p) formula
      3. "Softmax connection" — logits → probabilities
      4. "Reading the curve" — loss trajectory shapes
      5. "Baseline" — why ~3.3 is random guessing
```

### Sprint 3: Remaining Lessons (P2)

```
Day 4 — Parameter Anatomy + Adam lesson + FAQ
  ├── ParamsWidget (static/js/widgets/params.js, ~120 lines)
  │   ├── Interactive treemap or stacked bar chart
  │   ├── n_embd / n_layer sliders with live recalculation
  │   └── Category summary with percentages
  │
  ├── Parameter anatomy lesson steps (router.py: 5 steps)
  │
  ├── Add optimizer_state_callback to train() (engine.py: +15 lines)
  │
  ├── Extend SSE event stream (training.py: +15 lines)
  │   └── New "optimizer_state" event type
  │
  ├── AdamWidget (static/js/widgets/adam.js, ~180 lines)
  │   ├── m/v/grad curves over training steps
  │   ├── beta1/beta2 slider controls
  │   └── LR decay annotation
  │
  ├── Adam lesson steps (router.py: 5 steps)
  │
  ├── FAQ page (archetypes/faq.html, ~60 lines)
  │   ├── Accordion-style question/answer
  │   └── 7 questions from spec FR-016
  │
  └── Enrich attention lesson with residuals + RMSNorm steps
      ├── Add 2 steps to existing ATTENTION_STEPS
      └── RMSNorm: input values, RMS, scale factor, output
```

### Sprint 4: Tests + Polish

```
Day 5 — Tests, agent context, vault enrichment
  ├── test_examples.py (unit tests for train1/3/4)
  │   ├── train1: loss decreases, numerically verify gradients match
  │   ├── train3: loss decreases, output shape correct
  │   └── train4: loss decreases, param count correct
  │
  ├── test_inference_widgets.py (e2e tests)
  │   ├── backward-graph: returns valid graph with .grad populated
  │   ├── loss-breakdown: per-token losses sum to average
  │   └── model-params: sum of group params == total_params
  │
  ├── Update docs/vault/ with session log
  │
  └── Code review + lint pass
```

## Files to Create/Modify

### New Files (12)
```
microgpt/api/static/js/widgets/autograd.js     (~200 lines)
microgpt/api/static/js/widgets/loss.js         (~150 lines)
microgpt/api/static/js/widgets/params.js       (~120 lines)
microgpt/api/static/js/widgets/adam.js         (~180 lines)
microgpt/api/templates/archetypes/faq.html     (~60 lines)
examples/train1.py                              (~80 lines)
examples/train3.py                              (~100 lines)
examples/train4.py                              (~80 lines)
tests/unit/core/test_examples.py                (~60 lines)
tests/e2e/test_inference_widgets.py             (~80 lines)
docs/vault/Specs/007 Learning Content Enrichment/contracts/* (4 files — done)
```

### Modified Files (6)
```
microgpt/services/inference.py                  (+65 lines)
microgpt/api/v1/inference.py                    (+15 lines)
microgpt/api/v1/router.py                       (+120 lines)
microgpt/api/templates/archetypes/concept.html  (+10 lines)
microgpt/core/engine.py                         (+15 lines)
microgpt/services/training.py                   (+15 lines)
```

Total estimated new code: ~1,200 lines across 18 files.