# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Orchestration layer for async model-import jobs."""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import aiofiles  # type: ignore[import-untyped]
from sqlalchemy.exc import IntegrityError

from ...db.models.external_model import ExternalModel
from ...db.models.model_import_job import ModelImportJob
from ...db.repositories import external_models as external_models_repo
from ...db.repositories import model_import_jobs as model_import_jobs_repo
from .._shared.import_types import ModelSourceError
from .._shared.runnable_status import RunnableStatus
from ..catalog.catalog_unavailable_error import CatalogUnavailableError
from ..catalog.model_ref import derive_catalog_name

if TYPE_CHECKING:
    from ...db.repositories.catalog_identities import CatalogIdentityRepository
    from ...db.repositories.model_asset_repository import ModelAssetRepository
    from ...storage.local import LocalFileStore
    from ..catalog.model_catalog_service import ModelCatalogService

from .._shared.model_import_job_status import ModelImportJobStatus
from .._shared.source_type import SourceType
from ..secrets.user_secret_service import UserSecretService
from .model_source import ModelSource

_HF_TOKEN_KEY = "hf_token"
"""UserSecret key for the HuggingFace Hub token."""
_HF_TOKEN_ENV = "HF_TOKEN"
"""Environment-variable fallback for the HF token."""
_DEFAULT_USER = "default"
"""Single local-mode user ID for token resolution."""

logger = logging.getLogger(__name__)

_ALLOWED_ARCHITECTURES: frozenset[str] = frozenset({"LlamaForCausalLM"})

_ACCEPTED_FORMATS: frozenset[str] = frozenset({"safetensors"})

_MODELS_DIR = Path("data/models")
"""Root directory for model artifacts on disk."""


