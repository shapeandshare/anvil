# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Exception for HTTP 422 unprocessable-entity responses.

``ValidationError`` is raised when the server rejects the request payload
due to schema or constraint violations.
"""

from __future__ import annotations

from .api_error import ApiError


class ValidationError(ApiError):
    """Raised on HTTP 422 responses.

    Parameters
    ----------
    message : str
        Human-readable error description from the server.
    status_code : int | None
        HTTP status code. Defaults to ``422``.

    Attributes
    ----------
    message : str
    status_code : int | None
    """

    def __init__(self, message: str, status_code: int | None = 422) -> None:
        super().__init__(status_code=status_code, message=message)
