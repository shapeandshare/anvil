# Contract: `AnvilClient` Facade & `ServerConfig`

**Feature**: 026-client-sdk | Public surface developers interact with directly.

All methods are `async`. Type signatures shown are the public contract; bodies delegate to
`DomainClient`s / `Transport`. Every signature is `mypy --strict` clean.

---

## `AnvilClient` — `anvil/client/anvil_client.py`

```python
class AnvilClient:
    """Top-level async facade for the anvil server API.

    Aggregates per-domain sub-clients over a single shared transport. The
    only public entry point for SDK consumers.
    """

    config: ServerConfig
    health: HealthClient
    datasets: DatasetsClient
    training: TrainingClient
    experiments: ExperimentsClient
    registry: RegistryClient
    inference: InferenceClient
    # P3: corpora, eval, compute, services, governance, content

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
        retry_count: int | None = None,
        config: ServerConfig | None = None,
    ) -> None: ...

    async def login(self, api_key: str) -> None:
        """POST /login; capture and store the ``anvil_session`` cookie."""

    async def logout(self) -> None:
        """POST /logout; clear stored session cookie. Returns to unauthenticated state."""

    async def aclose(self) -> None:
        """Close the underlying transport (httpx client)."""

    async def __aenter__(self) -> "AnvilClient": ...
    async def __aexit__(self, *exc: object) -> None: ...
```

### Construction contract
- `AnvilClient()` with no args MUST produce a working client against `ANVIL_SERVER_URL`
  (default `http://localhost:8080`) — Pit of Success (Article IX, SC-001).
- Explicit args override env vars override defaults (see `ServerConfig.from_env`).
- Passing both `config=` and individual overrides: individual overrides win.
- The client is an async context manager; `async with AnvilClient(...) as client:` guarantees
  transport cleanup.

### Behavioral guarantees
- Constructing the client performs NO network I/O (lazy connect).
- `health.get()` MUST succeed without any auth configured (FR-010).
- All sub-clients share ONE `Transport` (one `httpx.AsyncClient`, one cookie jar).

---

## `ServerConfig` — `anvil/client/_shared/server_config.py`

```python
class ServerConfig(BaseModel):
    """Connection configuration for the anvil client SDK."""

    base_url: str = "http://localhost:8080"
    timeout: float = 30.0
    retry_count: int = 3
    retry_backoff: float = 0.5

    @classmethod
    def from_env(
        cls,
        base_url: str | None = None,
        timeout: float | None = None,
        retry_count: int | None = None,
        retry_backoff: float | None = None,
    ) -> "ServerConfig":
        """Build config with resolution order: explicit arg > env var > default.

        Env vars: ANVIL_SERVER_URL, ANVIL_TIMEOUT, ANVIL_RETRY_COUNT, ANVIL_RETRY_BACKOFF.
        """
```

### Validation contract
- `timeout > 0` else `pydantic.ValidationError`.
- `retry_count >= 0`, `retry_backoff >= 0`.
- `base_url` non-empty; trailing slash stripped at use sites.

---

## Acceptance mapping
- US-1 / SC-001 → `AnvilClient(base_url=...)` + `await client.health.get()` in ≤5 lines.
- US-5 / FR-003 → `AnvilClient(api_key=...)` and `await client.login(...)`.
- Edge case "config readback" → `client.config.base_url` etc. are public, readable attributes.
