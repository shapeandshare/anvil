# Catalog Format: `curated-models.yaml`

**Feature**: 041 HuggingFace Model Browser | **Date**: 2026-06-28

## Location

`anvil/data/curated-models.yaml` — bundled in the Python wheel via `pyproject.toml` `[tool.setuptools.package-data]`.

## Schema

The YAML file contains a single top-level `catalog` key with a list of model entries:

```yaml
# anvil/data/curated-models.yaml
catalog:
  - hf_id: "org/model-name"
    display_name: "Human Readable Name"
    params: "1.1B"
    license: "Apache-2.0"
    architecture: "LlamaForCausalLM"
    tokenizer_family: "SentencePiece"
    url: "https://huggingface.co/org/model-name"
    tags: ["tag1", "tag2"]
    resource_envelope:
      min_ram_gb: 8.0
      min_vram_per_backend:
        cpu: 0
        cuda: 4.0
        mps: 6.0
      supported_methods: ["lora", "full"]
```

## Field Reference

| Field | Required | Type | Constraints |
|-------|----------|------|-------------|
| `hf_id` | ✅ | `string` | Format: `org/name`. Stable key — must be unique across entries |
| `display_name` | ✅ | `string` | Human-readable name |
| `params` | ✅ | `string` | Parameter count label (e.g. `"1.1B"`, `"350M"`) |
| `license` | ✅ | `string` | SPDX identifier (e.g. `"Apache-2.0"`, `"MIT"`) |
| `architecture` | ✅ | `string` | Must match one of the allow-list enum values (v1: `LlamaForCausalLM`) |
| `tokenizer_family` | ✅ | `string` | Tokenizer type (e.g. `"SentencePiece"`, `"tokenizers"`) |
| `url` | ✅ | `string` | Full HTTPS URL to HF model card |
| `tags` | optional | `list[string]` | Categorization tags. Default: `[]` |
| `resource_envelope` | ✅ | `object` | See below |

## ResourceEnvelope Fields

| Field | Required | Type | Constraints |
|-------|----------|------|-------------|
| `min_ram_gb` | ✅ | `number` | >= 0. Minimum system RAM in GB |
| `min_vram_per_backend` | ✅ | `object` | Keys: backend names (`cpu`, `cuda`, `mps`); values: float >= 0. Must contain at least `cpu` |
| `supported_methods` | ✅ | `array[string]` | >= 1 item. Values: `"full"`, `"lora"` |

## Validation

The YAML is validated at load time by the Pydantic `CuratedCatalog` model. Invalid entries raise a clear `ValidationError` at startup with the entry's `hf_id` and the specific validation failure.

## Maintainability

- Updates to the catalog are submitted via PR
- New entries should include honest resource envelopes verified against the developer's hardware
- Entries should prioritize models that are commonly used for educational fine-tuning (small, well-documented, active community)