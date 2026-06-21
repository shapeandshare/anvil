# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Ingestion session and import job status enumeration."""

from enum import StrEnum


class IngestStatus(StrEnum):
    """Status of an ingestion session or import job.

    Attributes
    ----------
    OPEN : str
        Session is open and accepting staged content (``"open"``).
    VALIDATING : str
        Session is running validation gates (``"validating"``).
    ACCEPTED : str
        Session content has passed gates and been folded into the
        canonical corpus (``"accepted"``).
    FAILED : str
        Session content failed a blocking gate or was abandoned
        (``"failed"``).
    """

    OPEN = "open"
    VALIDATING = "validating"
    ACCEPTED = "accepted"
    FAILED = "failed"
