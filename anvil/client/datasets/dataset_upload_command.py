# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Dataset upload command — upload a file into a dataset.

``DatasetUploadCommand`` uploads a local file into a dataset on the server via
``POST /v1/datasets/upload`` (multipart).
"""

from __future__ import annotations

from pathlib import Path

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod

try:
    import aiofiles
except ImportError:
    aiofiles = None  # type: ignore[assignment]


class DatasetUploadCommand(AbstractCommand):
    """Upload a file into a dataset — ``POST /v1/datasets/upload`` (multipart)."""

    async def execute(self, dataset_id: int, file_path: str) -> dict[str, object]:
        """Upload a local file into a dataset.

        Parameters
        ----------
        dataset_id : int
            The target dataset's primary key.
        file_path : str
            Path to the local file to upload.

        Returns
        -------
        dict[str, object]
            The server response confirming the upload.
        """
        if aiofiles is None:
            msg = "aiofiles is required for file uploads. Install with: pip install aiofiles"
            raise ImportError(msg)

        async with aiofiles.open(file_path, "rb") as f:
            content = await f.read()
        filename = Path(file_path).name
        data: dict[str, object] = await self._transport.request(
            HttpMethod.POST,
            "/v1/datasets/upload",
            files={"file": (filename, content, "text/plain")},
            response_model=dict,
        )
        return data
