# API Contract: Backward Graph Endpoint

**Endpoint**: `POST /v1/inference/backward-graph`
**Purpose**: Run forward + backward pass on input text, return computation graph with gradient data.

## Request

```json
{
  "text": "the quick fox",
  "model_id": null,
  "version": null
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `text` | string | yes | — | Input text to run forward+backward on. Minimum 1 char. |
| `model_id` | int\|null | no | null | Model registry ID. null = use demo model. |
| `version` | int\|null | no | null | Model version. null = latest. |

## Response

```json
{
  "model": { "id": null, "name": "demo", "is_demo": true },
  "nodes": [
    {
      "id": "140234567890123",
      "op": "input",
      "label": "input[5]",
      "value": 0.0832,
      "grad": -0.0012,
      "local_grads": [],
      "depth": 5
    },
    {
      "id": "140234567890456",
      "op": "mul",
      "label": "mul[3]",
      "value": 0.0416,
      "grad": 0.0058,
      "local_grads": [0.5, 0.0832],
      "depth": 3
    }
  ],
  "edges": [
    { "from": "140234567890456", "to": "140234567890123" }
  ],
  "metadata": {
    "total_nodes": 142,
    "total_edges": 184,
    "max_depth": 8,
    "input_tokens": ["<BOS>", "t", "h", "e", "<BOS>"],
    "loss_value": 2.3415
  }
}
```

## Errors

| Code | Condition |
|------|-----------|
| 400 | `text` is empty or not a string |
| 400 | Character not in model vocabulary |

## Implementation Notes

- Must call `loss.backward()` on the final loss before traversing (unlike `forward_graph()` which only does forward)
- Nodes without children (leaf nodes) have `local_grads: []`
- Capped at 400 nodes for browser performance
- `metadata.loss_value` is the average cross-entropy loss over the input sequence

---

# API Contract: Autograd Example Graph Endpoint

**Endpoint**: `POST /v1/inference/autograd-example`
**Purpose**: Return a small, complete, *teaching-scale* computation graph for the autograd lesson.

## Why this exists

The full model's `backward-graph` is hundreds of nodes deep (`max_depth` ~155–166 for any input, dominated by an `add` accumulation chain), and the concepts the lesson teaches — the SiLU nonlinearity and gradient accumulation on a reused value — live deep inside it (depth 64+ and 130+ respectively). Bounding that graph by depth cannot surface those concepts.

This endpoint instead builds a tiny single-neuron-with-loss expression using the **real** `Value` autograd engine, seeded with **genuine embedding scalars** from the typed text, and runs an authentic forward + backward pass. Every `value` and `grad` is real; only the scale is reduced. The graph deliberately includes `input`, `mul`, `add`, `silu`, and `pow` ops plus one reused input whose gradient accumulates from two paths.

The widget uses this endpoint by default and exposes `backward-graph` behind a "Show full model graph" toggle (rendered with a frontend depth cap as a guard).

## Request / Response

Identical schema to `backward-graph` (same request fields, same `{ model, nodes, edges, metadata }` response shape). Differences:

| Field | `autograd-example` |
|-------|--------------------|
| `metadata.total_nodes` | small (≤ ~50; typically ~12) |
| `metadata.max_depth` | small (≤ ~12) |
| graph completeness | complete (not node-capped/truncated) |
| `depth` | longest path from the loss (root depth 0) |

## Errors

Same as `backward-graph` (400 on empty/non-string `text`; OOV characters are skipped and a graph is still returned).