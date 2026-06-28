# Data Model: 040 External Model Registry

## Storage Note

Enum-typed columns are stored as `String(20)` columns with the enum member as the default value
(matching the existing `Dataset`/`Corpus` pattern), NOT as native SQL enum types. At service
boundaries, raw strings are coerced via `MyEnum(value)` per Principle 11.

## Entities

### ExternalModel

The canonical metadata record for an externally-sourced model. Stored in a new `external_models` table.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `int` (PK, auto-increment) | Unique identifier |
| `display_name` | `str` (String(255)) | Human-readable name for the registry entry |
| `source_type` | `SourceType` enum → `String(20)` | Origin source: `huggingface`, `local` |
| `source_identifier` | `str` (String(255)) | Source-specific identifier (HF repo ID `org/name`, local path) |
| `architecture_family` | `str` (String(100)) | Model architecture (e.g., `LlamaForCausalLM`) |
| `parameter_count` | `int` | Total parameters (from model card, or `0` if unknown) |
| `license` | `str` (String(100)) | License identifier (e.g., `apache-2.0`, `mit`, `"unknown"`) |
| `tokenizer_family` | `str` (String(100)) | Tokenizer type (e.g., `sentencepiece`, `tokenizers`, `"unknown"`) |
| `revision_sha` | `str` (String(255)) | Source revision/commit SHA |
| `runnable_status` | `RunnableStatus` enum → `String(20)` | `runnable` or `track_only` with reason |
| `runnable_reason` | `str \| None` (Text, nullable) | Why not runnable (null if runnable) |
| `asset_availability` | `AssetState` enum → `String(20)` | `metadata_only`, `assets_available`, `assets_pending` |
| `config_json` | `str \| None` (Text, nullable) | Raw model configuration (JSON) as returned by source |
| `created_at` | `datetime` | TimestampMixin |
| `updated_at` | `datetime` | TimestampMixin |

**Identity**: `(source_type, source_identifier, revision_sha)` is the canonical identity triple.
Same triple → idempotent (return existing entry).

### ModelImportJob

Tracks the async import lifecycle. Stored in a new `model_import_jobs` table.

> **Naming**: This is a NEW, distinct entity. It is NOT the existing
> `anvil/db/models/content_import_job.py::ImportJob` (which tracks content-repository imports).
> The name `ModelImportJob` avoids a class-name collision.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `int` (PK, auto-increment) | Unique identifier |
| `status` | `ModelImportJobStatus` enum → `String(20)` | `queued`, `resolving`, `complete`, `failed` |
| `source_type` | `str` (String(20)) | Source type passed at creation |
| `source_identifier` | `str` (String(255)) | Source identifier passed at creation |
| `error_code` | `str \| None` (String(50), nullable) | Typed error code if failed |
| `error_message` | `str \| None` (Text, nullable) | Human-readable error detail |
| `external_model_id` | `int \| None` (FK → `external_models.id`, `ondelete="SET NULL"`) | Set on completion |
| `started_at` | `datetime \| None` (nullable) | When job began resolving |
| `finished_at` | `datetime \| None` (nullable) | When job completed or failed |
| `created_at` | `datetime` | TimestampMixin |
| `updated_at` | `datetime` | TimestampMixin |

## Enums

### SourceType (StrEnum)

| Member | Value | Description |
|--------|-------|-------------|
| `HUGGINGFACE` | `huggingface` | HuggingFace Hub repository |
| `LOCAL` | `local` | Local file or directory path |

### RunnableStatus (StrEnum)

| Member | Value | Description |
|--------|-------|-------------|
| `RUNNABLE` | `runnable` | Model is eligible for fine-tune/inference |
| `TRACK_ONLY` | `track_only` | Model is metadata only, cannot run |

### AssetState (StrEnum)

| Member | Value | Description |
|--------|-------|-------------|
| `METADATA_ONLY` | `metadata_only` | No assets downloaded (initial state) |
| `ASSETS_AVAILABLE` | `assets_available` | Weights/tokenizer/config downloaded (set by spec 042) |
| `ASSETS_PENDING` | `assets_pending` | Asset download in progress |

### ModelImportJobStatus (StrEnum)

| Member | Value | Description |
|--------|-------|-------------|
| `QUEUED` | `queued` | Job created, not yet started |
| `RESOLVING` | `resolving` | Metadata resolution in progress |
| `COMPLETE` | `complete` | Metadata resolved, ExternalModel created |
| `FAILED` | `failed` | Resolution failed with typed error code |

## State Transitions

### ModelImportJob lifecycle

```
queued → resolving → complete
                  ↘ failed
```

### ExternalModel lifecycle (across specs 040 + 042)

```
metadata_only ──(spec 042 download)──→ assets_available
                                      ↕ assets_pending (during download)
```

## ModelSource Protocol

Structural typing (PEP 544), not ABC:

```python
class ModelSource(Protocol):
    """Interface for resolving external model metadata."""

    name: str

    async def resolve_metadata(
        self, identifier: str, *, token: str | None = None
    ) -> ModelMetadata:
        """Resolve metadata from the source.

        Parameters
        ----------
        identifier : str
            Source-specific model identifier (HF repo ID, local path).
        token : str | None
            Optional authentication token (HF_TOKEN for HF Hub).

        Returns
        -------
        ModelMetadata
            Resolved metadata fields.

        Raises
        ------
        ModelSourceError
            With typed error code on failure.
        """
        ...
```

### ModelMetadata (Pydantic BaseModel)

| Field | Type | Description |
|-------|------|-------------|
| `display_name` | `str` | Human-readable name |
| `architecture_family` | `str` | e.g., `LlamaForCausalLM` |
| `parameter_count` | `int` | Total parameters |
| `license` | `str` | License identifier |
| `tokenizer_family` | `str` | Tokenizer type |
| `revision_sha` | `str` | Source revision SHA |
| `config_json` | `str \| None` | Raw config JSON |
| `raw_error` | `str \| None` | Source error message if partial |

### ModelSourceError

```python
class ModelSourceError(Exception):
    """Raised when metadata resolution fails.

    Attributes
    ----------
    code : str
        Typed error code: network_error, auth_required, rate_limited,
        not_found, invalid_identifier, parse_failure.
    message : str
        Human-readable error description.
    source : str
        The source type that raised the error.
    """
```

## Relationships

```
ExternalModel 1──0..1 ModelImportJob    (job that created this entry)
ModelImportJob 1──0..1 ExternalModel    (entry created by this job, via external_model_id FK)
```

The relationship is optional both ways: a job may fail without creating an entry,
and existing entries (from idempotent re-import) may have no new associated job. The FK
`model_import_jobs.external_model_id → external_models.id` uses `ondelete="SET NULL"`.