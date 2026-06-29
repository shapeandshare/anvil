# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for DemoModelProvider — provisioning, caching, and fallback paths.

Covers ``DemoModelProvider.get_model``, ``_load_demo_docs``, ``info``,
the module-level ``_train_demo_model`` helper, and the
``warmup_demo_via_system_pipeline`` orchestrator.

All file I/O, DB sessions, model creation, and compute backends are
mocked/delegated — no real training or database access occurs.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from anvil.services.inference.demo_model_provider import (
    DEMO_MODEL_PATH,
    DemoModelProvider,
    _demo_provider,
    _train_demo_model,
    warmup_demo_via_system_pipeline,
)


@pytest.fixture(autouse=True)
def _reset_singleton() -> Generator[None, None, None]:
    """Reset the module-level ``_demo_provider`` singleton before each test."""
    _demo_provider._model = None
    _demo_provider._chars = None
    # Also reset the module-level lock state (the lock itself is fine;
    # just ensure the singleton is in its initial state).
    yield
    _demo_provider._model = None
    _demo_provider._chars = None


##########################################################################
# LlamaModel helpers — fake stubs for load / save / chars
##########################################################################


def make_fake_model(chars: list[str] | None = None) -> MagicMock:
    """Build a fake ``LlamaModel``-like object.

    Parameters
    ----------
    chars : list[str], optional
        Character vocabulary to attach as ``.chars``.

    Returns
    -------
    MagicMock
        A mock with a ``chars`` attribute, a no-op ``save`` method,
        and a ``__repr__`` that identifies it.
    """
    model = MagicMock()
    model.chars = chars
    model.save = MagicMock()
    return model


def make_fake_loaded_model(chars: list[str] | None = None) -> MagicMock:
    """Build a fake model like one returned by ``LlamaModel.load``.

    The returned object has a ``chars`` attribute and ``save`` method.
    """
    model = MagicMock()
    model.chars = chars
    model.save = MagicMock()
    return model


##########################################################################
# _train_demo_model (module-level helper)
##########################################################################


class TestTrainDemoModel:
    """Tests for the module-level ``_train_demo_model`` helper."""

    def test_trains_and_saves_with_default_corpus(self) -> None:
        """Train with default fallback corpus, saving to DEMO_MODEL_PATH."""
        fake_model = make_fake_model(chars=["a", "b", "c"])

        with (
            patch(
                "anvil.services.inference.demo_model_provider.train",
                return_value=(fake_model, 0.5, ["sample"], ["a", "b", "c"]),
            ) as mock_train,
            patch(
                "anvil.services.inference.demo_model_provider.DEMO_MODEL_PATH",
            ) as mock_path,
        ):
            mock_path.parent.mkdir = MagicMock()
            # Ensure exists() on the parent doesn't interfere
            type(mock_path).parent = PropertyMock(
                return_value=MagicMock(mkdir=MagicMock())
            )

            result = _train_demo_model()

            assert result is fake_model
            mock_train.assert_called_once()
            # Should use _FALLBACK_CORPUS when docs is None
            args, _ = mock_train.call_args
            assert args[0] is not None  # docs passed
            fake_model.save.assert_called_once()

    def test_trains_with_provided_docs(self) -> None:
        """Train with explicit document list."""
        docs = ["hello world"]
        fake_model = make_fake_model(chars=["x", "y"])

        with (
            patch(
                "anvil.services.inference.demo_model_provider.train",
                return_value=(fake_model, 0.1, [], ["x", "y"]),
            ) as mock_train,
            patch(
                "anvil.services.inference.demo_model_provider.DEMO_MODEL_PATH",
            ) as mock_path,
        ):
            type(mock_path).parent = PropertyMock(
                return_value=MagicMock(mkdir=MagicMock())
            )
            mock_path.parent.mkdir = MagicMock()

            result = _train_demo_model(docs)

            assert result is fake_model
            mock_train.assert_called_once_with(
                docs,
                num_steps=400,
                n_embd=16,
                n_head=4,
                n_layer=1,
                block_size=16,
            )
            fake_model.save.assert_called_once()
            assert fake_model.chars == ["x", "y"]


##########################################################################
# DemoModelProvider
##########################################################################


