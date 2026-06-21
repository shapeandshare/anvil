# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Curation result data class — outcome of a curation operation.

Provides the ``CurationResult`` class used by ``DatasetCurationService``
to report the result of deduplication, length filtering, or sample deletion.
"""


class CurationResult:
    """Outcome of a curation operation on a dataset.

    Attributes
    ----------
    operation_id : int
        Database ID of the recorded curation operation.
    samples_removed : int
        Number of samples removed by the operation.
    samples_before : int
        Active sample count before the operation.
    samples_after : int
        Active sample count after the operation.
    """

    def __init__(
        self,
        operation_id: int,
        samples_removed: int,
        samples_before: int,
        samples_after: int,
    ):
        """Initialise the curation result.

        Parameters
        ----------
        operation_id : int
            Database ID of the curation operation.
        samples_removed : int
            Number of samples removed.
        samples_before : int
            Active sample count before the operation.
        samples_after : int
            Active sample count after the operation.
        """
        self.operation_id = operation_id
        self.samples_removed = samples_removed
        self.samples_before = samples_before
        self.samples_after = samples_after
