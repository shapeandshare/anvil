# Research: Subword Tokenizer Abstraction

**Phase 0 output** — resolves technical unknowns for plan.md

## 1. HuggingFace Tokenizers API Surface

### `tokenizers.Tokenizer` (Rust-backed, `[finetune]` extra)

**Decision**: Use `tokenizers.Tokenizer.from_file()` for `tokenizer.json` format; use `sentencepiece.SentencePieceProcessor` for `.model` files.

**API Surface for wrapper**:

| Method | Returns | Notes |
|--------|---------|-------|
| `Tokenizer.from_file(path)` | `Tokenizer` | Loads self-contained `tokenizer.json` |
| `.encode(text)` | `Encoding` | Call `.ids` to get `list[int]` |
| `.decode(ids, skip_special_tokens=True)` | `str` | Default strips special tokens |
| `.get_vocab_size(with_added_tokens=True)` | `int` | Total vocab including added tokens |

**SentencePiece (`.model` files — Llama 1/2, Gemma)**:

| Method | Returns | Notes |
|--------|---------|-------|
| `SentencePieceProcessor()` | processor | From `sentencepiece` package |
| `.load("path/to/model.file")` | `None` | Loads binary `.model` file |
| `.encode(text)` | `list[int]` | Returns IDs directly (not Encoding object) |
| `.decode(ids)` | `str` | Returns decoded text |
| `.get_piece_size()` | `int` | Vocab size |

**Key insight**: Llama 3+ uses `tokenizer.json` (TokenizersBackend). Llama 1/2 uses `.model` (SentencePieceBackend). The wrapper must handle both.

### `tokenizer.json` is self-contained

Includes vocab, merges, normalizer, pre-tokenizer, post-processor, decoder, added tokens — everything needed to replicate tokenization. Single file, no sidecar dependencies.

**API stability**: Core `encode()`/`decode()`/`from_file()` have been stable since v0.13+ (~2022). No breaking changes expected.

## 2. Existing Usage Patterns (Call Site Analysis)

### LoadedModel — the central hub

`LoadedModel` currently:
- Constructor takes `chars: list[str]` and immediately builds `self.vocab = Vocabulary.from_chars(chars)`
- Exposes `self.chars` (raw char list for display labels)
- Exposes `self.vocab` (Vocabulary instance for encode/decode)

### Production call sites (need updating)

| File | Usage | Change needed |
|------|-------|---------------|
| `inference.py` (7 sites) | `loaded.vocab.encode(text)`, `loaded.vocab.bos_id`, `loaded.vocab.vocab_size` | These call the protocol — minimal change (rename property or keep `.vocab`) |
| `inference.py` (7 sites) | `loaded.chars[i]` for display labels | Keep `.chars` as a property derived from tokenizer |
| `loaded_model.py` | Constructor `chars: list[str]`, builds `self.vocab` | Accept `Tokenizer` instead |
| `demo_model_provider.py` | Assigns `model.chars = uchars` | Update to pass Tokenizer |
| `training/export.py` | `chars = model.chars or []` | Extract chars from tokenizer |
| `eval.py`, `learning.py` | `loaded.chars`, `model.vocab_size` | Model hyperparameter stays; chars derived from tokenizer |

### Test call sites (need updating)

| File | Usage |
|------|-------|
| `test_inference.py` | `LoadedModel(gpt, uchars, ...)` — constructs with chars list |
| `test_tokenizer.py` | Imports `Tokenizer` and `Vocabulary` directly |
| `test_engine.py` | Imports `Tokenizer` and `Vocabulary` directly |

### Key architectural decisions confirmed

- `LlamaModel.vocab_size` is a model hyperparameter (embedding table size) — NOT a tokenizer property. Keep it separate.
- `.chars` is used for UI display labels (`loaded.chars[i]`) — derive from tokenizer, but keep the property name.
- All inference methods access tokenizer through `loaded.vocab.*` — the protocol replaces this seamlessly.

## 3. Protocol Design

### Minimal interface (stdlib only — lives in `anvil/core/`)

```python
class Tokenizer(ABC):
    @abstractmethod
    def encode(self, text: str) -> list[int]: ...
    @abstractmethod
    def decode(self, ids: list[int]) -> str: ...
    @property
    @abstractmethod
    def vocab_size(self) -> int: ...
```

**Why no `bos_id` on the protocol?** `bos_id` is char-level-specific. Subword tokenizers handle BOS via special tokens map, not a simple int. `LlamaModel` already has its own BOS handling. Remove `bos_id` from the protocol — callers that need it already have access through `TokenizerFamily`.

Actually, looking at the code more carefully, `bos_id` is used extensively in inference.py to identify BOS tokens in output for display (rendering `<BOS>` instead of a char). Let's keep it but make it optional — subword tokenizers can return `None`.

### Serialization type tracking

Support both:
- `hf_fast` — `tokenizer.json` (self-contained, load via `Tokenizer.from_file()`)
- `sentencepiece` — `tokenizer.model` / `sentencepiece.model` (load via `SentencePieceProcessor`)
- `char` — char-level (native anvil, `Vocabulary`)

Recorded as a string on the model metadata. Unknown types are flagged not-runnable.

## 4. Dependencies

| Package | Where needed | Extra group |
|---------|-------------|-------------|
| `tokenizers` (HF Rust-backed) | Subword tokenizer loading | `[finetune]` |
| `sentencepiece` | SentencePiece `.model` files (Llama 1/2) | `[finetune]` |
| `transformers` | AutoTokenizer for HF Hub model lookups | `[finetune]` |

All behind `[finetune]` extra — zero impact on base install. The `tokenizers` package is a lighter dependency than `transformers` (no PyTorch/JAX dependency), so it's preferred when possible.