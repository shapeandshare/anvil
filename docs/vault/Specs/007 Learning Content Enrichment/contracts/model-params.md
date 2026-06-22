# API Contract: Model Parameters Endpoint

**Endpoint**: `GET /v1/inference/model-params`
**Purpose**: Return named parameter breakdown for a model.

## Request

| Query Param | Type | Required | Default | Description |
|-------------|------|----------|---------|-------------|
| `model_id` | int\|null | no | null | null = use demo model |
| `version` | int\|null | no | null | null = latest |

## Response

```json
{
  "model": { "id": null, "name": "demo", "is_demo": true },
  "total_params": 4192,
  "n_embd": 16,
  "n_layer": 1,
  "n_head": 4,
  "block_size": 16,
  "vocab_size": 27,
  "groups": [
    {
      "name": "wte",
      "category": "embedding",
      "shape": [27, 16],
      "num_params": 432,
      "percentage": 10.31
    },
    {
      "name": "wpe",
      "category": "embedding",
      "shape": [16, 16],
      "num_params": 256,
      "percentage": 6.11
    },
    {
      "name": "layer0.attn_wq",
      "category": "attention",
      "shape": [16, 16],
      "num_params": 256,
      "percentage": 6.11
    },
    {
      "name": "layer0.attn_wk",
      "category": "attention",
      "shape": [16, 16],
      "num_params": 256,
      "percentage": 6.11
    },
    {
      "name": "layer0.attn_wv",
      "category": "attention",
      "shape": [16, 16],
      "num_params": 256,
      "percentage": 6.11
    },
    {
      "name": "layer0.attn_wo",
      "category": "attention",
      "shape": [16, 16],
      "num_params": 256,
      "percentage": 6.11
    },
    {
      "name": "layer0.mlp_fc1",
      "category": "mlp",
      "shape": [64, 16],
      "num_params": 1024,
      "percentage": 24.43
    },
    {
      "name": "layer0.mlp_fc2",
      "category": "mlp",
      "shape": [16, 64],
      "num_params": 1024,
      "percentage": 24.43
    },
    {
      "name": "lm_head",
      "category": "output",
      "shape": [27, 16],
      "num_params": 432,
      "percentage": 10.31
    }
  ]
}
```

## Category Summary (computed client-side or in endpoint)

| Category | Total Params | Percentage |
|----------|-------------|------------|
| embedding (wte + wpe) | 688 | 16.42% |
| attention (4 × Wq/Wk/Wv/Wo) | 1024 | 24.44% |
| mlp (fc1 + fc2) | 2048 | 48.85% |
| output (lm_head) | 432 | 10.31% |

## Implementation Notes

- Categories merge groups by prefix: `wte`/`wpe` → embedding, `.attn_` → attention, `.mlp_` → mlp, `lm_head` → output
- `percentage` is rounded to 2 decimal places
- `total_params` == sum of all `num_params` (verified in tests)