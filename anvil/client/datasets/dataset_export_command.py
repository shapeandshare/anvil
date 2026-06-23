# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Dataset export command — download a dataset.

``DatasetExportCommand`` exports a dataset from the server via
``GET /v1/datasets/{id}/export?format=`` and optionally saves it to disk.
"""

from __future__ import annotations

from pathlib import Path

from .._shared.abstract_command import AbstractCommand


class DatasetExportCommand(AbstractCommand):
    """Export a dataset — ``GET /v1/datasets/{id}/export?format=`` → download."""

    async def execute(
        self,
        dataset_id: int,
        *,
        fmt: str = "txt",
        dest: str | None = None,
    ) -> bytes | str | None:
        """Export a dataset, optionally saving to a local file.

        Parameters
        ----------
        dataset_id : int
            The dataset's primary key.
        fmt : str, optional
            Export format (e.g. ``"txt"``, ``"jsonl"``). Defaults to ``"txt"``.
        dest : str | None, optional
            Local file path to save the export to. If ``None``, returns raw
            bytes.

        Returns
        -------
        bytes | str | None
            Raw ``bytes`` if no ``dest`` given; ``str`` path if ``dest`` was
            provided; ``None`` on empty response.
        """
        if dest:
            result: Path | bytes = await self._transport.download(
                f"/v1/datasets/{dataset_id}/export",
                params={"format": fmt},
                dest=Path(dest),
            )
            return str(result)
        data: bytes = await self._transport.download(
            f"/v1/datasets/{dataset_id}/export",
            params={"format": fmt},
        )
        return data
