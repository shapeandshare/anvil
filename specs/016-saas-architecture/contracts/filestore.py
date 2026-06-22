# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""File store abstraction for application data.

All user-facing data (corpora, datasets, models, exports) flows through
this interface. Local mode writes to disk; SaaS mode writes to S3.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator


class FileStore(ABC):
    """Abstract file storage for application data."""

    @abstractmethod
    async def read(self, path: str) -> bytes:
        """Read the contents of a file at *path*."""

    @abstractmethod
    async def write(self, path: str, data: bytes) -> None:
        """Write *data* to *path*, creating parent directories as needed."""

    @abstractmethod
    async def delete(self, path: str) -> None:
        """Delete the file at *path*."""

    @abstractmethod
    async def list(self, prefix: str) -> list[str]:
        """List all file paths under *prefix*."""

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check whether a file exists at *path*."""

    @abstractmethod
    async def signed_download_url(self, path: str, expires_in: int = 3600) -> str:
        """Generate a time-limited URL for direct download."""

    @abstractmethod
    async def signed_upload_url(self, path: str, expires_in: int = 3600) -> str:
        """Generate a time-limited URL for direct upload."""

    @abstractmethod
    async def copy(self, source: str, dest: str) -> None:
        """Copy a file from *source* to *dest* within the store."""


# Implementations:
# - LocalFileStore: pathlib.Path (existing, refactored to implement this interface)
# - S3FileStore: boto3 S3 client (new, in anvil/_saas/implementations/)
