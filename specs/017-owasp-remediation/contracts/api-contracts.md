# API Contracts — Standardized Response Format & Typed Bodies

**Phase**: 1 (Design & Contracts) | **Date**: 2026-06-21 | **Plan**: `plan.md`

## 1. Standardized Error Response Format

All API error responses MUST follow this structure:

```json
{
    "detail": "User-facing error message (no internal paths, variable names, or stack traces)",
    "code": "VALIDATION_ERROR",
    "fields": {}
}
```

### Common Error Codes

| HTTP Status | `code` | When |
|-------------|--------|------|
| 400 | `BAD_REQUEST` | Malformed request (e.g., invalid JSON, query string) |
| 401 | `UNAUTHORIZED` | Missing or invalid API key |
| 403 | `FORBIDDEN` | Valid API key but insufficient permissions (future SaaS) |
| 404 | `NOT_FOUND` | Resource not found |
| 409 | `CONFLICT` | Resource already exists or lock conflict |
| 422 | `VALIDATION_ERROR` | Request body failed Pydantic validation |
| 429 | `RATE_LIMITED` | Too many requests |
| 500 | `INTERNAL_ERROR` | Unexpected server error (generic message only) |

### Implementation

Replace all `str(exc)` patterns with a helper:

```python
def sanitized_error(exc: Exception, status_code: int = 422) -> HTTPException:
    """Return an HTTPException with a sanitized detail message.
    
    The original exception is logged server-side for debugging.
    """
    logger.warning("Request error", exc_info=exc)
    generic_messages = {
        400: "Bad request",
        401: "Authentication required",
        403: "Access denied",
        404: "Resource not found",
        409: "Resource conflict",
        422: "Invalid request data",
        429: "Too many requests",
        500: "Internal server error",
    }
    return HTTPException(
        status_code=status_code,
        detail=generic_messages.get(status_code, "An error occurred"),
    )
```

---

## 2. Typed Request Body Contracts

### Existing Routes Requiring `body: dict` → Pydantic Migration

#### training.py — `POST /training/start`
```python
class TrainConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")  # Reject unknown fields
    
    n_embd: int = Field(default=16, ge=4, le=4096)
    n_layer: int = Field(default=1, ge=1, le=128)
    n_head: int = Field(default=4, ge=1, le=64)
    num_steps: int = Field(default=1000, ge=1, le=1_000_000)
    learning_rate: float = Field(default=0.01, gt=0, le=1.0)
    temperature: float = Field(default=0.5, ge=0, le=2.0)
    dataset_id: int | None = Field(default=None, ge=1)
    corpus_id: int | None = Field(default=None, ge=1)
    device: str | None = Field(default=None, min_length=1, max_length=50)
```

#### corpora.py — `POST /corpora`
```python
class CreateCorpusBody(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    root_path: str = Field(min_length=1, max_length=4096)
    description: str | None = Field(default=None, max_length=5000)
    language: str | None = Field(default=None, max_length=50)
```

#### inference.py — all POST routes
```python
class InferenceTokenizeBody(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)
    model_id: str | None = Field(default=None, max_length=255)

class InferenceEmbeddingsBody(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)
    model_id: str | None = Field(default=None, max_length=255)
```

(Similar typed models for all 8 inference endpoints)

#### registry.py — `POST /registry/models`
```python
class RegisterModelBody(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    tags: dict[str, str] = Field(default_factory=dict)
```

#### eval.py, eval_datasets.py — typed models
```python
class EvalPerplexityBody(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)
    model_id: str | None = Field(default=None, max_length=255)
```

---

## 3. Existing Schema Constraints Enhancement

Add `Field()` constraints to existing models in `schemas.py`:

| Model | Fields Needing Constraints |
|-------|---------------------------|
| `CreateDatasetBody` | `name: str = Field(min_length=1, max_length=255)` |
| `UpdateDatasetBody` | `name: str | None = Field(default=None, max_length=255)` |
| `ImportBody` | `format: str = Field(min_length=1, max_length=50)` |
| `FilterBody` | `query: str = Field(max_length=5000)` |
| `ReplaceBody` | `pattern: str = Field(max_length=1000)` (ReDoS note) |
| `UpdateSampleBody` | `text: str = Field(max_length=1_000_000)` |
| `CloneDatasetBody` | `name: str = Field(min_length=1, max_length=255)` |
| `CreateFromCorpusBody` | `name: str = Field(min_length=1, max_length=255)` |
| `TakedownBody` | `reason: str = Field(min_length=1, max_length=5000)` |
| `SessionOpenBody` | `corpus_id: int = Field(ge=1)` |
| `FreezeVersionBody` | `version_name: str | None = Field(default=None, max_length=255)` |
| `LockBody` | `scope: str = Field(min_length=1, max_length=255)`, `holder: str = Field(min_length=1, max_length=255)` |
| `ImportStart` | `source_uri: str = Field(max_length=4096)` |