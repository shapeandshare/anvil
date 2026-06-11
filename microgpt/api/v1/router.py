"""Versioned API v1 router."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from microgpt.api.v1.datasets import router as datasets_router
from microgpt.api.v1.experiments import router as experiments_router
from microgpt.api.v1.training import router as training_router

router = APIRouter()
router.include_router(training_router)
router.include_router(experiments_router)
router.include_router(datasets_router)


@router.get("/health")
async def health():
    return {"status": "healthy", "version": "0.1.0"}


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return request.app.state.templates.TemplateResponse(
        "training.html", {"request": request}
    )


@router.get("/training-page", response_class=HTMLResponse)
async def training_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        "training.html", {"request": request}
    )


@router.get("/experiments-page", response_class=HTMLResponse)
async def experiments_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        "experiments.html", {"request": request}
    )


@router.get("/datasets-page", response_class=HTMLResponse)
async def datasets_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        "datasets.html", {"request": request}
    )


@router.get("/operations-page", response_class=HTMLResponse)
async def operations_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        "operations.html", {"request": request}
    )


@router.get("/inference-page", response_class=HTMLResponse)
async def inference_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        "inference.html", {"request": request}
    )
