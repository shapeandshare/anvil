---
title: Data Model — Subword Tokenizer Abstraction
type: spec
tags:
  - type/spec
created: '2026-06-28'
updated: '2026-06-28'
---
# Data Model: Subword Tokenizer Abstraction

## Entities

### Tokenizer (Abstract Protocol)

**Location**: `anvil/core/_tokenizer_base.py`

| Field | Type | Description |
|-------|------|-------------|
| `encode(text: str)` | `list[int]` | Encode text to token IDs |
| `decode(ids: list[int])` | `str` | Decode token IDs to text |
| `vocab_size` | `int` | Vocabulary size (property) |
| `bos_id` | `int \| None` | BOS token id for char-level; `None` for subword (BOS is a named special token handled inside `decode()`). Used by inference UI to render `<BOS>` labels. |

**Constraints**:
- No third-party imports — stdlib-only ABC
- Must be implementable by both `Vocabulary` (char-level) and HF subword wrapper
- `bos_id` is an optional property: char-level returns its BOS index, subword returns `None`

---

### TokenizerFamily (StrEnum)

**Location**: `anvil/services/_shared/tokenizer_family.py`

| Member | Value | Description |
|--------|-------|-------------|
| `CHAR` | `"char"` | Native anvil character-level tokenizer |
| `SUBWORD` | `"subword"` | HuggingFace subword tokenizer |

**Relationships**: Recorded on model metadata to drive encode/decode dispatch.

---

### SerializationType (StrEnum)

**Location**: `anvil/services/_shared/tokenizer_family.py`

| Member | Value | Description |
|--------|-------|-------------|
| `CHAR_JSON` | `"char_json"` | anvil's own char-level tokenizer JSON format |
| `HF_FAST` | `"hf_fast"` | HuggingFace `tokenizer.json` (self-contained) |
| `SENTENCEPIECE` | `"sentencepiece"` | SentencePiece `.model` file (Llama 1/2) |

**Constraints**: v1 only supports `char_json`, `hf_fast`, and `sentencepiece`. All others raise `TokenizerLoadError`.

---

### TokenizerLoadError (Exception)

**Location**: `anvil/services/_shared/tokenizer_load_error.py`

A plain `Exception` subclass (NOT Pydantic `BaseModel` — exceptions must subclass `Exception`).

| Attribute | Type | Description |
|-----------|------|-------------|
| `message` | `str` | Descriptive error with file path and root cause |
| `file_path` | `str \| None` | Path to the problematic tokenizer file |
| `cause` | `str \| None` | Root cause description |

**Subtypes** (single class with discriminators):
- Missing tokenizer files
- Corrupt JSON/SentencePiece parse failure
- Unknown tokenizer family
- Vocabulary drift (mismatched checkpoint)

---

### TokenizerFactory (Loader)

**Location**: `anvil/services/inference/tokenizer_factory.py`

Resolves a `Tokenizer` instance from a model's recorded metadata. This is the dispatch linchpin — without it, the recorded `TokenizerFamily` has no runtime effect.

| Input | Type | Description |
|-------|------|-------------|
| `tokenizer_family` | `str` / `TokenizerFamily` | From model metadata |
| `serialization_type` | `str` / `SerializationType` | From model metadata |
| `chars` | `list[str] \| None` | Char list (for char-level) |
| `artifact_dir` | `str \| Path` | Directory holding tokenizer file(s) |

**Dispatch**:
- `char_json` → `Vocabulary.from_chars(chars)`
- `hf_fast` → `HFFastTokenizer(artifact_dir / "tokenizer.json")`
- `sentencepiece` → `SentencePieceTokenizer(artifact_dir / "tokenizer.model")`
- unknown/unsupported → raise `TokenizerLoadError`

Catches missing/corrupt-file errors and re-raises as `TokenizerLoadError(file_path=..., cause=...)`. Logs family + serialization type at INFO (FR-015b).

---

### LlamaModel persistence (Updated)

**Location**: `anvil/core/engine.py`

`LlamaModel.save()`/`load()` JSON gains two fields alongside the existing `chars`:

| Field | Type | Default on load (backward compat) |
|-------|------|-----------------------------------|
| `tokenizer_family` | `str` | `"char"` (when absent — old checkpoints) |
| `serialization_type` | `str` | `"char_json"` (when absent — old checkpoints) |

Stored as plain strings (core is stdlib-only; enums live in services). Old `experiment_*.json` files without these fields load as char-level (NMRG).

---

### LoadedModel (Updated)

**Location**: `anvil/services/inference/loaded_model.py`

| Field | Type | Current | New |
|-------|------|---------|-----|
| `tokenizer` | `Tokenizer` | `vocab: Vocabulary` | Protocol-based, holds any implementation |
| `chars` | `list[str]` | Direct attribute | Derived from `tokenizer` via `tokenizer.chars` (char impl) or `[]` (subword) |
| `model_id` | `int \| None` | Unchanged | Unchanged |
| `version` | `int \| None` | Unchanged | Unchanged |
| `name` | `str` | Unchanged | Unchanged |
| `is_demo` | `bool` | Unchanged | Unchanged |

**Constructor change**: Accepts `tokenizer: Tokenizer` instead of `chars: list[str]`.

---

### Model Metadata (Storage)

**Format**: Stored alongside model artifacts in `FileStore` (SQLite model record + filesystem artifacts)

| Field | Type | Description |
|-------|------|-------------|
| `tokenizer_family` | `TokenizerFamily` | `char` or `subword` |
| `serialization_type` | `SerializationType` | How the tokenizer is serialized |
| `tokenizer_path` | `str` | Relative path to tokenizer artifact within model directory |

**Storage layout** (flat alongside model files):
```
data/models/experiment_{id}/
├── model.safetensors       # Model weights
├── config.json             # Model config (HF-format)
├── tokenizer.json          # Tokenizer file (char_json, hf_fast, or sentencepiece.model renamed)
```

---

## Relationships

```
Model (artifact set)
 ├── config.json      ─── records tokenizer_family + serialization_type
 ├── model.safetensors ─── weights (unchanged)
 └── tokenizer.<ext>  ─── loaded by TokenizerFactory based on serialization_type
       │
       ▼
Tokenizer (protocol)
 ├── CharTokenizer (native anvil)
 └── SubwordTokenizer (HF, behind [finetune])
       ├── HFFastTokenizer  (tokenizer.json)
       └── SentencePieceTokenizer (sentencepiece.model)
```

---

## Validation Rules

1. Tokenizer is **immutable** after model creation — no swap operation
2. Unknown `TokenizerFamily` → `TokenizerLoadError` (not-runnable)
3. Unsupported `SerializationType` → `TokenizerLoadError` (FR-031)
4. Corrupt tokenizer file → `TokenizerLoadError` with diagnostic detail
5. Char-level vocab drift against checkpoint → `TokenizerLoadError`
6. Subword tokenizer files behind `[finetune]` extra only — base install raises `ImportError`

---

## State Transitions

```
Model Created → Tokenizer Attached (immutable)
                    │
                    ▼
           Inference / Eval
              │          │
              ▼          ▼
        char family    subword family
        (Vocabulary)   (SubwordTokenizer)
```

No lifecycle beyond create-and-use. A fine-tuned model (spec 044) is a **new model artifact** with a potentially new tokenizer.