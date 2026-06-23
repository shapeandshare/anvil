# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Compute backends command — enumerate available backends.

``ComputeBackendsCommand`` retrieves the list of available compute backends
via ``GET /v1/compute/backends``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class ComputeBackendsCommand(AbstractCommand):
    """List compute backends — ``GET /v1/compute/backends``."""

    async def execute(self) -> list[dict[str, object]]:
        """Retrieve all available compute backends.

        Returns
        -------
        list[dict[str, object]]
            A list of compute backend records as raw dictionaries.
        """
        data: list[dict[str, object]] = await self._transport.request(
            HttpMethod.GET, "/v1/compute/backends", response_model=list,
        )
        return data
