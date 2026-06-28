# SDK Contract: `client.models`

## Method: `client.models.import_model()`

```python
from anvil.client import AnvilClient

async with AnvilClient(base_url="http://localhost:8080") as client:
    result = await client.models.import_model(
        source="huggingface",
        identifier="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        revision="main",
        name="My TinyLlama",
    )
    print(f"Job ID: {result.job_id}, Status: {result.status}")
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `source` | `str` | Yes | — | Source type: `huggingface` or `local` |
| `identifier` | `str` | Yes | — | Source-specific model identifier |
| `revision` | `str` | No | `main` | Source revision/branch/commit |
| `name` | `str \| None` | No | `None` | Display name |

### Returns

`ImportResult` (Pydantic BaseModel):

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | `int` | Import job ID |
| `status` | `str` | Initial job status (`queued`) |

### Raises

| Exception | When |
|-----------|------|
| `ValueError` | Invalid source type or missing required fields |
| `TransportError` | Network/connection error to anvil server |

## Method: `client.models.get_import_status()`

```python
status = await client.models.get_import_status(job_id=42)
print(f"Status: {status.status}")
if status.status == "complete":
    model = await client.models.get(model_id=status.external_model_id)
    print(f"Model: {model.display_name}")
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | `int` | Yes | Import job ID from `import_model()` |

### Returns

`ImportJobStatus` (Pydantic BaseModel):

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | `int` | Job ID |
| `status` | `str` | `queued`, `resolving`, `complete`, `failed` |
| `started_at` | `datetime \| None` | When resolution began |
| `finished_at` | `datetime \| None` | When resolution ended |
| `error_code` | `str \| None` | Typed error code (if failed) |
| `error_message` | `str \| None` | Error message (if failed) |
| `external_model_id` | `int \| None` | Model ID (if complete) |

## Implementation Structure

```
anvil/client/models/
├── __init__.py                  # exports ModelsClient
├── models_client.py             # ModelsClient(transport) domain aggregator
├── models_import_command.py     # ModelsImportCommand(AbstractCommand)
├── models_get_status_command.py # ModelsGetStatusCommand(AbstractCommand)
└── models_get_command.py        # ModelsGetCommand(AbstractCommand)
```

### ModelsClient

```python
class ModelsClient:
    def __init__(self, transport: Transport) -> None:
        self._import_cmd = ModelsImportCommand(transport)
        self._status_cmd = ModelsGetStatusCommand(transport)
        self._get_cmd = ModelsGetCommand(transport)

    async def import_model(self, source: str, identifier: str, ...) -> ImportResult:
        return await self._import_cmd.execute(source, identifier, ...)

    async def get_import_status(self, job_id: int) -> ImportJobStatus:
        return await self._status_cmd.execute(job_id)

    async def get(self, model_id: int) -> ExternalModel:
        return await self._get_cmd.execute(model_id)
```

### AnvilClient integration

```python
# anvil/client/anvil_client.py
class AnvilClient:
    def __init__(self, ...):
        ...
        self._models: ModelsClient | None = None

    @property
    def models(self) -> ModelsClient:
        if self._models is None:
            self._models = ModelsClient(self._transport)
        return self._models
```
