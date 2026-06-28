# Tokenizer Protocol Contract

## Interface

```python
class Tokenizer(ABC):
    """Abstract tokenizer — all implementations must satisfy this protocol."""

    @abstractmethod
    def encode(self, text: str) -> list[int]:
        """Encode text to a sequence of token IDs.
        
        - Raises TokenizerLoadError if tokenizer is not loaded (e.g. missing files)
        - Must handle empty string (return [BOS, BOS] for char, [] for subword?)
        - Must not throw on unicode edge cases (emoji, CJK, combining chars)
        """
        ...

    @abstractmethod
    def decode(self, ids: list[int]) -> str:
        """Decode a sequence of token IDs back to text.
        
        - Must handle empty list (return "")
        - Must handle out-of-range IDs gracefully (skip or BOS-replace)
        """
        ...

    @property
    @abstractmethod
    def vocab_size(self) -> int:
        """Total vocabulary size (including special/added tokens)."""
        ...

    @property
    @abstractmethod
    def bos_id(self) -> int | None:
        """BOS token id (char-level) or None (subword).

        - Char-level: returns the BOS index (len(chars))
        - Subword: returns None — BOS is a named special token handled
          internally by decode(); inference UI treats None as "never BOS"
        """
        ...
```

## Implementations

### CharTokenizer (Vocabulary) — `anvil/core/vocabulary.py`

- **BOS-wrapped**: encode prepends/appends BOS; decode strips BOS
- **Chars derived**: `.chars` property returns the character list
- **Out-of-vocab chars**: silently skipped during encode
- **Out-of-range IDs**: silently skipped during decode
- **Vocab size**: `len(chars) + 1` (includes BOS)
- **bos_id**: returns `self.bos_id` (= `len(chars)`)

### Subword wrappers — `bos_id` returns `None`

Both `HFFastTokenizer` and `SentencePieceTokenizer` return `None` for `bos_id`. Inference display logic must treat `None` as "no token is BOS" (no `<BOS>` substitution).

### HFFastTokenizer — `anvil/services/inference/_subword_tokenizer.py`

- Wraps `tokenizers.Tokenizer.from_file("tokenizer.json")`
- `.encode(text)` → `tokenizer.encode(text).ids`
- `.decode(ids)` → `tokenizer.decode(ids, skip_special_tokens=True)`
- `.vocab_size` → `tokenizer.get_vocab_size(with_added_tokens=True)`

### SentencePieceTokenizer — `anvil/services/inference/_subword_tokenizer.py`

- Wraps `sentencepiece.SentencePieceProcessor`
- `.encode(text)` → `processor.encode(text)` (list of ints)
- `.decode(ids)` → `processor.decode(ids)`
- `.vocab_size` → `processor.get_piece_size()`

## Contract Tests

Every implementation MUST pass:

1. **Round-trip**: `decode(encode(text)) == text` for arbitrary input
2. **Empty string**: encode/decode round-trip of `""`
3. **Unicode**: emoji (😀, surrogate pairs), CJK (中文), combining diacritics (café → e+combining accent), null char (\x00)
4. **Vocab size consistency**: `len(tokenizer.encode(text))` never exceeds vocab size
5. **Idempotent**: `encode(text)` returns same result on repeated calls