# Data Model: Model Asset Storage (042)

**Date**: 2026-06-28 | **Branch**: `042-model-asset-storage`

## New Entities

### 1. AssetDownloadJobStatus — StrEnum

**Location**: `anvil/services/_shared/asset_download_job_status.py`

Follows the `ModelImportJobStatus` pattern exactly.

```python
class AssetDownloadJobStatus(StrEnum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETE = "complete"
    FAILED = "failed"
```

### 2. AssetDownloadJob — ORM Model

**Location**: `anvil/db/models/asset_download_job.py`
**Table**: `asset_download_jobs`

Follows the `ModelImportJob` pattern exactly.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | `int` PK auto | | Primary key |
| `external_model_id` | `int` FK → `external_models.id` | NOT NULL, ondelete=CASCADE | The model whose assets are being downloaded |
| `status` | `str` (20) | NOT NULL, default=QUEUED | `AssetDownloadJobStatus` value |
| `error_code` | `str` (50) | NULLABLE | Typed error code on failure |
| `error_message` | `Text` | NULLABLE | Human-readable error detail |
| `started_at` | `datetime` | NULLABLE | When download began |
| `finished_at` | `datetime` | NULLABLE | When download completed or failed |
| `created_at` | `datetime` | TimestampMixin | Row creation time |
| `updated_at` | `datetime` | TimestampMixin | Row last-update time |

### 3. ModelAsset — ORM Model

**Location**: `anvil/db/models/model_asset.py`
**Table**: `model_assets`

One row per asset file (one safetensors shard, config JSON, tokenizer file) belonging to a model.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | `int` PK auto | | Primary key |
| `external_model_id` | `int` FK → `external_models.id` | NOT NULL, ondelete=CASCADE | Parent model |
| `asset_type` | `str` (20) | NOT NULL | `ModelAssetType` enum value |
| `filename` | `str` (255) | NOT NULL | Original filename (e.g. `model.safetensors`, `config.json`) |
| `storage_path` | `str` (512) | NULLABLE | Relative path within store; set when AVAILABLE |
| `sha256` | `str` (64) | NULLABLE | SHA-256 content hash; set when AVAILABLE |
| `size_bytes` | `int` | NOT NULL, default=0 | Total file size in bytes |
| `downloaded_bytes` | `int` | NOT NULL, default=0 | Bytes downloaded so far (for resume + progress) |
| `format` | `str` (50) | NULLABLE | Format identifier (e.g. `"safetensors"`, `"json"`, `"tokenizer"`) |
| `status` | `str` (20) | NOT NULL, default=PENDING | `ModelAssetStatus` enum value |
| `source_url` | `str` (1024) | NULLABLE | HF Hub download URL for resume |
| `created_at` | `datetime` | TimestampMixin | Row creation time |
| `updated_at` | `datetime` | TimestampMixin | Row last-update time |

### 3a. ModelAssetType — StrEnum

**Location**: Collocated in `anvil/db/models/model_asset.py`

```python
class ModelAssetType(StrEnum):
    WEIGHTS = "weights"
    TOKENIZER = "tokenizer"
    CONFIG = "config"
```

### 3b. ModelAssetStatus — StrEnum

```python
class ModelAssetStatus(StrEnum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    CHECKSUM_MISMATCH = "checksum_mismatch"
```

### 4. UserSecret — ORM Model

**Location**: `anvil/db/models/user_secret.py`
**Table**: `user_secrets`

Encrypted per-user secrets (e.g. HuggingFace token). Modeled after `RuntimeConfig` pattern.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | `int` PK auto | | Primary key |
| `user_id` | `str` (255) | NOT NULL | User identifier (session-based in local mode; Cognito sub in SaaS) |
| `key` | `str` (100) | NOT NULL | Secret key name (e.g. `"hf_token"`). Unique per user. |
| `encrypted_value` | `Text` | NOT NULL | AES-256-GCM encrypted, base64-encoded value |
| `created_at` | `datetime` | TimestampMixin | Row creation time |
| `updated_at` | `datetime` | TimestampMixin | Row last-update time |

**Unique constraint**: (`user_id`, `key`)

---

## Entity Relationships

```
ExternalModel (1) ────── (N) ModelAsset
    │                         │ asset_type (WEIGHTS, TOKENIZER, CONFIG)
    │                         │ status lifecycle (PENDING → DOWNLOADING → AVAILABLE)
    │
    └── (1) ────── (N) AssetDownloadJob
                              │ status lifecycle (QUEUED → DOWNLOADING → COMPLETE/FAILED)

UserSecret (N)
    │ user_id + key unique
```

