# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Exception for HTTP 429 rate-limit responses.

``RateLimitError`` is raised when the client has exceeded the server's
rate limit. The ``retry_after`` attribute carries the server-recommended
wait time parsed from the ``Retry-After`` header.
"""

from __future__ import annotations

from .api_error import ApiError


class RateLimitError(ApiError):
    """Raised on HTTP 429 responses.

    Parameters
    ----------
    message : str
        Human-readable error description from the server.
    retry_after : float | None
        Seconds to wait before retrying, parsed from the ``Retry-After``
        header.
    status_code : int | None
        HTTP status code. Defaults to ``429``.

    Attributes
    ----------
    message : str
    retry_after : float | None
    status_code : int | None
    """

    def __init__(
        self,
        message: str,
        retry_after: float | None = None,
        status_code: int | None = 429,
    ) -> None:
        self.retry_after = retry_after
        super().__init__(status_code=status_code, message=message)
