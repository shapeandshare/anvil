# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Asset download service contract — interface for downloading and storing model assets.

This is the core service contract for model asset acquisition. It defines the
operations that the API layer calls and that background workers execute.
"""

from __future__ import annotations

from typing import Protocol


class AssetDownloadService(Protocol):
    """Downloads and manages model asset files from external sources.

    Each call to ``submit_download`` creates an ``AssetDownloadJob``,
    pre-resolves the file list for the model into ``ModelAsset`` rows,
    and spawns an async background worker to download each file.
    The caller polls via ``get_job_status`` to track progress.
    """

    async def submit_download(
        self,
        external_model_id: int,
        *,
        token: str | None = None,
    ) -> int:
        """Submit an asset download request for the given model.

        Creates a new ``AssetDownloadJob`` (status=QUEUED) and pre-creates
        ``ModelAsset`` rows for the resolved file list (config, tokenizer,
        weight shards). Returns the job ID for status polling.

        Parameters
        ----------
        external_model_id : int
            FK to the model to download assets for.
        token : str | None
            HuggingFace auth token override. Falls back to UserSecret > env var.

        Returns
        -------
        int
            The ``AssetDownloadJob.id`` for status polling.

        Raises
        ------
        ModelNotFoundError
            ``external_model_id`` does not exist.
        ModelAssetAlreadyAvailableError
            Assets already downloaded and marked available.
        DuplicateDownloadError
            A download job for this model is already in progress (model-level lock).
        UnsupportedFormatError
            The model resolves to a format not in the allow-list (FR-030).
        """
        ...

    async def get_job_status(self, job_id: int) -> dict[str, object]:
        """Return current job status.

        Returns a dict with keys matching the ``AssetDownloadJob`` shape,
        plus aggregate progress::

            {
                "job_id": int,
                "status": str,          # AssetDownloadJobStatus value
                "started_at": str | None,
                "finished_at": str | None,
                "error_code": str | None,
                "error_message": str | None,
                "total_assets": int,    # total ModelAsset rows
                "completed_assets": int,# AVAILABLE count
                "assets": [             # per-asset detail
                    {
                        "id": int,
                        "asset_type": str,
                        "filename": str,
                        "status": str,          # ModelAssetStatus value
                        "size_bytes": int,
                        "downloaded_bytes": int,
                        "sha256": str | None,
                    }
                ],
            }
        """
        ...

    async def run_download(self, job_id: int) -> None:
        """Execute a queued download job (called by the async background worker).

        This is the core method that:
        1. Sets job status to DOWNLOADING.
        2. Resolves the HuggingFace file list via ``HfApi.list_repo_files``.
        3. Pre-creates ``ModelAsset`` rows (one per file).
        4. Iterates each asset: downloads stream → computes SHA-256 → stores
           via ``FileStore.put()`` → updates ``ModelAsset`` status.
        5. Sets job status to COMPLETE (or FAILED on fatal error).

        Runs inside an ``asyncio.create_task`` with its own DB session.
        """
        ...


class ModelAssetQueryService(Protocol):
    """Returns model asset metadata (no download, no write)."""

    async def get_assets_for_model(
        self, external_model_id: int
    ) -> list[dict[str, object]]:
        """Return all ModelAsset rows for a model (read-only)."""
        ...
