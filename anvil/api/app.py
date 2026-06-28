# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""FastAPI web application factory.

Creates and configures the FastAPI application instance with static file
serving, Jinja2 templates, MLflow integration, demo data bootstrapping,
and security middleware.  Manages the full application lifecycle via an
``asynccontextmanager`` lifespan.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import sys
import threading
import time
from collections import defaultdict
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from importlib.metadata import version as _get_version
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

from ..config import get_config
from ..db import models  # noqa: F401  # pylint: disable=unused-import
from ..db.migration import MigrationService
from ..db.repositories.corpora import CorpusRepository
from ..db.repositories.datasets import DatasetRepository
from ..db.session import AsyncSessionLocal, init_engine, reinit_engine
from ..services.backup.backup_service import BackupService
from ..services.demo.demo_bootstrap import DemoBootstrapService
from ..services.inference.demo_model_provider import warmup_demo_via_system_pipeline
from ..services.tracking.tracking import TrackingService
from ..supervisor.services import MLflowService
from ..workbench import AnvilWorkbench
from ..workspace.boot_config import BootConfig
from ..workspace.workspace_paths import WorkspacePaths
from .auth import (
    SESSION_COOKIE_NAME,
    generate_csrf_token,
    get_session_store,
    is_csrf_exempt,
    is_exempt_route,
    is_page_route,
    verify_csrf_token,
)
from .deps import get_api_key_store
from .v1.router import router as v1_router

logger = logging.getLogger(__name__)

MLFLOW_EXPERIMENT_NAME = "anvil"

####################################################################
# Security middleware configuration
####################################################################

# Rate limiting (in-process sliding window)
_rate_limit_store: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_PER_MINUTE = int(os.getenv("ANVIL_RATE_LIMIT", "100"))
_LOGIN_RATE_LIMIT_PER_MINUTE = int(os.getenv("ANVIL_LOGIN_RATE_LIMIT", "100"))
_LOGIN_FAILURE_DELAY = 1.0  # seconds

# CORS configuration
_cors_origins_str = os.getenv("ANVIL_CORS_ORIGINS", "")


def _make_rate_limit_key(request: StarletteRequest) -> str:
    """Build a rate-limit key from client IP and route prefix.

    Parameters
    ----------
    request : StarletteRequest

    Returns
    -------
    str
    """
    client_ip = request.client.host if request.client else "unknown"
    path = request.url.path
    return f"{client_ip}:{path}"


####################################################################
# Lifespan
####################################################################


