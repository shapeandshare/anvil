# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Content session create command — create a content session.

``ContentSessionCreateCommand`` creates a new content session on the server
via ``POST /v1/content/sessions``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class ContentSessionCreateCommand(AbstractCommand):
    """Create a content session — ``POST /v1/content/sessions``."""

    async def execute(
        self,
        corpus_id: int,
        name: str | None = None,
    ) -> dict[str, object]:
        """Create a new content session on the server.

        Parameters
        ----------
        corpus_id : int
            The content corpus primary key to associate the session with.
        name : str | None, optional
            An optional name for the session.

        Returns
        -------
        dict[str, object]
            The newly created session record as a raw dictionary.
        """
        body: dict[str, object] = {"corpus_id": corpus_id}
        if name is not None:
            body["name"] = name
        data: dict[str, object] = await self._transport.request(
            HttpMethod.POST,
            "/v1/content/sessions",
            json=body,
            response_model=dict,
        )
        return data