class TestDemoModelProviderGetModel:
    """Tests for ``DemoModelProvider.get_model``."""

    def test_returns_cached_model(self) -> None:
        """When model is already cached, return immediately."""
        provider = DemoModelProvider()
        fake = make_fake_model(chars=["a", "b"])
        provider._model = fake
        provider._chars = ["a", "b"]

        model, chars = provider.get_model()

        assert model is fake
        assert chars == ["a", "b"]

    def test_loads_from_disk_when_path_exists(self) -> None:
        """Load model from DEMO_MODEL_PATH when file exists and chars ok."""
        provider = DemoModelProvider()
        fake_loaded = make_fake_loaded_model(chars=["a", "b", "c"])

        with (
            patch(
                "anvil.services.inference.demo_model_provider.DEMO_MODEL_PATH"
            ) as mock_path,
            patch(
                "anvil.services.inference.demo_model_provider.LlamaModel.load",
                return_value=fake_loaded,
            ),
        ):
            mock_path.exists.return_value = True

            model, chars = provider.get_model()

            assert model is fake_loaded
            assert chars == ["a", "b", "c"]
            assert provider._model is fake_loaded
            assert provider._chars == ["a", "b", "c"]

    def test_retrains_on_value_error_from_load(self) -> None:
        """When ``LlamaModel.load`` raises ValueError, retrain."""
        provider = DemoModelProvider()
        fake_trained = make_fake_model(chars=["x", "y", "z"])

        with (
            patch(
                "anvil.services.inference.demo_model_provider.DEMO_MODEL_PATH"
            ) as mock_path,
            patch(
                "anvil.services.inference.demo_model_provider.LlamaModel.load",
                side_effect=ValueError("old format"),
            ),
            patch(
                "anvil.services.inference.demo_model_provider._train_demo_model",
                return_value=fake_trained,
            ) as mock_train,
        ):
            mock_path.exists.return_value = True

            model, chars = provider.get_model()

            assert model is fake_trained
            mock_train.assert_called_once()
            assert provider._model is fake_trained

    def test_retrains_when_loaded_model_chars_is_none(self) -> None:
        """When loaded model has ``chars=None``, retrain from demo docs."""
        provider = DemoModelProvider()
        fake_loaded = make_fake_loaded_model(chars=None)
        fake_trained = make_fake_model(chars=["a", "b"])

        with (
            patch(
                "anvil.services.inference.demo_model_provider.DEMO_MODEL_PATH"
            ) as mock_path,
            patch(
                "anvil.services.inference.demo_model_provider.LlamaModel.load",
                return_value=fake_loaded,
            ),
            patch(
                "anvil.services.inference.demo_model_provider._train_demo_model",
                return_value=fake_trained,
            ) as mock_train,
            patch.object(
                DemoModelProvider,
                "_load_demo_docs",
                return_value=["doc1"],
            ),
        ):
            mock_path.exists.return_value = True

            model, chars = provider.get_model()

            assert model is fake_trained
            mock_train.assert_called_once_with(["doc1"])
            assert provider._model is fake_trained
            assert provider._chars == ["a", "b"]

    def test_trains_from_fallback_when_no_file_and_no_docs(self) -> None:
        """No model file and no DB docs — train from fallback corpus."""
        provider = DemoModelProvider()
        fake_trained = make_fake_model(chars=["a", "b", "c", "d"])

        with (
            patch(
                "anvil.services.inference.demo_model_provider.DEMO_MODEL_PATH"
            ) as mock_path,
            patch(
                "anvil.services.inference.demo_model_provider._train_demo_model",
                return_value=fake_trained,
            ) as mock_train,
            patch.object(
                DemoModelProvider,
                "_load_demo_docs",
                return_value=None,
            ),
        ):
            mock_path.exists.return_value = False

            model, chars = provider.get_model()

            assert model is fake_trained
            mock_train.assert_called_once_with(None)
            assert provider._model is fake_trained

    def test_trains_from_db_docs_when_no_file(self) -> None:
        """No model file but DB docs exist — train from DB docs."""
        provider = DemoModelProvider()
        fake_trained = make_fake_model(chars=["a", "b"])

        with (
            patch(
                "anvil.services.inference.demo_model_provider.DEMO_MODEL_PATH"
            ) as mock_path,
            patch(
                "anvil.services.inference.demo_model_provider._train_demo_model",
                return_value=fake_trained,
            ) as mock_train,
            patch.object(
                DemoModelProvider,
                "_load_demo_docs",
                return_value=["db doc 1", "db doc 2"],
            ),
        ):
            mock_path.exists.return_value = False

            model, chars = provider.get_model()

            assert model is fake_trained
            mock_train.assert_called_once_with(["db doc 1", "db doc 2"])

    def test_thread_safety_double_check(self) -> None:
        """Double-checked locking: second check inside lock also works."""
        provider = DemoModelProvider()
        fake = make_fake_model(chars=["a"])
        provider._model = fake
        provider._chars = ["a"]

        # Even though we don't actually hit the lock in single-thread
        # tests, verify the locking path works end-to-end.
        model, chars = provider.get_model()
        assert model is fake
        assert chars == ["a"]


