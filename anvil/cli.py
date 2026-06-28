# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""CLI entry points and AnvilWorkbench god class.

Defines the command-line interface for anvil — ``anvil``,
``anvil train``, ``anvil corpus``, ``anvil stop``,
``anvil bootstrap-datasets``, and ``anvil db``.

Public Functions
----------------
main
    Top-level ``anvil`` entry point (intercepts flags, then serves).
serve
    Start the web server.
train
    Run a training session from CLI args.
corpus_main
    Manage training corpora (CRUD).
stop
    Stop web and MLflow servers.
bootstrap_datasets_main
    Import bundled demo data.
db_main
    Manage database schema migrations.
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any

import uvicorn

from . import __version__
from .api.api_key_store import ApiKeyStore
from .config import get_config
from .db.migration import MigrationService
from .db.migration_error import MigrationError
from .db.repositories.corpora import CorpusRepository
from .db.repositories.datasets import DatasetRepository
from .db.repositories.external_models import ExternalModelRepository
from .db.repositories.model_import_jobs import ModelImportJobRepository
from .db.session import AsyncSessionLocal
from .services._shared.import_types import SourceType
from .services.compute.compute_backend import ComputeBackend
from .services.compute.resolve import resolve_backend
from .services.datasets.chunking_strategy import ChunkingStrategy
from .services.datasets.corpora import CorpusService
from .services.datasets.corpus_loader import CorpusLoader
from .services.demo.demo_bootstrap import DEFAULT_CORPUS_NAME, DemoBootstrapService
from .services.model_import.hf_source import HfHubSource
from .services.model_import.local_source import LocalSource
from .services.model_import.model_import_service import ModelImportService
from .services.tracking.tracking import TrackingService
from .services.training.export import SafetensorsExportService
from .services.training.training import TrainingService
from .supervisor.supervisor import kill_pid_file, write_pid

logger = logging.getLogger(__name__)


class AnvilWorkbench:
    """God class exposing high-level application services.

    Provides a single entry point for service access from CLI and
    route handlers. Currently wraps :class:`TrainingService` and
    previously exposed the model registry (removed in favour of
    MLflow Model Registry).

    Attributes
    ----------
    training : TrainingService
        The training service instance.
    """

    def __init__(self) -> None:
        self._training = TrainingService()

    @property
    def training(self) -> TrainingService:
        """Return the training service instance.

        Returns
        -------
        TrainingService
        """
        return self._training

    # registry property removed — using MLflow Model Registry instead


def _load_docs(corpus_id: int | None = None) -> list[str]:
    """Load documents from a corpus or the default demo corpus.

    Parameters
    ----------
    corpus_id : int, optional
        Specific corpus ID to load. If ``None``, loads the bundled
        demo corpus.

    Returns
    -------
    list of str
        Document text strings.

    Raises
    ------
    RuntimeError
        If *corpus_id* is ``None`` and no demo corpus has been
        bootstrapped.
    """
    if corpus_id is not None:

        async def _load() -> list[str]:
            """Load documents for the specified corpus ID.

            Returns
            -------
            list of str
            """
            async with AsyncSessionLocal() as session:
                repo = CorpusRepository(session)
                loader = CorpusLoader()
                svc = CorpusService(repo, loader)
                return await svc.load_docs(corpus_id)

        return asyncio.run(_load())

    async def _load_default() -> list[str]:
        """Load documents from the default demo corpus.

        Returns
        -------
        list of str

        Raises
        ------
        RuntimeError
            If the default demo corpus has not been bootstrapped.
        """
        async with AsyncSessionLocal() as session:
            bootstrap = DemoBootstrapService(session)
            corpus = await bootstrap.get_default_corpus()
            if corpus is None:
                raise RuntimeError(
                    f"No demo corpus found. Run 'anvil bootstrap-datasets' first "
                    f"to import demo data (expected corpus: {DEFAULT_CORPUS_NAME})"
                )
            repo = CorpusRepository(session)
            loader = CorpusLoader()
            svc = CorpusService(repo, loader)
            return await svc.load_docs(corpus.id)

    return asyncio.run(_load_default())


def main() -> None:
    """Top-level entry point for the ``anvil`` command.

    Intercepts top-level flags (``--show-api-key``, ``--version``)
    before falling through to :func:`serve`.  This avoids starting
    uvicorn (and binding the port) when the user only wants a quick
    informational query.
    """
    if "--show-api-key" in sys.argv:
        show_api_key()
        return
    if "--version" in sys.argv:
        print(__version__)
        return
    serve()