def _setup_logging() -> None:
    """Configure structured logging for the application.

    Sets up the root logger with a consistent format and level for all
    runtime entry points (uvicorn, Docker, CLI).  Called from the
    lifespan handler and from ``anvil.cli.serve``.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s [%(name)s] %(message)s",
        force=True,
    )


async def _init_database() -> None:
    """Initialize the async SQLAlchemy engine and run schema migrations.

    Creates the engine, applies pending Alembic migrations, and verifies
    the schema version.  Exits the process with ``sys.exit(1)`` on schema
    version mismatch.

    Raises
    ------
    SystemExit
        If the schema version check fails.
    """
    print("Setting up database...", flush=True)
    await init_engine()
    migration_svc = MigrationService()
    await migration_svc.ensure_migrated()

    try:
        await migration_svc.ensure_schema_version()
    except (ValueError, RuntimeError) as exc:
        logger.critical("Schema version check failed: %s", exc)
        print(f"FATAL: {exc}", flush=True)
        sys.exit(1)


def _start_mlflow_if_needed(_app: FastAPI, cfg: dict[str, object]) -> None:
    """Start the MLflow sidecar process unless disabled in configuration.

    Parameters
    ----------
    _app : FastAPI
        The application instance -- receives ``mlflow`` in its state.
    cfg : dict
        The application configuration dictionary.
    """
    if cfg["mlflow_disable_local"]:
        _app.state.mlflow = None
    else:
        mlflow_svc = MLflowService()
        mlflow_svc.start()
        _app.state.mlflow = mlflow_svc


async def _enable_tracking_and_reconcile() -> None:
    """Enable system metrics and reconcile orphaned MLflow runs.

    Both operations are best-effort; failures are logged but do not
    block application startup.
    """
    TrackingService.enable_system_metrics()

    try:
        await TrackingService().reconcile_orphans()
    except (ValueError, RuntimeError):
        logger.warning("Failed to reconcile orphaned MLflow runs", exc_info=True)


async def _seed_license_catalog() -> None:
    """Seed the approved-license catalog via the workbench governance layer.

    Best-effort -- failures are logged but do not block startup.
    """
    try:
        async with AsyncSessionLocal() as session:
            wb = AnvilWorkbench(session)
            count = await wb.governance.seed_catalog()
            if count > 0:
                logger.info(
                    "Seeded %d licenses into the approved-license catalog", count
                )
            await session.commit()
    except (ValueError, RuntimeError):
        logger.warning("License seeding failed during startup", exc_info=True)


async def _bootstrap_demo_data() -> None:
    """Bootstrap bundled demo corpora and datasets on first run.

    Checks whether demo data already exists; if not, creates it from
    the bundled ``data/demo/`` directory.  Best-effort.
    """
    try:
        async with AsyncSessionLocal() as session:
            corpus_repo = CorpusRepository(session)
            dataset_repo = DatasetRepository(session)
            corpus_count = await corpus_repo.count_by_origin("bundled")
            dataset_count = await dataset_repo.count_by_origin("bundled")

            if corpus_count > 0 or dataset_count > 0:
                logger.debug(
                    "Demo data already exists (%d corpora, %d datasets), "
                    "skipping bootstrap",
                    corpus_count,
                    dataset_count,
                )
            else:
                svc = DemoBootstrapService(session)
                result = await svc.bootstrap_all()
                if result.corpora_created > 0 or result.datasets_created > 0:
                    logger.info(
                        "Bootstrapped %d corpora, %d datasets from data/demo/",
                        result.corpora_created,
                        result.datasets_created,
                    )
                await session.commit()
    except (ValueError, RuntimeError, OSError):
        logger.warning("Demo bootstrap failed during startup", exc_info=True)


def _warmup_demo_model() -> None:
    """Warm up the demo inference model in a background daemon thread.

    Best-effort -- failures are logged but do not block startup.
    """
    print("Warming up demo model in background (may take ~30-60s)...", flush=True)
    try:
        threading.Thread(
            target=warmup_demo_via_system_pipeline,
            name="demo-model-warmup",
            daemon=True,
        ).start()
    except (RuntimeError, OSError):
        logger.warning("Demo model warmup failed to start", exc_info=True)


async def _init_backup_service(_app: FastAPI) -> None:
    """Initialise the process-lifetime BackupService and recover state.

    Recovers from an interrupted restore if one was in progress (FR-030).
    Best-effort -- failures are logged but do not block startup.
    """
    try:
        backup_svc = BackupService()
        _app.state.backup_service = backup_svc
        logger.info("BackupService initialised")
        await backup_svc.recover_interrupted_restore()
    except (ValueError, RuntimeError, OSError):
        logger.warning("BackupService init or journal recovery failed", exc_info=True)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager handling startup and shutdown.

    Delegates each startup phase to a dedicated helper function for
    maintainability.  On shutdown the MLflow sidecar is stopped if it
    was started by this process.

    When ``ANVIL_WORKSPACE_DIR`` is set (feature-028 workspace mode),
    the engine/env-vars are already configured by the instance-launch
    process; this lifespan stores the ``WorkspacePaths`` and a startup-
    config snapshot in ``app.state`` for per-instance path isolation
    and the pending-restart diff mechanism.
    """
    _setup_logging()

    # ── Workspace-aware state initialisation (feature-028) ─────────
    ws_dir = os.environ.get("ANVIL_WORKSPACE_DIR")
    workspace_paths: object = None
    boot_snapshot: dict[str, object] | None = None

    if ws_dir:
        ws_root = await asyncio.to_thread(lambda: Path(ws_dir).resolve())
        boot_file = ws_root / "instance.json"

        # Explicitly redirect the engine to the workspace DB path so
        # that the lifespan is robust regardless of env-var timing.
        boot_cfg = BootConfig.load(boot_file)
        await reinit_engine(boot_cfg.state_db_path)

        workspace_paths = WorkspacePaths(ws_root)

        # Capture the effective boot-config at process start for the
        # pending-restart diff (US3/T049).
        boot_snapshot = {
            "workspace_root": str(ws_root),
            "web_port": int(os.environ.get("ANVIL_PORT", str(boot_cfg.web_port))),
            "mlflow_port": int(
                os.environ.get(
                    "ANVIL_MLFLOW_URI", f"http://127.0.0.1:{boot_cfg.mlflow_port}"
                ).rsplit(":", 1)[-1]
            ),
            "state_db_path": os.environ.get(
                "ANVIL_STATE_DB_PATH", boot_cfg.state_db_path
            ),
        }

    await _init_database()

    _app.state.workspace_paths = workspace_paths
    _app.state.boot_snapshot = boot_snapshot

    cfg = get_config()
    _start_mlflow_if_needed(_app, cfg)
    await _enable_tracking_and_reconcile()
    await _seed_license_catalog()
    await _bootstrap_demo_data()
    _warmup_demo_model()
    await _init_backup_service(_app)

    yield
    running_mlflow = getattr(_app.state, "mlflow", None)
    if running_mlflow is not None:
        running_mlflow.stop()


