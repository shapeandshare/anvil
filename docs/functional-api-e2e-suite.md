# Whole-API E2E Test Suite Implementation Plan

## Overview

Today `tests/e2e/test_endpoints.py` is **3 trivial smoke tests** (health, list-datasets,
list-experiments) against a ~140-endpoint API. This plan builds **comprehensive e2e coverage of
the entire `/v1` API** — every router, driven server-side through the existing async httpx
`client` fixture (ASGI transport, in-process, no browser, no network).

This is the **API-layer** half of the testing effort. The **browser-layer** half (UI wiring,
live SSE chart, etc.) is owned by the separate `playwright-ui-smoke-harness.md` plan. The split
is clean: this plan proves *the API functions correctly*; the browser plan proves *the UI is
wired to it*.

**No new dependencies.** Uses existing `pytest`, `pytest-asyncio`, `httpx`. Runs inside the
normal `make test` loop (the CI `test` job).

---

## Ground Truth (verified against the codebase)

- The v1 router mounts under **`/v1`** (e.g. `/v1/health`). All paths below are relative to `/v1`.
- `tests/conftest.py` exposes an async `client` fixture (`httpx.AsyncClient` +
  `ASGITransport(app=app)`) that **creates+drops all tables per test**, plus an async `session`
  fixture. Tests are `async def`; `asyncio_mode = "auto"` (no explicit marker needed).
- pytest config: `testpaths = ["tests"]`,
  `addopts = "-v --cov=anvil --cov-report=term-missing --ignore=tests/system"`.
  Coverage gate is `fail_under = 23` (NOT 100 — AGENTS.md is aspirational).
- Some responses wrap payloads in a `{"data": ...}` envelope (see `test_endpoints.py:22`).
  **Confirm the exact envelope + field names per endpoint from source — never assume.**
- Fast training: `local-stdlib` backend, tiny model (`n_embd=16, n_layer=1, n_head=4`),
  small `num_steps` (≈20). MLflow runs in-process via the app lifespan.
- `tests/**` is exempt from docstring/lint strictness via existing ruff per-file ignores.

### Full router inventory (14 routers — every one MUST be covered)

Verified endpoint list (path prefixes relative to `/v1`). The agent MUST read each handler +
`anvil/api/v1/schemas.py` for exact request/response schemas before writing assertions.

