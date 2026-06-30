# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Service for async model asset download and lifecycle management."""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime

import aiofiles  # type: ignore[import-untyped]

from ...db.models.asset_download_job import AssetDownloadJob
from ...db.models.model_asset import ModelAsset, ModelAssetStatus, ModelAssetType
from ...db.repositories.asset_download_job_repository import AssetDownloadJobRepository
from ...db.repositories.external_models import ExternalModelRepository
from ...db.repositories.model_asset_repository import ModelAssetRepository
from ...storage.interface import FileStore
from .._shared.asset_download_job_status import AssetDownloadJobStatus
from .._shared.asset_state import AssetState
from .._shared.import_types import ModelSourceError
from ..secrets.user_secret_service import UserSecretService
from .format_detector import check_weight_format
from .hf_source import HfHubSource

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 65536
_HF_TOKEN_KEY = "hf_token"
_HF_TOKEN_ENV = "HF_TOKEN"
_DEFAULT_USER = "default"


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
        hf_source: HfHubSource | None = None,
        user_secret_service: UserSecretService | None = None,
    ) -> None:
        self._asset_repo = model_asset_repo
        self._job_repo = asset_download_job_repo
        self._model_repo = external_model_repo
        self._store = store
        self._hf_source = hf_source
        self._user_secrets = user_secret_service

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
        completed = sum(
            1 for a in assets if a.status == str(ModelAssetStatus.AVAILABLE)
        )

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

        Resolves the upstream file list, pre-creates one ``ModelAsset`` row per
        file, then downloads each file through the injected ``HfHubSource``,
        verifies weight-file format (FR-033), computes a SHA-256 content hash
        (FR-012a), and streams it into the ``FileStore`` seam (FR-010a/FR-011)
        at ``models/{model_id}/assets/{sha256}/{filename}`` (FR-011a).

        On full success the model's ``asset_availability`` becomes
        ``ASSETS_AVAILABLE``; on any failure it reverts to ``METADATA_ONLY``
        and the job is marked ``FAILED`` (FR-012b / SC-006).

        Parameters
        ----------
        job_id : int
            Download job primary key (returned by ``submit_download``).
        """
        job = await self._job_repo.get(job_id)
        if job is None:
            logger.error("Download job %d not found", job_id)
            return

        await self._job_repo.update_status(
            job_id,
            str(AssetDownloadJobStatus.DOWNLOADING),
            started_at=datetime.now(UTC),
        )

        model = await self._model_repo.get(job.external_model_id)
        if model is None:
            await self._job_repo.update_status(
                job_id,
                str(AssetDownloadJobStatus.FAILED),
                error_code="model_not_found",
                error_message=f"Model {job.external_model_id} not found",
                finished_at=datetime.now(UTC),
            )
            return

        model_id = job.external_model_id
        await self._model_repo.update_fields(
            model_id, asset_availability=str(AssetState.ASSETS_PENDING)
        )

        if self._hf_source is None:
            await self._fail_and_revert(
                job_id,
                model_id,
                "missing_extra",
                "Asset download source is not configured",
            )
            return

        token = await self._resolve_token()
        identifier = model.source_identifier
        revision = model.revision_sha or "main"

        try:
            file_list = await self._hf_source.list_asset_files(
                identifier, revision=revision, token=token
            )
        except ModelSourceError as exc:
            await self._fail_and_revert(job_id, model_id, exc.code, exc.message)
            return

        if not file_list:
            await self._fail_and_revert(
                job_id, model_id, "no_assets", "No downloadable assets found"
            )
            return

        created: list[ModelAsset] = []
        for entry in file_list:
            asset = await self._asset_repo.add(
                ModelAsset(
                    external_model_id=model_id,
                    asset_type=entry["asset_type"],
                    filename=entry["filename"],
                    size_bytes=0,
                    format=_format_for(entry["asset_type"], entry["filename"]),
                )
            )
            created.append(asset)

        all_ok = True
        for asset in created:
            if not await self._download_one(
                asset, identifier, revision, token, model_id
            ):
                all_ok = False

        if all_ok:
            await self._model_repo.update_fields(
                model_id, asset_availability=str(AssetState.ASSETS_AVAILABLE)
            )
            await self._job_repo.update_status(
                job_id,
                str(AssetDownloadJobStatus.COMPLETE),
                finished_at=datetime.now(UTC),
            )
        else:
            await self._fail_and_revert(
                job_id,
                model_id,
                "download_failed",
                "One or more asset downloads failed",
            )

    ####################################################################
    # Internal helpers
    ####################################################################

    async def _download_one(
        self,
        asset: ModelAsset,
        identifier: str,
        revision: str,
        token: str | None,
        model_id: int,
    ) -> bool:
        """Download, verify, hash, and store a single asset. Returns success."""
        assert self._hf_source is not None
        await self._asset_repo.update_status(
            asset.id, str(ModelAssetStatus.DOWNLOADING)
        )
        tmp_path: str | None = None
        try:
            tmp_path = await self._hf_source.download_asset_to_path(
                identifier, asset.filename, revision=revision, token=token
            )

            if asset.asset_type == str(ModelAssetType.WEIGHTS):
                header = await self._read_header(tmp_path)
                check_weight_format(asset.filename, header)

            sha256, size = await self._hash_and_size(tmp_path)
            storage_path = f"models/{model_id}/assets/{sha256}/{asset.filename}"
            await self._store.put(storage_path, self._file_stream(tmp_path))

            await self._asset_repo.update_progress(asset.id, size)
            await self._asset_repo.update_status(
                asset.id,
                str(ModelAssetStatus.AVAILABLE),
                sha256=sha256,
                storage_path=storage_path,
                size_bytes=size,
            )
            return True
        except ModelSourceError as exc:
            logger.warning(
                "Rejected asset %s (%s): %s",
                asset.filename,
                exc.code,
                exc.message,
            )
            await self._asset_repo.update_status(
                asset.id, str(ModelAssetStatus.UNAVAILABLE)
            )
            return False
        except Exception:
            logger.exception("Failed to download asset %d", asset.id)
            await self._asset_repo.update_status(
                asset.id, str(ModelAssetStatus.UNAVAILABLE)
            )
            return False
        finally:
            if tmp_path is not None:
                _cleanup_temp(tmp_path)

    async def _resolve_token(self) -> str | None:
        """Resolve the HF token via UserSecret > HF_TOKEN env var (FR-010d)."""
        if self._user_secrets is not None:
            return await self._user_secrets.resolve_token(
                _DEFAULT_USER, _HF_TOKEN_KEY, _HF_TOKEN_ENV
            )
        return os.environ.get(_HF_TOKEN_ENV)

    async def _fail_and_revert(
        self,
        job_id: int,
        model_id: int,
        error_code: str,
        error_message: str,
    ) -> None:
        """Mark the job FAILED and revert the model to METADATA_ONLY (SC-006)."""
        await self._model_repo.update_fields(
            model_id, asset_availability=str(AssetState.METADATA_ONLY)
        )
        await self._job_repo.update_status(
            job_id,
            str(AssetDownloadJobStatus.FAILED),
            error_code=error_code,
            error_message=error_message,
            finished_at=datetime.now(UTC),
        )

    async def _read_header(self, path: str, num_bytes: int = 8) -> bytes:
        """Read the first ``num_bytes`` of a file for format detection."""
        async with aiofiles.open(path, "rb") as handle:
            header: bytes = await handle.read(num_bytes)
            return header

    async def _hash_and_size(self, path: str) -> tuple[str, int]:
        """Stream a file to compute its SHA-256 hash and byte size."""
        hasher = hashlib.sha256()
        size = 0
        async with aiofiles.open(path, "rb") as handle:
            while chunk := await handle.read(_CHUNK_SIZE):
                hasher.update(chunk)
                size += len(chunk)
        return hasher.hexdigest(), size

    async def _file_stream(self, path: str) -> AsyncIterator[bytes]:
        """Yield a file's contents in chunks for streaming to the store."""
        async with aiofiles.open(path, "rb") as handle:
            while chunk := await handle.read(_CHUNK_SIZE):
                yield chunk


def _format_for(asset_type: str, filename: str) -> str:
    """Return the format string for an asset based on type and filename."""
    if asset_type == str(ModelAssetType.WEIGHTS):
        return "safetensors"
    if filename.endswith(".json"):
        return "json"
    return "tokenizer"


def _cleanup_temp(path: str) -> None:
    """Remove the ``anvil_hf_`` temporary directory holding a downloaded file."""
    current = os.path.dirname(os.path.abspath(path))
    while current and current != os.path.dirname(current):
        if os.path.basename(current).startswith("anvil_hf_"):
            shutil.rmtree(current, ignore_errors=True)
            return
        current = os.path.dirname(current)