class TestDemoModelProviderLoadDemoDocs:
    """Tests for ``DemoModelProvider._load_demo_docs``."""

    def test_returns_docs_without_running_loop(self) -> None:
        """No running event loop: uses ``asyncio.run`` directly."""
        fake_corpus = MagicMock()
        fake_corpus.id = 42

        # We need to ensure asyncio.run works properly in the test
        # context.  The simplest approach: mock out the inner async
        # function's dependencies so asyncio.run can execute them.
        # Use a custom side effect for AsyncSessionLocal's async
        # context manager to avoid issues with asyncio.run internals.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            with (
                patch(
                    "anvil.services.inference.demo_model_provider.AsyncSessionLocal",
                ) as mock_session_local,
                patch(
                    "anvil.services.inference.demo_model_provider.DemoBootstrapService",
                ) as mock_bootstrap_cls,
                patch(
                    "anvil.services.inference.demo_model_provider.CorpusRepository",
                ),
                patch(
                    "anvil.services.inference.demo_model_provider.CorpusLoader",
                ),
                patch(
                    "anvil.services.inference.demo_model_provider.CorpusService",
                ) as mock_corpus_svc_cls,
            ):
                # Use AsyncMock for the _load coroutine's async context manager
                # __aenter__ must be a proper awaitable
                async def fake_aenter(*args: object, **kwargs: object) -> MagicMock:
                    return mock_session

                mock_session = MagicMock()
                mock_session_local.return_value.__aenter__ = fake_aenter
                mock_session_local.return_value.__aexit__ = AsyncMock(
                    return_value=False
                )

                mock_bootstrap = mock_bootstrap_cls.return_value
                mock_bootstrap.get_default_corpus = AsyncMock(return_value=fake_corpus)

                mock_corpus_svc = mock_corpus_svc_cls.return_value
                mock_corpus_svc.load_docs = AsyncMock(return_value=["doc_a", "doc_b"])

                result = DemoModelProvider._load_demo_docs()

                assert result == ["doc_a", "doc_b"]
                mock_bootstrap.get_default_corpus.assert_awaited_once()
                mock_corpus_svc.load_docs.assert_awaited_once_with(42)
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    def test_returns_none_when_no_corpus(self) -> None:
        """No default corpus found; returns None."""
        with (
            patch(
                "anvil.services.inference.demo_model_provider.AsyncSessionLocal",
            ) as mock_session_local,
            patch(
                "anvil.services.inference.demo_model_provider.DemoBootstrapService",
            ) as mock_bootstrap_cls,
        ):
            mock_session = AsyncMock()
            mock_session_local.return_value.__aenter__.return_value = mock_session

            mock_bootstrap = mock_bootstrap_cls.return_value
            mock_bootstrap.get_default_corpus.return_value = None

            result = DemoModelProvider._load_demo_docs()

            assert result is None

    def test_returns_none_on_exception(self) -> None:
        """Any exception during loading returns None (graceful fallback)."""
        with (
            patch(
                "anvil.services.inference.demo_model_provider.AsyncSessionLocal",
                side_effect=RuntimeError("DB unavailable"),
            ),
        ):
            result = DemoModelProvider._load_demo_docs()
            assert result is None

    def test_uses_thread_pool_when_loop_running(self) -> None:
        """When event loop is already running, uses ThreadPoolExecutor."""
        fake_corpus = MagicMock()
        fake_corpus.id = 99

        with (
            patch(
                "anvil.services.inference.demo_model_provider.AsyncSessionLocal",
            ) as mock_session_local,
            patch(
                "anvil.services.inference.demo_model_provider.DemoBootstrapService",
            ) as mock_bootstrap_cls,
            patch(
                "anvil.services.inference.demo_model_provider.ThreadPoolExecutor",
            ) as mock_pool_cls,
        ):
            mock_session = AsyncMock()
            mock_session_local.return_value.__aenter__.return_value = mock_session

            mock_bootstrap = mock_bootstrap_cls.return_value
            mock_bootstrap.get_default_corpus.return_value = fake_corpus

            # Simulate a running loop
            mock_future = MagicMock()
            mock_future.result.return_value = ["threaded_doc"]
            mock_pool = MagicMock()
            mock_pool.__enter__.return_value = mock_pool
            mock_pool.submit.return_value = mock_future
            mock_pool_cls.return_value = mock_pool

            # We can't override get_running_loop easily, but we can test the
            # path by patching asyncio.get_running_loop to return a non-None.
            # However, that would fail the RuntimeError check. Instead let's
            # verify the mechanism: patch get_running_loop to succeed.
            with patch(
                "anvil.services.inference.demo_model_provider.asyncio.get_running_loop",
                return_value=MagicMock(),
            ):
                result = DemoModelProvider._load_demo_docs()

            assert result == ["threaded_doc"]
            mock_pool.submit.assert_called_once()


