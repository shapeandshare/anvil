# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Pluggable async file storage interface."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from .file_info import FileInfo


class FileStore(ABC):
    """Pluggable asynchronous file storage interface.

    Defines the contract for reading, writing, deleting, and listing
    files in an arbitrary storage backend. Implementations may target
    local filesystems, cloud object stores (S3, GCS), or other media.
    All I/O operations are asynchronous and operate on byte streams.

    Concrete subclasses must implement all abstract methods.
    """

    @abstractmethod
    async def get(self, path: str) -> AsyncIterator[bytes]:
        """Read a file as an asynchronous byte stream.

        Parameters
        ----------
        path : str
            Logical path of the file within the storage backend.

        Returns
        -------
        AsyncIterator[bytes]
            An asynchronous iterator yielding chunks of the file
            content (default chunk size is implementation-defined).
        """

    @abstractmethod
    async def put(self, path: str, stream: AsyncIterator[bytes]) -> str:
        """Write a file from an asynchronous byte stream.

        Parameters
        ----------
        path : str
            Logical path where the file will be stored.
        stream : AsyncIterator[bytes]
            An asynchronous iterator yielding chunks of data to write.

        Returns
        -------
        str
            An entity tag (etag) for the written file, usable for
            change detection (e.g. a mtime-based string).
        """

    @abstractmethod
    async def delete(self, path: str) -> None:
        """Delete a file from the storage backend.

        Parameters
        ----------
        path : str
            Logical path of the file to delete. Implementations
            must be idempotent (no error if the file does not exist).
        """

    @abstractmethod
    async def list(self, prefix: str) -> list[FileInfo]:
        """List files under a given path prefix.

        Parameters
        ----------
        prefix : str
            Directory or logical prefix to list files under.

        Returns
        -------
        list[FileInfo]
            A list of :class:`FileInfo` descriptors for every file
            found under the prefix. Returns an empty list if the
            prefix does not exist.
        """
