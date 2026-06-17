from __future__ import annotations

import asyncio
import json
import threading
import time
from collections import deque
from collections.abc import Awaitable, Callable

from anvil.config import get_config

# ── compute backend framework ──────────────────────────────────────────
from anvil.services.compute import ComputeResult, get_backend, register, resolve_backend

# Side-effect imports: each module registers its backends at module level.
import anvil.services.compute.local  # noqa: F401 — registers local-stdlib, local-torch
import anvil.services.compute.modal_backend  # noqa: F401 — registers modal


class StopRequested(Exception):
    """Raised when training is requested to stop."""
    pass


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
            Callable[[ComputeResult, dict], Awaitable[None]] | None
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

        # ── resolve backend ───────────────────────────────────────────
        resolved = resolve_backend(config)
        backend_name: str = resolved["backend"]  # "local" | "modal"
        engine_name: str = resolved["engine"]  # "stdlib" | "torch"
        device: str = resolved["device"]  # "cpu" | "cuda:0" | "mps"

        # Inject device into config so backends can read it
        config["device"] = device

        _num_steps = config.get("num_steps", 1000)
        _start_time = time.monotonic()
        _step_timestamps: deque = deque(maxlen=20)

        def progress_callback(step: int, loss: float) -> None:
            stop_event = self._stop_events.get(run_id)
            if stop_event is not None and stop_event.is_set():
                raise StopRequested(f"Training stopped at step {step}")

            now = time.monotonic()
            _step_timestamps.append(now)
            elapsed_sec = now - _start_time

            steps_per_sec: float | None = None
            eta_sec: float | None = None
            if len(_step_timestamps) >= 2:
                window_elapsed = _step_timestamps[-1] - _step_timestamps[0]
                window_intervals = len(_step_timestamps) - 1
                steps_per_sec = (
                    window_intervals / window_elapsed if window_elapsed > 0 else 0.0
                )
                if len(_step_timestamps) >= 5:
                    remaining = max(0, _num_steps - step - 1)
                    eta_sec = (
                        remaining / steps_per_sec
                        if steps_per_sec and steps_per_sec > 0
                        else None
                    )

            asyncio.run_coroutine_threadsafe(
                queue.put(
                    {
                        "event": "metrics",
                        "data": json.dumps(
                            {
                                "step": step,
                                "loss": loss,
                                "device": device,
                                "elapsed_sec": elapsed_sec,
                                "steps_per_sec": steps_per_sec,
                                "eta_sec": eta_sec,
                            }
                        ),
                    }
                ),
                loop,
            )
            if progress_callback_override:
                progress_callback_override(step, loss)

        # ── get backend from registry ─────────────────────────────────
        backend = get_backend(backend_name)

        stop_event = self._stop_events.get(run_id)
        stop_check = (lambda: stop_event.is_set()) if stop_event is not None else (lambda: False)

        # ── remote: emit submitted event before launching ─────────────
        if backend_name == "modal":
            asyncio.run_coroutine_threadsafe(
                queue.put({
                    "event": "submitted",
                    "data": json.dumps({
                        "backend": backend_name,
                        "device": device,
                    }),
                }),
                loop,
            )

        try:
            result = await backend.run(
                docs,
                config,
                progress_callback=progress_callback,
                stop_check=stop_check,
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

    def get_queue(self, run_id: int) -> asyncio.Queue | None:
        return self._queues.get(run_id)
