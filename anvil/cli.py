"""CLI entry points and AnvilWorkbench god class."""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys

import uvicorn

from anvil.config import get_config
from anvil.services.models import ModelRegistryService
from anvil.services.training import TrainingService
from anvil.supervisor.supervisor import kill_pid_file, write_pid

logger = logging.getLogger(__name__)


class AnvilWorkbench:
    def __init__(self):
        self._training = TrainingService()

    @property
    def training(self) -> TrainingService:
        return self._training

    @property
    def registry(self) -> ModelRegistryService:
        raise NotImplementedError("Use get_registry_service() for async access")


def _load_docs(corpus_id: int | None = None) -> list[str]:
    if corpus_id is not None:
        import asyncio

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

    from anvil.db.session import AsyncSessionLocal
    from anvil.services.demo_bootstrap import DemoBootstrapService, DEFAULT_CORPUS_NAME

    async def _load_default():
        import asyncio

        async with AsyncSessionLocal() as session:
            bootstrap = DemoBootstrapService(session)
            corpus = await bootstrap.get_default_corpus()
            if corpus is None:
                raise RuntimeError(
                    f"No demo corpus found. Run 'anvil bootstrap-datasets' first "
                    f"to import demo data (expected corpus: {DEFAULT_CORPUS_NAME})"
                )
            from anvil.db.repositories.corpora import CorpusRepository
            from anvil.services.corpus_loader import CorpusLoader
            from anvil.services.corpora import CorpusService

            repo = CorpusRepository(session)
            loader = CorpusLoader()
            svc = CorpusService(repo, loader)
            return await svc.load_docs(corpus.id)

    return asyncio.run(_load_default())


def serve():
    cfg = get_config()
    pid_path = write_pid("web", pid_dir=cfg["log_dir"])
    try:
        uvicorn.run(
            "anvil.api.app:app",
            host="0.0.0.0",
            port=cfg["port"],
            reload=False,
        )
    finally:
        pid_path.unlink(missing_ok=True)


