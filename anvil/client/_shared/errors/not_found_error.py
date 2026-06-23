# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Exception for HTTP 404 resource-not-found responses.

``NotFoundError`` is raised when the requested resource does not exist on
the server.
"""

from __future__ import annotations

from .api_error import ApiError


class NotFoundError(ApiError):
    """Raised on HTTP 404 responses.

    Parameters
    ----------
    message : str
        Human-readable error description from the server.
    status_code : int | None
        HTTP status code. Defaults to ``404``.

    Attributes
    ----------
    message : str
    status_code : int | None
    """

    def __init__(self, message: str, status_code: int | None = 404) -> None:
        super().__init__(status_code=status_code, message=message)
