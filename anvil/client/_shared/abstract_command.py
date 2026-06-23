# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Abstract base command for the anvil client SDK.

Every concrete command maps to exactly one (resource, verb) API operation.
Commands own their URL template and DTO types; they delegate HTTP I/O to the
shared ``Transport``.  No command touches ``httpx`` primitives directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AbstractCommand(ABC):
    """Base class for all SDK domain commands.

    Each concrete subclass implements exactly one API operation.
    Subclasses own their HTTP method, URL path template, request DTO
    type, and response DTO type — but delegate the actual HTTP I/O
    to the shared ``Transport``.

    Parameters
    ----------
    transport : Transport
        The SDK's shared transport instance. Must not be ``None``.
    """

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    @abstractmethod
    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Perform the single API operation this command represents.

        Returns a typed result (DTO or list/AsyncIterator thereof).
        Never returns a raw ``dict``.
        """