**Notes**:
- `ExternalModel.asset_availability` already exists — update to `ASSETS_AVAILABLE` when all `ModelAsset` rows reach `AVAILABLE`
- `AssetDownloadJob.external_model_id` is the job scope: one job = download all assets for one model
- `ModelAsset` rows are pre-created by the job: resolved file list → one `ModelAsset` per file → download per-asset

---

## State Machines

### ModelAsset Status Lifecycle

```
PENDING ──→ DOWNLOADING ──→ AVAILABLE
                │                 │
                ├──→ CHECKSUM_MISMATCH
                └──→ UNAVAILABLE
```

Transitions:
| From | To | Trigger |
|------|-----|---------|
| PENDING | DOWNLOADING | Job begins downloading this file |
| DOWNLOADING | AVAILABLE | Download completes + SHA-256 matches |
| DOWNLOADING | CHECKSUM_MISMATCH | Download completes but SHA-256 mismatch |
| DOWNLOADING | UNAVAILABLE | Network error, disk full, auth failure |

### AssetDownloadJob Status Lifecycle

```
QUEUED ──→ DOWNLOADING ──→ COMPLETE
                │
                └──→ FAILED
```

Transitions:
| From | To | Trigger |
|------|-----|---------|
| QUEUED | DOWNLOADING | `asyncio.create_task(_worker())` starts the job |
| DOWNLOADING | COMPLETE | All ModelAsset rows reach AVAILABLE |
| DOWNLOADING | FAILED | Fatal error (auth, unsupported format); individual asset failures don't fail the job |

### ExternalModel.asset_availability Lifecycle (existing AssetState enum, FR-012b)

```
METADATA_ONLY ──→ ASSETS_PENDING ──→ ASSETS_AVAILABLE
       ↑                  │
       └──────────────────┘  (job fails / no usable asset set)
```

Transitions:
| From | To | Trigger |
|------|-----|---------|
| METADATA_ONLY | ASSETS_PENDING | Download job starts (FR-012b) |
| ASSETS_PENDING | ASSETS_AVAILABLE | ALL ModelAsset rows reach AVAILABLE |
| ASSETS_PENDING | METADATA_ONLY | Job fails leaving no usable asset set (SC-006) |

**Note**: This is the existing `AssetState` enum on `ExternalModel` (spec 040) — no new column. The job drives both this model-level field and the per-file `ModelAsset.status`.

---

## Validation Rules (from spec FRs)

| Rule | Source | Description |
|------|--------|-------------|
| `format != "safetensors"` for weight assets → reject (v1) | FR-030 | Only safetensors weights accepted |
| File extension ≠ actual format → reject as mismatch | FR-033 | Must inspect structure, not extension |
| `trust_remote_code` must be disabled | FR-033a | Only allow-listed architectures (FR-032) |
| Duplicate download for same model → reject | FR-010c | Model-level lock prevents concurrent same-model download |
| Gated model + no HF token → fail actionable | FR-010d | Resolution: UserSecret > env var > fail |
| `track-only` model → refuse download | FR-033a / FR-009a | Track-only models (remote code / non-allow-listed arch) never fetched |
| Sharded weights → all shards + index required | edge case | Model AVAILABLE only when every shard + `*.index.json` is AVAILABLE |
| Failed job → revert model to METADATA_ONLY | FR-012b / SC-006 | No partial managed artifact; re-downloadable |

## New Repository Methods

### ModelAssetRepository

| Method | Description |
|--------|-------------|
| `get_by_model(model_id) → list[ModelAsset]` | Get all assets for a model |
| `get_by_model_and_type(model_id, asset_type) → list[ModelAsset]` | Filter by asset type |
| `add(asset: ModelAsset) → ModelAsset` | Create new asset row |
| `update_status(id, status, *, sha256=None, storage_path=None) → None` | Transition lifecycle |
| `update_progress(id, downloaded_bytes) → None` | Byte-level progress update |

### AssetDownloadJobRepository

| Method | Description |
|--------|-------------|
| `get(id) → AssetDownloadJob` | Get job by ID |
| `add(job) → AssetDownloadJob` | Create job |
| `update_status(id, status, *, error_code=None, error_message=None) → None` | Update |

### UserSecretRepository

| Method | Description |
|--------|-------------|
| `get(user_id, key) → UserSecret | None` | Get a specific secret |
| `get_all_for_user(user_id) → list[UserSecret]` | Get all secrets for user |
| `upsert(user_id, key, encrypted_value) → UserSecret` | Create or update |
| `delete(user_id, key) → None` | Remove a secret |
