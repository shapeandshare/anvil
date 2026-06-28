# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""File store abstraction for training artifacts.

All training-related data (configs, checkpoints, model artifacts) flows
through this interface. Local mode writes to disk; SaaS mode writes to S3
with deterministic key patterns and signed URLs.
"""

from abc import ABC, abstractmethod


class FileStore(ABC):
    """Abstract file storage for training artifacts.

    Training data paths in SaaS mode follow deterministic S3 key patterns:
    ``jobs/{job_id}/config.json`` — job configuration
    ``jobs/{job_id}/checkpoints/step_{N}.pt`` — periodic checkpoints (FR-045m)
    ``models/{org_id}/{run_id}/model.safetensors`` — final model artifact
    """

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
        """Generate a time-limited URL for direct download.

        Used for model artifact download in SaaS mode.
        """

    @abstractmethod
    async def signed_upload_url(self, path: str, expires_in: int = 3600) -> str:
        """Generate a time-limited URL for direct upload.

        Used for corpus/dataset upload in SaaS mode.
        """

    @abstractmethod
    async def copy(self, source: str, dest: str) -> None:
        """Copy a file from *source* to *dest* within the store."""


# Implementations:
# - LocalFileStore: pathlib.Path (in anvil/storage/, existing)
# - S3FileStore: boto3 S3 client (in anvil/_saas/implementations/, new)
