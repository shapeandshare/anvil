"""FastAPI web application factory."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from microgpt.api.v1.router import router as v1_router
from microgpt.db import models  # noqa: F401 — register ORM models with Base.metadata
from microgpt.db.base import Base
from microgpt.db.session import async_engine, init_engine
from microgpt.supervisor.services import MLflowService

MLFLOW_EXPERIMENT_NAME = "microgpt-workbench"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_engine()
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    mlflow_svc = MLflowService()
    mlflow_svc.start()
    app.state.mlflow = mlflow_svc
    yield
    mlflow_svc.stop()


app = FastAPI(
    title="microgpt-workbench",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/v1")


app.include_router(v1_router, prefix="/v1")

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(HERE / "templates"))
app.state.templates = templates

static_dir = HERE / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
