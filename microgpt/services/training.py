import asyncio
import json
import os
import random
import urllib.request
from collections.abc import Awaitable, Callable

from microgpt.core.engine import GPT, train


class TrainingService:
    def __init__(self):
        self._queues: dict[int, asyncio.Queue] = {}
        self._running = 0

    def _load_docs(self, corpus_id: int | None = None, dataset_id: int | None = None) -> list[str]:
        if dataset_id is not None:
            from microgpt.db.session import AsyncSessionLocal
            from microgpt.db.repositories.datasets import DatasetRepository
            from microgpt.services.datasets import DatasetService

            async def _load_dataset():
                async with AsyncSessionLocal() as session:
                    repo = DatasetRepository(session)
                    svc = DatasetService(repo)
                    return await svc.load_docs(dataset_id)

            return asyncio.run(_load_dataset())

        if corpus_id is not None:
            import asyncio

            from microgpt.db.session import AsyncSessionLocal
            from microgpt.db.repositories.corpora import CorpusRepository
            from microgpt.services.corpora import CorpusService
            from microgpt.services.corpus_loader import CorpusLoader

            async def _load():
                async with AsyncSessionLocal() as session:
                    repo = CorpusRepository(session)
                    loader = CorpusLoader()
                    svc = CorpusService(repo, loader)
                    return await svc.load_docs(corpus_id)

            return asyncio.run(_load())

        if not os.path.exists("input.txt"):
            url = (
                "https://raw.githubusercontent.com/karpathy/makemore/988aa59/names.txt"
            )
            urllib.request.urlretrieve(url, "input.txt")
        with open("input.txt") as f:
            docs = [line.strip() for line in f if line.strip()]
        random.shuffle(docs)
        return docs

    def reserve_run(self) -> int:
        run_id = self._running
        self._running += 1
        self._queues[run_id] = asyncio.Queue()
        return run_id

    async def start_training(
        self,
        config: dict,
        run_id: int | None = None,
        on_complete: Callable[[GPT, dict, float, list[str], list[str]], Awaitable[None]] | None = None,
        progress_callback_override: Callable[[int, float], None] | None = None,
    ) -> int:
        if run_id is None:
            run_id = self.reserve_run()
        queue = self._queues[run_id]

        loop = asyncio.get_event_loop()
        corpus_id = config.get("corpus_id")
        dataset_id = config.get("dataset_id")
        docs = await loop.run_in_executor(None, self._load_docs, corpus_id, dataset_id)

        def progress_callback(step: int, loss: float) -> None:
            asyncio.run_coroutine_threadsafe(
                queue.put(
                    {
                        "event": "metrics",
                        "data": json.dumps({"step": step, "loss": loss}),
                    }
                ),
                loop,
            )
            if progress_callback_override:
                progress_callback_override(step, loss)

        model, final_loss, samples, uchars = await loop.run_in_executor(
            None,
            lambda: train(
                docs,
                num_steps=config.get("num_steps", 1000),
                n_embd=config.get("n_embd", 16),
                n_head=config.get("n_head", 4),
                n_layer=config.get("n_layer", 1),
                learning_rate=config.get("learning_rate", 0.01),
                temperature=config.get("temperature", 0.5),
                progress_callback=progress_callback,
            ),
        )

        await queue.put(
            {
                "event": "complete",
                "data": json.dumps({"final_loss": final_loss, "samples": samples}),
            }
        )
        self._queues.pop(run_id, None)

        if on_complete:
            await on_complete(model, config, final_loss, samples, uchars)

        return run_id

    def get_queue(self, run_id: int) -> asyncio.Queue | None:
        return self._queues.get(run_id)
