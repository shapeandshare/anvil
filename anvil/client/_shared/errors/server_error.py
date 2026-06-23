# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Exception for HTTP 5xx server-error responses.

``ServerError`` is raised when the server encounters an internal failure.
The server's original error message is preserved for diagnostics.
"""

from __future__ import annotations

from .api_error import ApiError


class ServerError(ApiError):
    """Raised on HTTP 5xx responses. Preserves the server's error message.

    Parameters
    ----------
    message : str
        Human-readable error description from the server.
    status_code : int | None
        HTTP status code. Defaults to ``500``.

    Attributes
    ----------
    message : str
    status_code : int | None
    """

    def __init__(self, message: str, status_code: int | None = 500) -> None:
        super().__init__(status_code=status_code, message=message)
