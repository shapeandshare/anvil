# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Service for async model asset download and lifecycle management."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime

from ...db.models.asset_download_job import AssetDownloadJob
from ...db.models.model_asset import ModelAsset, ModelAssetStatus
from ...db.repositories.asset_download_job_repository import AssetDownloadJobRepository
from ...db.repositories.external_models import ExternalModelRepository
from ...db.repositories.model_asset_repository import ModelAssetRepository
from ...storage.interface import FileStore
from .._shared.asset_download_job_status import AssetDownloadJobStatus
from .._shared.asset_state import AssetState

logger = logging.getLogger(__name__)


class DuplicateDownloadError(Exception):
    """Raised when a download for a model is already in progress."""


class ModelAssetAlreadyAvailableError(Exception):
    """Raised when model assets are already downloaded and available."""


class ModelNotFoundError(Exception):
    """Raised when an external model ID does not exist."""


class ModelAssetService:
    """Orchestrates async model asset download jobs.

    The ``submit_download`` / ``run_download`` pair mirrors the
    ``ModelImportService`` pattern — the API layer calls ``submit_download``
    and fires ``asyncio.create_task``, which calls ``run_download`` with
    its own session.
    """

    def __init__(
        self,
        model_asset_repo: ModelAssetRepository,
        asset_download_job_repo: AssetDownloadJobRepository,
        external_model_repo: ExternalModelRepository,
        store: FileStore,
        hf_source: object | None = None,
    ) -> None:
        self._asset_repo = model_asset_repo
        self._job_repo = asset_download_job_repo
        self._model_repo = external_model_repo
        self._store = store
        # HF source set externally for late binding
        self._hf_source = hf_source

    async def submit_download(
        self,
        external_model_id: int,
    ) -> int:
        """Submit an async asset download request for a model.

        Parameters
        ----------
        external_model_id : int
            FK to the external model to download assets for.

        Returns
        -------
        int
            The ``AssetDownloadJob.id`` for status polling.

        Raises
        ------
        ModelNotFoundError
            Model does not exist.
        ModelAssetAlreadyAvailableError
            Model assets already downloaded.
        DuplicateDownloadError
            A download job for this model is already in flight.
        """
        model = await self._model_repo.get(external_model_id)
        if model is None:
            raise ModelNotFoundError(f"External model not found: {external_model_id}")

        if model.asset_availability == str(AssetState.ASSETS_AVAILABLE):
            raise ModelAssetAlreadyAvailableError(
                f"Assets already available for model {external_model_id}"
            )

        existing_jobs = await self._job_repo.get_active_for_model(external_model_id)
        if existing_jobs:
            raise DuplicateDownloadError(
                f"A download job is already in progress for model "
                f"{external_model_id}"
            )

        job = AssetDownloadJob(
            external_model_id=external_model_id,
            status=str(AssetDownloadJobStatus.QUEUED),
        )
        job = await self._job_repo.add(job)
        return job.id

    async def get_job_status(self, job_id: int) -> dict[str, object] | None:
        """Return the current status and aggregate progress of a download job.

        Parameters
        ----------
        job_id : int
            Download job primary key.

        Returns
        -------
        dict | None
            Job status dict with aggregate progress, or ``None`` if not found.
        """
        job = await self._job_repo.get(job_id)
        if job is None:
            return None

        assets = await self._asset_repo.get_by_model(job.external_model_id)
        total = len(assets)
        completed = sum(1 for a in assets if a.status == "available")

        return {
            "job_id": job.id,
            "status": job.status,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            "error_code": job.error_code,
            "error_message": job.error_message,
            "total_assets": total,
            "completed_assets": completed,
            "assets": [
                {
                    "id": a.id,
                    "asset_type": a.asset_type,
                    "filename": a.filename,
                    "status": a.status,
                    "size_bytes": a.size_bytes,
                    "downloaded_bytes": a.downloaded_bytes,
                    "sha256": a.sha256,
                }
                for a in assets
            ],
        }

    async def get_assets_for_model(
        self, external_model_id: int
    ) -> Sequence[ModelAsset]:
        """Return all ``ModelAsset`` rows for a model (read-only).

        Parameters
        ----------
        external_model_id : int
            FK to ``ExternalModel``.

        Returns
        -------
        Sequence[ModelAsset]
            The model's asset rows.
        """
        return await self._asset_repo.get_by_model(external_model_id)

    async def run_download(self, job_id: int) -> None:
        """Execute a queued download job (called by the async background worker).

        Sets the job to ``DOWNLOADING``, transitions the model to
        ``ASSETS_PENDING``, then iterates each pending ``ModelAsset`` row,
        downloading the file and storing it through the ``FileStore`` seam.

        Parameters
        ----------
        job_id : int
            Download job primary key (returned by ``submit_download``).
        """
        job = await self._job_repo.get(job_id)
        if job is None:
            logger.error("Download job %d not found", job_id)
            return

        # Mark the job as started.
        job = await self._job_repo.update_status(
            job_id,
            str(AssetDownloadJobStatus.DOWNLOADING),
            started_at=datetime.now(UTC),
        )
        if job is None:
            return

        model_id = job.external_model_id

        # Mark the model as having assets in progress.
        model = await self._model_repo.get(model_id)
        if model is not None:
            await self._model_repo.update_fields(
                model_id,
                asset_availability=str(AssetState.ASSETS_PENDING),
            )

        # Retrieve pre-created (or create) asset rows.
        assets = await self._asset_repo.get_by_model(model_id)
        if not assets:
            logger.warning(
                "No assets to download for model %d (job %d)",
                model_id,
                job_id,
            )

        all_ok = True
        for asset_inner in assets:
            try:
                updated = await self._asset_repo.update_status(
                    asset_inner.id,
                    str(ModelAssetStatus.DOWNLOADING),
                )
                if updated is None:
                    continue

                # TODO(T016): actual HF download logic.
                # In the current state, this stub skips each asset.
                # Implementation requires:
                # 1. Resolve file list via HfApi.list_repo_files()
                # 2. For each file: download stream → SHA-256 hash →
                #    FileStore.put() → update status → progress tracking
                # 3. Handle resumability via downloaded_bytes + Range header
                # 4. Use hf_source._huggingface_hub_available() guard

                await self._asset_repo.update_progress(updated.id, updated.size_bytes)
                await self._asset_repo.update_status(
                    updated.id,
                    str(ModelAssetStatus.AVAILABLE),
                    sha256="stub_hash_unimplemented",
                    storage_path=(
                        f"models/{model_id}/assets/stub/" f"{updated.filename}"
                    ),
                )
            except Exception:
                logger.exception(
                    "Failed to download asset %d (job %d)",
                    asset_inner.id,
                    job_id,
                )
                await self._asset_repo.update_status(
                    asset_inner.id,
                    str(ModelAssetStatus.UNAVAILABLE),
                )
                all_ok = False

        # Re-check all assets for final availability.
        if all_ok and assets:
            model = await self._model_repo.get(model_id)
            if model is not None:
                await self._model_repo.update_fields(
                    model_id,
                    asset_availability=str(AssetState.ASSETS_AVAILABLE),
                )
            await self._job_repo.update_status(
                job_id,
                str(AssetDownloadJobStatus.COMPLETE),
                finished_at=datetime.now(UTC),
            )
        else:
            await self._job_repo.update_status(
                job_id,
                str(AssetDownloadJobStatus.FAILED),
                error_code="download_failed",
                error_message="One or more asset downloads failed",
                finished_at=datetime.now(UTC),
            )
