"""FastAPI web application factory."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from anvil.api.v1.router import router as v1_router
from anvil.config import get_config
from anvil.db import models  # noqa: F401 — register ORM models with Base.metadata
from anvil.db.base import Base
from anvil.db.session import async_engine, init_engine
from anvil.supervisor.services import MLflowService

MLFLOW_EXPERIMENT_NAME = "anvil"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_engine()
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    cfg = get_config()
    if cfg["mlflow_disable_local"]:
        app.state.mlflow = None
    else:
        mlflow_svc = MLflowService()
        mlflow_svc.start()
        app.state.mlflow = mlflow_svc

    from anvil.services.tracking import TrackingService

    TrackingService.enable_system_metrics()

    try:
        await TrackingService().reconcile_orphans()
    except Exception:
        pass

    # Pre-train demo model so first inference request doesn't block
    try:
        from anvil.services.inference import _demo_provider

        _demo_provider.get_model()
    except Exception:
        pass

    # Auto-bootstrap demo data if not yet imported (best-effort)
    try:
        from anvil.db.session import AsyncSessionLocal
        from anvil.services.demo_bootstrap import DemoBootstrapService

        async with AsyncSessionLocal() as session:
            svc = DemoBootstrapService(session)
            result = await svc.bootstrap_all()
            if result.corpora_created > 0 or result.datasets_created > 0:
                import logging
                logger = logging.getLogger(__name__)
                logger.info(
                    "Bootstrapped %d corpora, %d datasets from data/demo/",
                    result.corpora_created, result.datasets_created,
                )
            await session.commit()
    except Exception:
        pass

    yield
    svc = getattr(app.state, "mlflow", None)
    if svc is not None:
        svc.stop()


from anvil import __version__ as anvil_version


app = FastAPI(
    title="anvil",
    version=anvil_version,
    lifespan=lifespan,
)


@app.get("/", response_class=HTMLResponse)
async def root_hero(request: Request):
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
