# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Asset download job status enumeration for async lifecycle."""

from __future__ import annotations

from enum import StrEnum


class AssetDownloadJobStatus(StrEnum):
    """Lifecycle state of an async asset-download job.

    Attributes
    ----------
    QUEUED : str
        Job created; not yet started (``"queued"``).
    DOWNLOADING : str
        Asset download in progress (``"downloading"``).
    COMPLETE : str
        All assets downloaded and verified (``"complete"``).
    FAILED : str
        Job failed with a typed error code (``"failed"``).
    """

    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETE = "complete"
    FAILED = "failed"