| Router file | Endpoints (verified) |
|---|---|
| `health_ops.py` | `POST /demo/bootstrap`, `GET /health`, `GET /services`, `GET /services/logs/{name}`, `POST /services/restart-all`, `POST /services/logs/{name}/clear`, `POST /services/{name}/start|stop|restart`, `POST /services/{name}/kill-port` |
| `datasets.py` | `GET /datasets`, `GET /datasets/{id}`, `POST /datasets`, `PUT /datasets/{id}`, `POST /datasets/upload`, `DELETE /datasets/{id}`, `POST /datasets/{id}/clone`, `POST /datasets/{id}/import`, `POST /datasets/{id}/import-corpus`, `POST /datasets/from-corpus`, `GET /datasets/{id}/preview-import`, `GET /datasets/{id}/samples`, `PUT|DELETE /datasets/{id}/samples/{sid}`, `POST /datasets/{id}/curate/dedup|filter|replace`, `GET /datasets/{id}/metrics`, `GET /datasets/{id}/export`, `GET /datasets/{id}/operations`, `GET /datasets/{id}/curate` (HTML) |
| `corpora.py` | `POST /corpora`, `POST /corpora/{id}/fork`, `GET /corpora`, `GET /corpora/{id}`, `DELETE /corpora/{id}`, `POST /corpora/{id}/ingest`, `GET /corpora/{id}/files`, `GET /corpora/{id}/files/{fid}`, `POST /corpora/resolve-path`, `POST /corpora/analyze-path` |
| `training.py` | `POST /training/start`, `GET /training/{run_id}/status`, `GET /training/stream/{run_id}` (SSE), `GET /training/configs`, `POST /training/{run_id}/stop`, `GET /forward-pass/graph` |
| `experiments.py` | `GET /experiments`, `GET /experiments/compare`, `GET /experiments/{id}`, `GET /experiments/{id}/mlflow`, `GET /experiments/{id}/metrics`, `DELETE /experiments/{id}`, `GET /experiments/{eid}/runs/{rid}/artifacts`, `GET /experiments/{eid}/runs/{rid}/download`, `POST /experiments/{eid}/retry-export` |
| `registry.py` | `POST /registry/models` (201), `GET /registry/models`, `GET /registry/models/{id}`, `GET /registry/models/{id}/versions/{v}`, `DELETE /registry/models/{id}/versions/{v}`, `DELETE /registry/models/{id}` |
| `inference.py` | `POST /inference/tokenize|embeddings|attention|sampling-distribution|backward-graph|autograd-example|loss-breakdown`, `GET /inference/forward-graph`, `GET /inference/model-params` |
| `learning.py` (data routes) | `GET /inference/models`, `POST /inference/sample`, plus HTML: `GET /learn`, `/learn/*` (14 lessons), `/models-page`, `/model-detail/{id}` |
| `eval.py` | `POST /eval/perplexity` |
| `eval_datasets.py` | `POST /eval-datasets`, `POST /eval-datasets/{name}/records`, `GET /eval-datasets/{name}` |
| `compute.py` | `GET /compute/backends` |
| `governance.py` | `GET /governance/audit`, `GET /governance/audit/verify`, `GET /governance/datasets/{id}/report`, `GET /governance/licenses`, `POST /datasets/{id}/takedown` |
| `content.py` | `POST|GET /content/corpora`, `GET|DELETE /content/corpora/{id}`, `GET /content/corpora/{id}/versions`, `POST|GET /content/sources`, `POST /content/sessions`, `POST /content/sessions/{id}/stage|validate|accept|abandon`, `GET /content/sessions`, `POST /content/corpora/{id}/freeze|revert`, `POST /content/corpora/{id}/composition/preview`, `POST /content/versions/{id}/tag`, `GET /content/versions/{id}`, `GET /content/versions/{id}/lineage`, `POST|GET /content/locks`, `POST /content/locks/{id}/release`, `POST|GET /content/imports`, `GET /content/imports/{id}`, SSE: `/content/stream/composition|injection|locks|import` |
| `pages.py` + `router.py` | HTML: `GET /` , `/acceptable-use`, `/training-page`, `/experiments-page`, `/datasets-page`, `/operations-page`, `/inference-page`, `/content-page`, `/about`, `/learn/graph` |

---

## Scope

### File layout — one module per router/domain + an integration backbone

```
tests/e2e/api/
├── conftest.py                  # shared seeding factories + helpers (see below)
├── test_health_ops.py          # health, services mgmt, demo bootstrap
├── test_datasets.py            # full dataset CRUD + upload + curate + import + export + samples
├── test_corpora.py             # corpus CRUD + ingest + fork + files + path resolve/analyze
├── test_training.py            # start/status/stream(SSE)/stop/configs + forward-pass graph
├── test_experiments.py         # list/compare/detail/metrics/mlflow/artifacts/download/delete/retry-export
├── test_registry.py           # register/list/detail/versions/delete-version/delete-model
├── test_inference.py          # tokenize/embeddings/attention/sampling/graphs/params + sample/models
├── test_eval.py               # perplexity + eval-datasets CRUD
├── test_compute.py            # compute backends listing
├── test_governance.py         # audit/verify/report/licenses + takedown
├── test_content.py            # content-repo: corpora/sources/sessions/versions/locks/imports/streams
├── test_pages.py              # every HTML page route renders 200 + key markup landmark
└── test_lifecycle_journey.py  # cross-router money-path integration test (the backbone)
```