####################################################################
# Application factory
####################################################################

anvil_version = _get_version("anvil")

app = FastAPI(
    title="anvil",
    version=anvil_version,
    lifespan=lifespan,
)


@app.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Default HTTP exception handler — returns structured JSON."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


try:
    from ..services._shared.tokenizer_load_error import TokenizerLoadError
except ImportError:
    TokenizerLoadError = None  # type: ignore[assignment, misc]


if TokenizerLoadError is not None:

    @app.exception_handler(TokenizerLoadError)  # type: ignore[arg-type]
    async def _tokenizer_load_error_handler(
        request: Request, exc: TokenizerLoadError
    ) -> JSONResponse:
        """Handle tokenizer load failures with structured error responses."""
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "type": "tokenizer_load_error",
                    "message": str(exc),
                    "file": exc.file_path,
                    "cause": exc.cause,
                }
            },
        )


HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(HERE / "templates"))
templates.env.globals["version"] = anvil_version
app.state.templates = templates

static_dir = HERE / "static"
if static_dir.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(static_dir), html=False),
        name="static",
    )

####################################################################
# Middleware registration order (FR-029).
#
# Starlette executes ``@app.middleware`` handlers in REVERSE registration
# order (the last registered runs first / outermost).  To achieve the
# required execution order on each request:
#
#     rate-limit -> CORS -> security-headers -> auth -> route
#
# the handlers below are REGISTERED in the opposite order:
#
#     auth (first) -> security-headers -> CORS -> rate-limit (last)
#
# Rate limiting must run outermost so unauthenticated floods (e.g. login
# brute force, FR-028) are throttled BEFORE the auth check runs.
####################################################################


@app.middleware("http")
async def auth_middleware(
    request: StarletteRequest, call_next: RequestResponseEndpoint
) -> Response:
    """Authentication and CSRF protection middleware (runs last, innermost).

    - ``OPTIONS`` (CORS preflight) passes through without auth (FR-029).
    - Exempt routes (``/login``, ``/v1/health``, ``/static/*``) pass through.
    - ``/v1/*`` API routes accept EITHER ``X-API-Key`` header OR session cookie
      (cookie fallback required for browser SSE — FR-025).
    - Page routes require a valid session cookie; redirect to ``/login`` if missing.
    - Cookie-authenticated state-changing requests must carry ``X-CSRF-Token``
      (FR-027), unless the path is CSRF-exempt (``/v1/mlflow-proxy/*``).
    """
    path = request.url.path

    if request.method == "OPTIONS":
        return await call_next(request)

    if is_exempt_route(path):
        return await call_next(request)

    api_key_store = get_api_key_store()
    session_store = get_session_store()

    api_key = request.headers.get("X-API-Key")
    session_id = request.cookies.get(SESSION_COOKIE_NAME)

    authenticated = False
    authed_via_cookie = False

    if api_key is not None and api_key_store.verify(api_key):
        authenticated = True
    elif session_id is not None and session_store.validate(session_id):
        authenticated = True
        authed_via_cookie = True

    if not authenticated:
        if is_page_route(path) or "text/html" in request.headers.get("accept", ""):
            return RedirectResponse(url="/login", status_code=303)
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required", "code": "UNAUTHORIZED"},
        )

    if authed_via_cookie and not api_key and session_id is not None:
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            if not is_csrf_exempt(path):
                csrf_token = request.headers.get("X-CSRF-Token")
                if not csrf_token or not verify_csrf_token(session_id, csrf_token):
                    return JSONResponse(
                        status_code=403,
                        content={
                            "detail": "CSRF token invalid or missing",
                            "code": "FORBIDDEN",
                        },
                    )

    return await call_next(request)