def train():
    parser = argparse.ArgumentParser(description="Train Llama model")
    parser.add_argument(
        "--corpus",
        type=int,
        default=None,
        help="Corpus ID to train on (default: bundled demo corpus)",
    )
    parser.add_argument(
        "--dataset",
        type=int,
        default=None,
        help="Dataset ID to train on",
    )
    parser.add_argument(
        "--backend",
        type=str,
        default=None,
        choices=["auto", "local-cpu", "local-gpu", "modal"],
        help=(
            "Compute backend. "
            "auto=best available, local-cpu=CPU only, "
            "local-gpu=GPU if available else CPU, modal=Modal cloud GPU"
        ),
    )
    parser.add_argument(
        "--gpu",
        action="store_true",
        help="Alias for --backend local-gpu (mutually exclusive with --backend)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help='Device override (e.g. "cuda:0", "mps", "cpu")',
    )
    args, _ = parser.parse_known_args()

    # Resolve backend from --gpu/--backend
    if args.backend and args.gpu:
        parser.error("--backend and --gpu are mutually exclusive")
    use_gpu = args.gpu or os.getenv("USE_GPU", "").lower() in ("true", "1", "yes")
    compute_backend = args.backend or ("local-gpu" if use_gpu else "auto")

    from anvil.services.compute import resolve_backend
    from anvil.services.tracking import TrackingService
    from anvil.services.training import TrainingService

    svc = TrainingService()
    tracking_svc = TrackingService()

    resolved = resolve_backend({"compute_backend": compute_backend, "device": args.device or None})
    engine_backend: str = resolved["engine"]
    device: str = resolved["device"]

    config = {
        "compute_backend": compute_backend,
        "device": device,
        "corpus_id": args.corpus,
        "dataset_id": args.dataset,
    }

    async def _run():
        from anvil.services.tracking import TrackingService

        TrackingService.enable_system_metrics()
        mlflow_run_id = await tracking_svc.start_run(
            run_name=None,
            params={
                "corpus_id": args.corpus,
                "dataset_id": args.dataset,
                "compute_backend": compute_backend,
            },
            engine_backend=engine_backend,
            device=device,
        )

        from anvil.db.repositories.experiments import ExperimentRepository
        from anvil.db.session import AsyncSessionLocal

        experiment_id = None
        async with AsyncSessionLocal() as session:
            repo = ExperimentRepository(session)
            exp = await repo.create_running(
                config_id=None,
                run_name="cli-run",
                mlflow_run_id=mlflow_run_id or None,
                dataset_id=args.dataset,
                corpus_id=args.corpus,
                engine_backend=engine_backend,
                device=device,
            )
            experiment_id = exp.id
            await session.commit()

        run_id = svc.reserve_run()

        _progress_tasks: set[asyncio.Task] = set()

        def progress_cb(step: int, loss: float) -> None:
            try:
                loop = asyncio.get_event_loop()
                t = loop.create_task(
                    tracking_svc.log_metric(mlflow_run_id, "loss", loss, step=step)
                )
                _progress_tasks.add(t)
                t.add_done_callback(_progress_tasks.discard)
            except Exception:
                pass

        final_loss_holder: list[float] = []

        async def on_complete(result, cfg: dict) -> None:
            final_loss = result.final_loss or 0.0
            model = result.model
            samples = result.samples
            uchars = result.uchars
            final_loss_holder.append(final_loss)
            await tracking_svc.finish_run(mlflow_run_id)
            await tracking_svc.log_final_metric(mlflow_run_id, "final_loss", final_loss)
            if mlflow_run_id:
                registry_name = None
                if args.dataset is not None:
                    from anvil.db.repositories.datasets import DatasetRepository

                    async with AsyncSessionLocal() as sess:
                        ds_repo = DatasetRepository(sess)
                        ds = await ds_repo.get(args.dataset)
                        if ds:
                            registry_name = ds.name
                elif args.corpus is not None:
                    from anvil.db.repositories.corpora import CorpusRepository

                    async with AsyncSessionLocal() as sess:
                        corp_repo = CorpusRepository(sess)
                        corpus = await corp_repo.get(args.corpus)
                        if corpus:
                            registry_name = corpus.name

                try:
                    await tracking_svc.register_source_model(
                        run_id=mlflow_run_id,
                        name=registry_name,
                        dataset_id=args.dataset,
                        corpus_id=args.corpus,
                    )
                except Exception:
                    logger.exception("Failed to register model for CLI training run")

            # Auto-export safetensors after every successful local training
            # (remote jobs export inside the cloud — Q-B corrected)
            if model is not None:
                import tempfile

                from anvil.services.export import SafetensorsExportService

                export_svc = SafetensorsExportService()
                with tempfile.TemporaryDirectory() as tmpdir:
                    export_result = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: export_svc.export(model, tmpdir, uchars)
                    )
                    if export_result["error"]:
                        logger.warning(
                            "Safetensors export failed: %s", export_result["error"]
                        )
                    else:
                        if mlflow_run_id and export_result["safetensors_path"]:
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
                                    if export_result["config_path"]:
                                        await loop.run_in_executor(
                                            None,
                                            lambda: client.log_artifact(
                                                mlflow_run_id,
                                                export_result["config_path"],
                                            ),
                                        )
                                    if export_result["tokenizer_path"]:
                                        await loop.run_in_executor(
                                            None,
                                            lambda: client.log_artifact(
                                                mlflow_run_id,
                                                export_result["tokenizer_path"],
                                            ),
                                        )
                            except Exception:
                                logger.exception(
                                    "Failed to log safetensors artifacts to MLflow"
                                )

            async with AsyncSessionLocal() as session:
                from datetime import UTC, datetime

                repo = ExperimentRepository(session)
                await repo.mark_finished(
                    experiment_id,
                    final_loss=final_loss,
                    generated_samples=None,
                    completed_at=datetime.now(UTC),
                )
                await session.commit()

        try:
            await svc.start_training(
                config,
                run_id=run_id,
                on_complete=on_complete,
                progress_callback_override=progress_cb,
            )
        except Exception as e:
            await tracking_svc.fail_run(mlflow_run_id, reason=str(e))
            if experiment_id:
                async with AsyncSessionLocal() as session:
                    from datetime import UTC, datetime

                    repo = ExperimentRepository(session)
                    await repo.mark_failed(
                        experiment_id,
                        error_message=str(e),
                        completed_at=datetime.now(UTC),
                    )
                    await session.commit()
            raise

        queue = svc.get_queue(run_id)
        if queue is None:
            return
        while True:
            msg = await queue.get()
            if msg["event"] == "metrics":
                data = json.loads(msg["data"])
                print(
                    f"step {data['step']:6d} | loss {data['loss']:.4f} | device {data.get('device', 'cpu')}"
                )
            elif msg["event"] == "complete":
                data = json.loads(msg["data"])
                print(
                    f"\nFinal loss: {data['final_loss']:.4f} (device: {data.get('device', 'cpu')})"
                )
                print("\n--- Generated samples ---")
                for i, sample in enumerate(data.get("samples", []), 1):
                    print(f"sample {i:2d}: {sample}")
                break
            elif msg["event"] == "error":
                print(f"\nError: {msg['data']}")
                break

    asyncio.run(_run())
    sys.exit(0)


def corpus_main():
    parser = argparse.ArgumentParser(description="Manage training corpora")
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

    sub.add_parser("list", help="List all corpora")

    show_p = sub.add_parser("show", help="Show corpus details")
    show_p.add_argument("id", type=int, help="Corpus ID")

    delete_p = sub.add_parser("delete", help="Delete a corpus")
    delete_p.add_argument("id", type=int, help="Corpus ID")

    files_p = sub.add_parser("files", help="List files in a corpus")
    files_p.add_argument("id", type=int, help="Corpus ID")

    args = parser.parse_args()

    import asyncio

    from anvil.db.repositories.corpora import CorpusRepository
    from anvil.db.session import AsyncSessionLocal
    from anvil.services.corpora import CorpusService
    from anvil.services.corpus_loader import CorpusLoader

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
                corpus, _errors = await svc.ingest(args.id)
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


