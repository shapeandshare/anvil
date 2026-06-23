# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Content session validate command — validate a session.

``ContentSessionValidateCommand`` triggers validation of a content session
via ``POST /v1/content/sessions/{id}/validate``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class ContentSessionValidateCommand(AbstractCommand):
    """Validate a content session — ``POST /v1/content/sessions/{id}/validate``."""

    async def execute(self, session_id: int) -> dict[str, object]:
        """Trigger validation of a content session.

        Parameters
        ----------
        session_id : int
            The session primary key to validate.

        Returns
        -------
        dict[str, object]
            The validation result as a raw dictionary.
        """
        data: dict[str, object] = await self._transport.request(
            HttpMethod.POST,
            f"/v1/content/sessions/{session_id}/validate",
            response_model=dict,
        )
        return data
