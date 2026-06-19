"""FastAPI web application factory.

Creates and configures the FastAPI application instance with static file
serving, Jinja2 templates, MLflow integration, and demo data bootstrapping.
Manages the full application lifecycle via an ``asynccontextmanager`` lifespan.
"""

import logging
from contextlib import asynccontextmanager
from importlib.metadata import version as _get_version
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..config import get_config
from ..db import models  # noqa: F401 — register ORM models with Base.metadata
from ..db.migration import MigrationService
from ..db.session import init_engine
from ..supervisor.services import MLflowService
from .v1.router import router as v1_router

logger = logging.getLogger(__name__)

MLFLOW_EXPERIMENT_NAME = "anvil"
"""str: The default MLflow experiment name used for all training runs."""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager handling startup and shutdown.

    On startup:
      1. Initializes the async SQLAlchemy engine and runs Alembic migrations.
      2. Starts the MLflow service (unless ``mlflow_disable_local`` is set).
      3. Enables system metrics collection via ``TrackingService``.
      4. Reconciles orphaned MLflow runs.
      5. Bootstraps demo corpora and datasets from ``data/demo/`` (best-effort).
      6. Warms up the demo model in a background thread via the full system
         pipeline (compute backend -> MLflow tracking -> model registration).

    On shutdown:
      1. Stops the MLflow service if it was started by this process.

    Parameters
    ----------
    app : FastAPI
        The FastAPI application instance. State is stored in ``app.state``.
    """
    print("Setting up database...", flush=True)
    await init_engine()
    migration_svc = MigrationService()
    await migration_svc.ensure_migrated()

    cfg = get_config()
    if cfg["mlflow_disable_local"]:
        app.state.mlflow = None
    else:
        mlflow_svc = MLflowService()
        mlflow_svc.start()
        app.state.mlflow = mlflow_svc

    from ..services.tracking.tracking import TrackingService

    TrackingService.enable_system_metrics()

    try:
        await TrackingService().reconcile_orphans()
    except Exception:
        pass

    # Seed the approved-license catalog (idempotent; before demo
    # bootstrap so license FK refs resolve).
    try:
        from ..db.session import AsyncSessionLocal
        from ..workbench import AnvilWorkbench

        async with AsyncSessionLocal() as session:
            wb = AnvilWorkbench(session)
            count = await wb.governance.seed_catalog()
            if count > 0:
                logger.info(
                    "Seeded %d licenses into the approved-license catalog", count
                )
            await session.commit()
    except Exception:
        pass

    # Auto-bootstrap demo data if not yet imported (best-effort)
    try:
        from ..db.session import AsyncSessionLocal
        from ..services.demo.demo_bootstrap import DemoBootstrapService

        async with AsyncSessionLocal() as session:
            svc = DemoBootstrapService(session)
            result = await svc.bootstrap_all()
            if result.corpora_created > 0 or result.datasets_created > 0:
                logger.info(
                    "Bootstrapped %d corpora, %d datasets from data/demo/",
                    result.corpora_created,
                    result.datasets_created,
                )
            await session.commit()
    except Exception:
        pass

    # Warm up the demo model in the background so the server can come online
    # immediately. Runs through the real system pipeline: compute backend ->
    # MLflow tracking -> model registration, so the demo seeds data into all
    # system views (experiment history, model registry). The training itself
    # is CPU-bound pure Python and takes tens of seconds; running it
    # synchronously here would block uvicorn from binding the port.
    print("Warming up demo model in background (may take ~30-60s)...", flush=True)
    try:
        import threading

        from ..services.inference.demo_model_provider import warmup_demo_via_system_pipeline

        threading.Thread(
            target=warmup_demo_via_system_pipeline,
            name="demo-model-warmup",
            daemon=True,
        ).start()
    except Exception:
        pass

    yield
    svc = getattr(app.state, "mlflow", None)
    if svc is not None:
        svc.stop()


anvil_version = _get_version("anvil")
"""str: The installed version of the ``anvil`` package from package metadata."""


app = FastAPI(
    title="anvil",
    version=anvil_version,
    lifespan=lifespan,
)


@app.get("/", response_class=HTMLResponse)
async def root_hero(request: Request):
    """Render the root hero landing page.

    Parameters
    ----------
    request : Request
        The incoming HTTP request.

    Returns
    -------
    HTMLResponse
        The rendered ``archetypes/hero.html`` template with the anvil version.
    """
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/hero.html",
        context={"version": anvil_version},
    )


app.include_router(v1_router, prefix="/v1")

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(HERE / "templates"))
templates.env.globals["version"] = anvil_version
app.state.templates = templates

static_dir = HERE / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
