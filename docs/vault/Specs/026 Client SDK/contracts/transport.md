# Contract: `Transport`, `Response[T]`, Envelope & Error Mapping

**Feature**: 026-client-sdk | The sole HTTP-primitive holder (Article VII analogue).

---

## `Transport` — `anvil/client/_shared/transport.py`

```python
class Transport:
    """Owns the single httpx.AsyncClient; performs all HTTP I/O for the SDK.

    No layer above Transport touches httpx primitives. Handles envelope
    unwrap, status→exception mapping, auth header/cookie injection, CSRF,
    and retry/backoff.
    """

    def __init__(self, config: ServerConfig, api_key: str | None = None) -> None: ...

    async def request(
        self,
        method: HttpMethod,
        path: str,
        *,
        response_model: type[T],
        json: dict[str, object] | None = None,
        params: dict[str, object] | None = None,
        files: dict[str, object] | None = None,
        idempotency_key: str | None = None,
    ) -> T:
        """Execute a request and return validated ``.data`` of type ``T``.

        Raises a typed ApiError subclass on non-2xx or non-null envelope error.
        """

    async def stream_sse(
        self, path: str, *, params: dict[str, object] | None = None
    ) -> AsyncIterator[StreamEvent]:
        """Open an SSE stream; yield typed StreamEvent objects until close."""

    async def download(
        self, path: str, *, dest: Path | None = None, params: dict[str, object] | None = None
    ) -> bytes | Path:
        """Stream a binary/file response; to ``dest`` if given, else return bytes."""

    async def aclose(self) -> None: ...
```

### Request contract
1. **URL**: `f"{config.base_url.rstrip('/')}{path}"` (path starts with `/v1/...` or `/login`).
2. **Auth header**: if `api_key` set → add `X-API-Key`.
3. **CSRF**: if authed via session cookie AND method ∈ {POST, PUT, DELETE, PATCH} → add
   `X-CSRF-Token`. (API-key auth is CSRF-exempt.)
4. **Idempotency**: if `idempotency_key` given → add `Idempotency-Key` header (allow-listed by anvil CORS).
5. **Envelope**: parse JSON into `Response[response_model]`; on success return `.data`;
   if `error` is non-null → raise mapped exception with that message.
6. **Status mapping**: see table below — applied BEFORE envelope parse for non-2xx.

### Retry contract (FR-009)
- Retries on: `ConnectionError` (transport), `5xx`, `429`.
- Backoff: `config.retry_backoff * 2 ** attempt`; on `429` honor `Retry-After` header if present.
- Max attempts: `config.retry_count`.
- Does NOT auto-retry non-idempotent `POST`/`PATCH`/`PUT` UNLESS an `idempotency_key` is supplied.
- `GET`/`DELETE`/SSE-open are treated idempotent.

---

## `Response[T]` — `anvil/client/_shared/response.py`

```python
T = TypeVar("T")

class Response(BaseModel, Generic[T]):
    """Generic wrapper for the anvil ``{"data": ..., "error": ...}`` envelope."""

    data: T | None = None
    error: str | None = None
```

- Verified envelope shape against `anvil/api/v1/datasets.py` (`{"data": ..., "error": None}`).
- Transport validates `response.json()` into `Response[Model]` and returns `.data` (non-null on success).

---

## Status → Exception Mapping (FR-005, SC-004)

| HTTP status | Exception | Message source |
|---|---|---|
| `401`, `403` | `AuthenticationError` | server `error` or status text |
| `404` | `NotFoundError` | server `error` |
| `422` | `ValidationError` | server `error` / validation detail |
| `429` | `RateLimitError` (`retry_after`) | server `error`; `Retry-After` header |
| `500`–`599` | `ServerError` | **server `error` preserved verbatim** (SC-004) |
| transport failure / unreachable | `ConnectionError` | underlying httpx error message |
| `2xx` + `error != null` | mapped by best-effort, else `ApiError` | envelope `error` |

### Acceptance mapping
- US-1 scenario 3 (unreachable URL) → `ConnectionError`, never a hang (bounded by `timeout`).
- US-5 scenario 4 (invalid creds) → `AuthenticationError`.
- FR-011 → envelope consistently unwrapped here, one place.