def _find_pid_by_port(port: int) -> list[int]:
    """Find process PIDs listening on a port using lsof."""
    import subprocess

    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        pids = [int(pid) for pid in result.stdout.strip().split()]
        # Filter out non-Python processes (system services, etc.)
        filtered = []
        for pid in pids:
            try:
                comm = subprocess.run(
                    ["ps", "-p", str(pid), "-o", "comm="],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                cmd = comm.stdout.strip().lower()
                if any(kw in cmd for kw in ("python", "mlflow", "uvicorn")):
                    filtered.append(pid)
            except (subprocess.TimeoutExpired, ValueError):
                pass
        return filtered
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        return []


def _kill_pids(pids: list[int], sig: int = signal.SIGTERM) -> bool:
    """Kill a list of PIDs. Returns True if at least one was killed."""
    killed = False
    for pid in pids:
        try:
            os.kill(pid, sig)
            killed = True
        except ProcessLookupError:
            pass
    return killed


def stop():
    cfg = get_config()
    pid_dir = cfg["log_dir"]
    web_killed = False
    mlflow_killed = False

    if kill_pid_file("web", pid_dir=pid_dir):
        print("Stopped web server.")
        web_killed = True

    if not cfg["mlflow_disable_local"]:
        if kill_pid_file("mlflow", pid_dir=pid_dir):
            print("Stopped MLflow server.")
            mlflow_killed = True

    # Always try port-based fallback, regardless of PID file results.
    print("Verifying ports are free...")
    web_pids = _find_pid_by_port(cfg["port"])
    if web_pids:
        _kill_pids(web_pids, signal.SIGTERM)
        _wait_and_sigkill(web_pids, cfg["port"])
        print(f"Stopped web server (PID{' '.join(str(p) for p in web_pids)}).")
        web_killed = True

    if not cfg["mlflow_disable_local"]:
        mlflow_pids = _find_pid_by_port(cfg["mlflow_port"])
        if mlflow_pids:
            _kill_pids(mlflow_pids, signal.SIGTERM)
            _wait_and_sigkill(mlflow_pids, cfg["mlflow_port"])
            print(
                f"Stopped MLflow server (PID{' '.join(str(p) for p in mlflow_pids)})."
            )
            mlflow_killed = True

    if not web_killed and not mlflow_killed:
        print("No running servers found.")


def _wait_and_sigkill(pids: list[int], port: int) -> None:
    """Wait briefly for processes to die, then SIGKILL any survivors.

    Verifies the port is actually free afterward.
    """
    import time

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        time.sleep(0.3)
        survivors = []
        for pid in pids:
            try:
                os.kill(pid, 0)
                survivors.append(pid)
            except ProcessLookupError:
                pass
        if not survivors:
            remaining = _find_pid_by_port(port)
            if not remaining:
                return
            pids = remaining
            survivors = remaining
        pids = survivors

    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def migrate_registry():
    """Migrate local model registry entries to MLflow model registry."""

    async def _run():
        from anvil.db.repositories.models import ModelRepository
        from anvil.db.session import AsyncSessionLocal
        from anvil.services.models import ModelRegistryService
        from anvil.services.tracking import TrackingService

        tracking_svc = TrackingService()
        async with AsyncSessionLocal() as session:
            repo = ModelRepository(session)
            svc = ModelRegistryService(repo)
            result = await svc.migrate_local_registry_to_mlflow(tracking_svc)
            print(f"Migration complete: {result}")

    asyncio.run(_run())


def bootstrap_datasets_main():
    """Import bundled demo data (corpora and datasets) from ``data/demo/``."""
    parser = argparse.ArgumentParser(description="Bootstrap demo datasets")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and report what would be imported without making changes",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed per-item progress",
    )
    args = parser.parse_args()

    async def _run():
        from anvil.db.session import AsyncSessionLocal
        from anvil.services.demo_bootstrap import DemoBootstrapService

        async with AsyncSessionLocal() as session:
            svc = DemoBootstrapService(session)

            if args.dry_run:
                print("Dry-run mode — scanning data/demo/...")
                bootstrap = await svc.bootstrap_all()
                if bootstrap.errors:
                    for err in bootstrap.errors:
                        print(f"  ⚠ {err}")
                print(f"\nWould create: {bootstrap.corpora_created} corpora, {bootstrap.datasets_created} datasets")
                print(f"Would skip:   {bootstrap.corpora_skipped} corpora, {bootstrap.datasets_skipped} datasets")
                return

            print("Bootstrapping demo data from data/demo/...")
            bootstrap = await svc.bootstrap_all()

            for err in bootstrap.errors:
                print(f"  ⚠ {err}")

            print(
                f"\nSummary: {bootstrap.corpora_created} corpora created, "
                f"{bootstrap.datasets_created} datasets created, "
                f"{bootstrap.corpora_skipped + bootstrap.datasets_skipped} skipped, "
                f"{len(bootstrap.errors)} errors"
            )
            print(f"Done in {bootstrap.total_time_ms / 1000:.1f}s")

            if bootstrap.errors:
                await session.rollback()
                sys.exit(1)
            await session.commit()
            sys.exit(0)

    asyncio.run(_run())