def serve() -> None:
    """Start the anvil web server via uvicorn.

    Reads configuration from ``get_config()``, writes a PID file to
    the log directory, and starts uvicorn serving the FastAPI app.
    The PID file is cleaned up on shutdown.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s [%(name)s] %(message)s",
        force=True,
    )
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


def train() -> None:
    """Run a training session from CLI arguments.

    Parses command-line arguments for corpus/dataset selection,
    compute backend, device override, and orchestrates training with
    live progress reporting via the event queue. On completion,
    safetensors model artifacts are exported and logged to MLflow.
    """
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
        choices=[cb.value for cb in ComputeBackend],
        help=(
            "Compute backend. "
            "auto=auto-detect, local-cpu=CPU only, "
            "local-gpu=GPU if available else CPU, "
            "modal=Modal cloud GPU (local mode only, not available in SaaS)"
        ),
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help='Device override (e.g. "cuda:0", "mps", "cpu")',
    )
    args, _ = parser.parse_known_args()

    compute_backend = args.backend or "auto"

    svc = TrainingService()
    tracking_svc = TrackingService()

    resolved = resolve_backend(
        {"compute_backend": compute_backend, "device": args.device or None}
    )
    engine_backend: str = resolved["engine"]
    device: str = resolved["device"]

    config = {
        "compute_backend": compute_backend,
        "device": device,
        "corpus_id": args.corpus,
        "dataset_id": args.dataset,
    }

    async def _run() -> None:
        """Execute the training run with MLflow tracking and progress reporting.

        Starts an MLflow run, schedules training with callbacks for
        metrics and completion, then drains the event queue printing
        progress to stdout.
        """
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

        run_id = svc.reserve_run()

        _progress_tasks: set[asyncio.Task[Any]] = set()

        def progress_cb(step: int, loss: float) -> None:
            """Log training metrics to MLflow asynchronously.

            Parameters
            ----------
            step : int
                Current training step.
            loss : float
                Current loss value.
            """
            try:
                loop = asyncio.get_event_loop()
                t = loop.create_task(
                    tracking_svc.log_metric(mlflow_run_id, "loss", loss, step=step)
                )
                _progress_tasks.add(t)
                t.add_done_callback(_progress_tasks.discard)
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        final_loss_holder: list[float] = []

        async def on_complete(result: object, _cfg: dict[str, Any]) -> None:
            """Handle training completion: finalise MLflow run and export artifacts.

            Parameters
            ----------
            result
                Training result object with ``final_loss``, ``model``,
                ``samples``, and ``uchars`` attributes.
            cfg : dict
                Training configuration dictionary.
            """
            final_loss = result.final_loss or 0.0  # type: ignore[attr-defined]
            model = result.model  # type: ignore[attr-defined]
            uchars = result.uchars  # type: ignore[attr-defined]
            final_loss_holder.append(final_loss)
            await tracking_svc.finish_run(mlflow_run_id)
            await tracking_svc.log_final_metric(mlflow_run_id, "final_loss", final_loss)
            if mlflow_run_id:
                registry_name = None
                if args.dataset is not None:
                    async with AsyncSessionLocal() as sess:
                        ds_repo = DatasetRepository(sess)
                        ds = await ds_repo.get(args.dataset)
                        if ds:
                            registry_name = ds.name
                elif args.corpus is not None:
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
                except Exception:  # pylint: disable=broad-exception-caught
                    logger.exception("Failed to register model for CLI training run")

            # Auto-export safetensors after every successful local training
            # (remote jobs export inside the cloud — Q-B corrected)
            if model is not None:
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
                                client = (
                                    tracking_svc._client
                                )  # pylint: disable=protected-access
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
                            except Exception:  # pylint: disable=broad-exception-caught
                                logger.exception(
                                    "Failed to log safetensors artifacts to MLflow"
                                )

        try:
            await svc.start_training(
                config,
                run_id=run_id,
                on_complete=on_complete,
                progress_callback_override=progress_cb,
            )
        except Exception as e:
            await tracking_svc.fail_run(mlflow_run_id, _reason=str(e))
            raise

        queue = svc.get_queue(run_id)
        if queue is None:
            return
        while True:
            msg = await queue.get()
            if msg["event"] == "metrics":
                data = json.loads(str(msg["data"]))
                print(
                    f"step {data['step']:6d} | loss {data['loss']:.4f} | device {data.get('device', 'cpu')}"
                )
            elif msg["event"] == "complete":
                data = json.loads(str(msg["data"]))
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


def show_api_key() -> None:
    """Print the configured API key to stdout.

    Reads the persisted key from the API key store.  If the key file
    does not exist (e.g. the server has never been started), prints an
    error and exits with status 1.
    """
    store = ApiKeyStore()
    key = store.key
    if key is None:
        print("No API key found. Start the server first with 'anvil'.", file=sys.stderr)
        sys.exit(1)
    print(key)


def corpus_main() -> None:
    """Manage training corpora via the CLI.

    Provides subcommands for creating, ingesting, listing, showing,
    deleting, and listing files of training corpora.

    Subcommands: ``create``, ``ingest``, ``list``, ``show``,
    ``delete``, ``files``.
    """
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
        default=ChunkingStrategy.WINDOWED.value,
        choices=[cs.value for cs in ChunkingStrategy],
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

    async def _run() -> None:
        """Execute the corpus management command.

        Dispatches to the appropriate ``CorpusService`` method based
        on the parsed subcommand and prints results to stdout.
        """
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
                corpora = await svc.list_all()
                for c in corpora:
                    print(
                        f"{c.id:3d}  {c.name:30s}  "
                        f"{c.file_count:4d} files  "
                        f"{c.document_count:5d} docs  "
                        f"{c.chunking_strategy}"
                    )

            elif args.command == "show":
                show_result = await svc.get(args.id)
                if show_result is None:
                    print(f"Corpus {args.id} not found")
                    return
                print(f"ID:          {show_result.id}")
                print(f"Name:        {show_result.name}")
                print(f"Root:        {show_result.root_path}")
                print(f"Strategy:    {show_result.chunking_strategy}")
                print(f"Overlap:     {show_result.chunk_overlap}")
                print(f"Files:       {show_result.file_count}")
                print(f"Documents:   {show_result.document_count}")

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
    """Find Python-related process PIDs listening on a given port.

    Uses ``lsof`` to discover listening processes on *port*, then
    filters to only those whose command name contains ``python``,
    ``mlflow``, or ``uvicorn``.

    Parameters
    ----------
    port : int
        TCP port number to check.

    Returns
    -------
    list of int
        PIDs of matching processes, or an empty list.
    """
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
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
                    check=False,
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


def stop() -> None:
    """Stop web and MLflow servers.

    Reads PID files from the log directory and sends ``SIGTERM`` to
    the corresponding processes. Falls back to port-based discovery
    via ``lsof`` if PID files are missing. Verifies ports are freed
    and escalates to ``SIGKILL`` if necessary.
    """
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


def bootstrap_datasets_main() -> None:
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

    async def _run() -> None:
        """Execute the bootstrap process.

        Runs in dry-run or live mode, printing a summary of
        created/skipped corpora and datasets. On errors in live
        mode the session is rolled back.
        """
        async with AsyncSessionLocal() as session:
            svc = DemoBootstrapService(session)

        if args.dry_run:
            print("Dry-run mode — scanning data/demo/...")
            bootstrap = await svc.bootstrap_all()
            if bootstrap.errors:
                for err in bootstrap.errors:
                    print(f"  ⚠ {err}")
            print(
                f"\nWould create: {bootstrap.corpora_created} corpora, {bootstrap.datasets_created} datasets"
            )
            print(
                f"Would skip:   {bootstrap.corpora_skipped} corpora, {bootstrap.datasets_skipped} datasets"
            )
            return

        bootstrap = await svc.bootstrap_all()
        if bootstrap.corpora_created > 0 or bootstrap.datasets_created > 0:
            print("Bootstrapping demo data from data/demo/...")

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


def db_main(argv: list[str] | None = None) -> None:
    """CLI subcommands for database schema management.

    Usage: anvil db <upgrade|downgrade|current|history|revision|stamp|verify>
    """
    parser = argparse.ArgumentParser(description="Manage database schema migrations")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("upgrade", help="Apply all pending migrations")
    sub.add_parser("current", help="Show current migration revision")
    sub.add_parser("history", help="Show migration history")
    sub.add_parser("verify", help="Check all ORM model tables exist in the database")

    downgrade_p = sub.add_parser("downgrade", help="Roll back one or more migrations")
    downgrade_p.add_argument(
        "revision",
        nargs="?",
        default="-1",
        help="Revision to downgrade to (default: -1 = one step back)",
    )

    revision_p = sub.add_parser("revision", help="Auto-generate a new migration")
    revision_p.add_argument(
        "-m", "--message", required=True, help="Migration description"
    )

    stamp_p = sub.add_parser("stamp", help="Stamp the database at a revision")
    stamp_p.add_argument("revision", help="Revision hash to stamp")

    args = parser.parse_args(argv)

    async def _run() -> None:
        """Execute the database migration command.

        Dispatches to the appropriate ``MigrationService`` method
        based on the parsed subcommand (``upgrade``, ``downgrade``,
        ``current``, ``history``, ``revision``, or ``stamp``).
        """
        svc = MigrationService()
        try:
            if args.command == "upgrade":
                before, after = await svc.upgrade()
                print(
                    f"All migrations applied. Database at revision: {after or '<base>'} (HEAD)"
                    if before != after
                    else f"Database already at latest revision: {after or '<base>'} (HEAD)"
                )
            elif args.command == "downgrade":
                result = await svc.downgrade(args.revision)
                print(f"Downgraded to revision: {result or '<base>'}")
            elif args.command == "current":
                rev = await svc.current()
                print(rev or "<base>")
            elif args.command == "history":
                entries = await svc.history()
                current_rev = await svc.current()
                for entry in entries:
                    down = entry["down_revision"]
                    rev = entry["revision"]
                    msg = entry["message"]
                    head = " (HEAD)" if rev == current_rev else ""
                    print(f"{down} -> {rev}{head} {msg}".strip())
            elif args.command == "revision":
                rev = await svc.create_revision(args.message)
                print(f"Generated migration revision: {rev}")
            elif args.command == "stamp":
                await svc.stamp(args.revision)
                print(f"Stamped database at revision: {args.revision}")
            elif args.command == "verify":
                missing = await MigrationService.verify_table_integrity()
                if not missing:
                    print("All ORM model tables present in database.")
                else:
                    print(
                        f"Missing {len(missing)} table(s): {', '.join(missing)}",
                        file=sys.stderr,
                    )
                    print(
                        "Fix: rm data/anvil-state.db && make run",
                        file=sys.stderr,
                    )
                    sys.exit(1)
        except MigrationError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

    asyncio.run(_run())


def import_main() -> None:
    """Import an external model via the CLI."""
    parser = argparse.ArgumentParser(
        description="Import a model from an external source"
    )
    parser.add_argument("source", help="Source type: huggingface or local")
    parser.add_argument("identifier", help="Source-specific model identifier")
    parser.add_argument("--name", help="Display name (auto-derived if omitted)")
    parser.add_argument("--revision", default="main", help="Source revision")
    args = parser.parse_args()

    async def _run() -> None:
        async with AsyncSessionLocal() as session:
            repo = ExternalModelRepository(session)
            job_repo = ModelImportJobRepository(session)
            svc = ModelImportService(
                repo,
                job_repo,
                {
                    SourceType.HUGGINGFACE: HfHubSource(),
                    SourceType.LOCAL: LocalSource(),
                },
            )
            job_id = await svc.submit_import(
                source=args.source,
                identifier=args.identifier,
                revision=args.revision,
                name=args.name,
            )
            await svc.run_import(job_id)
            await session.commit()
            print(f"Import complete. Job ID: {job_id}")

    asyncio.run(_run())


def import_status_main() -> None:
    """Check the status of an import job via the CLI."""
    parser = argparse.ArgumentParser(description="Check import job status")
    parser.add_argument("job_id", type=int, help="Import job ID")
    args = parser.parse_args()

    async def _run() -> None:
        async with AsyncSessionLocal() as session:
            repo = ExternalModelRepository(session)
            job_repo = ModelImportJobRepository(session)
            svc = ModelImportService(repo, job_repo, {})
            job = await svc.get_job_status(args.job_id)
            if job is None:
                print(f"Import job {args.job_id} not found", file=sys.stderr)
                sys.exit(1)
            print(f"Status: {job.status}")
            if job.error_code:
                print(f"Error: [{job.error_code}] {job.error_message}")
            if job.external_model_id:
                print(f"External model ID: {job.external_model_id}")

    asyncio.run(_run())
