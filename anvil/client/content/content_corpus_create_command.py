# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Content corpus create command — create a content corpus.

``ContentCorpusCreateCommand`` creates a new versioned content corpus on the
server via ``POST /v1/content/corpora``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class ContentCorpusCreateCommand(AbstractCommand):
    """Create a content corpus — ``POST /v1/content/corpora``."""

    async def execute(
        self, name: str, description: str | None = None,
    ) -> dict[str, object]:
        """Create a new versioned content corpus on the server.

        Parameters
        ----------
        name : str
            The corpus name.
        description : str | None, optional
            An optional description for the corpus.

        Returns
        -------
        dict[str, object]
            The newly created content corpus record as a raw dictionary.
        """
        body: dict[str, object] = {"name": name}
        if description is not None:
            body["description"] = description
        data: dict[str, object] = await self._transport.request(
            HttpMethod.POST, "/v1/content/corpora", json=body, response_model=dict,
        )
        return data
