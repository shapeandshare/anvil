# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""SSE event type enumeration for the anvil client SDK.

``StreamEventType`` enumerates the Server-Sent Events the anvil server
emits during training runs and content ingestion workflows.
"""

from enum import StrEnum


class StreamEventType(StrEnum):
    """Type of SSE event from the anvil server.

    Attributes
    ----------
    METRICS : str
        Per-step training metrics with ``step`` and ``loss`` (``"metrics"``).
    COMPLETE : str
        Training run completed successfully (``"complete"``).
    ERROR : str
        Training run failed with an error (``"error"``).
    DIVERGENCE : str
        Loss diverged beyond recovery (``"divergence"``).
    HEARTBEAT : str
        Liveness signal — no payload data (``"heartbeat"``).
    EXPORT_ERROR : str
        Safetensors export failed (``"export_error"``).
    """

    METRICS = "metrics"
    COMPLETE = "complete"
    ERROR = "error"
    DIVERGENCE = "divergence"
    HEARTBEAT = "heartbeat"
    EXPORT_ERROR = "export_error"
