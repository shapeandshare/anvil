# Contract: HTTP API endpoints

**Feature**: `016-lakefs-content-repo` | **Phase 1**

New router `anvil/api/v1/content.py` (`router = APIRouter()`), included in
`anvil/api/v1/router.py`, mounted under `/v1`. All handlers async, use
`workbench: AnvilWorkbench = Depends(get_workbench)`, and return the
`{"data": ..., "error": ...}` envelope. Errors via `HTTPException` with `detail: str`.
SSE endpoints use `StreamingResponse(media_type="text/event-stream")` + `asyncio.Queue`
(mirroring `training.py`), consumed by the `SSESession` client.

## Corpora

| Method | Path | Purpose | FR |
|---|---|---|---|
| POST | `/v1/content/corpora` | Create a corpus (name, chunk cfg, provenance gate) | FR-018 ctx, governance |
| GET | `/v1/content/corpora` | List corpora (status, latest version, size, source mix) | FR-027 |
| GET | `/v1/content/corpora/{id}` | Corpus detail | FR-027 |
| DELETE | `/v1/content/corpora/{id}` | Delete corpus (guarded; never removes run-referenced versions) | FR-024 |
| GET | `/v1/content/corpora/{id}/versions` | Version timeline (ref, count, tag, diff-vs-prior) | FR-028 |
| POST | `/v1/content/corpora/{id}/revert` | Revert canonical to a prior version | FR-011 |

## Sources

| Method | Path | Purpose |
|---|---|---|
| POST | `/v1/content/sources` | Register a source (slug, name, kind) |
| GET | `/v1/content/sources` | List sources |

## Ingestion (isolated sessions + gates)

| Method | Path | Purpose | FR |
|---|---|---|---|
| POST | `/v1/content/sessions` | Open isolated ingest session (corpus, source) | FR-006 |
| POST | `/v1/content/sessions/{id}/stage` | Stage entry(ies) into session (multipart) | FR-006 |
| POST | `/v1/content/sessions/{id}/validate` | Run per-batch gates (~5s) | FR-012 |
| POST | `/v1/content/sessions/{id}/accept` | Pre-acceptance gates (~30s) + serialized atomic fold → new version | FR-009/010/013/014/016 |
| POST | `/v1/content/sessions/{id}/abandon` | Discard session | FR-025 |
| GET | `/v1/content/sessions` | List active sessions (Injection Monitor) | FR-029 |
| GET | `/v1/content/stream/injection` | **SSE** `injection-status` stream | FR-029 |

## Versions, composition, tags, lineage

| Method | Path | Purpose | FR |
|---|---|---|---|
| POST | `/v1/content/corpora/{id}/freeze` | Freeze version (optional composition + weights) | FR-001/020 |
| POST | `/v1/content/corpora/{id}/composition/preview` | Preview mix (token/byte contribution) | FR-019 |
| GET | `/v1/content/stream/composition` | **SSE** `composition-preview` stream | FR-019 |
| GET | `/v1/content/versions/{id}` | Version detail (manifest digest, entries) | FR-028 |
| POST | `/v1/content/versions/{id}/tag` | Promote with a tag | FR-023 |
| GET | `/v1/content/versions/{id}/lineage` | Sources + referencing runs | FR-026/031 |

## Import

| Method | Path | Purpose | FR |
|---|---|---|---|
| POST | `/v1/content/imports` | Start import job (routes through an ingest session) | FR-032/033 |
| GET | `/v1/content/imports/{id}` | Import job status | FR-030 |
| GET | `/v1/content/stream/import` | **SSE** `import-progress` stream | FR-030 |

## Checkout locks

| Method | Path | Purpose | FR |
|---|---|---|---|
| POST | `/v1/content/locks` | Acquire advisory lock (scope, holder) | FR-034 |
| DELETE | `/v1/content/locks/{id}` | Release lock | FR-034 |
| GET | `/v1/content/locks` | Checkout board (active locks) | FR-035 |
| GET | `/v1/content/stream/locks` | **SSE** `lock-events` stream | FR-035 |

## Pages (forge screens) — `anvil/api/v1/pages.py`

A single **content hub** page hosts the views (forge archetype, `base.html`,
design-system conformant per Article VIII / DESIGN.md). Client interactions live in
`anvil/api/static/js/content.js`; live views use the `SSESession` client.

| Path / view | Template / mount | Screen | FR |
|---|---|---|---|
| `/v1/content-page` | `archetypes/content_library.html` (hub shell) + nav tab | Corpus Library | FR-027 |
| Version Timeline view | hub mount | timeline + diff vs prior | FR-028 |
| Lineage view | hub mount | sources + referencing runs | FR-031 |
| Injection Monitor view | hub mount | live sessions (injection SSE) | FR-029 |
| Ensemble Composer view | hub mount | weights + live mix preview (composition SSE) | FR-018/019/020/022 |
| Import Console view | hub mount | import jobs (import SSE) | FR-030/032 |
| Checkout Board view | hub mount | active locks (lock SSE) | FR-035 |
| Back-office | SQLAdmin `/admin` (SaaS-deferred) | RBAC/raw records | FR-037 |

## Back-office (optional, lower priority)

| Path | Purpose | FR |
|---|---|---|
| `/admin` | SQLAdmin (async) for RBAC/raw-record inspection; `add_view`s at app construction; auth-guarded | FR-037 |

## MLflow wiring (on training run start)

When a run pins a corpus version: record a `VersionRunRef` (version_id, mlflow_run_id,
corpus_ref=manifest_digest); `mlflow.log_param("corpus_ref", digest)`;
`client.log_input(MetaDataset(source="anvil-content://<slug>/<digest>", digest=digest))`;
attach `corpus_manifest.json`. (FR-002, lineage FR-026/031.)

## Error conventions

`404` not found; `409` conflict (e.g., accept race / deleting run-referenced corpus);
`422` validation/gate failure (body includes structured `problems`); `5xx` only on
unexpected/fail-closed internal errors. Gate failures on `accept` return the
`ValidationReport` with per-item reasons.
