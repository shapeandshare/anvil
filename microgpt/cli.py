"""CLI entry points and MicroGPTWorkbench god class."""

import os
import random
import sys
import urllib.request

import uvicorn

from microgpt.config import get_config
from microgpt.core.engine import train as run_training
from microgpt.services.training import TrainingService
from microgpt.supervisor.supervisor import ProcessSupervisor


class MicroGPTWorkbench:
    def __init__(self):
        self._training = TrainingService()

    @property
    def training(self) -> TrainingService:
        return self._training


def _load_docs() -> list[str]:
    if not os.path.exists("input.txt"):
        url = "https://raw.githubusercontent.com/karpathy/makemore/988aa59/names.txt"
        urllib.request.urlretrieve(url, "input.txt")
    with open("input.txt") as f:
        docs = [line.strip() for line in f if line.strip()]
    random.shuffle(docs)
    return docs


def serve():
    cfg = get_config()
    uvicorn.run(
        "microgpt.api.app:app",
        host="0.0.0.0",
        port=cfg["port"],
        reload=False,
    )


def train():
    docs = _load_docs()
    _, final_loss, samples, _ = run_training(docs)
    print(f"\nFinal loss: {final_loss:.4f}")
    print("\n--- Generated samples ---")
    for i, sample in enumerate(samples, 1):
        print(f"sample {i:2d}: {sample}")
    sys.exit(0)


def stop():
    sup = ProcessSupervisor()
    sup.stop_all()