> Keep the existing `tests/e2e/test_endpoints.py` (or fold its 3 cases into the new modules and
> delete it — agent's choice, but no loss of coverage).

### Shared seeding factories + helpers (`tests/e2e/api/conftest.py`)

Because the `client` fixture drops tables per test, each test self-seeds. Provide reusable
async factory fixtures to keep tests terse:

1. `tiny_corpus_bytes()` — small deterministic `.txt` payload for uploads.
2. `make_dataset(client) -> dict` — creates a ready dataset (via upload or `POST /datasets`),
   returns its serialized record (id, name).
3. `make_corpus(client, tmp_path) -> dict` — creates + ingests a tiny corpus.
4. `make_trained_run(client) -> dict` — full tiny training run to terminal success; returns
   run_id / experiment id / model artifact reference. (Used by experiments, registry, inference.)
5. `make_registered_model(client) -> dict` — trains + registers; returns model_id + version.
6. `async poll_until_terminal(client, run_id, timeout_s=60)` — polls `GET /training/{run_id}/status`
   to the real terminal enum value (read it from `training.py`/the training service; do NOT guess).
7. `async read_sse_events(client, url, max_events=5, timeout_s=30)` — `client.stream("GET", url)`,
   parse `data:` lines, return decoded events. Reused by training + content SSE tests.

---

## Per-Router Coverage Requirements

For **every** router, cover: the happy path, the primary error paths (404 unknown id, 422
validation, 409/conflict where applicable), and any state transition the router owns. Specifics:

### `test_health_ops.py`
- `GET /health` → 200 `{"status": "healthy"}`.
- `GET /services` → returns service list with expected shape.
- `GET /services/logs/{name}` for a known service → 200; unknown → error path.
- `POST /demo/bootstrap` → idempotent (second call is a no-op / guarded; verify the origin-guard
  behavior described in AGENTS.md "014-demo-data-bootstrap").
- Service start/stop/restart/restart-all/clear-logs/kill-port: assert they respond sanely.
  **MUST NOT** actually kill the test process's ports or destabilize the in-process app — verify
  what these do against a test app and assert only safe observable outcomes (status/JSON), or
  assert the guarded/no-op response. Read `health_ops.py` first.

### `test_datasets.py`
- Create (upload + `POST /datasets`), read (list/detail/samples/metrics/operations), update
  (`PUT`), clone, import (`/import`, `/import-corpus`, `/from-corpus`, `/preview-import`),
  curate (dedup/filter/replace), edit/delete samples, export, delete.
- Error paths: duplicate name (422), unknown id (404), empty-dataset operations.
- Verify samples live in `LocalFileStore` and content is preserved byte-for-byte where the route
  promises it (see `custom-dataset-features.md` for the clone/from-corpus contracts).

### `test_corpora.py`
- Create, ingest (with include/exclude patterns — note they're JSON strings in DB), list, detail,
  files listing + single file fetch, fork, delete, `resolve-path` / `analyze-path`.
- Error paths: unknown corpus (404), invalid path inputs.

### `test_training.py`
- `GET /training/configs` → presets returned.
- `POST /training/start` (tiny stdlib config) → capture run_id.
- `poll_until_terminal` → success state.
- `read_sse_events("/training/stream/{run_id}")` → ≥1 metric event with a finite numeric loss
  (if a finished run's stream yields nothing, run stream-read concurrently with the run via
  `asyncio.gather` — verify behavior in `training.py:645`).
- `POST /training/{run_id}/stop` on an active/long run → stops it (use a slightly larger
  num_steps just for this case if needed to win the race, but keep it bounded).
- `GET /forward-pass/graph` → valid graph structure.
- Error paths: start with unknown dataset (404/422), status/stream for unknown run (404).

### `test_experiments.py`
- After `make_trained_run`: list, detail, metrics (non-empty loss series), `compare` (2 runs),
  `mlflow` link/data, artifacts listing, `download` (200 + non-empty body = safetensors bundle),
  `retry-export`, delete.
- Error paths: unknown experiment (404).

### `test_registry.py`
- Register (201) + capture id/version, list, detail, version detail (params, byte size,
  safetensors ref), delete a version, delete the model.
- Error paths: register from unknown run (404/422), unknown model (404).

### `test_inference.py`
- With a registered/loaded model: `tokenize`, `embeddings`, `attention`,
  `sampling-distribution`, `forward-graph`, `backward-graph`, `autograd-example`,
  `loss-breakdown`, `model-params` → each returns the documented shape.
- `GET /inference/models` → registered model selectable.
- `POST /inference/sample` → **non-empty** generated text.
- Error paths: sample/tokenize with unknown model (404/422).

### `test_eval.py`
- `POST /eval-datasets` + `POST /eval-datasets/{name}/records` + `GET /eval-datasets/{name}` →
  create/append/read.
- `POST /eval/perplexity` against a trained model + eval dataset → finite numeric perplexity.

### `test_compute.py`
- `GET /compute/backends` → lists at least `local-stdlib`; shape matches schema.

### `test_governance.py`
- `GET /governance/licenses` → seeded OSI/CC catalog present.
- `GET /governance/audit` + `GET /governance/audit/verify` → hash-chain verifies OK on a fresh DB
  (and after an auditable action, the chain grows + still verifies).
- `GET /governance/datasets/{id}/report` → provenance report for a seeded dataset.
- `POST /datasets/{id}/takedown` → marks the dataset; verify side effects + a new audit event.
- Error paths: report/takedown for unknown id (404).

### `test_content.py` (content repository — spec 016)
- Full reproducibility lifecycle: `POST /content/corpora` → `POST /content/sources` →
  `POST /content/sessions` (open) → `/stage` → `/validate` → `/accept` (atomic fold) →
  `/freeze` (immutable version) → `GET /content/versions/{id}` + `/lineage` →
  resolve byte-identically. Also: `/tag`, `/revert`, composition `/preview`, locks
  (acquire/list/release), imports (create/get), and at least one SSE stream
  (`/content/stream/composition`) via `read_sse_events`.
- Error/edge paths the QA pass already flagged (see ADR-033 session notes): empty-version accept,
  revert unique-constraint, ambiguous ORM relationship, session abandon.

### `test_pages.py`
- Every HTML route (`/`, `/about`, `/acceptable-use`, `*-page`, `/learn` + all `/learn/*`
  lessons, `/learn/graph`, `/models-page`, `/model-detail/{id}`) → 200 + a known landmark string
  in the HTML (title/heading). This is render-smoke, not interaction (interaction = browser plan).

### `test_lifecycle_journey.py` (integration backbone)
- One end-to-end test chaining real routers: upload corpus → build dataset → start training
  (stdlib, tiny) → poll terminal → confirm experiment + metrics → register model → download
  artifact → load + sample inference → assert non-empty output. This is the single most important
  test; it proves the routers compose correctly, not just in isolation.

---

## Acceptance Criteria (Definition of Done)

- [ ] Every one of the 14 routers has a dedicated test module with happy-path + error-path coverage.
- [ ] The lifecycle backbone test passes end-to-end.
- [ ] `make test` passes locally and in the CI `test` job.
- [ ] Full suite passes deterministically across **3 consecutive runs** (no flakes).
- [ ] No equality assertions on non-deterministic values (loss/perplexity) — assert
      finite / numeric / sane-range instead.
- [ ] `lsp_diagnostics` clean on all new files; `make lint` + `make typecheck` pass.
- [ ] Suite runtime stays bounded (tiny model + small steps); target **< ~90s** total on CPU.
- [ ] Coverage gate (`fail_under = 23`) still passes; report the new measured coverage % to the user.

---

## MUST DO

1. Use the existing async `client` fixture — do NOT spin up a live uvicorn server.
2. Read each handler + `schemas.py` for **exact** body/response field names and the `{"data": ...}`
   envelope before asserting.
3. Use `local-stdlib` + tiny model + small `num_steps` everywhere training is involved.
4. Use real status/backend/enum values from source — never magic strings the plan guessed.
5. Self-seed each test via the shared factory fixtures (tables drop per test).
6. Cover error paths (404/422/409), not just happy paths.

## MUST NOT DO

1. Do NOT add any new runtime or dev dependency (no Playwright, no live server, no `requests`).
2. Do NOT use the GPU/torch backend or large `num_steps`.
3. Do NOT assert exact loss/perplexity values.
4. Do NOT put these tests in `tests/system/` (excluded from `make test`).
5. Do NOT modify application code to make tests pass — if a real bug surfaces, document it (vault)
   and flag it to the user; never `xfail` without a written reason.
6. Do NOT suppress type errors (`# type: ignore`, `cast`, `Any` abuse).
7. Do NOT let service-control endpoints (`kill-port`, `stop`, `restart-all`) destabilize the
   in-process test app — assert safe observable responses only.

---

## Vault Enrichment (required per AGENTS.md)

- Session log under `docs/vault/Sessions/`.
- Discovery notes under `docs/vault/Discoveries/` for any real integration bug found (surface to
  user; do not silently fix unrelated code).
- Controlled-vocabulary tags from `docs/vault/_meta/tags.md`; run `make vault-audit` → 0 errors.

## Sequencing / Parallelism

- **Independent of the browser plan** (`playwright-ui-smoke-harness.md`) — can run in parallel.
- Within this plan: build `conftest.py` factories first (they unblock every module). The 14
  router modules are then **mutually independent and can be split across parallel sub-agents**;
  the lifecycle backbone test goes last (depends on the factories being stable).

## Out of Scope

- Browser/UI interaction testing (owned by `playwright-ui-smoke-harness.md`).
- Performance/load testing, auth/SaaS-mode endpoints, MLflow server UI internals.
