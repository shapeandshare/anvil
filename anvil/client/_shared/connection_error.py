# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Exception for transport-layer connectivity failures.

``ConnectionError`` is raised when the SDK cannot establish a connection
to the server. This is **not** an HTTP error — it wraps transport-level
failures such as DNS resolution issues, refused connections, or network
timeouts.
"""

from __future__ import annotations

from .api_error import ApiError


class ConnectionError(ApiError):  # pylint: disable=redefined-builtin
    """Raised when the transport layer cannot reach the server.

    Not an HTTP error — wraps ``httpx`` connectivity failures.

    Parameters
    ----------
    message : str
        Description of the connectivity failure.

    Attributes
    ----------
    message : str
    status_code : None
        Always ``None`` for transport errors.
    """

    def __init__(self, message: str) -> None:
        super().__init__(status_code=None, message=message)
