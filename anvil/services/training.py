import asyncio
import json
import threading
from collections.abc import Awaitable, Callable

from anvil.config import get_config
from anvil.core.engine import GPT, train
from anvil.core.torch_engine import torch_available, train_torch
from anvil.gpu import resolve_device


class StopRequested(Exception):
    """Raised when training is requested to stop."""
    pass


def _load_weights_into_model(model: GPT, weights: dict) -> None:
    """Load exported weight lists into a CPU GPT model.

    Handles both 2D matrices (attention, SwiGLU, embeddings) and
    1D vectors (RMSNorm learned scale parameters).
    """
    for k, data in weights.items():
        mat = model.state_dict[k]
        if isinstance(mat[0], list):
            # 2D matrix
            for i, row in enumerate(data):
                for j, val in enumerate(row):
                    mat[i][j].data = val
        else:
            # 1D vector (RMSNorm scales)
            for i, val in enumerate(data):
                mat[i].data = val


class TrainingService:
    def __init__(self):
        self._queues: dict[int, asyncio.Queue] = {}
        self._stop_events: dict[int, threading.Event] = {}
        self._running = 0
        self._run_metadata: dict[int, dict] = {}

    def store_run_metadata(self, run_id: int, *, mlflow_run_id: str | None = None, experiment_id: int | None = None) -> None:
        self._run_metadata[run_id] = {
            "mlflow_run_id": mlflow_run_id,
            "experiment_id": experiment_id,
        }

    def get_mlflow_run_id(self, run_id: int) -> str | None:
        meta = self._run_metadata.get(run_id)
        return meta.get("mlflow_run_id") if meta else None

    def get_experiment_id(self, run_id: int) -> int | None:
        meta = self._run_metadata.get(run_id)
        return meta.get("experiment_id") if meta else None

    def _load_docs(
        self, corpus_id: int | None = None, dataset_id: int | None = None
    ) -> list[str]:
        if dataset_id is not None:
            from anvil.db.repositories.datasets import DatasetRepository
            from anvil.db.session import AsyncSessionLocal
            from anvil.services.datasets import DatasetService

            async def _load_dataset():
                async with AsyncSessionLocal() as session:
                    repo = DatasetRepository(session)
                    svc = DatasetService(repo)
                    return await svc.load_docs(dataset_id)

            return asyncio.run(_load_dataset())

        if corpus_id is not None:
            from anvil.db.repositories.corpora import CorpusRepository
            from anvil.db.session import AsyncSessionLocal
            from anvil.services.corpora import CorpusService
            from anvil.services.corpus_loader import CorpusLoader

            async def _load():
                async with AsyncSessionLocal() as session:
                    repo = CorpusRepository(session)
                    loader = CorpusLoader()
                    svc = CorpusService(repo, loader)
                    return await svc.load_docs(corpus_id)

            return asyncio.run(_load())

        # Fallback: use default demo corpus when no corpus/dataset specified
        from anvil.db.repositories.corpora import CorpusRepository
        from anvil.db.session import AsyncSessionLocal
        from anvil.services.corpus_loader import CorpusLoader
        from anvil.services.corpora import CorpusService
        from anvil.services.demo_bootstrap import DemoBootstrapService, DEFAULT_CORPUS_NAME

        async def _load_default():
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

    def reserve_run(self) -> int:
        run_id = self._running
        self._running += 1
        self._queues[run_id] = asyncio.Queue()
        self._stop_events[run_id] = threading.Event()
        return run_id

    def stop_run(self, run_id: int) -> None:
        """Signal a running training to stop. Thread-safe."""
        event = self._stop_events.get(run_id)
        if event is not None:
            event.set()

    async def start_training(
        self,
        config: dict,
        run_id: int | None = None,
        on_complete: (
            Callable[[GPT, dict, float, list[str], list[str]], Awaitable[None]] | None
        ) = None,
        progress_callback_override: Callable[[int, float], None] | None = None,
    ) -> int:
        if run_id is None:
            run_id = self.reserve_run()
        queue = self._queues[run_id]

        loop = asyncio.get_event_loop()
        corpus_id = config.get("corpus_id")
        dataset_id = config.get("dataset_id")
        docs = await loop.run_in_executor(None, self._load_docs, corpus_id, dataset_id)

        use_gpu = config.get("use_gpu", False)
        cfg = get_config()
        preferred_device = config.get("device", cfg["device"])
        device = resolve_device(use_gpu=use_gpu, preferred=preferred_device or None)

        def progress_callback(step: int, loss: float) -> None:
            stop_event = self._stop_events.get(run_id)
            if stop_event is not None and stop_event.is_set():
                raise StopRequested(f"Training stopped at step {step}")
            asyncio.run_coroutine_threadsafe(
                queue.put(
                    {
                        "event": "metrics",
                        "data": json.dumps(
                            {"step": step, "loss": loss, "device": device}
                        ),
                    }
                ),
                loop,
            )
            if progress_callback_override:
                progress_callback_override(step, loss)

        def optimizer_state_callback(step: int, m: list, v: list, grads: list) -> None:
            snapshot_step = config.get("optimizer_snapshot_interval", 10)
            if step % snapshot_step == 0:
                asyncio.run_coroutine_threadsafe(
                    queue.put(
                        {
                            "event": "optimizer_state",
                            "data": json.dumps({
                                "step": step,
                                "params": [
                                    {"index": i, "m": round(m[i], 8), "v": round(v[i], 8), "grad": round(grads[i], 8)}
                                    for i in range(min(10, len(m)))
                                ],
                            }),
                        }
                    ),
                    loop,
                )

        # Dispatch to GPU or CPU engine
        stop_event = self._stop_events.get(run_id)
        stop_check = (lambda: stop_event.is_set()) if stop_event is not None else None

        use_gpu_backend = device != "cpu"

        try:
            if use_gpu_backend and torch_available():
                raw_weights, final_loss, samples, uchars = await loop.run_in_executor(
                    None,
                    lambda: train_torch(
                        docs,
                        device=device,
                        num_steps=config.get("num_steps", 1000),
                        n_embd=config.get("n_embd", 16),
                        n_head=config.get("n_head", 4),
                        n_layer=config.get("n_layer", 1),
                        block_size=config.get("block_size", 16),
                        learning_rate=config.get("learning_rate", 0.01),
                        temperature=config.get("temperature", 0.5),
                        progress_callback=progress_callback,
                        stop_check=stop_check,
                    ),
                )
                # Wrap GPU weights into a CPU GPT model for downstream compatibility
                model = GPT(
                    vocab_size=len(uchars) + 1,
                    n_embd=config.get("n_embd", 16),
                    n_head=config.get("n_head", 4),
                    n_layer=config.get("n_layer", 1),
                    block_size=config.get("block_size", 16),
                )
                _load_weights_into_model(model, raw_weights)

            else:
                model, final_loss, samples, uchars = await loop.run_in_executor(
                    None,
                    lambda: train(
                        docs,
                        num_steps=config.get("num_steps", 1000),
                        n_embd=config.get("n_embd", 16),
                        n_head=config.get("n_head", 4),
                        n_layer=config.get("n_layer", 1),
                        block_size=config.get("block_size", 16),
                        learning_rate=config.get("learning_rate", 0.01),
                        temperature=config.get("temperature", 0.5),
                        progress_callback=progress_callback,
                        optimizer_state_callback=optimizer_state_callback,
                        stop_check=stop_check,
                    ),
                )

        except StopRequested:
            await queue.put({
                "event": "error",
                "data": json.dumps({"message": "Training stopped by user"}),
            })
            raise
        finally:
            self._queues.pop(run_id, None)
            self._stop_events.pop(run_id, None)

        await queue.put(
            {
                "event": "complete",
                "data": json.dumps(
                    {
                        "final_loss": final_loss,
                        "samples": samples,
                        "device": device,
                    }
                ),
            }
        )

        if on_complete:
            await on_complete(model, config, final_loss, samples, uchars)

        return run_id

    def get_queue(self, run_id: int) -> asyncio.Queue | None:
        return self._queues.get(run_id)
