# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for TrainingService — run reservation, doc loading, training lifecycle.

Covers ``TrainingService`` methods:
- ``reserve_run`` — atomic run ID allocation
- ``_load_docs`` — corpus/dataset/content-version doc loading
- ``start_training`` — async training dispatch with compute backends
- ``get_queue`` / ``release_queue`` — SSE event queue management
- ``stop_run`` — thread-safe stop signalling
- ``store_run_metadata`` — metadata persistence
- ``is_diverged`` — divergence tracking
- ``allocate_experiment_id`` — DB-backed experiment ID allocation
- ``_build_progress_callback`` — per-step callback construction

All DB operations, file I/O, compute backends, and asyncio primitives
are mocked — no real training or database access occurs.
"""

from __future__ import annotations

import asyncio
import json
import threading
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anvil.services.compute.compute_backend_result import ComputeBackendResult
from anvil.services.compute.compute_status import ComputeStatus
from anvil.services.compute.training_engine import TrainingEngine
from anvil.services.training.divergence_error import DivergenceError
from anvil.services.training.divergence_reason import DivergenceReason
from anvil.services.training.stop_requested import StopRequested
from anvil.services.training.training import TrainingService


@pytest.fixture
def svc() -> TrainingService:
    """Return a fresh ``TrainingService`` for each test."""
    return TrainingService()


@pytest.fixture
def fake_compute_result() -> MagicMock:
    """Build a standard successful compute result."""
    result = MagicMock()
    result.status = ComputeStatus.COMPLETED
    result.final_loss = 0.05
    result.samples = ["hello world"]
    result.error_message = None
    return result


##########################################################################
# reserve_run
##########################################################################


class TestReserveRun:
    """Tests for ``TrainingService.reserve_run``."""

    def test_returns_incrementing_ids(self, svc: TrainingService) -> None:
        run_0 = svc.reserve_run()
        run_1 = svc.reserve_run()
        run_2 = svc.reserve_run()
        assert run_0 == 0
        assert run_1 == 1
        assert run_2 == 2

    def test_initialises_queue_and_stop_event(self, svc: TrainingService) -> None:
        run_id = svc.reserve_run()
        queue = svc.get_queue(run_id)
        assert queue is not None
        assert isinstance(queue, asyncio.Queue)
        assert run_id not in svc._diverged_runs


##########################################################################
# _load_docs
##########################################################################


class TestLoadDocs:
    """Tests for ``TrainingService._load_docs``."""

    def test_loads_from_content_version(self, svc: TrainingService) -> None:
        """Load docs from a content version ID."""
        fake_entries = [
            MagicMock(content_hash=b"abc", weight=1.0),
            MagicMock(content_hash=b"def", weight=2.0),
        ]

        with (
            patch(
                "anvil.services.training.training.AsyncSessionLocal",
            ) as mock_session_local,
            patch(
                "anvil.services.training.training.ContentVersionRepository",
            ) as mock_ver_repo_cls,
            patch(
                "anvil.services.training.training.LocalVersionedContentStore",
            ) as mock_store_cls,
        ):
            mock_session = AsyncMock()
            mock_session_local.return_value.__aenter__.return_value = mock_session

            mock_ver_repo = mock_ver_repo_cls.return_value
            mock_version = MagicMock()
            mock_version.manifest_digest = "digest1"
            mock_version.id = 42
            mock_version.version_number = 1
            mock_version.label = "test"
            mock_ver_repo.get = AsyncMock(return_value=mock_version)
            mock_ver_repo.get_entries = AsyncMock(return_value=fake_entries)

            mock_store = mock_store_cls.return_value
            mock_manifest = MagicMock()
            mock_manifest.chunk_cfg = {
                "strategy": "windowed",
                "block_size": 8,
                "chunk_overlap": 0.5,
            }
            mock_store.resolve = AsyncMock(return_value=mock_manifest)
            mock_store.open_blob = AsyncMock()
            mock_store.open_blob.return_value.__aiter__.return_value = [b"hello chunk "]

            docs = svc._load_docs(content_version_id=99)

            assert len(docs) > 0
            # Entry with weight 2.0 should produce 2 copies
            mock_ver_repo.get.assert_awaited_once_with(99)
            mock_ver_repo.get_entries.assert_awaited_once_with(99)

    def test_loads_from_dataset(self, svc: TrainingService) -> None:
        """Load docs from a dataset ID."""
        with (
            patch(
                "anvil.services.training.training.AsyncSessionLocal",
            ) as mock_session_local,
            patch(
                "anvil.services.training.training.DatasetRepository",
            ) as mock_ds_repo_cls,
            patch(
                "anvil.services.training.training.LocalFileStore",
            ),
            patch(
                "anvil.services.training.training.DatasetService",
            ) as mock_ds_svc_cls,
        ):
            mock_session = AsyncMock()
            mock_session_local.return_value.__aenter__.return_value = mock_session

            mock_ds_svc = mock_ds_svc_cls.return_value
            mock_ds_svc.load_docs = AsyncMock(return_value=["dataset doc"])

            docs = svc._load_docs(dataset_id=55)

            assert docs == ["dataset doc"]
            mock_ds_svc.load_docs.assert_awaited_once_with(55)

    def test_loads_from_corpus_fallback(self, svc: TrainingService) -> None:
        """Fall back to default demo corpus when no ID provided."""
        with (
            patch(
                "anvil.services.training.training.AsyncSessionLocal",
            ) as mock_session_local,
            patch(
                "anvil.services.training.training.CorpusRepository",
            ),
            patch(
                "anvil.services.training.training.CorpusLoader",
            ),
            patch(
                "anvil.services.training.training.CorpusService",
            ) as mock_corpus_svc_cls,
            patch(
                "anvil.services.training.training.DemoBootstrapService",
            ) as mock_bootstrap_cls,
        ):
            mock_session = AsyncMock()
            mock_session_local.return_value.__aenter__.return_value = mock_session

            mock_corpus = MagicMock()
            mock_corpus.id = 1
            mock_bootstrap = mock_bootstrap_cls.return_value
            mock_bootstrap.get_default_corpus = AsyncMock(return_value=mock_corpus)

            mock_corpus_svc = mock_corpus_svc_cls.return_value
            mock_corpus_svc.load_docs = AsyncMock(return_value=["fallback doc"])

            docs = svc._load_docs()

            assert docs == ["fallback doc"]
            mock_bootstrap.get_default_corpus.assert_awaited_once()

    def test_raises_when_no_fallback_corpus(self, svc: TrainingService) -> None:
        """Raise RuntimeError when no demo corpus found."""
        with (
            patch(
                "anvil.services.training.training.AsyncSessionLocal",
            ) as mock_session_local,
            patch(
                "anvil.services.training.training.DemoBootstrapService",
            ) as mock_bootstrap_cls,
        ):
            mock_session = AsyncMock()
            mock_session_local.return_value.__aenter__.return_value = mock_session

            mock_bootstrap = mock_bootstrap_cls.return_value
            mock_bootstrap.get_default_corpus = AsyncMock(return_value=None)

            with pytest.raises(RuntimeError, match="No demo corpus found"):
                svc._load_docs()

    def test_raises_when_version_not_found(self, svc: TrainingService) -> None:
        """Raise RuntimeError when content version not found."""
        with (
            patch(
                "anvil.services.training.training.AsyncSessionLocal",
            ) as mock_session_local,
            patch(
                "anvil.services.training.training.ContentVersionRepository",
            ) as mock_ver_repo_cls,
        ):
            mock_session = AsyncMock()
            mock_session_local.return_value.__aenter__.return_value = mock_session

            mock_ver_repo = mock_ver_repo_cls.return_value
            mock_ver_repo.get = AsyncMock(return_value=None)

            with pytest.raises(RuntimeError, match="Content version 999 not found"):
                svc._load_docs(content_version_id=999)

    def test_loads_from_version_with_file_strategy(self, svc: TrainingService) -> None:
        """Content version with FILE chunking strategy."""
        fake_entries = [MagicMock(content_hash=b"abc", weight=1.0)]

        with (
            patch(
                "anvil.services.training.training.AsyncSessionLocal",
            ) as mock_session_local,
            patch(
                "anvil.services.training.training.ContentVersionRepository",
            ) as mock_ver_repo_cls,
            patch(
                "anvil.services.training.training.LocalVersionedContentStore",
            ) as mock_store_cls,
        ):
            mock_session = AsyncMock()
            mock_session_local.return_value.__aenter__.return_value = mock_session

            mock_ver_repo = mock_ver_repo_cls.return_value
            mock_version = MagicMock()
            mock_version.manifest_digest = "d1"
            mock_version.id = 1
            mock_version.version_number = 1
            mock_version.label = "v1"
            mock_ver_repo.get = AsyncMock(return_value=mock_version)
            mock_ver_repo.get_entries = AsyncMock(return_value=fake_entries)

            mock_store = mock_store_cls.return_value
            mock_manifest = MagicMock()
            mock_manifest.chunk_cfg = {"strategy": "file"}
            mock_store.resolve = AsyncMock(return_value=mock_manifest)
            mock_store.open_blob = AsyncMock()
            mock_store.open_blob.return_value.__aiter__.return_value = [b"file content"]

            docs = svc._load_docs(content_version_id=1)
            assert len(docs) >= 1

    def test_loads_from_version_with_line_strategy(self, svc: TrainingService) -> None:
        """Content version with LINE chunking strategy."""
        fake_entries = [MagicMock(content_hash=b"abc", weight=1.0)]

        with (
            patch(
                "anvil.services.training.training.AsyncSessionLocal",
            ) as mock_session_local,
            patch(
                "anvil.services.training.training.ContentVersionRepository",
            ) as mock_ver_repo_cls,
            patch(
                "anvil.services.training.training.LocalVersionedContentStore",
            ) as mock_store_cls,
        ):
            mock_session = AsyncMock()
            mock_session_local.return_value.__aenter__.return_value = mock_session

            mock_ver_repo = mock_ver_repo_cls.return_value
            mock_version = MagicMock()
            mock_version.manifest_digest = "d1"
            mock_version.id = 1
            mock_version.version_number = 1
            mock_version.label = "v1"
            mock_ver_repo.get = AsyncMock(return_value=mock_version)
            mock_ver_repo.get_entries = AsyncMock(return_value=fake_entries)

            mock_store = mock_store_cls.return_value
            mock_manifest = MagicMock()
            mock_manifest.chunk_cfg = {"strategy": "line"}
            mock_store.resolve = AsyncMock(return_value=mock_manifest)
            mock_store.open_blob = AsyncMock()
            mock_store.open_blob.return_value.__aiter__.return_value = [b"line content"]

            docs = svc._load_docs(content_version_id=1)
            assert len(docs) >= 1


##########################################################################
# _build_progress_callback
##########################################################################


class TestBuildProgressCallback:
    """Tests for ``TrainingService._build_progress_callback``."""

    def test_emits_metrics_and_milestones(self, svc: TrainingService) -> None:
        run_id = svc.reserve_run()
        queue = svc.get_queue(run_id)
        assert queue is not None
        loop = asyncio.new_event_loop()

        callback = svc._build_progress_callback(
            run_id=run_id,
            queue=queue,
            loop=loop,
            device="cpu",
            num_steps=100,
            progress_callback_override=None,
        )

        # Emulate a few steps
        callback(0, 0.5, tokens=10)
        # Run loop to process coroutines scheduled via run_coroutine_threadsafe
        loop.run_until_complete(asyncio.sleep(0))
        callback(1, 0.3, tokens=10)
        loop.run_until_complete(asyncio.sleep(0))
        callback(10, 0.2, tokens=10)  # milestone (100/10=10)
        loop.run_until_complete(asyncio.sleep(0))

        # Check that events were enqueued
        assert not queue.empty()

        # Clean up
        loop.close()

    def test_raises_stop_requested(self, svc: TrainingService) -> None:
        run_id = svc.reserve_run()
        queue = svc.get_queue(run_id)
        assert queue is not None
        loop = asyncio.new_event_loop()

        svc.stop_run(run_id)

        callback = svc._build_progress_callback(
            run_id=run_id,
            queue=queue,
            loop=loop,
            device="cpu",
            num_steps=100,
            progress_callback_override=None,
        )

        with pytest.raises(StopRequested):
            callback(1, 0.5, tokens=10)

    def test_raises_divergence_error(self, svc: TrainingService) -> None:
        run_id = svc.reserve_run()
        queue = svc.get_queue(run_id)
        assert queue is not None
        loop = asyncio.new_event_loop()

        callback = svc._build_progress_callback(
            run_id=run_id,
            queue=queue,
            loop=loop,
            device="cpu",
            num_steps=100,
            progress_callback_override=None,
        )

        with pytest.raises(DivergenceError):
            callback(1, float("nan"), tokens=10)

    def test_calls_override_callback(self, svc: TrainingService) -> None:
        run_id = svc.reserve_run()
        queue = svc.get_queue(run_id)
        assert queue is not None
        loop = asyncio.new_event_loop()
        override = MagicMock()

        callback = svc._build_progress_callback(
            run_id=run_id,
            queue=queue,
            loop=loop,
            device="cpu",
            num_steps=100,
            progress_callback_override=override,
        )

        callback(0, 0.5, tokens=5)
        override.assert_called_once_with(0, 0.5)


##########################################################################
# start_training
##########################################################################


class TestStartTraining:
    """Tests for ``TrainingService.start_training``."""

    @pytest.mark.asyncio
    async def test_uses_provided_run_id(self, svc: TrainingService) -> None:
        config = {"num_steps": 10, "compute_backend": "local-cpu"}
        # Pre-reserve the run so the queue and stop_event exist
        run_id = svc.reserve_run()

        with (
            patch.object(svc, "_load_docs", return_value=["doc"]),
            patch(
                "anvil.services.training.training.resolve_backend",
                return_value={
                    "backend": ComputeBackendResult.LOCAL,
                    "engine": TrainingEngine.STDLIB,
                    "device": "cpu",
                },
            ),
            patch(
                "anvil.services.training.training.get_backend",
            ) as mock_get_backend,
        ):
            mock_backend = MagicMock()
            mock_backend.run = AsyncMock(
                return_value=MagicMock(
                    status=ComputeStatus.COMPLETED,
                    final_loss=0.05,
                    samples=["sample"],
                )
            )
            mock_get_backend.return_value = mock_backend

            result_id = await svc.start_training(config=config, run_id=run_id)

            assert result_id == run_id
            mock_backend.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_reserves_new_run_id(self, svc: TrainingService) -> None:
        config = {"num_steps": 10, "compute_backend": "local-cpu"}

        with (
            patch.object(svc, "_load_docs", return_value=["doc"]),
            patch(
                "anvil.services.training.training.resolve_backend",
                return_value={
                    "backend": ComputeBackendResult.LOCAL,
                    "engine": TrainingEngine.STDLIB,
                    "device": "cpu",
                },
            ),
            patch(
                "anvil.services.training.training.get_backend",
            ) as mock_get_backend,
        ):
            mock_backend = MagicMock()
            mock_backend.run = AsyncMock(
                return_value=MagicMock(
                    status=ComputeStatus.COMPLETED,
                    final_loss=0.05,
                    samples=["sample"],
                )
            )
            mock_get_backend.return_value = mock_backend

            run_id = await svc.start_training(config=config)

            assert run_id == 0  # first reservation

    @pytest.mark.asyncio
    async def test_calls_on_complete_callback(self, svc: TrainingService) -> None:
        config = {"num_steps": 10, "compute_backend": "local-cpu"}
        on_complete = AsyncMock()
        fake_result = MagicMock(
            status=ComputeStatus.COMPLETED,
            final_loss=0.05,
            samples=["sample"],
        )

        with (
            patch.object(svc, "_load_docs", return_value=["doc"]),
            patch(
                "anvil.services.training.training.resolve_backend",
                return_value={
                    "backend": ComputeBackendResult.LOCAL,
                    "engine": TrainingEngine.STDLIB,
                    "device": "cpu",
                },
            ),
            patch(
                "anvil.services.training.training.get_backend",
            ) as mock_get_backend,
        ):
            mock_backend = MagicMock()
            mock_backend.run = AsyncMock(return_value=fake_result)
            mock_get_backend.return_value = mock_backend

            await svc.start_training(config=config, on_complete=on_complete)

            on_complete.assert_awaited_once_with(fake_result, config)

    @pytest.mark.asyncio
    async def test_handles_backend_failure(self, svc: TrainingService) -> None:
        config = {"num_steps": 10, "compute_backend": "local-cpu"}

        with (
            patch.object(svc, "_load_docs", return_value=["doc"]),
            patch(
                "anvil.services.training.training.resolve_backend",
                return_value={
                    "backend": ComputeBackendResult.LOCAL,
                    "engine": TrainingEngine.STDLIB,
                    "device": "cpu",
                },
            ),
            patch(
                "anvil.services.training.training.get_backend",
            ) as mock_get_backend,
        ):
            mock_backend = MagicMock()
            mock_backend.run = AsyncMock(
                return_value=MagicMock(
                    status=ComputeStatus.FAILED,
                    final_loss=None,
                    samples=[],
                    error_message="GPU OOM",
                )
            )
            mock_get_backend.return_value = mock_backend

            run_id = await svc.start_training(config=config)

            # Should return the run_id, not raise
            assert run_id == 0
            # Should emit error event
            queue = svc.get_queue(run_id)
            assert queue is not None
            # Drain queue to find error event
            events = []
            while not queue.empty():
                events.append(queue.get_nowait())
            error_events = [e for e in events if e.get("event") == "error"]
            assert len(error_events) == 1

    @pytest.mark.asyncio
    async def test_propagates_stop_requested(self, svc: TrainingService) -> None:
        config = {"num_steps": 10, "compute_backend": "local-cpu"}

        with (
            patch.object(svc, "_load_docs", return_value=["doc"]),
            patch(
                "anvil.services.training.training.resolve_backend",
                return_value={
                    "backend": ComputeBackendResult.LOCAL,
                    "engine": TrainingEngine.STDLIB,
                    "device": "cpu",
                },
            ),
            patch(
                "anvil.services.training.training.get_backend",
            ) as mock_get_backend,
        ):
            mock_backend = MagicMock()
            mock_backend.run = AsyncMock(side_effect=StopRequested("Stopped"))
            mock_get_backend.return_value = mock_backend

            with pytest.raises(StopRequested):
                await svc.start_training(config=config)

            # After stop, the stop_event should be cleaned up
            # (the finally block pops it)
            assert svc._stop_events.get(0) is None

    @pytest.mark.asyncio
    async def test_propagates_divergence_error(self, svc: TrainingService) -> None:
        config = {"num_steps": 10, "compute_backend": "local-cpu"}

        with (
            patch.object(svc, "_load_docs", return_value=["doc"]),
            patch(
                "anvil.services.training.training.resolve_backend",
                return_value={
                    "backend": ComputeBackendResult.LOCAL,
                    "engine": TrainingEngine.STDLIB,
                    "device": "cpu",
                },
            ),
            patch(
                "anvil.services.training.training.get_backend",
            ) as mock_get_backend,
        ):
            mock_backend = MagicMock()
            mock_backend.run = AsyncMock(
                side_effect=DivergenceError(
                    5, cast(DivergenceReason, DivergenceReason.LOSS_NAN)
                )
            )
            mock_get_backend.return_value = mock_backend

            with pytest.raises(DivergenceError):
                await svc.start_training(config=config)

            assert svc.is_diverged(0) is True

    @pytest.mark.asyncio
    async def test_emits_submitted_event_for_modal(self, svc: TrainingService) -> None:
        config = {"num_steps": 10, "compute_backend": "modal"}

        with (
            patch.object(svc, "_load_docs", return_value=["doc"]),
            patch(
                "anvil.services.training.training.resolve_backend",
                return_value={
                    "backend": ComputeBackendResult.MODAL,
                    "engine": TrainingEngine.TORCH,
                    "device": "cuda",
                },
            ),
            patch(
                "anvil.services.training.training.get_backend",
            ) as mock_get_backend,
        ):
            mock_backend = MagicMock()
            mock_backend.run = AsyncMock(
                return_value=MagicMock(
                    status=ComputeStatus.COMPLETED,
                    final_loss=0.05,
                    samples=["sample"],
                )
            )
            mock_get_backend.return_value = mock_backend

            run_id = await svc.start_training(config=config)

            queue = svc.get_queue(run_id)
            assert queue is not None
            events = []
            while not queue.empty():
                events.append(queue.get_nowait())
            submitted = [e for e in events if e.get("event") == "submitted"]
            assert len(submitted) == 1
            data = json.loads(submitted[0]["data"])
            assert data["backend"] == "modal"
            assert data["device"] == "cuda"

    @pytest.mark.asyncio
    async def test_injects_device_into_config(self, svc: TrainingService) -> None:
        config: dict = {"num_steps": 10, "compute_backend": "local-cpu"}

        with (
            patch.object(svc, "_load_docs", return_value=["doc"]),
            patch(
                "anvil.services.training.training.resolve_backend",
                return_value={
                    "backend": ComputeBackendResult.LOCAL,
                    "engine": TrainingEngine.STDLIB,
                    "device": "cpu",
                },
            ),
            patch(
                "anvil.services.training.training.get_backend",
            ) as mock_get_backend,
        ):
            mock_backend = MagicMock()
            mock_backend.run = AsyncMock(
                return_value=MagicMock(
                    status=ComputeStatus.COMPLETED,
                    final_loss=0.05,
                    samples=["sample"],
                )
            )
            mock_get_backend.return_value = mock_backend

            await svc.start_training(config=config)

            assert config["device"] == "cpu"


##########################################################################
# get_queue / release_queue
##########################################################################


class TestQueueManagement:
    """Tests for ``get_queue`` and ``release_queue``."""

    def test_get_queue_returns_none_for_unknown(self, svc: TrainingService) -> None:
        assert svc.get_queue(999) is None

    def test_get_queue_returns_queue_for_known(self, svc: TrainingService) -> None:
        run_id = svc.reserve_run()
        queue = svc.get_queue(run_id)
        assert queue is not None
        assert isinstance(queue, asyncio.Queue)

    def test_release_queue_removes_queue(self, svc: TrainingService) -> None:
        run_id = svc.reserve_run()
        assert svc.get_queue(run_id) is not None
        svc.release_queue(run_id)
        assert svc.get_queue(run_id) is None

    def test_release_queue_does_not_raise_for_unknown(
        self, svc: TrainingService
    ) -> None:
        svc.release_queue(999)  # should not raise


##########################################################################
# stop_run
##########################################################################


class TestStopRun:
    """Tests for ``TrainingService.stop_run``."""

    def test_stops_running_run(self, svc: TrainingService) -> None:
        run_id = svc.reserve_run()
        svc.stop_run(run_id)
        event = svc._stop_events.get(run_id)
        assert event is not None
        assert event.is_set()

    def test_stop_unknown_run_does_nothing(self, svc: TrainingService) -> None:
        svc.stop_run(999)  # should not raise


##########################################################################
# store_run_metadata / get_mlflow_run_id / get_experiment_id
##########################################################################


class TestRunMetadata:
    """Tests for metadata persistence methods."""

    def test_store_and_retrieve_mlflow_id(self, svc: TrainingService) -> None:
        svc.store_run_metadata(1, mlflow_run_id="mlflow_abc")
        assert svc.get_mlflow_run_id(1) == "mlflow_abc"

    def test_store_and_retrieve_experiment_id(self, svc: TrainingService) -> None:
        svc.store_run_metadata(1, experiment_id=42)
        assert svc.get_experiment_id(1) == 42

    def test_store_both(self, svc: TrainingService) -> None:
        svc.store_run_metadata(1, mlflow_run_id="mlf", experiment_id=7)
        assert svc.get_mlflow_run_id(1) == "mlf"
        assert svc.get_experiment_id(1) == 7

    def test_returns_none_for_unknown(self, svc: TrainingService) -> None:
        assert svc.get_mlflow_run_id(999) is None
        assert svc.get_experiment_id(999) is None

    def test_overwrite_metadata(self, svc: TrainingService) -> None:
        svc.store_run_metadata(1, mlflow_run_id="old")
        svc.store_run_metadata(1, mlflow_run_id="new")
        assert svc.get_mlflow_run_id(1) == "new"


##########################################################################
# is_diverged
##########################################################################


class TestIsDiverged:
    """Tests for ``TrainingService.is_diverged``."""

    def test_not_diverged_by_default(self, svc: TrainingService) -> None:
        assert svc.is_diverged(0) is False

    def test_diverged_run(self, svc: TrainingService) -> None:
        svc._diverged_runs.add(42)
        assert svc.is_diverged(42) is True


##########################################################################
# allocate_experiment_id
##########################################################################


class TestAllocateExperimentId:
    """Tests for ``TrainingService.allocate_experiment_id``."""

    @pytest.mark.asyncio
    async def test_allocates_from_db_sequence(self, svc: TrainingService) -> None:
        with (
            patch(
                "anvil.services.training.training.AsyncSessionLocal",
            ) as mock_session_local,
        ):
            mock_session = AsyncMock()
            mock_session_local.return_value.__aenter__.return_value = mock_session
            mock_result = MagicMock()
            mock_result.fetchone.return_value = (42,)
            mock_session.execute = AsyncMock(return_value=mock_result)

            exp_id = await svc.allocate_experiment_id()

            assert exp_id == 42
            mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fallback_on_missing_row(self, svc: TrainingService) -> None:
        with (
            patch(
                "anvil.services.training.training.AsyncSessionLocal",
            ) as mock_session_local,
            patch(
                "time.time",
                return_value=1234567.890,
            ),
        ):
            mock_session = AsyncMock()
            mock_session_local.return_value.__aenter__.return_value = mock_session
            mock_result = MagicMock()
            mock_result.fetchone.return_value = None
            mock_session.execute = AsyncMock(return_value=mock_result)

            exp_id = await svc.allocate_experiment_id()

            # int(time.time() * 1000) = int(1234567.890 * 1000) = 1234567890
            assert exp_id == 1234567890
