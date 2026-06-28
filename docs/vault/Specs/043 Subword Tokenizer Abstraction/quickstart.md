---
title: Quickstart — Subword Tokenizer Abstraction
type: spec
tags:
  - type/spec
created: '2026-06-28'
updated: '2026-06-28'
---
# Quickstart: Subword Tokenizer Abstraction

## What this feature does

Models carry their tokenizer as a first-class artifact. Encode/decode dispatches based on `TokenizerFamily` — char-level for native anvil models, subword for imported HuggingFace models.

## Structure to implement

### 1. Protocol (`anvil/core/_tokenizer_base.py`)

```python
from abc import ABC, abstractmethod


class Tokenizer(ABC):
    """Abstract tokenizer protocol — stdlib only, zero deps."""

    @abstractmethod
    def encode(self, text: str) -> list[int]: ...
    @abstractmethod
    def decode(self, ids: list[int]) -> str: ...
    @property
    @abstractmethod
    def vocab_size(self) -> int: ...
```

### 2. StrEnums (`anvil/services/_shared/tokenizer_family.py`)

```python
from enum import StrEnum


class TokenizerFamily(StrEnum):
    CHAR = "char"
    SUBWORD = "subword"


class SerializationType(StrEnum):
    CHAR_JSON = "char_json"
    HF_FAST = "hf_fast"
    SENTENCEPIECE = "sentencepiece"
```

### 3. Update `Vocabulary` to implement `Tokenizer`

`anvil/core/vocabulary.py` — add `Tokenizer` to the class signature. Existing methods already match the protocol. Add a `chars` property.

### 4. Subword wrapper (`anvil/services/inference/_subword_tokenizer.py`)

Behind `[finetune]` extra. Wraps `tokenizers.Tokenizer` and `sentencepiece.SentencePieceProcessor`.

### 5. Update `LoadedModel`

Accept `tokenizer: Tokenizer` instead of `chars: list[str]`. Derive `chars` property from tokenizer.

### 6. Update call sites

- `inference.py` — 7 `loaded.vocab.encode()` → `loaded.tokenizer.encode()`
- `inference.py` — 12 `loaded.vocab.bos_id` → handle `None` for subword
- `export.py` — extract chars from tokenizer
- `demo_model_provider.py` — provide Tokenizer instead of chars
- Tests — same pattern

## Key constraints

| Constraint | Why |
|------------|-----|
| No `transformers`/`tokenizers` import in base install | Article I — zero-dependency core |
| `Vocabulary` must be byte-identical post-refactor | FR-014a — contract tests prove parity |
| Fail fast on corrupt/unsupported tokenizers | FR-014b — no silent fallback |
| INFO log on dispatch | FR-015b — debuggability |
| Tokenizer files flat alongside model on export | HF convention for `AutoTokenizer.from_pretrained()` |

## Testing

- **Contract tests**: Char-level encode/decode parity (pre- and post-abstraction)
- **Unicode tests**: Emoji (surrogate pairs), CJK, combining diacritics, null char
- **Subword tests**: Round-trip via TinyLlama `tokenizer.json`
- **Error tests**: Corrupt file, missing file, unknown family — all raise `TokenizerLoadError`
- **NMRG**: Base install cannot import subword tokenizer