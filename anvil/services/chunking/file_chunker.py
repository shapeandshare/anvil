# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""File-as-document chunking strategy.

This module provides ``FileAsDocChunker``, a trivial chunker that
treats the entire input text as a single monolithic chunk.  It is
useful when downstream processing benefits from full-document context
and no splitting is desired.

Use this chunker as a baseline / identity strategy in comparisons or
when text length is guaranteed to fit within downstream limits.
"""

from .base import Chunker


class FileAsDocChunker(Chunker):
    """Chunker that returns the entire input as one chunk.

    This is a pass-through strategy: the whole ``text`` string is
    wrapped in a single-element list unless the input is empty, in
    which case an empty list is returned.
    """

    def chunk(self, text: str) -> list[str]:
        """Return the full ``text`` as a single chunk.

        Parameters
        ----------
        text : str
            The input text to wrap as a chunk. May be empty.

        Returns
        -------
        list of str
            A list containing ``text`` as its only element, or an
            empty list when ``text`` is empty.
        """
        if not text:
            return []
        return [text]
