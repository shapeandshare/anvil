# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Generic response envelope for the anvil REST API.

``Response[T]`` wraps every server response in a consistent ``{"data": ...,
"error": ...}`` envelope that clients can pattern-match on.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class Response(BaseModel, Generic[T]):
    """Generic wrapper for the anvil ``{"data": ..., "error": ...}`` envelope.

    Parameters
    ----------
    data : T | None
        The response payload. ``None`` only on error envelopes.
    error : str | None
        Server error message. ``None`` on success.
    """

    model_config = ConfigDict(extra="forbid")

    data: T | None = None
    error: str | None = None
