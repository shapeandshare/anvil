# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Fine-tune dataset status enumeration for async preparation lifecycle."""

from __future__ import annotations

from enum import StrEnum


class FineTuneDatasetStatus(StrEnum):
    """Lifecycle state of an asynchronous fine-tune dataset preparation job.

    Attributes
    ----------
    PREPARING : str
        Preparation job is in progress (``"preparing"``).
    READY : str
        Preparation completed successfully; records are rendered and tracked
        (``"ready"``).
    FAILED : str
        Preparation terminated with a fatal error before or during processing
        (``"failed"``).
    """

    PREPARING = "preparing"
    READY = "ready"
    FAILED = "failed"
