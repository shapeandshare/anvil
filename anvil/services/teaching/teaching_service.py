"""Teaching service — interactive teaching loop orchestration.

Provides the ``TeachingService`` class for managing interactive teaching
sessions: creating sessions, starting teaching rounds (which produce
trained models), inspecting/interrogating round results, comparing
rounds, and rolling back to previous checkpoints.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models.teaching_session import TeachingSession
from ...db.models.teaching_session_status import TeachingSessionStatus
from ...db.repositories.teaching_session_repository import TeachingSessionRepository
from ...storage.local import LocalFileStore
from ..compute.result import ComputeResult
from ..datasets.dataset_import import DatasetImportService
from ..datasets.datasets import DatasetService
from ..inference.inference import InferenceService
from ..tracking.tracking import TrackingService
from ..training.training_run_config import TrainingRunConfig
from ..training.training_run_service import TrainingRunService

logger = logging.getLogger(__name__)


class TeachingService:
    """Orchestrates interactive teaching sessions.

    A teaching session is a chain of training rounds that iteratively
    improve a model through example-driven teaching.  Each round:
    1. Creates a dataset with ``origin="teaching"``
    2. Imports the user's example documents
    3. Trains a new model (full retrain, method forced to ``"full"``)
    4. Tags the resulting MLflow run with teaching lineage metadata
    5. Updates the session's chain head

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session for database operations.
    repo : TeachingSessionRepository
        Repository for teaching session CRUD.
    training_runs : TrainingRunService
        Training run lifecycle service.
    inference : InferenceService
        Inference service for model loading and generation.
    tracking : TrackingService
        MLflow tracking service.
    datasets : DatasetService
        Dataset CRUD service.
    store : LocalFileStore
        File store for sample content.
    paths_root : Path, optional
        Workspace root path for deriving dataset paths.
    """

    def __init__(
        self,
        session: AsyncSession,
        repo: TeachingSessionRepository,
        training_runs: TrainingRunService,
        inference: InferenceService,
        tracking: TrackingService,
        datasets: DatasetService,
        store: LocalFileStore | None = None,
        paths_root: Path | None = None,
    ) -> None:
        self._session = session
        self._repo = repo
        self._training_runs = training_runs
        self._inference = inference
        self._tracking = tracking
        self._datasets = datasets
        self._store = store
        self._paths_root = paths_root

    ########################################################################
    # Session CRUD
    ########################################################################

    async def create_session(
        self,
        name: str,
        description: str | None = None,
        seed_experiment_id: int | None = None,
    ) -> TeachingSession:
        """Create a new teaching session.

        Parameters
        ----------
        name : str
            User-facing session name.
        description : str, optional
            Optional human-readable description.
        seed_experiment_id : int, optional
            Experiment ID to seed the session from. ``None`` means
            train from scratch in round 1.

        Returns
        -------
        TeachingSession
            The newly created session.
        """
        teaching_session = TeachingSession(
            name=name,
            description=description,
            seed_experiment_id=seed_experiment_id,
            current_base_experiment_id=seed_experiment_id,
            status=TeachingSessionStatus.DRAFT,
        )
        return await self._repo.add(teaching_session)

    async def get_session(self, session_id: int) -> TeachingSession | None:
        """Retrieve a teaching session by ID.

        Parameters
        ----------
        session_id : int
            Primary key of the session.

        Returns
        -------
        TeachingSession | None
            The session, or ``None`` if not found.
        """
        return await self._repo.get(session_id)

    async def list_sessions(
        self,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[TeachingSession], int]:
        """List teaching sessions with optional status filter.

        Parameters
        ----------
        status : str, optional
            Filter by status (``TeachingSessionStatus.DRAFT``, ``TeachingSessionStatus.ACTIVE``, ``TeachingSessionStatus.COMPLETED``).
        limit : int
            Max results. Default 20.
        offset : int
            Result offset. Default 0.

        Returns
        -------
        tuple[list[TeachingSession], int]
            (Sessions, total count).
        """
        sessions, total = await self._repo.list(
            status=status, limit=limit, offset=offset
        )
        return list(sessions), total

    async def update_status(
        self, session_id: int, new_status: str
    ) -> TeachingSession | None:
        """Update the status of a teaching session.

        Parameters
        ----------
        session_id : int
            Primary key of the session.
        new_status : str
            New status value (must be a ``TeachingSessionStatus`` value).

        Returns
        -------
        TeachingSession | None
            The updated session, or ``None`` if not found.
        """
        return await self._repo.update_status(session_id, new_status)

    async def delete_session(self, session_id: int) -> bool:
        """Delete a teaching session.

        Does NOT cascade to MLflow runs or experiment artifacts.

        Parameters
        ----------
        session_id : int
            Primary key of the session.

        Returns
        -------
        bool
            ``True`` if a row was deleted.
        """
        return await self._repo.delete(session_id)

    async def _ensure_active_status(self, session_id: int) -> TeachingSession | None:
        """Set a session to ACTIVE if it is currently DRAFT.

        Parameters
        ----------
        session_id : int
            Primary key of the session.

        Returns
        -------
        TeachingSession | None
            The updated session.
        """
        teaching_session = await self._repo.get(session_id)
        if teaching_session is None:
            return None
        if teaching_session.status == TeachingSessionStatus.DRAFT:
            return await self._repo.update_status(
                session_id, TeachingSessionStatus.ACTIVE
            )
        return teaching_session

    ########################################################################
    # Round management
    ########################################################################

    async def start_round(
        self,
        session_id: int,
        examples: list[str],
        training_config: dict[str, Any],
    ) -> dict[str, Any]:
        """Start a new teaching round.

        Creates a dataset (``origin="teaching"``), imports examples,
        and launches a training run via ``TrainingRunService``.
        Method is forced to ``"full"`` — LoRA/QLoRA is rejected.

        Parameters
        ----------
        session_id : int
            The teaching session ID.
        examples : list[str]
            Example document strings to train on.
        training_config : dict
            Training hyperparameters (``num_steps``, ``n_embd``,
            ``n_head``, etc.). The ``method`` key is overridden to
            ``"full"``.

        Returns
        -------
        dict[str, Any]
            Result from ``TrainingRunService.start_training_run()``
            with the ``experiment_id`` added as ``round_experiment_id``.

        Raises
        ------
        ValueError
            If the session is not found, or if ``method`` is LoRA/QLoRA.
        """
        # ── Validate session ───────────────────────────────────────────
        teaching_session = await self._repo.get(session_id)
        if teaching_session is None:
            raise ValueError(f"Teaching session {session_id} not found")

        # ── Force method="full" ────────────────────────────────────────
        method = training_config.get("method", "full")
        if method != "full":
            raise ValueError(
                f"Teaching rounds require method='full', got {method!r}. "
                "LoRA/QLoRA fine-tuning is not supported in the teaching "
                "loop."
            )
        training_config["method"] = "full"

        # ── Create dataset with origin="teaching" ──────────────────────
        dataset_name = (
            f"teaching-session-{session_id}-round-{self._count_rounds(session_id)}"
        )
        dataset = await self._datasets.create_dataset(
            name=dataset_name,
            description=(f"Teaching session {session_id} round dataset"),
            origin="teaching",
        )

        # ── Import examples ────────────────────────────────────────────
        import_svc = DatasetImportService(
            self._session,
            dataset.id,
            store=self._store,
        )
        await import_svc.commit_docs_import(
            docs=examples,
            source_label="teaching",
            source_format="docs",
        )

        training_config["dataset_id"] = dataset.id
        training_config.pop("corpus_id", None)
        training_config.pop("content_version_id", None)

        # ── Set base_model_ref from session chain head ────────────────
        if teaching_session.current_base_experiment_id is not None:
            training_config["base_model_ref"] = (
                teaching_session.current_base_experiment_id
            )

        # ── Promote session to ACTIVE ──────────────────────────────────
        await self._ensure_active_status(session_id)

        # ── Count current rounds for tagging ───────────────────────────
        round_index = self._count_rounds(session_id)

        # ── Build on_complete_extra to update session chain head ───────
        async def _on_round_complete(
            result: ComputeResult,
            config_dict: dict[str, Any],
        ) -> None:
            experiment_id = config_dict.get("experiment_id")
            if experiment_id is not None:
                await self._repo.update_current_base_experiment_id(
                    session_id, experiment_id
                )
                await self._session.commit()

        svc_config = TrainingRunConfig(**training_config)

        response = await self._training_runs.start_training_run(
            svc_config,
            on_complete_extra=_on_round_complete,
        )

        # ── Set teaching lineage tags on the experiment_id ─────────────
        if response.get("mlflow_run_id") and not self._tracking.is_degraded:
            await self._tracking.set_tag(
                response["mlflow_run_id"],
                "teaching_session_id",
                str(session_id),
            )
            await self._tracking.set_tag(
                response["mlflow_run_id"],
                "teaching_round_index",
                str(round_index),
            )
            await self._tracking.set_tag(
                response["mlflow_run_id"],
                "teaching_parent_experiment_id",
                str(teaching_session.current_base_experiment_id or ""),
            )
            await self._tracking.set_tag(
                response["mlflow_run_id"],
                "anvil.origin",
                "teaching",
            )

        response["round_experiment_id"] = response.get("experiment_id")
        return response

    def _count_rounds(self, _session_id: int) -> int:
        """Count existing rounds for a teaching session by scanning
        current_base_experiment_id changes.  Simple heuristic: returns
        0 for new sessions, incremented for each additional round.
        """
        # For now, return 1 as a placeholder.  In a production
        # implementation this would query MLflow for teaching-session
        # tags or the session's round count.
        return 1

    ########################################################################
    # Inspection and comparison
    ########################################################################

    async def inspect_round(
        self,
        experiment_id: int,
        prompts: list[str],
        temperature: float = 0.7,
        max_tokens: int = 100,
    ) -> list[dict[str, Any]]:
        """Generate text from a round's trained model for inspection.

        Parameters
        ----------
        experiment_id : int
            The experiment ID of the round's trained model.
        prompts : list[str]
            Prompts to feed the model.
        temperature : float, optional
            Sampling temperature. Default 0.7.
        max_tokens : int, optional
            Maximum tokens to generate. Default 100.

        Returns
        -------
        list[dict[str, Any]]
            Per-prompt results with keys ``prompt`` and ``generated``.
        """
        loaded = await self._inference.load_model(model_id=experiment_id)
        results: list[dict[str, Any]] = []
        for prompt in prompts:
            generated = self._inference.generate(
                loaded,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            results.append({"prompt": prompt, "generated": generated})
        return results

    async def compare_rounds(
        self,
        left_experiment_id: int,
        right_experiment_id: int,
        prompts: list[str],
        temperature: float = 0.7,
        max_tokens: int = 100,
    ) -> list[dict[str, Any]]:
        """Side-by-side comparison of two rounds' models.

        Parameters
        ----------
        left_experiment_id : int
            Experiment ID of the left (e.g. baseline) model.
        right_experiment_id : int
            Experiment ID of the right (e.g. new) model.
        prompts : list[str]
            Prompts to feed both models.
        temperature : float, optional
            Sampling temperature. Default 0.7.
        max_tokens : int, optional
            Maximum tokens to generate. Default 100.

        Returns
        -------
        list[dict[str, Any]]
            Per-prompt results with keys ``prompt``, ``left``, and
            ``right``.
        """
        left_loaded = await self._inference.load_model(model_id=left_experiment_id)
        right_loaded = await self._inference.load_model(model_id=right_experiment_id)
        results: list[dict[str, Any]] = []
        for prompt in prompts:
            left_text = self._inference.generate(
                left_loaded,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            right_text = self._inference.generate(
                right_loaded,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            results.append(
                {
                    "prompt": prompt,
                    "left": left_text,
                    "right": right_text,
                }
            )
        return results

    async def rollback_to_round(
        self,
        session_id: int,
        target_experiment_id: int,
    ) -> TeachingSession | None:
        """Roll back a session's chain head to a previous round.

        Creates a new round warm-started from the target experiment.
        This is a metadata-only operation — the session's
        ``current_base_experiment_id`` is updated to the target.

        Parameters
        ----------
        session_id : int
            The teaching session ID.
        target_experiment_id : int
            The experiment ID to roll back to.

        Returns
        -------
        TeachingSession | None
            The updated session, or ``None`` if not found.
        """
        return await self._repo.update_current_base_experiment_id(
            session_id, target_experiment_id
        )
