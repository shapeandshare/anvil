# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Corpus scan result data class — statistics from a directory scan.

Provides the ``CorpusScanResult`` class used by ``CorpusLoader`` to report
file counts, byte sizes, and language distribution from scanning a directory
without reading file contents.
"""


class CorpusScanResult:
    """Result container for a corpus directory scan (no file contents read).

    Attributes
    ----------
    file_count : int
        Number of files matched.
    total_bytes : int
        Total size of all matched files in bytes.
    sizes : list[int]
        Individual file sizes in bytes.
    language_map : dict[str, int]
        Mapping from language label to file count.
    language_sizes : dict[str, list[int]]
        Mapping from language label to list of individual file sizes.
    """

    def __init__(
        self,
        file_count: int,
        total_bytes: int,
        sizes: list[int],
        language_map: dict[str, int],
        language_sizes: dict[str, list[int]] | None = None,
    ):
        """Initialise the scan result.

        Parameters
        ----------
        file_count : int
            Number of files matched.
        total_bytes : int
            Total size of all matched files in bytes.
        sizes : list[int]
            Individual file sizes in bytes.
        language_map : dict[str, int]
            Language label to file count mapping.
        language_sizes : dict[str, list[int]], optional
            Language label to list of individual file sizes.
            Defaults to an empty dict.
        """
        self.file_count = file_count
        self.total_bytes = total_bytes
        self.sizes = sizes
        self.language_map = language_map
        self.language_sizes = language_sizes or {}
