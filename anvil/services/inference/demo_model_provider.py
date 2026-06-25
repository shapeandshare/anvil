# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Demo model provider — provisions a tiny trained model for educational widgets.

Provides the ``DemoModelProvider`` class which lazily trains or loads a
small Llama model for demo/inference purposes, plus module-level helpers
for fallback corpus data and warm-up via the system pipeline.
"""

# pylint: disable=protected-access
# Intentional: module-level singleton attribute access from warmup functions.
# pylint: disable=broad-exception-caught
# Intentional: catch-all guards in fallback / startup code paths.

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, cast

from ...core.engine import LlamaModel

DEMO_MODEL_PATH = Path("data/models/demo/model.json")
""":py:class:`~pathlib.Path`: Filesystem path to the demo model checkpoint."""

# Minimal embedded fallback — used when the demo dataset has not been
# bootstrapped into the DB yet (e.g. first app startup before setup).
# Includes both uppercase and lowercase so the demo model's vocabulary
# supports any alphanumeric input in the tokenization widget.
_FALLBACK_CORPUS = [
    "the quick brown fox jumps over the lazy dog",
    "The Quick Brown Fox Jumps Over The Lazy Dog",
    "what's this? it's a demo!",
    "HI there, let's GO!",
    "hello HELLO",
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefghijklmnopqrstuvwxyz",
]
_DEMO_TRAIN_LOCK = threading.Lock()


def _train_demo_model(docs: list[str] | None = None) -> LlamaModel:
    """Train a tiny demo model on the given or fallback corpus.

    Parameters
    ----------
    docs : list[str], optional
        Training documents. Falls back to ``_FALLBACK_CORPUS`` when
        ``None``.

    Returns
    -------
    LlamaModel
        The trained demo model with its ``chars`` attribute set.
    """
    from ...core.engine import train

    model, _loss, _samples, uchars = train(
        docs or _FALLBACK_CORPUS,
        num_steps=400,
        n_embd=16,
        n_head=4,
        n_layer=1,
        block_size=16,
    )
    DEMO_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(DEMO_MODEL_PATH), uchars)
    model.chars = uchars
    return model


def warmup_demo_via_system_pipeline() -> None:
    """Train the demo model through the real system pipeline.

    Goes through: compute backend resolution -> engine training ->
    MLflow experiment/run creation -> metric logging -> model registration.

    Runs in a background thread during server startup. Falls back to the
    inline training path if MLflow or the compute backend is unavailable.
    """
    import logging

    logger = logging.getLogger(__name__)

    try:
        # Try to load docs from the bootstrapped demo corpus first
        docs: list[str] | None = None
        try:
            from ...db.repositories.corpora import CorpusRepository
            from ...db.session import AsyncSessionLocal
            from ..datasets.corpora import CorpusService
            from ..datasets.corpus_loader import CorpusLoader
            from ..demo.demo_bootstrap import DemoBootstrapService

            async def _get_docs() -> list[str] | None:
                async with AsyncSessionLocal() as session:
                    bootstrap = DemoBootstrapService(session)
                    corpus = await bootstrap.get_default_corpus()
                    if corpus is None:
                        return None
                    repo = CorpusRepository(session)
                    loader = CorpusLoader()
                    svc = CorpusService(repo, loader)
                    return await svc.load_docs(corpus.id)

            docs = asyncio.run(_get_docs())
        except Exception:
            pass

        docs = docs or _FALLBACK_CORPUS

        config: dict[str, object] = {
            "n_embd": 16,
            "n_head": 4,
            "n_layer": 1,
            "block_size": 16,
            "num_steps": 400,
            "learning_rate": 0.01,
            "temperature": 0.5,
        }

        from ..compute.compute_backend import ComputeBackend
        from ..compute.registry import get_backend
        from ..compute.resolve import resolve_backend
        from ..tracking.tracking import TrackingService
        from ..training.training import TrainingService

        async def _run() -> None:
            tracking_svc = TrackingService()
            resolved = resolve_backend({"compute_backend": ComputeBackend.LOCAL_CPU})
            backend_name = f"local-{resolved['engine']}"
            backend = get_backend(backend_name)

            mlflow_run_id = await tracking_svc.start_run(
                run_name="demo-warmup",
                params=config,
                engine_backend=resolved["engine"],
                device=resolved["device"],
            )

            # Allocate a numeric experiment ID for consistency with user training runs
            training_svc = TrainingService()
            experiment_id = await training_svc.allocate_experiment_id()
            if mlflow_run_id:
                await tracking_svc.set_tag(
                    mlflow_run_id, "anvil.experiment_id", str(experiment_id)
                )

            result = await backend.run(
                docs,
                config,
                progress_callback=lambda *args, **kwargs: None,
                stop_check=lambda: False,
            )

            if result.status.value != "completed" or result.model is None:
                logger.warning(
                    "Demo model warm-up via system pipeline failed: %s",
                    result.error_message,
                )
                return

            assert result.model is not None

            model = cast(LlamaModel, result.model)
            uchars = result.uchars

            if mlflow_run_id:
                await tracking_svc.finish_run(mlflow_run_id)
                await tracking_svc.log_final_metric(
                    mlflow_run_id, "final_loss", result.final_loss or 0.0
                )
                await tracking_svc.set_tag(
                    mlflow_run_id, "architectures", "LlamaForCausalLM"
                )
                await tracking_svc.set_tag(mlflow_run_id, "anvil.status", "finished")
                await tracking_svc.register_source_model(
                    run_id=mlflow_run_id, name="demo"
                )

            # ── Replicate dataset/corpus metadata tags that user training sets ──
            try:
                from ...db.session import AsyncSessionLocal
                from ..demo.demo_bootstrap import DemoBootstrapService

                async with AsyncSessionLocal() as sess:
                    bootstrap = DemoBootstrapService(sess)
                    corpus = await bootstrap.get_default_corpus()
                    if corpus and mlflow_run_id:
                        await tracking_svc.set_tag(
                            mlflow_run_id, "anvil.dataset.name", corpus.name
                        )
                        await tracking_svc.set_tag(
                            mlflow_run_id,
                            "anvil.corpus.file_count",
                            str(corpus.file_count or 0),
                        )
                        await tracking_svc.set_tag(
                            mlflow_run_id,
                            "anvil.corpus.document_count",
                            str(corpus.document_count or 0),
                        )
            except Exception:
                pass

            # ── Save to experiment-specific path for GET /experiments/{id} ──
            MODELS_DIR = Path("data/models")
            await asyncio.to_thread(MODELS_DIR.mkdir, parents=True, exist_ok=True)
            experiment_model_path = MODELS_DIR / f"experiment_{experiment_id}.json"
            model.save(str(experiment_model_path), uchars)

            # ── Run safetensors export & log artifacts to MLflow ──
            import tempfile

            from ..training.export import SafetensorsExportService

            with tempfile.TemporaryDirectory() as tmpdir:
                export_svc = SafetensorsExportService()
                export_result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: export_svc.export(model, tmpdir, uchars)
                )

                if export_result["error"]:
                    logger.warning(
                        "Demo safetensors export failed: %s",
                        export_result["error"],
                    )
                elif mlflow_run_id and export_result.get("safetensors_path"):
                    try:
                        client = tracking_svc._client
                        if client:
                            loop = asyncio.get_event_loop()
                            await loop.run_in_executor(
                                None,
                                lambda: client.log_artifact(
                                    mlflow_run_id,
                                    export_result["safetensors_path"],
                                ),
                            )
                            if export_result.get("config_path"):
                                await loop.run_in_executor(
                                    None,
                                    lambda: client.log_artifact(
                                        mlflow_run_id,
                                        export_result["config_path"],
                                    ),
                                )
                            if export_result.get("tokenizer_path"):
                                await loop.run_in_executor(
                                    None,
                                    lambda: client.log_artifact(
                                        mlflow_run_id,
                                        export_result["tokenizer_path"],
                                    ),
                                )
                    except Exception:
                        logger.exception(
                            "Failed to log demo safetensors artifacts to MLflow"
                        )

            # Save to demo path so it's immediately loadable by _demo_provider
            DEMO_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
            model.save(str(DEMO_MODEL_PATH), uchars)
            model.chars = uchars

            # Update _demo_provider cache so inference routes don't re-load
            _demo_provider._model = model
            _demo_provider._chars = uchars

            logger.info("Demo model warm-up complete (via system pipeline)")
            print("Demo model warm-up complete.", flush=True)

        asyncio.run(_run())

    except Exception:
        logger.warning(
            "Demo model warm-up failed, falling back to inline training",
            exc_info=True,
        )
        try:
            model = _train_demo_model()
            _demo_provider._model = model
            _demo_provider._chars = model.chars
        except Exception:
            pass


class DemoModelProvider:
    """Provisions a tiny demo model on first request.

    The demo model is a real trained model — all data returned is genuine.
    """

    def __init__(self) -> None:
        self._model: LlamaModel | None = None
        self._chars: list[str] | None = None

    def get_model(self) -> tuple[LlamaModel, list[str]]:
        """Return the loaded model and its character vocabulary.

        Lazily trains or loads the demo model on first call. Subsequent
        calls return the cached instance.

        Returns
        -------
        tuple[LlamaModel, list[str]]
            A tuple of ``(model, chars)`` where ``chars`` is the
            character-level vocabulary.
        """
        if self._model is not None:
            chars_list = self._chars if self._chars is not None else []
            return self._model, chars_list

        with _DEMO_TRAIN_LOCK:
            if self._model is not None:
                chars_list = self._chars if self._chars is not None else []
                return self._model, chars_list

            if DEMO_MODEL_PATH.exists():
                try:
                    model = LlamaModel.load(str(DEMO_MODEL_PATH))
                except ValueError:
                    # Old GPT-2 format detected — retrain with Llama architecture
                    model = _train_demo_model()
                    self._model = model
                    self._chars = model.chars
                    chars_list = self._chars if self._chars is not None else []
                    return model, chars_list
                if model.chars is not None:
                    self._model = model
                    self._chars = model.chars
                    return model, model.chars

            docs = self._load_demo_docs()
            model = _train_demo_model(docs)
            self._model = model
            self._chars = model.chars
            chars_list = self._chars if self._chars is not None else []
            return model, chars_list

    @staticmethod
    def _load_demo_docs() -> list[str] | None:
        """Try to load docs from the bootstrapped demo corpus; return None on failure."""
        try:
            from ...db.repositories.corpora import CorpusRepository
            from ...db.session import AsyncSessionLocal
            from ..datasets.corpora import CorpusService
            from ..datasets.corpus_loader import CorpusLoader
            from ..demo.demo_bootstrap import DemoBootstrapService

            async def _load() -> list[str] | None:
                async with AsyncSessionLocal() as session:
                    bootstrap = DemoBootstrapService(session)
                    corpus = await bootstrap.get_default_corpus()
                    if corpus is None:
                        return None
                    repo = CorpusRepository(session)
                    loader = CorpusLoader()
                    svc = CorpusService(repo, loader)
                    return await svc.load_docs(corpus.id)

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is None:
                return asyncio.run(_load())
            else:
                # Running event loop detected (e.g. FastAPI startup).
                # Run async DB access in a separate thread with its own loop.
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, _load())
                    return future.result()
        except Exception:
            return None

    def info(self) -> dict[str, Any]:
        """Return demo model metadata.

        Returns
        -------
        dict[str, Any]
            Dict with ``id`` (``None``), ``version`` (``None``),
            ``name`` (``"demo"``), and ``is_demo`` (``True``).
        """
        return {"id": None, "version": None, "name": "demo", "is_demo": True}


_demo_provider = DemoModelProvider()
"""Module-level singleton used by ``InferenceService`` and warm-up pipeline."""
