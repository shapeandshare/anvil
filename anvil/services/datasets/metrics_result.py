"""Metrics result data class — aggregate statistics for a curated dataset.

Provides the ``MetricsResult`` class used by ``DatasetCurationService``
to report dataset metrics such as sample count, character distribution,
and duplicate statistics.
"""


class MetricsResult:
    """Aggregate statistics for a curated dataset.

    Attributes
    ----------
    sample_count : int
        Number of active (non-removed) samples.
    total_chars : int
        Total character count across all active samples.
    estimated_tokens : int
        Estimated token count (``total_chars // 4``).
    vocabulary_size : int
        Number of unique content hashes.
    length_distribution : dict
        Character length distribution with keys ``"min"``, ``"max"``,
        ``"mean"``, ``"median"``.
    duplicate_count : int
        Number of samples whose content hash appears more than once.
    """

    def __init__(
        self,
        sample_count: int,
        total_chars: int,
        estimated_tokens: int,
        vocabulary_size: int,
        length_distribution: dict,
        duplicate_count: int,
    ):
        """Initialise the metrics result.

        Parameters
        ----------
        sample_count : int
            Active sample count.
        total_chars : int
            Total characters across all active samples.
        estimated_tokens : int
            Estimated token count.
        vocabulary_size : int
            Unique content hash count.
        length_distribution : dict
            Length distribution with ``"min"``, ``"max"``, ``"mean"``,
            ``"median"`` keys.
        duplicate_count : int
            Count of duplicate content hashes.
        """
        self.sample_count = sample_count
        self.total_chars = total_chars
        self.estimated_tokens = estimated_tokens
        self.vocabulary_size = vocabulary_size
        self.length_distribution = length_distribution
        self.duplicate_count = duplicate_count
