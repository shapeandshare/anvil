"""Character-level tokenizer for the anvil training framework.

Builds a vocabulary from a list of text documents, mapping characters
to integer IDs. The tokenizer wraps all sequences with a BOS (beginning
of sequence) token and filters out-of-vocabulary characters during
encoding and decoding.
"""


class Tokenizer:
    """Character-level tokenizer built from a corpus of documents.

    Extracts all unique characters from the provided documents and
    assigns each an integer ID. A BOS (beginning of sequence) token
    at index ``len(uchars)`` marks sequence boundaries.

    This is a simple character-level tokenizer suitable for small-scale
    experiments. It does not support subword tokenization or special
    tokens beyond BOS.
    """

    def __init__(self, docs: list[str]):
        """Initialize the tokenizer from a list of documents.

        Parameters
        ----------
        docs : list of str
            Documents to derive the character vocabulary from. All
            unique characters across the documents are collected
            and sorted.
        """
        self.uchars = sorted(set("".join(docs)))
        self.BOS = len(self.uchars)
        self.vocab_size = len(self.uchars) + 1

    def encode(self, doc: str) -> list[int]:
        """Encode a document into a sequence of token IDs.

        Prepends and appends a BOS token. Characters not in the
        vocabulary are silently skipped.

        Parameters
        ----------
        doc : str
            The input document string.

        Returns
        -------
        list of int
            Token IDs including the surrounding BOS markers.
        """
        return (
            [self.BOS]
            + [self.uchars.index(ch) for ch in doc if ch in self.uchars]
            + [self.BOS]
        )

    def decode(self, ids: list[int]) -> str:
        """Decode a sequence of token IDs back into a string.

        BOS tokens are silently omitted from the output.

        Parameters
        ----------
        ids : list of int
            Token ID sequence to decode.

        Returns
        -------
        str
            The reconstructed string (BOS markers excluded).
        """
        return "".join(self.uchars[i] for i in ids if i != self.BOS)
