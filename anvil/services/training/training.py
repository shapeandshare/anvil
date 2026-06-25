# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Training orchestration service — manages training lifecycle and SSE events.

Provides the ``TrainingService`` class for coordinating training runs:
reserving run IDs, loading documents, resolving compute backends,
dispatching training, and streaming progress via asyncio queues.
"""

import asyncio
import json
import threading
import time
from collections.abc import Awaitable, Callable
from typing import Any

# Side-effect imports: each module registers its backends at module level.
from ..compute import local_stdlib_backend  # noqa: F401 — registers local-stdlib
from ..compute import local_torch_backend  # noqa: F401 — registers local-torch
from ..compute import modal_backend  # noqa: F401 — registers modal

# ── compute backend framework ──────────────────────────────────────────
from ..compute.compute_backend_result import ComputeBackendResult
from ..compute.registry import get_backend
from ..compute.resolve import resolve_backend
from ..compute.result import ComputeResult
from ..compute.training_engine import TrainingEngine
from .divergence_error import DivergenceError
from .step_metrics import StepMetrics
from .stop_requested import StopRequested
from .throughput import ThroughputTracker, classify_divergence

_TRAINING_QUEUE_MAXSIZE = 1024
"""int: Maximum number of events buffered per-run in the SSE event queue.

