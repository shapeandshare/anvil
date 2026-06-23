# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Datasets client — domain aggregator for dataset lifecycle operations.

``DatasetsClient`` provides a single entry point for all dataset operations:
list, get, create, update, delete, upload, export, and search. It delegates
each operation to its corresponding command class.
"""

from __future__ import annotations

import builtins

from .._shared.transport import Transport
from .dataset_create_command import DatasetCreateCommand
from .dataset_delete_command import DatasetDeleteCommand
from .dataset_export_command import DatasetExportCommand
from .dataset_get_command import DatasetGetCommand
from .dataset_list_command import DatasetListCommand
from .dataset_update_command import DatasetUpdateCommand
from .dataset_upload_command import DatasetUploadCommand


class DatasetsClient:
    """Dataset lifecycle operations.

    Aggregates all dataset commands behind a single facade. Each public method
    maps to one server API operation.

    Parameters
    ----------
    transport : Transport
        The shared SDK transport instance.
    """

    def __init__(self, transport: Transport) -> None:
        self._list_cmd = DatasetListCommand(transport)
        self._get_cmd = DatasetGetCommand(transport)
        self._create_cmd = DatasetCreateCommand(transport)
        self._update_cmd = DatasetUpdateCommand(transport)
        self._delete_cmd = DatasetDeleteCommand(transport)
        self._upload_cmd = DatasetUploadCommand(transport)
        self._export_cmd = DatasetExportCommand(transport)

    async def list(self, query: str | None = None) -> builtins.list[dict[str, object]]:
        """List all datasets.

        Parameters
        ----------
        query : str | None, optional
            Optional search query to filter datasets.

        Returns
        -------
        List[dict[str, object]]
            A list of dataset records.
        """
        return await self._list_cmd.execute(query=query)

    async def get(self, dataset_id: int) -> dict[str, object]:
        """Get a single dataset by its primary key.

        Parameters
        ----------
        dataset_id : int
            The dataset's primary key.

        Returns
        -------
        dict[str, object]
            The dataset record.
        """
        return await self._get_cmd.execute(dataset_id)

    async def create(
        self,
        name: str,
        description: str | None = None,
    ) -> dict[str, object]:
        """Create a new dataset.

        Parameters
        ----------
        name : str
            The dataset name.
        description : str | None, optional
            An optional description.

        Returns
        -------
        dict[str, object]
            The newly created dataset record.
        """
        return await self._create_cmd.execute(name, description=description)

    async def update(
        self,
        dataset_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> dict[str, object]:
        """Update an existing dataset.

        Parameters
        ----------
        dataset_id : int
            The dataset's primary key.
        name : str | None, optional
            New name. Omit to leave unchanged.
        description : str | None, optional
            New description. Omit to leave unchanged.

        Returns
        -------
        dict[str, object]
            The updated dataset record.
        """
        return await self._update_cmd.execute(
            dataset_id,
            name=name,
            description=description,
        )

    async def delete(
        self,
        dataset_id: int,
        *,
        force: bool = False,
    ) -> dict[str, object]:
        """Delete a dataset.

        Parameters
        ----------
        dataset_id : int
            The dataset's primary key.
        force : bool, optional
            Force deletion even with associated resources. Defaults to
            ``False``.

        Returns
        -------
        dict[str, object]
            A response payload confirming the deletion.
        """
        return await self._delete_cmd.execute(dataset_id, force=force)

    async def upload(
        self,
        dataset_id: int,
        file_path: str,
    ) -> dict[str, object]:
        """Upload a file into a dataset.

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
        return await self._upload_cmd.execute(dataset_id, file_path)

    async def export(
        self,
        dataset_id: int,
        *,
        fmt: str = "txt",
        dest: str | None = None,
    ) -> bytes | str | None:
        """Export a dataset.

        Parameters
        ----------
        dataset_id : int
            The dataset's primary key.
        fmt : str, optional
            Export format (e.g. ``"txt"``, ``"jsonl"``). Defaults to
            ``"txt"``.
        dest : str | None, optional
            Local file path to save to. If ``None``, returns raw bytes.

        Returns
        -------
        bytes | str | None
            Raw ``bytes``, ``str`` path if ``dest`` was given, or ``None``.
        """
        return await self._export_cmd.execute(
            dataset_id,
            fmt=fmt,
            dest=dest,
        )

    async def search(self, query: str) -> builtins.list[dict[str, object]]:
        """Search datasets by query string.

        This is a convenience alias for ``list(query=query)``.

        Parameters
        ----------
        query : str
            Search query string.

        Returns
        -------
        List[dict[str, object]]
            Matching dataset records.
        """
        return await self._list_cmd.execute(query=query)
