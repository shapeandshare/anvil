# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Orchestration layer for async model-import jobs."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime

from ...db.models.external_model import ExternalModel
from ...db.models.model_import_job import ModelImportJob
from ...db.repositories import external_models as external_models_repo
from ...db.repositories import model_import_jobs as model_import_jobs_repo
from .._shared.import_types import (
    AssetState,
    ModelImportJobStatus,
    ModelSourceError,
    RunnableStatus,
    SourceType,
)
from .model_source import ModelSource

logger = logging.getLogger(__name__)

_ALLOWED_ARCHITECTURES: frozenset[str] = frozenset({"LlamaForCausalLM"})

_ACCEPTED_FORMATS: frozenset[str] = frozenset({"safetensors"})


class ModelImportService:
    """Orchestrates async model-import jobs.

    Wires a ``ModelSource`` registry to the ``ExternalModel`` and
    ``ModelImportJob`` repositories.  The ``submit_import`` / ``run_import``
    pair supports both inline execution (CLI) and fire-and-forget background
    execution (API routes with their own session).

    Parameters
    ----------
    external_model_repo : ExternalModelRepository
        Repository for ``ExternalModel`` CRUD.
    model_import_job_repo : ModelImportJobRepository
        Repository for ``ModelImportJob`` CRUD.
    sources : dict[SourceType, ModelSource]
        Registered source resolvers keyed by ``SourceType``.
    """

    def __init__(
        self,
        external_model_repo: external_models_repo.ExternalModelRepository,
        model_import_job_repo: model_import_jobs_repo.ModelImportJobRepository,
        sources: dict[SourceType, ModelSource],
    ) -> None:
        self._external_model_repo = external_model_repo
        self._model_import_job_repo = model_import_job_repo
        self._sources = sources

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

        Call this synchronously (CLI) or via ``asyncio.create_task``
        (API) with its **own** session.  Updates the job through its
        lifecycle and creates the ``ExternalModel`` entry on success.

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

        try:
            metadata = await source.resolve_metadata(
                job.source_identifier, revision=job.revision
            )
        except ModelSourceError as exc:
            return await self._fail_job(
                job_id,
                error_code=exc.code,
                error_message=exc.message,
            )

        existing = await self._external_model_repo.find_by_source(
            source_type=str(source_type),
            source_identifier=job.source_identifier,
            revision_sha=metadata.revision_sha,
        )
        if existing is not None:
            job = await self._model_import_job_repo.update_status(
                job_id,
                str(ModelImportJobStatus.COMPLETE),
                external_model_id=existing.id,
                finished_at=datetime.now(UTC),
            )
            assert job is not None
            return job

        is_runnable = metadata.architecture_family in _ALLOWED_ARCHITECTURES
        runnable_reason = None
        if not is_runnable:
            runnable_reason = (
                f"Architecture {metadata.architecture_family} not in "
                f"allow-list: {{{','.join(sorted(_ALLOWED_ARCHITECTURES))}}}"
            )

        model = ExternalModel(
            display_name=metadata.display_name,
            source_type=str(source_type),
            source_identifier=job.source_identifier,
            architecture_family=metadata.architecture_family,
            parameter_count=metadata.parameter_count,
            license=metadata.license,
            tokenizer_family=metadata.tokenizer_family,
            revision_sha=metadata.revision_sha,
            runnable_status=(
                str(RunnableStatus.RUNNABLE)
                if is_runnable
                else str(RunnableStatus.TRACK_ONLY)
            ),
            runnable_reason=runnable_reason,
            asset_availability=str(AssetState.METADATA_ONLY),
            config_json=metadata.config_json,
        )
        model = await self._external_model_repo.add(model)

        job = await self._model_import_job_repo.update_status(
            job_id,
            str(ModelImportJobStatus.COMPLETE),
            external_model_id=model.id,
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
