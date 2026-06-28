# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Exception for HTTP 401/403 authentication and authorization failures.

``AuthenticationError`` is raised when the server rejects the request due
to missing, invalid, or insufficient credentials.
"""

from __future__ import annotations

from .api_error import ApiError


class AuthenticationError(ApiError):
    """Raised on HTTP 401/403 responses.

    Parameters
    ----------
    message : str
        Human-readable error description from the server.
    status_code : int | None
        HTTP status code. Defaults to ``401``.

    Attributes
    ----------
    message : str
    status_code : int | None
    """

    def __init__(self, message: str, status_code: int | None = 401) -> None:
        super().__init__(status_code=status_code, message=message)
