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