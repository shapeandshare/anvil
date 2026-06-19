"""Parsed sample data class — a single sample ready for import.

Provides the ``ParsedSample`` class used by ``DatasetImportService``
to represent a parsed text sample before it is committed to the database.
"""

import hashlib


class ParsedSample:
    """A single parsed sample ready for import.

    Attributes
    ----------
    text : str
        The sample text content.
    index : int
        Sequential index within the import batch.
    content_hash : str
        SHA-256 hex digest of the UTF-8 encoded text.
    length : int
        Character length of the text.
    """

    def __init__(self, text: str, index: int):
        """Initialise a parsed sample.

        Parameters
        ----------
        text : str
            The sample text content.
        index : int
            Sequential index within the import batch.
        """
        self.text = text
        self.index = index
        self.content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self.length = len(text)
