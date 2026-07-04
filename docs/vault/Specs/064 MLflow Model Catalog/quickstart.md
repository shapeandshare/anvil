---
title: 064 MLflow Model Catalog - Quickstart
type: spec
tags:
  - type/spec
created: 2026-07-03
updated: 2026-07-03
---

# Quickstart: Unified MLflow Model Catalog

**Feature**: 064 | Validates the four user stories end-to-end on a fresh instance.

## Prerequisites

```bash
make setup && make run     # web :8080 + MLflow sidecar :5001
export API_KEY=$(cat data/.api_key)
```

## 1. Import an external model (US2)

```bash
curl -s -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"source":"huggingface","identifier":"TinyLlama/TinyLlama-1.1B-Chat-v1.0","revision":"main"}' \
  http://localhost:8080/v1/models/import
# → {"job_id": 1, "status": "queued"}

curl -s -H "X-API-Key: $API_KEY" http://localhost:8080/v1/models/import/1/status
# → status=complete, model_name=hf--TinyLlama--TinyLlama-1.1B-Chat-v1.0, model_version=1
```

Verify idempotency: re-POST the same body → job completes pointing at the
**same** ModelRef; `GET /v1/models` still shows exactly one entry (SC-003).

## 2. One catalog everywhere (US1)

```bash
curl -s -H "X-API-Key: $API_KEY" http://localhost:8080/v1/models | python3 -m json.tool
# → contains BOTH kind=external (TinyLlama) and kind=trained (demo) entries
```

UI check: `/v1/models-page` lists both with kind badges; the inference
page picker (`/v1/inference-page`) lists both; MLflow UI
(`localhost:5001`) shows the same registered models — single catalog.

## 3. Download assets & play (US1/FR-012)

```bash
curl -s -X POST -H "X-API-Key: $API_KEY" \
  "http://localhost:8080/v1/models/hf--TinyLlama--TinyLlama-1.1B-Chat-v1.0/versions/1/download"
# poll .../download/{job_id}/status until complete → asset_availability=assets_available
```

Play is disabled until availability flips (check the Models page button
state), then generation works from the inference page with the external
model selected from the picker.

## 4. Fine-tune + evaluate via ModelRef (US3)

Train a LoRA adapter from the Training page (base = the TinyLlama entry),
then:

```bash
curl -s -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"model_name":"hf--TinyLlama--TinyLlama-1.1B-Chat-v1.0","model_version":1,
       "base_model_name":"hf--TinyLlama--TinyLlama-1.1B-Chat-v1.0","base_model_version":1,
       "adapter_id":"run_1","eval_dataset_name":"smoke-eval"}' \
  http://localhost:8080/v1/eval/fine-tuned
# → eval record references models by name+version, no numeric model IDs anywhere
```

## 5. Fail-closed catalog (US-edge / SC-005)

```bash
kill $(pgrep -f "mlflow server")   # stop the sidecar only
curl -s -H "X-API-Key: $API_KEY" http://localhost:8080/v1/models
# → 503 {"detail":"Model catalog unavailable","code":"CATALOG_UNAVAILABLE"}
curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" http://localhost:8080/v1/operations-page
# → 200  (non-catalog surfaces keep working)
```

Restart with `make run`; listing recovers (reconnect backoff).

## 6. Archive semantics (US4)

```bash
curl -s -X DELETE -H "X-API-Key: $API_KEY" \
  "http://localhost:8080/v1/models/hf--TinyLlama--TinyLlama-1.1B-Chat-v1.0/versions/1"
# → {"status":"archived",...}
curl -s -H "X-API-Key: $API_KEY" http://localhost:8080/v1/models          # entry gone
curl -s -H "X-API-Key: $API_KEY" "http://localhost:8080/v1/models?include_archived=true"  # entry present, archived
ls data/models/hf--TinyLlama--TinyLlama-1.1B-Chat-v1.0/1/hf/ 2>&1        # assets removed
# eval history from step 4 still renders and resolves the archived ref
```

## 7. Removal verification (SC-006)

```bash
grep -rn "ExternalModelRepository\|external_model_id" anvil/ | wc -l   # → 0
curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" http://localhost:8080/v1/models/external  # → 404
```

## 8. Gates

```bash
make lint && make typecheck && make test && make vault-audit
```
