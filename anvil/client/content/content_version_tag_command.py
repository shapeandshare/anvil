# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Content version tag command — tag a version.

``ContentVersionTagCommand`` applies a tag to a specific content version via
``POST /v1/content/versions/{id}/tag``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class ContentVersionTagCommand(AbstractCommand):
    """Tag a content version — ``POST /v1/content/versions/{id}/tag``."""

    async def execute(self, version_id: int, tag: str) -> dict[str, object]:
        """Apply a tag to a content version.

        Parameters
        ----------
        version_id : int
            The version primary key.
        tag : str
            The tag label to apply (e.g. ``"production"``, ``"staging"``).

        Returns
        -------
        dict[str, object]
            The updated version record as a raw dictionary.
        """
        body: dict[str, object] = {"tag": tag}
        data: dict[str, object] = await self._transport.request(
            HttpMethod.POST,
            f"/v1/content/versions/{version_id}/tag",
            json=body,
            response_model=dict,
        )
        return data
