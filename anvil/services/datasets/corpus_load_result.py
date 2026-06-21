# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Corpus load result data class — outcome of a corpus ingestion operation.

Provides the ``CorpusLoadResult`` class used by ``CorpusLoader`` to report
metadata about ingested files, total chunk count, language distribution,
and ingestion errors.
"""


class CorpusLoadResult:
    """Result container for a corpus ingestion operation.

    Attributes
    ----------
    files : list[dict]
        Metadata for each ingested file.
    total_docs : int
        Total number of chunked documents across all files.
    language_map : dict[str, int]
        Mapping from language label to file count.
    errors : list[str]
        Error messages encountered during ingestion.
    """

    def __init__(
        self,
        files: list[dict],
        total_docs: int,
        language_map: dict[str, int],
        errors: list[str],
    ):
        """Initialise the load result.

        Parameters
        ----------
        files : list[dict]
            Metadata for each ingested file.
        total_docs : int
            Total chunk count across all files.
        language_map : dict[str, int]
            Language label to file count mapping.
        errors : list[str]
            Ingestion error messages.
        """
        self.files = files
        self.total_docs = total_docs
        self.language_map = language_map
        self.errors = errors