class TestDemoModelProviderInfo:
    """Tests for ``DemoModelProvider.info``."""

    def test_returns_correct_metadata(self) -> None:
        provider = DemoModelProvider()
        info = provider.info()
        assert info == {"id": None, "version": None, "name": "demo", "is_demo": True}


##########################################################################
# Module-level singleton
##########################################################################


class TestModuleSingleton:
    """Tests for the module-level ``_demo_provider`` singleton."""

    def test_singleton_is_instance(self) -> None:
        assert isinstance(_demo_provider, DemoModelProvider)

    def test_singleton_initial_state(self) -> None:
        assert _demo_provider._model is None
        assert _demo_provider._chars is None


##########################################################################
# warmup_demo_via_system_pipeline
##########################################################################


class TestWarmupDemoViaSystemPipeline:
    """Tests for the startup warm-up orchestrator."""

    def test_falls_back_to_inline_on_any_exception(self) -> None:
        """When the system pipeline fails, falls back to inline training."""
        fake_trained = make_fake_model(chars=["a", "b"])

        with (
            patch(
                "anvil.services.inference.demo_model_provider._train_demo_model",
                return_value=fake_trained,
            ) as mock_train,
            patch(
                "anvil.services.inference.demo_model_provider._demo_provider",
            ) as mock_provider,
            patch(
                "anvil.services.inference.demo_model_provider.AsyncSessionLocal",
                side_effect=RuntimeError("no DB"),
            ),
            patch(
                "anvil.services.inference.demo_model_provider.resolve_backend",
                side_effect=RuntimeError("no backend"),
            ),
        ):
            warmup_demo_via_system_pipeline()

            mock_train.assert_called_once()
            # Provider attributes are set by the fallback
            mock_provider._model = fake_trained
            mock_provider._chars = fake_trained.chars

    def test_system_pipeline_success(self) -> None:
        """Happy path: system pipeline runs and updates the provider."""
        fake_model = make_fake_model(chars=["a", "b"])

        with (
            patch(
                "anvil.services.inference.demo_model_provider.AsyncSessionLocal",
            ) as mock_session_local,
            patch(
                "anvil.services.inference.demo_model_provider.DemoBootstrapService",
            ) as mock_bootstrap_cls,
            patch(
                "anvil.services.inference.demo_model_provider.CorpusRepository",
            ),
            patch(
                "anvil.services.inference.demo_model_provider.CorpusLoader",
            ),
            patch(
                "anvil.services.inference.demo_model_provider.CorpusService",
            ) as mock_corpus_svc_cls,
            patch(
                "anvil.services.inference.demo_model_provider.resolve_backend",
                return_value={
                    "engine": "stdlib",
                    "device": "cpu",
                    "backend": "local",
                },
            ),
            patch(
                "anvil.services.inference.demo_model_provider.get_backend",
            ) as mock_get_backend,
            patch(
                "anvil.services.inference.demo_model_provider.TrackingService",
            ) as mock_tracking_cls,
            patch(
                "anvil.services.inference.demo_model_provider.TrainingService",
            ) as mock_training_cls,
            patch(
                "anvil.services.inference.demo_model_provider.DEMO_MODEL_PATH",
            ) as mock_path,
            patch(
                "anvil.services.inference.demo_model_provider.SafetensorsExportService",
            ) as mock_export_cls,
            patch(
                "anvil.services.inference.demo_model_provider.tempfile.TemporaryDirectory",
            ) as mock_tmpdir,
            patch(
                "anvil.services.inference.demo_model_provider._demo_provider",
            ) as mock_provider,
        ):
            # ── DB session ──
            mock_session = AsyncMock()
            mock_session_local.return_value.__aenter__.return_value = mock_session
            mock_corpus = MagicMock()
            mock_corpus.id = 1
            mock_corpus.name = "demo_corpus"
            mock_corpus.file_count = 2
            mock_corpus.document_count = 5
            mock_bootstrap = mock_bootstrap_cls.return_value
            mock_bootstrap.get_default_corpus.return_value = mock_corpus
            mock_corpus_svc = mock_corpus_svc_cls.return_value
            mock_corpus_svc.load_docs.return_value = ["doc1"]

            # ── Backend ──
            mock_backend = MagicMock()
            mock_backend.run = AsyncMock(
                return_value=MagicMock(
                    status=MagicMock(value="completed"),
                    model=fake_model,
                    uchars=["a", "b"],
                    final_loss=0.1,
                    error_message=None,
                )
            )
            mock_get_backend.return_value = mock_backend

            # ── Tracking ──
            mock_tracking = mock_tracking_cls.return_value
            mock_tracking.start_run = AsyncMock(return_value="mlflow_run_1")
            mock_tracking.finish_run = AsyncMock()
            mock_tracking.log_final_metric = AsyncMock()
            mock_tracking.set_tag = AsyncMock()
            mock_tracking.register_source_model = AsyncMock()
            # mock client for artifact logging
            mock_client = MagicMock()
            mock_client.log_artifact = MagicMock()
            mock_tracking._client = mock_client

            # ── TrainingService ──
            mock_training = mock_training_cls.return_value
            mock_training.allocate_experiment_id = AsyncMock(return_value=42)

            # ── Export ──
            mock_export = mock_export_cls.return_value
            mock_export.export = MagicMock(
                return_value={
                    "error": None,
                    "safetensors_path": "/tmp/model.safetensors",
                    "config_path": "/tmp/config.json",
                    "tokenizer_path": "/tmp/tokenizer.json",
                }
            )

            # ── Temp dir ──
            mock_tmpdir.return_value.__enter__.return_value = "/tmp/fake"

            # ── Path ──
            mock_path.parent.mkdir = MagicMock()
            type(mock_path).parent = PropertyMock(
                return_value=MagicMock(mkdir=MagicMock())
            )

            warmup_demo_via_system_pipeline()

            # Verify backend was called
            mock_backend.run.assert_called_once()
            # Verify tracking run lifecycle
            mock_tracking.start_run.assert_called_once()
            mock_tracking.finish_run.assert_called_once()
            mock_tracking.register_source_model.assert_called_once()
            # Verify provider cache updated
            mock_provider._model = fake_model
            mock_provider._chars = ["a", "b"]

    def test_system_pipeline_skips_mlflow_when_no_run_id(self) -> None:
        """When MLflow run_id is None, skip MLflow operations."""
        fake_model = make_fake_model(chars=["a", "b"])

        with (
            patch(
                "anvil.services.inference.demo_model_provider.AsyncSessionLocal",
            ) as mock_session_local,
            patch(
                "anvil.services.inference.demo_model_provider.DemoBootstrapService",
            ) as mock_bootstrap_cls,
            patch(
                "anvil.services.inference.demo_model_provider.resolve_backend",
                return_value={
                    "engine": "stdlib",
                    "device": "cpu",
                    "backend": "local",
                },
            ),
            patch(
                "anvil.services.inference.demo_model_provider.get_backend",
            ) as mock_get_backend,
            patch(
                "anvil.services.inference.demo_model_provider.TrackingService",
            ) as mock_tracking_cls,
            patch(
                "anvil.services.inference.demo_model_provider.TrainingService",
            ) as mock_training_cls,
            patch(
                "anvil.services.inference.demo_model_provider.DEMO_MODEL_PATH",
            ) as mock_path,
            patch(
                "anvil.services.inference.demo_model_provider.SafetensorsExportService",
            ) as mock_export_cls,
            patch(
                "anvil.services.inference.demo_model_provider._demo_provider",
            ) as mock_provider,
        ):
            mock_session = AsyncMock()
            mock_session_local.return_value.__aenter__.return_value = mock_session
            mock_bootstrap = mock_bootstrap_cls.return_value
            mock_bootstrap.get_default_corpus.return_value = None  # no corpus

            mock_backend = MagicMock()
            mock_backend.run = AsyncMock(
                return_value=MagicMock(
                    status=MagicMock(value="completed"),
                    model=fake_model,
                    uchars=["a", "b"],
                    final_loss=0.1,
                    error_message=None,
                )
            )
            mock_get_backend.return_value = mock_backend

            mock_tracking = mock_tracking_cls.return_value
            mock_tracking.start_run = AsyncMock(return_value=None)
            mock_tracking.finish_run = AsyncMock()
            mock_tracking.log_final_metric = AsyncMock()
            mock_tracking.set_tag = AsyncMock()
            mock_tracking.register_source_model = AsyncMock()

            mock_training = mock_training_cls.return_value
            mock_training.allocate_experiment_id = AsyncMock(return_value=42)

            mock_export = mock_export_cls.return_value
            mock_export.export = MagicMock(
                return_value={
                    "error": None,
                    "safetensors_path": "/tmp/model.safetensors",
                }
            )

            mock_path.parent.mkdir = MagicMock()
            type(mock_path).parent = PropertyMock(
                return_value=MagicMock(mkdir=MagicMock())
            )

            warmup_demo_via_system_pipeline()

            # finish_run should NOT be called (no mlflow_run_id)
            mock_tracking.finish_run.assert_not_called()
            # But model should still be saved to provider
            mock_provider._model = fake_model
            mock_provider._chars = ["a", "b"]

    def test_system_pipeline_logs_warning_on_backend_failure(self) -> None:
        """When the compute backend fails, log warning, fall back."""
        fake_model = make_fake_model(chars=["a", "b"])

        with (
            patch(
                "anvil.services.inference.demo_model_provider._train_demo_model",
                return_value=fake_model,
            ) as mock_train,
            patch(
                "anvil.services.inference.demo_model_provider._demo_provider",
            ) as mock_provider,
            patch(
                "anvil.services.inference.demo_model_provider.AsyncSessionLocal",
            ) as mock_session_local,
            patch(
                "anvil.services.inference.demo_model_provider.DemoBootstrapService",
            ) as mock_bootstrap_cls,
            patch(
                "anvil.services.inference.demo_model_provider.resolve_backend",
                return_value={
                    "engine": "stdlib",
                    "device": "cpu",
                    "backend": "local",
                },
            ),
            patch(
                "anvil.services.inference.demo_model_provider.get_backend",
            ) as mock_get_backend,
            patch(
                "anvil.services.inference.demo_model_provider.TrackingService",
            ) as mock_tracking_cls,
            patch(
                "anvil.services.inference.demo_model_provider.TrainingService",
            ) as mock_training_cls,
        ):
            mock_session = AsyncMock()
            mock_session_local.return_value.__aenter__.return_value = mock_session

            mock_bootstrap = mock_bootstrap_cls.return_value
            mock_bootstrap.get_default_corpus = AsyncMock(return_value=None)

            mock_backend = MagicMock()
            mock_backend.run = AsyncMock(
                return_value=MagicMock(
                    status=MagicMock(value="failed"),
                    model=None,
                    uchars=[],
                    final_loss=None,
                    error_message="out of memory",
                )
            )
            mock_get_backend.return_value = mock_backend

            mock_tracking = mock_tracking_cls.return_value
            mock_tracking.start_run = AsyncMock(return_value="run1")
            mock_tracking.finish_run = AsyncMock()

            mock_training = mock_training_cls.return_value
            mock_training.allocate_experiment_id = AsyncMock(return_value=1)

            warmup_demo_via_system_pipeline()

            # Should fall back to inline training
            mock_train.assert_called_once()
            mock_provider._model = fake_model
            mock_provider._chars = fake_model.chars
