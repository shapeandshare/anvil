# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Content corpus list command — list all content corpora.

``ContentCorpusListCommand`` fetches all versioned content corpora from the
server via ``GET /v1/content/corpora``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class ContentCorpusListCommand(AbstractCommand):
    """List content corpora — ``GET /v1/content/corpora``."""

    async def execute(self) -> list[dict[str, object]]:
        """Fetch all versioned content corpora from the server.

        Returns
        -------
        list[dict[str, object]]
            A list of content corpus records as raw dictionaries.
        """
        data: list[dict[str, object]] = await self._transport.request(
            HttpMethod.GET,
            "/v1/content/corpora",
            response_model=list,
        )
        return data
