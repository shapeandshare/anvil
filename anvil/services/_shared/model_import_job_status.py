# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Import job status enumeration for async model-import lifecycle."""

from __future__ import annotations

from enum import StrEnum


class ModelImportJobStatus(StrEnum):
    """Lifecycle state of an asynchronous model-import job.

    Attributes
    ----------
    QUEUED : str
        Job created; not yet started (``"queued"``).
    RESOLVING : str
        Metadata resolution is in progress (``"resolving"``).
    COMPLETE : str
        Metadata resolved and ``ExternalModel`` entry created (``"complete"``).
    FAILED : str
        Resolution failed with a typed error code (``"failed"``).
    """

    QUEUED = "queued"
    RESOLVING = "resolving"
    COMPLETE = "complete"
    FAILED = "failed"