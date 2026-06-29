# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""PreparationResult value object for fine-tune dataset preparation jobs."""

from __future__ import annotations

import json
from typing import Any


class PreparationResult:
    """Summary of a fine-tune dataset preparation job.

    Parameters
    ----------
    job_id : int
        The preparation job identifier.
    total : int
        Total number of input records processed.
    succeeded : int
        Number of records that passed validation and were rendered.
    failed : int
        Number of records that failed validation.
    errors : list[dict]
        Per-record error details, each containing ``row`` and ``error`` keys.
    """

    def __init__(
        self,
        job_id: int,
        total: int,
        succeeded: int,
        failed: int,
        errors: list[dict[str, Any]],
    ) -> None:
        self.job_id = job_id
        self.total = total
        self.succeeded = succeeded
        self.failed = failed
        self.errors = errors

    def to_summary_json(self) -> dict[str, Any]:
        """Serialize to a JSON-serializable dict suitable for ``summary_json``.

        Returns
        -------
        dict
            A dict with ``total``, ``succeeded``, ``failed``, and ``errors`` keys.
        """
        return {
            "total": self.total,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "errors": self.errors,
        }

    @classmethod
    def from_summary_json(cls, job_id: int, json_str: str) -> PreparationResult:
        """Reconstruct from a JSON string stored in the database.

        Parameters
        ----------
        job_id : int
            The preparation job identifier.
        json_str : str
            The JSON string previously produced by ``to_summary_json()``.

        Returns
        -------
        PreparationResult
            A new instance with deserialized values.
        """
        data = json.loads(json_str)
        return cls(
            job_id=job_id,
            total=data["total"],
            succeeded=data["succeeded"],
            failed=data["failed"],
            errors=data.get("errors", []),
        )
