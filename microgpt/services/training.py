import asyncio
import json
import os
import random
import urllib.request

from microgpt.core.engine import train


class TrainingService:
    def __init__(self):
        self._queues: dict[int, asyncio.Queue] = {}
        self._running = 0

    def _load_docs(self) -> list[str]:
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

    async def start_training(self, config: dict, run_id: int | None = None) -> int:
        if run_id is None:
            run_id = self.reserve_run()
        queue = self._queues[run_id]

        loop = asyncio.get_event_loop()
        docs = await loop.run_in_executor(None, self._load_docs)

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

        _, final_loss, samples = await loop.run_in_executor(
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
        return run_id

    def get_queue(self, run_id: int) -> asyncio.Queue | None:
        return self._queues.get(run_id)