When the queue is full, new events are silently dropped to prevent
unbounded memory growth when the SSE consumer is slow or disconnected.
"""


async def _enqueue_or_drop(
    queue: asyncio.Queue[dict[str, object]], event: dict[str, object]
) -> None:
    """Put an event into the queue, silently dropping if the queue is full.

    Designed to be submitted via ``asyncio.run_coroutine_threadsafe`` from
    a worker thread.  Runs on the event loop thread where ``put_nowait``
    is safe to call.

    Parameters
    ----------
    queue : asyncio.Queue
        The target SSE event queue.
    event : dict
        The event payload to enqueue.
    """
    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:
        pass


class TrainingService:
    """Orchestrates training runs: doc loading, backend dispatch, SSE streaming.

    Maintains per-run asyncio queues for SSE progress events and
    threading events for stop signalling. Supports local
    (:class:`TrainingEngine.STDLIB` / :class:`TrainingEngine.TORCH`)
    and remote (:class:`ComputeBackendResult.MODAL`) compute backends.
    """

    def __init__(self) -> None:
        """Initialise the training service with empty run state."""
        self._queues: dict[int, asyncio.Queue[dict[str, object]]] = {}
        self._stop_events: dict[int, threading.Event] = {}
        self._running = 0
        self._run_metadata: dict[int, dict[str, Any]] = {}
        self._diverged_runs: set[int] = set()

    def is_diverged(self, run_id: int) -> bool:
        """Return whether a run terminated due to divergence.

        Parameters
        ----------
        run_id : int
            The local run ID.

        Returns
        -------
        bool
            ``True`` if the run was halted by a divergence (non-finite loss).
        """
        return run_id in self._diverged_runs

    def _build_progress_callback(
        self,
        *,
        run_id: int,
        queue: asyncio.Queue[dict[str, object]],
        loop: asyncio.AbstractEventLoop,
        device: str,
        num_steps: int,
        progress_callback_override: Callable[[int, float], None] | None,
    ) -> Callable[..., None]:
        """Build the per-step progress callback for a run.

        The returned callback (invoked on a worker thread) emits neutral SSE
        signals: a ``metrics`` payload each step, a periodic ``milestone``
        marker, and on non-finite loss a ``divergence`` event followed by a
        raised :class:`DivergenceError` to halt the run.

        Parameters
        ----------
        run_id : int
            Local run ID, used to honour stop requests.
        queue : asyncio.Queue
            SSE event queue for this run.
        loop : asyncio.AbstractEventLoop
            Event loop the worker thread marshals events into.
        device : str
            Compute device label included in each metrics payload.
        num_steps : int
            Total planned steps (drives ETA and milestone cadence).
        progress_callback_override : callable or None
            Optional external ``(step, loss)`` progress hook.

        Returns
        -------
        callable
            The progress callback.
        """
        start_time = time.monotonic()
        tracker = ThroughputTracker(window=20)
        milestone_every = max(1, num_steps // 10)

        def progress_callback(
            step: int,
            loss: float,
            *,
            tokens: int = 0,
            grad_norm: float | None = None,
        ) -> None:
            stop_event = self._stop_events.get(run_id)
            if stop_event is not None and stop_event.is_set():
                raise StopRequested(f"Training stopped at step {step}")

            reason = classify_divergence(loss)
            if reason is not None:
                asyncio.run_coroutine_threadsafe(
                    _enqueue_or_drop(
                        queue,
                        {
                            "event": "divergence",
                            "data": json.dumps({"step": step, "reason": reason.value}),
                        },
                    ),
                    loop,
                )
                raise DivergenceError(step, reason)

            now = time.monotonic()
            tracker.record(tokens=tokens, now=now)
            metrics = StepMetrics(
                step=step,
                loss=loss,
                device=device,
                elapsed_sec=now - start_time,
                steps_per_sec=tracker.steps_per_sec,
                eta_sec=tracker.eta_sec(step, num_steps),
                grad_norm=grad_norm,
                tokens_per_sec=tracker.tokens_per_sec,
            )
            asyncio.run_coroutine_threadsafe(
                _enqueue_or_drop(
                    queue, {"event": "metrics", "data": metrics.model_dump_json()}
                ),
                loop,
            )

            if step > 0 and step % milestone_every == 0:
                asyncio.run_coroutine_threadsafe(
                    _enqueue_or_drop(
                        queue,
                        {"event": "milestone", "data": json.dumps({"step": step})},
                    ),
                    loop,
                )
            if progress_callback_override:
                progress_callback_override(step, loss)

        return progress_callback

    def store_run_metadata(
        self,
        run_id: int,
        *,
        mlflow_run_id: str | None = None,
        experiment_id: int | None = None,
    ) -> None:
        """Associate MLflow and experiment IDs with a run.

        Parameters
        ----------
        run_id : int
            The local run ID.
        mlflow_run_id : str, optional
            The MLflow run ID. Defaults to ``None``.
        experiment_id : int, optional
            The numeric experiment ID. Defaults to ``None``.
        """
        self._run_metadata[run_id] = {
            "mlflow_run_id": mlflow_run_id,
            "experiment_id": experiment_id,
        }

    def get_mlflow_run_id(self, run_id: int) -> str | None:
        """Retrieve the MLflow run ID associated with a local run ID.

        Parameters
        ----------
        run_id : int
            The local run ID.

        Returns
        -------
        str or None
            The MLflow run ID, or ``None`` if not stored.
        """
        meta = self._run_metadata.get(run_id)
        return meta.get("mlflow_run_id") if meta else None

    def get_experiment_id(self, run_id: int) -> int | None:
        """Retrieve the experiment ID associated with a local run ID.

        Parameters
        ----------
        run_id : int
            The local run ID.

        Returns
        -------
        int or None
            The experiment ID, or ``None`` if not stored.
        """
        meta = self._run_metadata.get(run_id)
        return meta.get("experiment_id") if meta else None

    def _load_docs(
        self,
        corpus_id: int | None = None,
        dataset_id: int | None = None,
        content_version_id: int | None = None,
    ) -> list[str]:
        """Load training documents from a corpus, dataset, or content
        version.

        Falls back to the default demo corpus when none of the three
        identifiers is provided.

        Parameters
        ----------
        corpus_id : int, optional
            Legacy corpus ID to load from.
        dataset_id : int, optional
            Dataset ID to load from.
        content_version_id : int, optional
            Versioned content repository version ID. When provided,
            resolves the manifest from the content-addressed store
            and streams entries for chunking.

        Returns
        -------
        list[str]
            Loaded document texts.

        Raises
        ------
        RuntimeError
            If no data source is available or the version cannot be
            resolved.
        """
        if content_version_id is not None:
            return self._load_docs_from_version(content_version_id)

        if dataset_id is not None:
            from ...db.repositories.datasets import DatasetRepository
            from ...db.session import AsyncSessionLocal
            from ...storage.local import LocalFileStore
            from ..datasets.datasets import DatasetService

            async def _load() -> list[str]:
                async with AsyncSessionLocal() as session:
                    repo = DatasetRepository(session)
                    store = LocalFileStore()
                    svc = DatasetService(repo, store)
                    return await svc.load_docs(dataset_id)

            return asyncio.run(_load())

        # Fallback: use default demo corpus when no corpus/dataset specified
        from ...db.repositories.corpora import CorpusRepository
        from ...db.session import AsyncSessionLocal
        from ..datasets.corpora import CorpusService
        from ..datasets.corpus_loader import CorpusLoader
        from ..demo.demo_bootstrap import DEFAULT_CORPUS_NAME, DemoBootstrapService

        async def _load_default() -> list[str]:
            async with AsyncSessionLocal() as session:
                repo = CorpusRepository(session)
                loader = CorpusLoader()
                svc = CorpusService(repo, loader)
                bootstrap = DemoBootstrapService(session)
                corpus = await bootstrap.get_default_corpus()
                if corpus is None:
                    raise RuntimeError(
                        f"No demo corpus found. Run 'anvil bootstrap-datasets' first "
                        f"to import demo data (expected corpus: {DEFAULT_CORPUS_NAME})"
                    )
                return await svc.load_docs(corpus.id)

        return asyncio.run(_load_default())

    def _load_docs_from_version(self, content_version_id: int) -> list[str]:
        """Load training documents from a versioned content repository
        version.

        Resolves the version manifest via the content store, opens each
        content-addressed blob, and chunks the text using the default
        windowed chunking strategy.

        Parameters
        ----------
        content_version_id : int
            Primary key of the ``ContentVersion`` to load from.

        Returns
        -------
        list[str]
            Chunked document texts.

        Raises
        ------
        RuntimeError
            If the version cannot be resolved.
        """
        from ...db.repositories.content_versions import ContentVersionRepository
        from ...db.session import AsyncSessionLocal

        async def _load() -> list[str]:
            async with AsyncSessionLocal() as session:
                ver_repo = ContentVersionRepository(session)
                version = await ver_repo.get(content_version_id)
                if version is None:
                    raise RuntimeError(
                        f"Content version {content_version_id} not found"
                    )
                entries = await ver_repo.get_entries(content_version_id)

                from ...services.content.local_versioned_content_store import (
                    LocalVersionedContentStore,
                )

                store = LocalVersionedContentStore(db_session=session)

                from ...services.content.version_ref import VersionRef

                version_ref = VersionRef(
                    manifest_digest=version.manifest_digest,
                    version_id=version.id,
                    version_number=version.version_number,
                    label=version.label,
                )
                manifest = await store.resolve(version_ref)
                chunk_cfg = manifest.chunk_cfg or {}
                strategy = chunk_cfg.get("strategy", "windowed")
                block_size = chunk_cfg.get("block_size", 16)
                overlap = chunk_cfg.get("chunk_overlap", 0.5)

                from ..chunking.base import Chunker
                from ..chunking.file_chunker import FileAsDocChunker
                from ..chunking.line_chunker import LineAsDocChunker
                from ..chunking.window_chunker import FixedSizeWindowChunker
                from ..datasets.chunking_strategy import ChunkingStrategy

                chunker: Chunker
                if strategy == ChunkingStrategy.FILE:
                    chunker = FileAsDocChunker()
                elif strategy == ChunkingStrategy.LINE:
                    chunker = LineAsDocChunker()
                else:
                    chunker = FixedSizeWindowChunker(block_size, overlap)

                all_chunks: list[str] = []
                for entry in entries:
                    blob_bytes = b""
                    blob_stream = await store.open_blob(entry.content_hash)
                    async for chunk in blob_stream:
                        blob_bytes += chunk
                    text = blob_bytes.decode("utf-8")
                    chunks = chunker.chunk(text)

                    # FR-021: apply weight-based replication.
                    # Replicate chunks by weight factor (round to nearest
                    # int, minimum 1) so heavily weighted entries contribute
                    # proportionally more training examples.
                    weight = getattr(entry, "weight", 1.0)
                    factor = max(1, round(weight))
                    for _ in range(factor):
                        all_chunks.extend(chunks)
                return all_chunks

        return asyncio.run(_load())

    def reserve_run(self) -> int:
        """Atomically reserve a new run ID and initialise its queues.

        Returns
        -------
        int
            A unique local run ID.
        """
        run_id = self._running
        self._running += 1
        self._queues[run_id] = asyncio.Queue(maxsize=_TRAINING_QUEUE_MAXSIZE)
        self._stop_events[run_id] = threading.Event()
        return run_id

    async def allocate_experiment_id(self) -> int:
        """Atomically allocate a new numeric experiment ID from the DB sequence.

        Uses a PostgreSQL-style ``run_id_seq`` sequence table.

        Returns
        -------
        int
            A new unique experiment ID.
        """
        from sqlalchemy import text

        from ...db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text(
                    "UPDATE run_id_seq SET next_id = next_id + 1 RETURNING next_id - 1 AS allocated_id"
                )
            )
            row = result.fetchone()
            await session.commit()
            if row:
                return row[0]  # type: ignore[no-any-return]
            return int(__import__("time").time() * 1000)  # fallback

    def stop_run(self, run_id: int) -> None:
        """Signal a running training to stop. Thread-safe.

        Parameters
        ----------
        run_id : int
            The local run ID to stop.
        """
        event = self._stop_events.get(run_id)
        if event is not None:
            event.set()

    async def start_training(
        self,
        config: dict[str, Any],
        run_id: int | None = None,
        on_complete: (
            Callable[[ComputeResult, dict[str, Any]], Awaitable[None]] | None
        ) = None,
        progress_callback_override: Callable[[int, float], None] | None = None,
    ) -> int:
        """Start a training run with the given configuration.

        Loads documents, resolves the compute backend, dispatches
        training, and streams progress events via an asyncio queue.

        Parameters
        ----------
        config : dict
            Training configuration dict with keys such as
            ``"corpus_id"``, ``"dataset_id"``, ``"num_steps"``,
            ``"learning_rate"``, etc.
        run_id : int, optional
            Pre-reserved run ID. If ``None``, a new ID is reserved.
        on_complete : callable, optional
            Async callback invoked with ``(ComputeResult, config)``
            after training completes.
        progress_callback_override : callable, optional
            Optional sync callback for external progress tracking.

        Returns
        -------
        int
            The local run ID.

        Raises
        ------
        StopRequested
            If the user requests a stop during training.
        """
        if run_id is None:
            run_id = self.reserve_run()
        queue = self._queues[run_id]

        loop = asyncio.get_event_loop()
        corpus_id = config.get("corpus_id")
        dataset_id = config.get("dataset_id")
        content_version_id = config.get("content_version_id")
        docs = await loop.run_in_executor(
            None,
            self._load_docs,
            corpus_id,
            dataset_id,
            content_version_id,
        )

        # ── resolve backend ───────────────────────────────────────────
        resolved = resolve_backend(config)
        backend_name = resolved["backend"]  # ComputeBackendResult.LOCAL | .MODAL
        engine_name: TrainingEngine = resolved[
            "engine"
        ]  # TrainingEngine.STDLIB | .TORCH
        device: str = resolved["device"]  # DeviceType.CPU | .CUDA | .MPS

        # Map generic "local" to engine-qualified registry name
        # (registry has "local-stdlib" and "local-torch", not bare "local")
        if backend_name == ComputeBackendResult.LOCAL:
            backend_name = f"local-{engine_name}"

        # Inject device into config so backends can read it
        config["device"] = device

        _num_steps = config.get("num_steps", 1000)
        progress_callback = self._build_progress_callback(
            run_id=run_id,
            queue=queue,
            loop=loop,
            device=device,
            num_steps=_num_steps,
            progress_callback_override=progress_callback_override,
        )

        # ── get backend from registry ─────────────────────────────────
        backend = get_backend(backend_name)

        stop_event = self._stop_events.get(run_id)
        stop_check = (
            (lambda: stop_event.is_set()) if stop_event is not None else (lambda: False)
        )

        # ── remote: emit submitted event before launching ─────────────
        if backend_name == ComputeBackendResult.MODAL:
            try:
                queue.put_nowait(
                    {
                        "event": "submitted",
                        "data": json.dumps(
                            {
                                "backend": backend_name,
                                "device": device,
                            }
                        ),
                    }
                )
            except asyncio.QueueFull:
                pass

        try:
            result = await backend.run(
                docs,
                config,
                progress_callback=progress_callback,
                stop_check=stop_check,
            )

        except StopRequested:
            await queue.put(
                {
                    "event": "error",
                    "data": json.dumps({"message": "Training stopped by user"}),
                }
            )
            raise
        except DivergenceError:
            self._diverged_runs.add(run_id)
            raise
        finally:
            self._queues.pop(run_id, None)
            self._stop_events.pop(run_id, None)

        # ── emit complete SSE event ───────────────────────────────────
        await queue.put(
            {
                "event": "complete",
                "data": json.dumps(
                    {
                        "final_loss": result.final_loss,
                        "samples": result.samples,
                        "device": device,
                    }
                ),
            }
        )

        if on_complete:
            await on_complete(result, config)

        return run_id

    def get_queue(self, run_id: int) -> asyncio.Queue[dict[str, object]] | None:
        """Get the SSE event queue for a running training session.

        Parameters
        ----------
        run_id : int
            The local run ID.

        Returns
        -------
        asyncio.Queue or None
            The event queue, or ``None`` if the run does not exist.
        """
        return self._queues.get(run_id)
