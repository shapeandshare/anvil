class Tokenizer:
    def __init__(self, docs: list[str]):
        self.uchars = sorted(set("".join(docs)))
        self.BOS = len(self.uchars)
        self.vocab_size = len(self.uchars) + 1

    def encode(self, doc: str) -> list[int]:
        return [self.BOS] + [self.uchars.index(ch) for ch in doc] + [self.BOS]

    def decode(self, ids: list[int]) -> str:
        return "".join(self.uchars[i] for i in ids if i != self.BOS)


class Vocabulary:
    """Reconstructable from a chars list (no docs required).

    Matches Tokenizer encode/decode semantics exactly (BOS-wrapped).
    """

    def __init__(self, chars: list[str]):
        self.chars = chars
        self.bos_id = len(chars)
        self.vocab_size = len(chars) + 1
        self._char_to_id = {ch: i for i, ch in enumerate(chars)}

    @classmethod
    def from_chars(cls, chars: list[str]) -> "Vocabulary":
        return cls(chars)

    def encode(self, text: str) -> list[int]:
        return [self.bos_id] + [self._char_to_id[ch] for ch in text] + [self.bos_id]

    def decode(self, ids: list[int]) -> str:
        return "".join(self.chars[i] for i in ids if i != self.bos_id)
