class Tokenizer:
    def __init__(self, docs: list[str]):
        self.uchars = sorted(set("".join(docs)))
        self.BOS = len(self.uchars)
        self.vocab_size = len(self.uchars) + 1

    def encode(self, doc: str) -> list[int]:
        return [self.BOS] + [self.uchars.index(ch) for ch in doc] + [self.BOS]

    def decode(self, ids: list[int]) -> str:
        return "".join(self.uchars[i] for i in ids if i != self.BOS)
