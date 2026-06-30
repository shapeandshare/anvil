# Research: Model Asset Acquisition & Storage (042)

**Date**: 2026-06-28 | **Branch**: `042-model-asset-storage`

## 1. Async Job Infrastructure

### Decision
Reuse the **model-import job pattern**: DB-backed job status + HTTP 202 + polling. Do NOT introduce Celery, Redis queues, or SSE channels for asset downloads.

### Rationale
The codebase already has a proven async job pattern for model imports (`anvil/api/v1/models.py`):
- `POST` returns `202 Accepted` with `{"job_id": int, "status": "queued"}`
- `asyncio.create_task(_worker())` fires a background worker with its **own** `AsyncSessionLocal()` session
- `_worker()` calls the service `run_*()` method
- Client polls `GET /.../{job_id}/status`
- DB row tracks `status` via `StrEnum` (`QUEUED`, `DOWNLOADING`, `COMPLETE`, `FAILED`), `error_code`, `error_message`, `started_at`, `finished_at`
- Repository pattern: `get()`, `add()`, `update_status()`

Training jobs (in-memory) and content import jobs (similar DB pattern) confirm this is the established norm.

### Alternatives Considered
- **Celery/Redis**: Not used anywhere in the project; violates "boring technology" / no new deps
- **FastAPI BackgroundTasks**: No status tracking, no retry, no error reporting
- **SSE push**: Overengineered for asset download; polling is consistent with existing import pattern

---

## 2. FileStore Streaming API

### Decision
Use the existing `FileStore` interface (`anvil/storage/interface.py`) directly — no new methods needed. The `put()` and `get()` methods already support streaming via `AsyncIterator[bytes]`.

### Rationale
- `put(path, stream: AsyncIterator[bytes])` writes atomically (temp-then-rename) — perfect for asset files
- `get(path) → AsyncIterator[bytes]` reads in 64 KiB chunks — ideal for large weight files
- `WorkspacePaths.models_dir` already exists at `data/models` — use as storage prefix
- Dataset import (`dataset_import.py`) shows the streaming pattern: `_text_stream()` → `store.put()`

### Important Caveats
- `put()` returns nanosecond-mtime etag — **not** a cryptographic hash. Must compute SHA-256 separately during streaming for `ModelAsset.sha256`
- No factory/registry exists for storage backend selection — hardcoded `LocalFileStore` in `AnvilWorkbench`. Need to add a lightweight factory.

---

## 3. HuggingFace Hub Download Patterns

### Decision
Add `hf_hub_download()` calls to `hf_source.py` (currently only calls `HfApi.model_info()`). Wrap blocking I/O in `loop.run_in_executor()` — same pattern as existing metadata resolution.

### Key Details
- **No `snapshot_download` or `hf_hub_download` calls exist yet** — this is new code
- File discovery: `HfApi.list_repo_files(repo_id, revision)` → filter for `.safetensors`, `config.json`, `tokenizer.json`, `tokenizer_config.json`
- Download: `hf_hub_download(repo_id, filename, revision, token)` — supports HTTP Range internally for resume
- Resumability: track `downloaded_bytes` on `ModelAsset`; use HTTP `Range` header on retry
- Format detection: inspect file structure (not just extension) using `safetensors.safe_open()` for validation per FR-033

### Token Resolution (per FR-010d)
```
UserSecret (DB) > HF_TOKEN env var > fail with actionable message if gated
```
- `UserSecret` is a new ORM model (encrypted, per-user)
- Env var fallback already exists: `token or os.environ.get("HF_TOKEN")` in `hf_source.py`
- `huggingface_hub` is behind `[finetune]` extra — download must check availability

---

## 4. Encryption for UserSecret

### Decision
Use `cryptography` library's AES-256-GCM via `AESGCM`. Create `anvil/services/_shared/encryption.py` module.

### Rationale
- `cryptography` v48.0.1 is already present in `uv.lock` (transitive dep of `mlflow`)
- No new dependency introduced — the transitive dep is already deployed
- AES-256-GCM provides authenticated encryption (AEAD) — correct for secret storage
- Master key management follows `ApiKeyStore` pattern: `ANVIL_MASTER_SECRET` env var, auto-generate + persist with `0600` perms in dev

### Alternatives Considered
- **Stdlib only**: Python stdlib has no AES-GCM; would require complex low-level crypto
- **Fernet**: Simpler API but less explicit about algorithm; AES-GCM is the modern standard
- **Plaintext + file perms** (like `ApiKeyStore`): Not appropriate for per-user secrets in DB

---

## 5. Storage Seam (FileStore vs VersionedContentStore)

### Decision
For spec 042, use `FileStore` directly for asset blob storage. The `VersionedContentStore` (`anvil/services/content/`) is for versioned corpus/content — a different domain.

### Rationale
- `FileStore` (blob store) is the right abstraction for raw model weights, tokenizer files, config JSON
- `VersionedContentStore` is for content-addressed versioned corpora (datasets, not model assets)
- The spec says "local `FileStore` in local mode and `VersionedContentStore` in SaaS mode" — for SaaS, the `FileStore` implementation would be backed by LakeFS's S3-compatible API, not the versioned content layer
- No factory pattern exists yet — need to create one for SaaS-compatible `FileStore` selection

### Per FR-011
- Local: `workbench.store` (LocalFileStore at `data/models/`)
- SaaS: A future `LakeFSFileStore` implementing same `FileStore` ABC, wired via factory
- Path prefix: `orgs/{org_id}/models/{model_id}/assets/{sha256}/{filename}`

---

## Complexity Tracking

| Decision | Why Not Simpler | Rationale |
|----------|----------------|-----------|
| AES-256-GCM over plaintext | `ApiKeyStore` uses plaintext + file perms | Per-user secrets in DB need encryption; plaintext in DB is a security risk for multi-tenant SaaS |
| Separate `ModelAsset` + `UserSecret` models | Could embed in `ExternalModel` JSON blob | Relational integrity, queryability, separate lifecycle (follows existing ORM patterns) |
| Async job per model-import pattern | Could use sync download | GB-scale downloads would timeout proxies, block the API worker |
