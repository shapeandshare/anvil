# Data Model: HuggingFace Model Browser

**Feature**: 041 HuggingFace Model Browser | **Date**: 2026-06-28

## Entities

### CuratedModelCatalog

A bundled YAML file (`anvil/data/curated-models.yaml`) containing vetted small models. Loaded at runtime into a validated Pydantic model.

**File format** (YAML):

```yaml
# anvil/data/curated-models.yaml
catalog:
  - hf_id: "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    display_name: "TinyLlama 1.1B Chat"
    params: "1.1B"
    license: "Apache-2.0"
    architecture: "LlamaForCausalLM"
    tokenizer_family: "SentencePiece"
    url: "https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    tags: ["tiny", "chat"]
    resource_envelope:
      min_ram_gb: 8.0
      min_vram_per_backend:
        cpu: 0
        cuda: 4.0
        mps: 6.0
      supported_methods: ["lora", "full"]
```

### Pydantic Models

These models validate the YAML data at load time and are used throughout the service layer.

```python
# anvil/services/inference/model_browser_types.py

from __future__ import annotations

from pydantic import BaseModel, Field


class ResourceEnvelope(BaseModel):
    """Resource requirements for running/fine-tuning a model, per backend.

    Attributes
    ----------
    min_ram_gb : float
        Minimum system RAM in GB.
    min_vram_per_backend : dict[str, float]
        Per-backend minimum VRAM in GB, keyed by backend name
        (e.g. ``{"cpu": 0, "cuda": 4.0, "mps": 6.0}``).
    supported_methods : list[str]
        Supported fine-tuning methods (e.g. ``["full", "lora"]``).
    """

    min_ram_gb: float = Field(ge=0, description="Minimum system RAM in GB")
    min_vram_per_backend: dict[str, float] = Field(
        description="Per-backend minimum VRAM in GB",
    )
    supported_methods: list[str] = Field(
        min_length=1,
        description="Supported fine-tuning methods",
    )


class CatalogEntry(BaseModel):
    """A single entry in the curated model catalog.

    Attributes
    ----------
    hf_id : str
        HuggingFace model ID, e.g. ``"TinyLlama/TinyLlama-1.1B-Chat-v1.0"``.
        Serves as the stable key for the entry.
    display_name : str
        Human-readable name.
    params : str
        Parameter count label, e.g. ``"1.1B"``.
    license : str
        SPDX license identifier, e.g. ``"Apache-2.0"``.
    architecture : str
        HuggingFace architecture class, e.g. ``"LlamaForCausalLM"``.
    tokenizer_family : str
        Tokenizer type, e.g. ``"SentencePiece"``, ``"tokenizers"``.
    url : str
        Link to live HuggingFace model card.
    tags : list[str]
        Categorization tags, e.g. ``["tiny", "chat", "base"]``.
    resource_envelope : ResourceEnvelope
        Embedded resource requirements for fine-tuning eligibility.
    """

    hf_id: str = Field(description="HuggingFace model ID (stable key)")
    display_name: str = Field(description="Human-readable name")
    params: str = Field(description="Parameter count label")
    license: str = Field(description="SPDX license identifier")
    architecture: str = Field(description="HF architecture class")
    tokenizer_family: str = Field(description="Tokenizer type")
    url: str = Field(description="Link to live HF model card")
    tags: list[str] = Field(default_factory=list, description="Categorization tags")
    resource_envelope: ResourceEnvelope = Field(
        description="Resource requirements for fine-tuning",
    )


class CuratedCatalog(BaseModel):
    """The full curated model catalog loaded from YAML."""

    catalog: list[CatalogEntry] = Field(
        description="List of curated model entries",
    )
```

### Architecture Allow-List & Accepted Format (REUSE — do not redefine)

The runnable architecture allow-list and accepted weight format already exist in spec 040 and MUST be
reused as the single source of truth (Constitution Article XI §11.4 — Reuse First). Do **not** create a
parallel `RunnableArchitecture` enum.

```python
# anvil/services/model_import/model_import_service.py  (EXISTING — spec 040)
_ALLOWED_ARCHITECTURES: frozenset[str] = frozenset({"LlamaForCausalLM"})
_ACCEPTED_FORMATS: frozenset[str] = frozenset({"safetensors"})
```

The "track-but-not-run" concept is also already modeled by the existing `RunnableStatus` enum — reuse it:

```python
# anvil/services/_shared/runnable_status.py  (EXISTING — spec 040)
class RunnableStatus(StrEnum):
    RUNNABLE = "runnable"
    TRACK_ONLY = "track_only"
```

