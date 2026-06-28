# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Base exception for all anvil SDK errors.

``ApiError`` is the root of the SDK's exception hierarchy. Every error
raised by the client inherits from this class, allowing callers to catch
a single base type for all API-related failures.
"""

from __future__ import annotations


class ApiError(Exception):
    """Base exception for all anvil SDK errors.

    Parameters
    ----------
    status_code : int | None
        HTTP status code that caused the error, or ``None`` for transport
        errors.
    message : str
        Human-readable error description.

    Attributes
    ----------
    status_code : int | None
    message : str
    """

    def __init__(self, status_code: int | None, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)
