---
title: 007 Learning Content Enrichment - data-model
type: data-model
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/007 Learning Content Enrichment/
related:
  - '[[007 Learning Content Enrichment]]'
created: ~
updated: ~
---
# Data Model: Learning Content Enrichment

**Phase**: 1 (Design) | **Date**: 2026-06-13 | **Plan**: [plan.md](plan.md)

## Entities

### 1. ComputationGraphNode

Represents a single `Value` in the autograd computation graph. Rendered as a node in the canvas-based graph visualization.

| Field | Type | Description | Source |
|-------|------|-------------|--------|
| `id` | string | Unique node identifier (memory address of Value) | `str(id(v))` in Python |
| `op` | string | Operation type: `input`, `add`, `mul`, `pow`, `log`, `exp`, `relu`, `combine` | Inferred by `assign_op()` in `forward_graph()` |
| `label` | string | Display label: `{op}[{depth}]` | Generated in `traverse()` |
| `value` | float | Scalar value of this node after forward pass | `v.data` |
| `grad` | float | Gradient after backward pass (0 if backward not called) | `v.grad` |
| `local_grads` | float[] | Local gradient contribution to each child | `v._local_grads` |
| `depth` | int | Depth in computation graph (0 = output node) | Computed during DFS traversal |

**Relationships**:
- A node connects to its children via edges: `{from: parentId, to: childId}`
- Nodes at depth 0 are the root (loss or logits); nodes at max depth are leaf parameters/inputs

**Validation**:
- Max 400 nodes per graph (browser rendering limit)
- No cycles (traversal terminates at leaf nodes with no children)

---

### 2. LossBreakdown

Per-token cross-entropy values for an input text sequence. Powers the cross-entropy loss lesson widget.

| Field | Type | Description |
|-------|------|-------------|
| `tokens` | TokenLabel[] | Array of tokens in the sequence |
| `losses` | float[] | Per-token cross-entropy loss: `-log(p(target))` |
| `average_loss` | float | Mean of all per-token losses |
| `random_baseline` | float | `-log(1/vocab_size)` — loss of random guessing |
| `vocab_size` | int | Number of tokens in vocabulary |

**TokenLabel**:
| Field | Type | Description |
|-------|------|-------------|
| `char` | string | The character (or `<BOS>` for boundary) |
| `id` | int | Token ID in vocabulary |

**Derivation**:
```python
for pos_id in range(n):
    logits = model.forward(token_id, pos_id, keys, values)
    probs = softmax(logits)
    loss_t = -probs[target_id].log()
    losses.append(loss_t.data)
average_loss = sum(losses) / n
random_baseline = -math.log(1 / vocab_size)
```

**Validation**:
- `len(losses)` == `len(tokens) - 1` (each token except BOS is a prediction target)
- All losses are positive (log of a probability < 1)

---

### 3. ParameterBreakdown

Named matrix groups with shapes and parameter counts. Powers the parameter anatomy lesson.

| Field | Type | Description |
|-------|------|-------------|
| `groups` | ParamGroup[] | Array of named parameter groups |
| `total_params` | int | Sum of all parameter counts |
| `n_embd` | int | Current embedding dimension |
| `n_layer` | int | Current layer count |

**ParamGroup**:
| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Group name: `wte`, `wpe`, `lm_head`, `layer{i}.attn_wq`, etc. |
| `category` | string | Category: `embedding`, `attention`, `mlp`, `output` |
| `shape` | [int, int] | Matrix dimensions `[rows, cols]` |
| `num_params` | int | `rows * cols` |
| `percentage` | float | `num_params / total_params * 100` |

**Derivation**:
```python
# From GPT.state_dict
groups = []
for name, mat in model.state_dict.items():
    rows, cols = len(mat), len(mat[0]) if mat else 0
    num_params = rows * cols
    # Categorize by name prefix
    if name == "wte": category = "embedding"
    elif name == "wpe": category = "embedding"
    elif name == "lm_head": category = "output"
    elif ".attn_" in name: category = "attention"
    elif ".mlp_" in name: category = "mlp"
```

---

### 4. OptimizerSnapshot

Per-parameter optimizer state at a given training step. Captured during the training loop via callback.

| Field | Type | Description |
|-------|------|-------------|
| `step` | int | Training step number |
| `params` | ParamSnapshot[] | Per-parameter optimizer state |

**ParamSnapshot**:
| Field | Type | Description |
|-------|------|-------------|
| `index` | int | Parameter index (0 to N-1) |
| `m` | float | First moment (momentum) estimate |
| `v` | float | Second moment (adaptive LR) estimate |
| `grad` | float | Current gradient value |

**Derivation**:
```python
# Captured inside train() after Adam update:
snapshot = {
    "step": step,
    "params": [
        {"index": i, "m": m[i], "v": v[i], "grad": p.grad}
        for i, p in enumerate(model.params)
    ]
}
```

---

## State Transitions

### ComputationGraph (autograd lesson)

```
[User types text] → POST /v1/inference/backward-graph
  → InferenceService.backward_graph(text, loaded)
    → forward pass on text (builds computation graph)
    → compute loss on last logits
    → loss.backward() (populates .grad on all nodes)
    → traverse graph with DFS (builds {nodes, edges} with .grad and _local_grads)
  → Response: { nodes: [...], edges: [...] }
  → Browser: render nodes + edges on canvas + annotate with grad values
```

### LossBreakdown (loss lesson)

```
[User types text] → POST /v1/inference/loss-breakdown
  → InferenceService.loss_breakdown(text, loaded)
    → tokenize text → encode with BOS
    → for each position: forward → softmax → -log(p(target))
    → accumulate losses, compute average + random baseline
  → Response: { tokens: [...], losses: [...], average_loss, random_baseline }
  → Browser: render bar chart with each token's loss + baseline indicator
```

### OptimizerSnapshot (Adam lesson)

```
[User starts training] → POST /v1/training/start
  → TrainingService.start_training(config)
    → train() with optimizer_state_callback
    → At each step, callback captures m/v/grad for ALL params
    → SSE event: "optimizer_state" with snapshot data
  → Browser: SSESession.onoptimizerstate(d) → render m/v curves
```

---

## Validation Rules

| Entity | Rule | Enforcement |
|--------|------|-------------|
| ComputationGraph | No more than 400 nodes | `max_nodes` parameter in `traverse()` |
| ComputationGraph | Edges must reference valid node IDs | Built during same traversal |
| LossBreakdown | All losses > 0 | Guaranteed by -log(p) where p in (0,1] |
| LossBreakdown | len(losses) == len(tokens) - 1 | BOS wrapping ensures this |
| ParameterBreakdown | Sum of group percentages == 100% (±0.1 rounding) | Verified in test |
| ParameterBreakdown | All 4 categories present (embedding, attention, mlp, output) | Verified in test |
| OptimizerSnapshot | len(m) == len(v) == len(params) | Guaranteed by Adam implementation |