`ModelBrowserService` MUST import these (do not copy the literal strings). If these constants need to be
shared more broadly, promote them to a `_shared` location in a separate refactor commit (Article X §10.9),
but this spec does not require that — a direct import is sufficient.

### HF Search Result (runtime)

```python
# anvil/services/inference_hub/hub_types.py
# (behind [finetune] extra — never imported at module level without guard)

from __future__ import annotations

from pydantic import BaseModel, Field


class HfSearchResult(BaseModel):
    """Summary of a HuggingFace model from live API search."""

    hf_id: str = Field(description="Full HF model ID")
    display_name: str = Field(description="Model name")
    params: str | None = Field(default=None, description="Parameter count label")
    license: str | None = Field(default=None, description="SPDX license identifier")
    architecture: str | None = Field(default=None, description="HF architecture class")
    is_curated: bool = Field(default=False, description="Whether this model is in the curated catalog")
```

## Eligibility Algorithm (inputs grounded in real detection)

`check_eligibility` is a pure function with signature:

```python
def check_eligibility(envelope: ResourceEnvelope, gpu: GpuInfo, ram_total_gb: float) -> bool:
    # 1. RAM check (always applies)
    if ram_total_gb < envelope.min_ram_gb:
        return False
    # 2. VRAM check (only when a GPU backend is detected)
    if gpu.available and gpu.backend is not None:
        backend = str(gpu.backend)  # "cuda" | "mps"
        required = envelope.min_vram_per_backend.get(backend)
        detected = gpu.memory_total_gb  # NOTE: on MPS this is unified system RAM (best-effort)
        if required is not None and detected is not None and detected < required:
            return False
    # CPU-only host: VRAM check skipped — RAM is the binding constraint.
    return True
```

Inputs come from existing code:
- `gpu: GpuInfo` ← `detect_gpu()` in `anvil/gpu.py` (fields: `available`, `backend`, `memory_total_gb`).
- `ram_total_gb: float` ← `psutil.virtual_memory().total / (1024**3)` (psutil is a **core** dependency).

There is **no** `workbench.compute.device` property; `anvil/services/compute/resolve.py` returns only a
device *type* (`DeviceType`), not quantities. The service layer is responsible for calling `detect_gpu()`
and `psutil` and passing the values into this pure function (keeps the function unit-testable).

## Validation Rules

| Field | Rule | Enforcement |
|-------|------|-------------|
| `CatalogEntry.hf_id` | Must be non-empty, valid HF ID format (`org/name`) | Pydantic `Field(min_length=1)` + regex |
| `CatalogEntry.architecture` | SHOULD match `_ALLOWED_ARCHITECTURES` for runnable entries; otherwise rendered track-only | Compared at load against spec 040 constant |
| `CatalogEntry.resource_envelope` | Required for catalog entries | Pydantic model required |
| `ResourceEnvelope.min_ram_gb` | Must be >= 0 | `Field(ge=0)` |
| `ResourceEnvelope.min_vram_per_backend` | Must contain at least `cpu` key | `field_validator` in the Pydantic model |
| `ResourceEnvelope.supported_methods` | Must have at least one method | `Field(min_length=1)` |

## State Transitions

The curated catalog is **static** — entries are defined in the YAML file and loaded at startup. No runtime state transitions. The YAML file is updated via PR (not at runtime).

HF search results are ephemeral — fetched live and cached with TTL. No persistent state.

## Relationship Diagram

```
CuratedCatalog (YAML file)
  └── CatalogEntry (1..*)
        ├── hf_id: str (key)
        └── ResourceEnvelope (1)
              ├── min_ram_gb: float
              ├── min_vram_per_backend: dict[str, float]
              └── supported_methods: list[str]

ModelBrowserService
  ├── loads CuratedCatalog from YAML (1)  [PyYAML — must be declared core dep]
  ├── eligibility: ResourceEnvelope × GpuInfo × ram_total_gb → bool  [pure function]
  ├── reuses spec 040 _ALLOWED_ARCHITECTURES / _ACCEPTED_FORMATS / RunnableStatus
  └── import → workbench.model_imports.submit_import(source="huggingface", identifier=hf_id)
                (or the existing POST /v1/models/import route)
```

> **Note on `min_vram_per_backend` keys**: keys are `DeviceType` values as strings (`"cuda"`, `"mps"`,
> `"cpu"`) to match `GpuInfo.backend`. The catalog author MUST use these exact backend names so the
> eligibility lookup (`envelope.min_vram_per_backend.get(str(gpu.backend))`) resolves correctly.