@app.middleware("http")
async def security_headers_middleware(
    request: StarletteRequest, call_next: RequestResponseEndpoint
) -> Response:
    """Inject security headers (CSP, HSTS, XFO, XCTO) into every response."""
    nonce = secrets.token_urlsafe(16)
    request.state.csp_nonce = nonce
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "img-src 'self' data: https://fastapi.tiangolo.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "connect-src 'self' https://cdn.jsdelivr.net; "
            "worker-src 'self' blob:; "
        )
        if request.url.path in ("/docs", "/redoc", "/openapi.json")
        or request.url.path.startswith("/docs/")
        or request.url.path.startswith("/redoc/")
        else (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}';"
        )
    )
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


# CORS middleware (built-in, no new dependency). Registered after the two
# @middleware handlers above but before rate-limit, so on the request path it
# runs after rate-limit and before security-headers/auth.
if _cors_origins_str:
    origins = [o.strip() for o in _cors_origins_str.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key", "Idempotency-Key", "X-CSRF-Token"],
        allow_credentials=True,
    )


@app.middleware("http")
async def rate_limit_middleware(
    request: StarletteRequest, call_next: RequestResponseEndpoint
) -> Response:
    """Sliding-window rate-limiting middleware (runs first, outermost).

    Exempts ``/v1/health`` and ``/static/*``.
    ``POST /login`` has its own stricter limit (5/min/IP) per FR-028.
    """
    path = request.url.path
    if path == "/v1/health" or path.startswith("/static"):
        return await call_next(request)

    key = _make_rate_limit_key(request)
    now = time.time()
    window = 60.0

    limit = (
        _LOGIN_RATE_LIMIT_PER_MINUTE
        if request.method == "POST" and path == "/login"
        else _RATE_LIMIT_PER_MINUTE
    )

    timestamps = _rate_limit_store[key]
    cutoff = now - window
    _rate_limit_store[key] = [t for t in timestamps if t > cutoff]

    if len(_rate_limit_store[key]) >= limit:
        retry_after = int(window - (now - _rate_limit_store[key][0]))
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests", "code": "RATE_LIMITED"},
            headers={"Retry-After": str(retry_after)},
        )

    _rate_limit_store[key].append(now)
    return await call_next(request)


####################################################################
# Routes
####################################################################


@app.get("/", response_class=HTMLResponse)
async def root_hero(request: Request) -> Response:
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
    csrf_token = _get_csrf_token_for_request(request)
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/hero.html",
        context={
            "version": anvil_version,
            "csrf_token": csrf_token,
        },
    )


####################################################################
# Login / Logout routes
####################################################################


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> Response:
    """Render the login page.

    Parameters
    ----------
    request : Request
        The incoming HTTP request.

    Returns
    -------
    HTMLResponse
        The login page template.
    """
    return templates.TemplateResponse(
        request,
        "login.html",
        context={},
    )


@app.post("/login")
async def login_post(request: Request) -> Response:
    """Authenticate with an API key and set a session cookie.

    Expects ``{"api_key": "..."}`` in the JSON body.
    On success sets ``HttpOnly; SameSite=Strict; Max-Age=86400`` cookie.
    """
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid JSON body", "code": "BAD_REQUEST"},
        )

    api_key = body.get("api_key", "")
    api_key_store = get_api_key_store()

    if not api_key_store.verify(api_key):
        # Small fixed delay on failure (FR-028)
        await asyncio.sleep(_LOGIN_FAILURE_DELAY)
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid API key", "code": "UNAUTHORIZED"},
        )

    session_store = get_session_store()
    session_id = session_store.create()

    response = JSONResponse(
        status_code=200,
        content={"status": "ok", "session_id": session_id},
    )
    # Mark the session cookie Secure whenever the connection is HTTPS so it is
    # never sent over plaintext. Over local HTTP (no TLS) it must remain usable,
    # so the flag tracks the request scheme rather than being hardcoded.
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        samesite="strict",
        max_age=86_400,
        path="/",
        secure=request.url.scheme == "https",
    )
    return response


@app.post("/logout")
async def logout_post(request: Request) -> Response:
    """Clear the session cookie and invalidate the server-side session."""
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        get_session_store().delete(session_id)

    response = JSONResponse(status_code=200, content={"status": "logged_out"})
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
    )
    return response


####################################################################
# CSRF token helper
####################################################################


def _get_csrf_token_for_request(request: Request) -> str:
    """Extract or generate a CSRF token for the current request's session.

    Parameters
    ----------
    request : Request
        The incoming HTTP request.

    Returns
    -------
    str
        The CSRF token, or an empty string if no session is present.
    """
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        return generate_csrf_token(session_id)
    return ""


####################################################################
# Router registration
####################################################################

app.include_router(v1_router, prefix="/v1")
