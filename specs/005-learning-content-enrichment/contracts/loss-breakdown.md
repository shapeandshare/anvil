# API Contract: Loss Breakdown Endpoint

**Endpoint**: `POST /v1/inference/loss-breakdown`
**Purpose**: Compute per-token cross-entropy loss for input text.

## Request

```json
{
  "text": "emma",
  "model_id": null,
  "version": null
}
```

## Response

```json
{
  "model": { "id": null, "name": "demo", "is_demo": true },
  "tokens": [
    { "char": "<BOS>", "id": 26 },
    { "char": "e", "id": 4 },
    { "char": "m", "id": 12 },
    { "char": "m", "id": 12 },
    { "char": "a", "id": 0 },
    { "char": "<BOS>", "id": 26 }
  ],
  "losses": [2.4501, 2.1203, 1.8902, 1.5601, 2.0104],
  "average_loss": 2.0062,
  "random_baseline": 3.2958,
  "vocab_size": 27
}
```

## Errors

Same as existing inference endpoints (400 on bad input, 404 on missing model).

## Implementation Notes

- `losses[i]` corresponds to predicting `tokens[i+1]` given `tokens[0..i]`
- `len(losses)` == `len(tokens) - 1` (last token has no prediction target since it's the final BOS)
- `random_baseline` = `-log(1/vocab_size)` — always computable, no model needed