class ModelImportService:
    """Orchestrates async model-import jobs.

    Wires source resolvers, the MLflow Model Catalog, and the catalog
    identity guard to register imported models in a unified registry.

    Parameters
    ----------
    external_model_repo : ExternalModelRepository
        Repository for ``ExternalModel`` CRUD (legacy).
    model_import_job_repo : ModelImportJobRepository
        Repository for ``ModelImportJob`` CRUD.
    sources : dict[SourceType, ModelSource]
        Registered source resolvers keyed by ``SourceType``.
    catalog_service : ModelCatalogService
        MLflow-backed catalog service for model registration.
    catalog_identity_repo : CatalogIdentityRepository
        Repository for the identity triple dedup guard.
    user_secret_service : UserSecretService | None
        Optional service for resolving HF tokens from the encrypted
        UserSecret store.
    """

    def __init__(
        self,
        external_model_repo: external_models_repo.ExternalModelRepository | None,
        model_import_job_repo: model_import_jobs_repo.ModelImportJobRepository,
        sources: dict[SourceType, ModelSource],
        catalog_service: ModelCatalogService | None = None,
        catalog_identity_repo: CatalogIdentityRepository | None = None,
        user_secret_service: UserSecretService | None = None,
    ) -> None:
        self._external_model_repo = external_model_repo
        self._model_import_job_repo = model_import_job_repo
        self._sources = sources
        self._catalog_service = catalog_service
        self._catalog_identity_repo = catalog_identity_repo
        self._user_secrets = user_secret_service

    async def submit_import(
        self,
        source: str,
        identifier: str,
        *,
        revision: str = "main",
        name: str | None = None,
    ) -> int:
        """Create an import job and return its ID (does NOT start execution).

        Parameters
        ----------
        source : str
            Source type string (``"huggingface"`` or ``"local"``).
        identifier : str
            Source-specific model identifier.
        revision : str
            Source revision. Defaults to ``"main"``.
        name : str | None
            Optional display name for the registry entry.

        Returns
        -------
        int
            The new job's primary key.

        Raises
        ------
        ValueError
            If the source type is unknown.
        """
        source_type = SourceType(source)

        if source_type not in self._sources:
            raise ValueError(f"Unknown source type: {source}")

        job = ModelImportJob(
            status=str(ModelImportJobStatus.QUEUED),
            source_type=str(source_type),
            source_identifier=identifier,
            revision=revision,
        )
        job = await self._model_import_job_repo.add(job)
        return job.id

    async def run_import(self, job_id: int) -> ModelImportJob:
        """Execute the full import workflow for a job (inline).

        Resolves metadata via ``ModelSource``, deduplicates via the
        catalog identity guard, registers in the MLflow Model Catalog,
        and writes ``config.json`` to disk.  Does NOT create
        ``ExternalModel`` rows.

        Parameters
        ----------
        job_id : int
            Import job primary key (returned by ``submit_import``).

        Returns
        -------
        ModelImportJob
            The completed or failed job entry.
        """
        job = await self._model_import_job_repo.get(job_id)
        if job is None:
            raise ValueError(f"Import job not found: {job_id}")

        job = await self._model_import_job_repo.update_status(
            job_id,
            str(ModelImportJobStatus.RESOLVING),
            started_at=datetime.now(UTC),
        )
        assert job is not None

        source_type = SourceType(job.source_type)
        source = self._sources.get(source_type)

        if source is None:
            return await self._fail_job(
                job_id,
                error_code="invalid_identifier",
                error_message=f"Unknown source type: {job.source_type}",
            )

        token = await self._resolve_token()

        try:
            metadata = await source.resolve_metadata(
                job.source_identifier, revision=job.revision, token=token
            )
        except ModelSourceError as exc:
            return await self._fail_job(
                job_id,
                error_code=exc.code,
                error_message=exc.message,
            )

        # ── Dedup via catalog identity guard ─────────────────────────
        existing = await self._catalog_identity_repo.find_by_triple(
            source_type=str(source_type),
            source_identifier=job.source_identifier,
            revision_sha=metadata.revision_sha,
        )
        if existing is not None:
            job = await self._model_import_job_repo.update_status(
                job_id,
                str(ModelImportJobStatus.COMPLETE),
                registry_model_name=existing.registry_model_name,
                registry_model_version=existing.registry_model_version,
                finished_at=datetime.now(UTC),
            )
            assert job is not None
            return job

        # ── Derive catalog name and insert identity guard row ─────────
        catalog_name = derive_catalog_name(source_type, job.source_identifier)
        try:
            identity = await self._catalog_identity_repo.add(
                source_type=str(source_type),
                source_identifier=job.source_identifier,
                revision_sha=metadata.revision_sha,
                registry_model_name=catalog_name,
            )
        except IntegrityError:
            # Race: another worker inserted this triple between our
            # find_by_triple check and add.  Resolve against the existing row.
            existing = await self._catalog_identity_repo.find_by_triple(
                source_type=str(source_type),
                source_identifier=job.source_identifier,
                revision_sha=metadata.revision_sha,
            )
            if existing is not None:
                job = await self._model_import_job_repo.update_status(
                    job_id,
                    str(ModelImportJobStatus.COMPLETE),
                    registry_model_name=existing.registry_model_name,
                    registry_model_version=existing.registry_model_version,
                    finished_at=datetime.now(UTC),
                )
                assert job is not None
                return job
            return await self._fail_job(
                job_id,
                error_code="catalog_unavailable",
                error_message=(
                    "Concurrent import conflict: could not acquire identity guard"
                ),
            )

        # ── Register in the MLflow Model Catalog ─────────────────────
        is_runnable = metadata.architecture_family in _ALLOWED_ARCHITECTURES
        runnable_reason = None
        if not is_runnable:
            runnable_reason = (
                f"Architecture {metadata.architecture_family} not in "
                f"allow-list: {{{','.join(sorted(_ALLOWED_ARCHITECTURES))}}}"
            )

        runnable_status = (
            RunnableStatus.RUNNABLE if is_runnable else RunnableStatus.TRACK_ONLY
        )
        try:
            ref = await self._catalog_service.register_external_model(
                catalog_name=catalog_name,
                display_name=metadata.display_name,
                source_type=str(source_type),
                source_identifier=job.source_identifier,
                revision_sha=metadata.revision_sha,
                architecture_family=metadata.architecture_family,
                tokenizer_family=metadata.tokenizer_family,
                license=metadata.license,
                parameter_count=metadata.parameter_count,
                runnable_status=runnable_status,
                runnable_reason=runnable_reason,
                config_json=metadata.config_json,
            )
        except CatalogUnavailableError:
            return await self._fail_job(
                job_id,
                error_code="catalog_unavailable",
                error_message="MLflow Model Registry is unavailable",
            )

        # ── Set version on the identity guard row ────────────────────
        await self._catalog_identity_repo.set_version(identity.id, ref.version)

        # ── Write config.json to disk ────────────────────────────────
        if metadata.config_json:
            config_dir = _MODELS_DIR / ref.name / str(ref.version) / "hf"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_file = config_dir / "config.json"
            async with aiofiles.open(str(config_file), "w") as f:
                await f.write(metadata.config_json)

        # ── Mark job complete with registry reference ────────────────
        job = await self._model_import_job_repo.update_status(
            job_id,
            str(ModelImportJobStatus.COMPLETE),
            registry_model_name=ref.name,
            registry_model_version=ref.version,
            finished_at=datetime.now(UTC),
        )
        assert job is not None
        return job

    async def _fail_job(
        self,
        job_id: int,
        *,
        error_code: str,
        error_message: str,
    ) -> ModelImportJob:
        """Mark a job as failed with the given error details."""
        job = await self._model_import_job_repo.update_status(
            job_id,
            str(ModelImportJobStatus.FAILED),
            error_code=error_code,
            error_message=error_message,
            finished_at=datetime.now(UTC),
        )
        assert job is not None
        return job

    async def _resolve_token(self) -> str | None:
        """Resolve the HF token via UserSecret > HF_TOKEN env var.

        Matches the precedence in ``ModelAssetService._resolve_token``
        (FR-010d): encrypted DB secret first, then environment variable.
        """
        if self._user_secrets is not None:
            return await self._user_secrets.resolve_token(
                _DEFAULT_USER, _HF_TOKEN_KEY, _HF_TOKEN_ENV
            )
        return os.environ.get(_HF_TOKEN_ENV)

    async def get_job_status(self, job_id: int) -> ModelImportJob | None:
        """Return the current state of an import job.

        Parameters
        ----------
        job_id : int
            Import job primary key.

        Returns
        -------
        ModelImportJob | None
            The job entry, or ``None`` if not found.
        """
        return await self._model_import_job_repo.get(job_id)

    async def list_jobs(self) -> Sequence[ModelImportJob]:
        """Return all import jobs, newest first.

        Returns
        -------
        Sequence[ModelImportJob]
            All import job entries.
        """
        return await self._model_import_job_repo.list_all()

    async def retry_import(self, job_id: int) -> int:
        """Re-submit a failed (or any) import job, creating a new job entry.

        Fetches the existing job's source/identifier/revision and submits
        a fresh import with the same parameters.

        Parameters
        ----------
        job_id : int
            Primary key of the job to retry.

        Returns
        -------
        int
            The new job's primary key.

        Raises
        ------
        ValueError
            If no job exists with the given ``job_id``.
        """
        job = await self._model_import_job_repo.get(job_id)
        if job is None:
            raise ValueError(f"Import job not found: {job_id}")
        return await self.submit_import(
            source=job.source_type,
            identifier=job.source_identifier,
            revision=job.revision,
        )

    async def get_external_model(self, model_id: int) -> ExternalModel | None:
        """Return an external model by primary key.

        Parameters
        ----------
        model_id : int
            ``ExternalModel`` primary key.

        Returns
        -------
        ExternalModel | None
            The model entry, or ``None`` if not found.
        """
        return await self._external_model_repo.get(model_id)

    async def _cleanup_model_assets(
        self,
        model_id: int,
        model_asset_repo: ModelAssetRepository,
        store: LocalFileStore,
    ) -> None:
        """Delete asset files associated with a model.

        Parameters
        ----------
        model_id : int
            ``ExternalModel`` primary key.
        model_asset_repo : ModelAssetRepository
            Repository for listing model assets to clean up files.
        store : LocalFileStore
            File store for deleting asset files from disk.
        """
        get_by_model = getattr(model_asset_repo, "get_by_model", None)
        if get_by_model is None:
            return
        assets = await get_by_model(model_id)
        for asset in assets:
            storage_path = getattr(asset, "storage_path", None)
            if storage_path:
                try:
                    await store.delete(storage_path)
                except Exception:
                    logger.exception("Failed to delete asset file: %s", storage_path)

    async def delete_external_model(
        self,
        model_id: int,
        *,
        model_asset_repo: ModelAssetRepository | None = None,
        store: LocalFileStore | None = None,
    ) -> None:
        """Delete an external model and clean up its asset files.

        Parameters
        ----------
        model_id : int
            ``ExternalModel`` primary key.
        model_asset_repo : ModelAssetRepository, optional
            Repository for listing model assets to clean up files.
        store : FileStore, optional
            File store for deleting asset files from disk.

        Raises
        ------
        ValueError
            If the model does not exist.
        """
        model = await self._external_model_repo.get(model_id)
        if model is None:
            raise ValueError(f"External model not found: {model_id}")

        if model_asset_repo is not None and store is not None:
            await self._cleanup_model_assets(model_id, model_asset_repo, store)

        await self._external_model_repo.delete(model_id)

    async def list_external_models(
        self,
    ) -> Sequence[ExternalModel]:
        """Return all external models, newest first.

        Returns
        -------
        Sequence[ExternalModel]
            All registered external model entries.
        """
        return await self._external_model_repo.get_all()
