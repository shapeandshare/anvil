# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Corpus analyze path command — analyze filesystem paths.

``CorpusAnalyzePathCommand`` analyzes a given filesystem path and returns
metadata about discoverable corpora files via ``POST /v1/corpora/analyze-path``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class CorpusAnalyzePathCommand(AbstractCommand):
    """Analyze a filesystem path — ``POST /v1/corpora/analyze-path``."""

    async def execute(self, path: str) -> dict[str, object]:
        """Analyze a filesystem path for discoverable corpus files.

        Parameters
        ----------
        path : str
            The filesystem path to analyze.

        Returns
        -------
        dict[str, object]
            Metadata about files discoverable at the given path.
        """
        body: dict[str, object] = {"path": path}
        data: dict[str, object] = await self._transport.request(
            HttpMethod.POST,
            "/v1/corpora/analyze-path",
            json=body,
            response_model=dict,
        )
        return data
