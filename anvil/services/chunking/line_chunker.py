"""Line-based chunking strategy.

This module provides ``LineAsDocChunker``, a chunker that splits input
text by newline boundaries and returns one chunk per non-empty line.
Empty lines are discarded; each returned line is stripped of leading
and trailing whitespace.

Use this chunker when the input is structured as line-oriented records
(e.g. logs, config files, CSV rows without embedded newlines) and each
line can be processed independently.
"""

from .base import Chunker


class LineAsDocChunker(Chunker):
    """Chunker that splits text into one chunk per non-empty line.

    Each line is stripped of leading/trailing whitespace.  Lines that
    become empty after stripping are omitted from the result.
    """

    def chunk(self, text: str) -> list[str]:
        """Split ``text`` into stripped, non-empty line chunks.

        Parameters
        ----------
        text : str
            The input text to split by newlines. May contain empty
            lines or be empty itself.

        Returns
        -------
        list of str
            A list of stripped non-empty lines.  Returns an empty list
            when ``text`` is empty or contains only whitespace lines.
        """
        return [line.strip() for line in text.splitlines() if line.strip()]
