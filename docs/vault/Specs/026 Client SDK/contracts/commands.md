# Contract: `AbstractCommand` & Per-Domain Command Catalog

**Feature**: 026-client-sdk | The command paradigm (darkness `AbstractCommand` analogue).

---

## `AbstractCommand` — `anvil/client/_shared/abstract_command.py`

```python
class AbstractCommand(ABC):
    """Base class for all SDK commands.

    Each concrete command maps to exactly one (resource, verb) API
    operation. Commands own their URL template and DTO types; they
    delegate HTTP I/O to the shared Transport.
    """

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    @abstractmethod
    async def execute(self, *args: object, **kwargs: object) -> object:
        """Perform the command's single API operation and return a typed result."""
```

### Command contract
- One class per file; one (resource, verb) per command.
- A command MUST NOT import or call `httpx` directly — only `self._transport`.
- A command's `execute` returns a typed DTO (or `list`/`AsyncIterator` thereof), never a raw dict.
- URL paths are owned by the command (e.g. `/v1/datasets/{id}`); ids are interpolated at call time.

### `DomainClient` aggregator contract
Each domain has a `*Client` that instantiates its commands with the shared transport and exposes
ergonomic methods. Example:

```python
class DatasetsClient:
    """Dataset lifecycle operations."""

    def __init__(self, transport: Transport) -> None:
        self._list = DatasetListCommand(transport)
        self._get = DatasetGetCommand(transport)
        # ...

    async def list(self, query: str | None = None) -> list[Dataset]: ...
    async def get(self, dataset_id: int) -> Dataset: ...
    async def create(self, name: str, description: str | None = None) -> Dataset: ...
    async def update(self, dataset_id: int, *, name: str | None = None,
                     description: str | None = None) -> Dataset: ...
    async def delete(self, dataset_id: int, *, force: bool = False) -> None: ...
    async def upload(self, dataset_id: int, file_path: Path) -> Dataset: ...
    async def export(self, dataset_id: int, *, fmt: str = "txt",
                     dest: Path | None = None) -> bytes | Path: ...
    async def search(self, query: str) -> list[Dataset]: ...
```

---

## Command Catalog (endpoint → command → method)

> Verified endpoint paths from the anvil API exploration. P-tier from spec priorities.

### P1 — health (`HealthClient`)
| Method | Endpoint | Command |
|---|---|---|
| `health.get()` | `GET /v1/health` | `HealthGetCommand` |
| `health.detailed()` | `GET /v1/health/detailed` | `HealthDetailedCommand` |

### P1 — datasets (`DatasetsClient`)
| Method | Endpoint | Command |
|---|---|---|
| `datasets.list(query=None)` | `GET /v1/datasets[?q=]` | `DatasetListCommand` |
| `datasets.get(id)` | `GET /v1/datasets/{id}` | `DatasetGetCommand` |
| `datasets.create(name, description)` | `POST /v1/datasets` | `DatasetCreateCommand` |
| `datasets.update(id, ...)` | `PUT /v1/datasets/{id}` | `DatasetUpdateCommand` |
| `datasets.delete(id, force=False)` | `DELETE /v1/datasets/{id}[?force=]` | `DatasetDeleteCommand` |
| `datasets.upload(id, file_path)` | `POST /v1/datasets/upload` (multipart) | `DatasetUploadCommand` |
| `datasets.export(id, fmt)` | `GET /v1/datasets/{id}/export?format=` | `DatasetExportCommand` |
| `datasets.search(query)` | `GET /v1/datasets?q=` | (delegates to `DatasetListCommand`) |

### P1 — training (`TrainingClient`)
| Method | Endpoint | Command |
|---|---|---|
| `training.start(config)` | `POST /v1/training/start` | `TrainingStartCommand` |
| `training.status(run_id)` | `GET /v1/training/{run_id}/status` | `TrainingStatusCommand` |
| `training.stop(run_id)` | `POST /v1/training/{run_id}/stop` | `TrainingStopCommand` |
| `training.stream(run_id)` | `GET /v1/training/stream/{run_id}` (SSE) | `TrainingStreamCommand` |

### P2 — experiments (`ExperimentsClient`)
| Method | Endpoint | Command |
|---|---|---|
| `experiments.list()` | `GET /v1/experiments` | `ExperimentListCommand` |
| `experiments.get(id)` | `GET /v1/experiments/{id}` | `ExperimentGetCommand` |
| `experiments.compare(ids)` | `GET /v1/experiments/compare?id=...` | `ExperimentCompareCommand` |
| `experiments.get_metrics(id)` | `GET /v1/experiments/{id}/metrics` | `ExperimentMetricsCommand` |
| `experiments.delete(id)` | `DELETE /v1/experiments/{id}` | `ExperimentDeleteCommand` |
| `experiments.list_artifacts(exp_id, run_id)` | `GET /v1/experiments/{exp}/runs/{run}/artifacts` | `ExperimentArtifactsCommand` |
| `experiments.download_artifact(exp_id, run_id, path, dest)` | `GET .../download?path=` | `ExperimentDownloadCommand` |

### P2 — registry (`RegistryClient`)
| Method | Endpoint | Command |
|---|---|---|
| `registry.register(experiment_id, ...)` | `POST /v1/registry/models` | `RegistryRegisterCommand` |
| `registry.list(search=None)` | `GET /v1/registry/models[?search=]` | `RegistryListCommand` |
| `registry.get(model_id)` | `GET /v1/registry/models/{id}` | `RegistryGetCommand` |
| `registry.delete(model_id, version=None)` | `DELETE /v1/registry/models/{id}[/versions/{v}]` | `RegistryDeleteCommand` |

### P3 — inference (`InferenceClient`)
| Method | Endpoint | Command |
|---|---|---|
| `inference.models()` | `GET /v1/inference/models` | `InferenceModelsCommand` |
| `inference.sample(model_id, prompt, temperature)` | `POST /v1/inference/sample` | `InferenceSampleCommand` |

### P3 — remaining domains
`corpora` (`/v1/corpora/*`), `eval` (`/v1/eval/*`, `/v1/eval-datasets/*`), `compute`
(`/v1/compute/backends`), `services` (`/v1/services/*`, `/v1/demo/bootstrap`), `governance`
(`/v1/governance/*`), `content` (`/v1/content/*`, incl. SSE streams) — each follows the same
`DomainClient` + one-command-per-endpoint shape. Full per-endpoint commands enumerated during
P3 task generation. (FR-012 requires complete coverage.)

---

## Acceptance mapping
- US-2 → all `DatasetsClient` methods.
- US-3 → all `TrainingClient` methods (stream contract in `streaming.md`).
- US-4 → `ExperimentsClient` + `RegistryClient`.
- US-6 → `experiments.download_artifact`, `datasets.export`, `inference.sample`.
- FR-002 → every operation reachable via a named domain attribute.
- FR-012 → catalog covers all 12 domains; P3 completes the long tail.
