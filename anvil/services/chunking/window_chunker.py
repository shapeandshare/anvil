"""Fixed-size sliding-window chunking strategy.

This module provides ``FixedSizeWindowChunker``, a chunker that splits
input text into fixed-length windows that advance by a configurable
stride.  Overlap between adjacent windows is controlled as a fraction
of the window size, enabling continuous-feature-style segmentation for
downstream processing such as embedding or language-model inference.

Use this chunker when downstream models have a fixed context window
and you want to cover the input text densely with overlapping segments.
"""

from .base import Chunker


class FixedSizeWindowChunker(Chunker):
    """Chunker that splits text into fixed-size windows with overlap.

    Windows are produced by sliding a fixed-size ``block_size`` window
    across the text.  The stride between consecutive windows is
    ``block_size * (1 - overlap)``, so ``overlap=0.0`` yields disjoint
    windows and ``overlap=0.75`` yields quarters of new content per
    window.  The final window may be shorter than ``block_size`` if the
    text length is not a multiple of the stride.
    """

    def __init__(self, block_size: int = 16, overlap: float = 0.5):
        """Configure the sliding-window chunker.

        Parameters
        ----------
        block_size : int
            The maximum number of characters per chunk.  Must be at
            least 1.  Defaults to ``16``.
        overlap : float
            Fraction of adjacent windows that overlap, in ``[0.0, 1.0)``.
            ``0.0`` produces disjoint windows with no overlap; values
            close to ``1.0`` produce near-identical consecutive chunks.
            Defaults to ``0.5`` (50 % overlap).

        Raises
        ------
        ValueError
            If ``overlap`` is outside the allowed range, or if
            ``block_size`` is less than 1.
        """
        if not 0.0 <= overlap < 1.0:
            raise ValueError(f"overlap must be in [0.0, 1.0), got {overlap}")
        if block_size < 1:
            raise ValueError(f"block_size must be >= 1, got {block_size}")
        self._block_size = block_size
        self._overlap = overlap

    def chunk(self, text: str) -> list[str]:
        """Split ``text`` into fixed-size windows with configured overlap.

        Parameters
        ----------
        text : str
            The input text to window. May be empty.

        Returns
        -------
        list of str
            A list of window strings, each of at most ``block_size``
            characters.  Returns an empty list when ``text`` is empty.
        """
        if not text:
            return []
        stride = max(1, int(self._block_size * (1 - self._overlap)))
        chunks = []
        start = 0
        while start < len(text):
            end = start + self._block_size
            chunks.append(text[start:end])
            start += stride
        return chunks
