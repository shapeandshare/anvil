# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Abstract interface for text chunking strategies.

This module defines the ``Chunker`` abstract base class that all chunker
implementations must subclass. The contract is minimal — a single
``chunk`` method that accepts a string and returns a list of string
chunks — so that chunking strategies can be composed, tested, and
swapped independently of the consumers that depend on them.

A chunker is expected to be stateless with respect to the text it
processes: calling ``chunk`` multiple times with the same input should
produce the same output.
"""

from abc import ABC, abstractmethod


class Chunker(ABC):
    """Abstract base class for all chunker implementations.

    Subclasses must implement :meth:`chunk` to define their specific
    splitting strategy.  The base class enforces no constraints on
    chunk size, count, or content; each subclass is free to encode its
    own policy (e.g. line-based, fixed-size window, file-as-document).

    A chunker should be stateless with respect to the input text so
    that instances can be reused across multiple documents.
    """

    @abstractmethod
    def chunk(self, text: str) -> list[str]:
        """Split ``text`` into a list of chunk strings.

        Parameters
        ----------
        text : str
            The full input text to be chunked. May be empty.

        Returns
        -------
        list of str
            A (potentially empty) list of string chunks. Each element
            represents one logical document fragment produced by the
            subclass's splitting strategy.
        """
        ...
