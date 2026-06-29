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

### Architecture Allow-List

```python
# anvil/services/inference/allow_list.py (or within model_browser_types.py)

from enum import StrEnum


class RunnableArchitecture(StrEnum):
    """Architecture classes eligible for local fine-tuning (v1 allow-list).

    A model whose ``architecture`` does not match any member of this
    enum is shown as **track-but-not-run** — importable as metadata,
    but fine-tune/inference disabled.
    """

    LLAMA_FOR_CAUSAL_LM = "LlamaForCausalLM"
```

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

## Validation Rules

| Field | Rule | Enforcement |
|-------|------|-------------|
| `CatalogEntry.hf_id` | Must be non-empty, valid HF ID format (`org/name`) | Pydantic `Field(min_length=1)` + regex |
| `CatalogEntry.resource_envelope` | Required for catalog entries | Pydantic model required |
| `ResourceEnvelope.min_ram_gb` | Must be >= 0 | `Field(ge=0)` |
| `ResourceEnvelope.min_vram_per_backend` | Must contain at least `cpu` key | Runtime validation in service layer |
| `ResourceEnvelope.supported_methods` | Must have at least one method | `Field(min_length=1)` |
| `RunnableArchitecture` | Values must match HF architecture class strings | `StrEnum` — compile-time check |

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
  ├── loads CuratedCatalog from YAML (1)
  ├── eligibility: CatalogEntry × detected_device → bool
  └── delegates import to ModelImportService (spec 040)
```