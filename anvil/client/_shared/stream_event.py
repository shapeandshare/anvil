# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""SSE streaming event model for the anvil client SDK.

``StreamEvent`` represents a single typed Server-Sent Event received from
the anvil server during streaming operations such as training runs and
content ingestion workflows.
"""

from __future__ import annotations

from pydantic import BaseModel

from anvil.client._shared.stream_event_type import StreamEventType


class StreamEvent(BaseModel):
    """Typed SSE event from the anvil server.

    Parameters
    ----------
    type : StreamEventType
        Parsed from the ``event:`` SSE line.
    data : dict[str, object]
        Parsed from the ``data:`` JSON line.
    """

    type: StreamEventType
    data: dict[str, object]
