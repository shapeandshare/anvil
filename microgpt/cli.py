"""CLI entry points and MicroGPTWorkbench god class."""

import argparse
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


def _load_docs(corpus_id: int | None = None) -> list[str]:
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


def serve():
    cfg = get_config()
    uvicorn.run(
        "microgpt.api.app:app",
        host="0.0.0.0",
        port=cfg["port"],
        reload=False,
    )


def train():
    parser = argparse.ArgumentParser(
        description="Train GPT model"
    )
    parser.add_argument(
        "--corpus",
        type=int,
        default=None,
        help="Corpus ID to train on (default: input.txt)",
    )
    args, _ = parser.parse_known_args()
    docs = _load_docs(corpus_id=args.corpus)
    _, final_loss, samples, _ = run_training(docs)
    print(f"\nFinal loss: {final_loss:.4f}")
    print("\n--- Generated samples ---")
    for i, sample in enumerate(samples, 1):
        print(f"sample {i:2d}: {sample}")
    sys.exit(0)


def corpus_main():
    parser = argparse.ArgumentParser(
        description="Manage training corpora"
    )
    sub = parser.add_subparsers(dest="command")

    create_p = sub.add_parser("create", help="Create a new corpus")
    create_p.add_argument("root_path", help="Path to directory")
    create_p.add_argument("--name", required=True, help="Corpus name")
    create_p.add_argument("--description", help="Corpus description")
    create_p.add_argument(
        "--pattern", action="append", dest="include_patterns", help="Include pattern"
    )
    create_p.add_argument(
        "--ignore", action="append", dest="exclude_patterns", help="Exclude pattern"
    )
    create_p.add_argument(
        "--strategy",
        default="windowed",
        choices=["line", "windowed", "file"],
        help="Chunking strategy",
    )
    create_p.add_argument("--overlap", type=float, default=0.5, help="Chunk overlap")

    ingest_p = sub.add_parser("ingest", help="Ingest a corpus")
    ingest_p.add_argument("id", type=int, help="Corpus ID")

    list_p = sub.add_parser("list", help="List all corpora")

    show_p = sub.add_parser("show", help="Show corpus details")
    show_p.add_argument("id", type=int, help="Corpus ID")

    delete_p = sub.add_parser("delete", help="Delete a corpus")
    delete_p.add_argument("id", type=int, help="Corpus ID")

    files_p = sub.add_parser("files", help="List files in a corpus")
    files_p.add_argument("id", type=int, help="Corpus ID")

    args = parser.parse_args()

    import asyncio

    from microgpt.db.session import AsyncSessionLocal
    from microgpt.db.repositories.corpora import CorpusRepository
    from microgpt.services.corpora import CorpusService
    from microgpt.services.corpus_loader import CorpusLoader

    async def _run():
        async with AsyncSessionLocal() as session:
            repo = CorpusRepository(session)
            loader = CorpusLoader()
            svc = CorpusService(repo, loader)

            if args.command == "create":
                corpus = await svc.create(
                    name=args.name,
                    root_path=args.root_path,
                    description=args.description,
                    include_patterns=args.include_patterns,
                    exclude_patterns=args.exclude_patterns,
                    chunking_strategy=args.strategy,
                    chunk_overlap=args.overlap,
                )
                print(f"Created corpus {corpus.id}: {corpus.name}")

            elif args.command == "ingest":
                corpus = await svc.ingest(args.id)
                print(
                    f"Ingested corpus {corpus.id}: "
                    f"{corpus.file_count} files, "
                    f"{corpus.document_count} documents"
                )

            elif args.command == "list":
                corpora = await svc.list()
                for c in corpora:
                    print(
                        f"{c.id:3d}  {c.name:30s}  "
                        f"{c.file_count:4d} files  "
                        f"{c.document_count:5d} docs  "
                        f"{c.chunking_strategy}"
                    )

            elif args.command == "show":
                corpus = await svc.get(args.id)
                if corpus is None:
                    print(f"Corpus {args.id} not found")
                    return
                print(f"ID:          {corpus.id}")
                print(f"Name:        {corpus.name}")
                print(f"Root:        {corpus.root_path}")
                print(f"Strategy:    {corpus.chunking_strategy}")
                print(f"Overlap:     {corpus.chunk_overlap}")
                print(f"Files:       {corpus.file_count}")
                print(f"Documents:   {corpus.document_count}")

            elif args.command == "delete":
                ok = await svc.delete(args.id)
                print("Deleted" if ok else "Not found")

            elif args.command == "files":
                files = await svc.get_files(args.id)
                for f in files:
                    print(
                        f"{f.relative_path:50s}  "
                        f"{f.language or '?':10s}  "
                        f"{f.line_count or 0:5d} lines"
                    )

    asyncio.run(_run())


def stop():
    sup = ProcessSupervisor()
    sup.stop_all()