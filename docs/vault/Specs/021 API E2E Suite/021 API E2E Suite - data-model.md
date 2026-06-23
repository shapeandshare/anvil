---
title: 021 API E2E Suite - data-model
type: data-model
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/021 API E2E Suite/
related:
  - '[[021 API E2E Suite]]'
created: ~
updated: ~
---
# Data Model: Whole-API E2E Test Suite

**Phase**: 1 — Design & Contracts
**Date**: 2026-06-21
**Spec**: [spec.md](../spec.md)

## 1. Test Entity Model

The test suite defines entities for factory fixture contracts, not application data models.

### Corpus (factory-produced)
| Field | Type | Description |
|-------|------|-------------|
| `id` | `int` or `str` | Corpus identifier (returned by API) |
| `name` | `str` | Corpus name |
| `files` | `list[dict]` | File entries after ingestion |

**Factory**: `make_corpus(client) → dict`
- Creates corpus via `POST /corpora` with deterministic name
- Uploads small `.txt` payload via `POST /corpora/{id}/ingest`
- Returns the corpus record (`{"id": ..., "name": ..., ...}`)

### Dataset (factory-produced)
| Field | Type | Description |
|-------|------|-------------|
| `id` | `int` or `str` | Dataset identifier |
| `name` | `str` | Dataset name |
| `corpus_id` | `int` or `str` | Source corpus reference |

**Factory**: `make_dataset(client, corpus_id=None) → dict`
- Creates dataset via `POST /datasets` or from corpus via `POST /datasets/from-corpus`
- Returns the dataset record

### Training Run (factory-produced)
| Field | Type | Description |
|-------|------|-------------|
| `run_id` | `str` | Run identifier (UUID) |
| `experiment_id` | `str` or `int` | MLflow experiment ID |
| `status` | `str` | Terminal status: `"completed"` or `"failed"` |
| `model_artifact_path` | `str` | Safetensors path (if exported) |

**Factory**: `make_trained_run(client) → dict`
- Creates a corpus + dataset → starts training → polls to completion
- Uses tiny model config (`n_embd=16, n_layer=1, n_head=4, num_steps=5`)
- Returns run metadata

### Registered Model (factory-produced)
| Field | Type | Description |
|-------|------|-------------|
| `model_id` | `str` | Model registry identifier |
| `version` | `int` | Model version number |

**Factory**: `make_registered_model(client) → dict`
- Runs `make_trained_run` → registers via `POST /registry/models`
- Returns model registration metadata

### Evaluation Dataset
| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Eval dataset name |
| `records` | `list[dict]` | Records with text/prompt fields |

**Factory**: `make_eval_dataset(client) → dict`
- Creates via `POST /eval-datasets` + `POST /eval-datasets/{name}/records`
- Returns eval dataset metadata

## 2. Shared Helpers

### `poll_until_terminal(client, run_id, timeout_s=60)`
- Polls `GET /training/{run_id}/status` every 1 second
- Terminal condition: status is `"completed"` or `"failed"`
- Raises `TimeoutError` if not terminal within `timeout_s`

### `read_sse_events(client, url, max_events=5, timeout_s=30)`
- Uses `client.stream("GET", url)` with `httpx.AsyncClient`
- Parses `event:` and `data:` SSE lines
- Returns list of decoded `(event_name, payload_dict)` tuples
- Raises `TimeoutError` if `max_events` not received within `timeout_s`

## 3. Seed Data Values

### Tiny Corpus Payload
Deterministic ~100-byte `.txt` string for upload tests:
```
Hello world. This is a tiny test corpus for anvil.
It has two sentences and some words.
```

### Training Config (tiny model)
```python
TINY_TRAINING_CONFIG = {
    "n_layer": 1,
    "n_embd": 16,
    "n_head": 4,
    "block_size": 16,
    "num_steps": 5,
    "learning_rate": 0.01,
    "beta1": 0.85,
    "beta2": 0.99,
    "temperature": 0.5,
    "compute_backend": "local-stdlib",
}
```

## 4. Validation Rules (from spec FRs)

| FR | Rule | Assertion |
|----|------|-----------|
| FR-001 | All 14 routers covered | Each router has ≥1 test function |
| FR-002 | Happy + error paths per module | At least 2 tests per module (success + error) |
| FR-006 | In-process transport | Uses `ASGITransport`, not live server |
| FR-007 | Tiny model config | Training tests use `TINY_TRAINING_CONFIG` |
| FR-008 | No exact non-deterministic assertions | Loss/perplexity: assert finite/numeric; Text: assert non-empty |
| FR-009 | Deterministic results | 3 consecutive runs → identical pass/fail |
| FR-013 | Clear failure messages | Assertion messages include endpoint path + expected contract |

## 5. Lifecycle State Machine (Integration Test)

```
create_corpus → ingest_corpus → build_dataset → start_training →
poll_complete → verify_experiment → register_model →
download_artifact → load_model → sample_inference → assert_output
```

Each step depends on previous step's output (run_id, dataset_id, model_id, etc.).