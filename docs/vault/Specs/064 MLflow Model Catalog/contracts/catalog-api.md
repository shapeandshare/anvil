---
title: 064 MLflow Model Catalog - API Contract
type: spec
tags:
  - type/spec
created: 2026-07-03
updated: 2026-07-03
---

# HTTP Contract: Unified Model Catalog API

**Feature**: 064 | **Date**: 2026-07-03
**Auth**: All endpoints require `X-API-Key` header or session cookie (existing middleware — unchanged).

## Error contract (all catalog endpoints)

When the catalog backend (MLflow) is unreachable (FR-009 / research D7):

```
HTTP 503
{ "detail": "Model catalog unavailable", "code": "CATALOG_UNAVAILABLE" }
```

`404` uses the existing `{"detail": "..."}` shape. ModelRef path params:
`{name}` matches `[A-Za-z0-9._-]+`; `{version}` is a positive int.

---

## GET /v1/models — unified listing (replaces GET /v1/models/external; backs all pickers)

Query: `kind` (optional, repeatable: `trained|external|merged`),
`runnable_only` (bool, default false), `include_archived` (bool, default
false), `search` (optional substring on name/display_name).

```json
200
{
  "data": [
    {
      "name": "hf--TinyLlama--TinyLlama-1.1B-Chat-v1.0",
      "version": 1,
      "kind": "external",
      "display_name": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
      "source_type": "huggingface",
      "source_identifier": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
      "revision_sha": "fe8a4ea1ffedaf415f4da2f062534de366a451e6",
      "architecture_family": "LlamaForCausalLM",
      "tokenizer_family": "sentencepiece",
      "license": "apache-2.0",
      "parameter_count": 1100048384,
      "runnable_status": "runnable",
      "runnable_reason": null,
      "asset_availability": "assets_available",
      "final_loss": null,
      "lifecycle_state": "active",
      "created_at": "2026-07-03T12:00:00Z",
      "total_versions": 1
    },
    {
      "name": "demo",
      "version": 1,
      "kind": "trained",
      "display_name": "demo",
      "source_type": "internal",
      "source_identifier": "demo",
      "revision_sha": null,
      "architecture_family": "LlamaForCausalLM",
      "tokenizer_family": "char",
      "license": null,
      "parameter_count": 12345,
      "runnable_status": "runnable",
      "runnable_reason": null,
      "asset_availability": "assets_available",
      "final_loss": 2.7811,
      "lifecycle_state": "active",
      "created_at": "2026-07-03T12:00:00Z",
      "total_versions": 1
    }
  ]
}
```

Notes: one item per **latest active version** of each logical model;
performance budget SC-008 (≤100 models < 2 s; no per-model run lookups).
`GET /v1/inference/models` becomes a thin alias returning the same
entries filtered `runnable_only=true` (response wrapped as `{"models":
[...]}` for template compatibility, fields as above).

## GET /v1/models/{name} — logical model detail

```json
200
{
  "name": "hf--TinyLlama--TinyLlama-1.1B-Chat-v1.0",
  "display_name": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
  "kind": "external",
  "source_type": "huggingface",
  "source_identifier": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
  "lifecycle_state": "active",
  "versions": [ { /* CatalogEntry fields per version, newest first */ } ]
}
404 — unknown name
```

## GET /v1/models/{name}/versions/{version} — pinned version detail

`200` → single CatalogEntry object (fields as in listing) plus
`"config": { ...parsed config manifest... }` retrieved from the import
run artifact (FR-003 retrievable document). `404` — unknown ref.

## POST /v1/models/import — unchanged request, ModelRef result

Request (existing shape):
```json
{ "source": "huggingface", "identifier": "TinyLlama/TinyLlama-1.1B-Chat-v1.0", "revision": "main", "name": null }
```
Responses:
```json
202 { "job_id": 7, "status": "queued" }
```
Job status (`GET /v1/models/import/{job_id}/status`, existing route) gains
ModelRef fields on completion:
```json
200 { "job_id": 7, "status": "complete",
      "model_name": "hf--TinyLlama--TinyLlama-1.1B-Chat-v1.0",
      "model_version": 1, ... }
```
Duplicate identity triple → job completes referencing the existing
ModelRef (idempotent; FR-005/SC-003). Catalog down → job `failed`,
`error_code: "catalog_unavailable"`, retryable via existing retry route.

## POST /v1/models/{name}/versions/{version}/download — asset download (re-keyed)

Replaces `POST /v1/models/{model_id}/download`. Semantics unchanged
(202 + job id; per-file progress via existing status route, now
`GET /v1/models/{name}/versions/{version}/download/{job_id}/status`).
Assets listing: `GET /v1/models/{name}/versions/{version}/assets`
(same per-file shape as today).

## DELETE /v1/models/{name}/versions/{version} — archive (never destroy)

```json
200 { "status": "archived", "name": "...", "version": 1 }
```
Effects (FR-008 / US4): sets `anvil.lifecycle_state=archived`; removes
FileStore assets + `model_assets` rows; cancels in-flight download jobs;
entry disappears from active listings; existing references (evals,
adapters) still resolve with `lifecycle_state: "archived"`.

## Removed routes (FR-007 / SC-006)

- `GET /v1/models/external` → **410 gone from codebase** (no route; 404)
- `GET /v1/models/external/{model_id}` → removed
- `DELETE /v1/models/external/{model_id}` → removed
- Integer-keyed `POST /v1/models/{model_id}/download` and
  `GET /v1/models/{model_id}/assets` → replaced by ModelRef-keyed routes

## Unchanged consumers (verified response-shape compatibility)

- `POST /v1/inference/sample`, `POST /v1/inference/generate` — request
  bodies switch `model_id: int` → `model_name: str` + `model_version:
  int` (templates updated in the same change; no dual support, ADR-032)
- `POST /v1/eval/fine-tuned` — same rename; eval records expose
  `model_name`/`model_version` + `base_model_name`/`base_model_version`
- `GET /v1/registry/models` — retained for the experiments UI, now served
  by `ModelCatalogService` filtered `kind=trained|merged` (same field
  names as today where they exist; enrichment fields come from tags)
