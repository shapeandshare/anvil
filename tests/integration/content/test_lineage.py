"""HTTP-level integration tests for the content lineage endpoint.

Exercises ``GET /content/versions/{id}/lineage`` end-to-end via an ASGI
transport, verifying that the endpoint returns source information (from
the ingestion session that created the version) and MLflow run references
(from ``VersionRunRef``).
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import anvil.db.models as _models_pkg
from anvil.api.deps import get_api_key_store, get_workbench
from anvil.api.v1.content import router as content_router
from anvil.config import get_config
from anvil.db.base import Base
from anvil.workbench import AnvilWorkbench


def _register_all_models() -> None:
    """Import every ORM model module so ``Base.metadata`` is complete."""
    for module in pkgutil.iter_modules(_models_pkg.__path__):
        importlib.import_module(f"{_models_pkg.__name__}.{module.name}")


@pytest_asyncio.fixture
async def api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    """Yield an HTTP client bound to the content router on a temp DB +
    content dir."""
    monkeypatch.setenv("ANVIL_CONTENT_DIR", str(tmp_path / "content"))
    _db_path = tmp_path / "lineage.db"
    get_config.cache_clear()

    _register_all_models()
    engine = create_async_engine(f"sqlite+aiosqlite:///{_db_path}", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    app = FastAPI()
    app.include_router(content_router, prefix="/v1")

    async def _override_workbench() -> AsyncIterator[AnvilWorkbench]:
        async with session_factory() as session:
            yield AnvilWorkbench(session)

    app.dependency_overrides[get_workbench] = _override_workbench

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://test",
        headers={"X-API-Key": get_api_key_store().key or ""},
    ) as client:
        yield client

    await engine.dispose()
    get_config.cache_clear()


@pytest.mark.asyncio
async def test_lineage_returns_sources_from_accepted_session(
    api: httpx.AsyncClient,
) -> None:
    """Lineage must include the source slug from the accepted session."""
    r = await api.post("/v1/content/corpora", json={"name": "Lineage Corpus"})
    assert r.status_code == 200, r.text
    corpus_id = r.json()["data"]["id"]

    r = await api.post(
        "/v1/content/sources",
        json={"slug": "gutenberg", "name": "Project Gutenberg", "kind": "importer"},
    )
    assert r.status_code == 200, r.text

    r = await api.post(
        "/v1/content/sessions",
        json={"corpus_id": corpus_id, "source": "gutenberg"},
    )
    assert r.status_code == 200, r.text
    session_id = r.json()["data"]["id"]

    r = await api.post(
        f"/v1/content/sessions/{session_id}/stage",
        params={"path": "doc.txt"},
        files={"file": ("doc.txt", b"content", "text/plain")},
    )
    assert r.status_code == 200, r.text

    r = await api.post(f"/v1/content/sessions/{session_id}/validate")
    assert r.status_code == 200, r.text

    r = await api.post(f"/v1/content/sessions/{session_id}/accept")
    assert r.status_code == 200, r.text
    version_id = r.json()["data"]["version_id"]

    r = await api.get(f"/v1/content/versions/{version_id}/lineage")
    assert r.status_code == 200, r.text
    data = r.json()["data"]

    assert "sources" in data
    assert "run_refs" in data
    source_slugs = [s["slug"] for s in data["sources"]]
    assert "gutenberg" in source_slugs


@pytest.mark.asyncio
async def test_lineage_includes_run_refs_when_recorded(
    api: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    """Lineage must include recorded MLflow run refs."""
    r = await api.post("/v1/content/corpora", json={"name": "RunRef Corpus"})
    assert r.status_code == 200, r.text
    corpus_id = r.json()["data"]["id"]

    r = await api.post(
        "/v1/content/sources",
        json={"slug": "manual", "name": "Manual", "kind": "manual"},
    )
    assert r.status_code == 200, r.text

    r = await api.post(
        "/v1/content/sessions",
        json={"corpus_id": corpus_id, "source": "manual"},
    )
    session_id = r.json()["data"]["id"]

    await api.post(
        f"/v1/content/sessions/{session_id}/stage",
        params={"path": "f.txt"},
        files={"file": ("f.txt", b"data", "text/plain")},
    )
    await api.post(f"/v1/content/sessions/{session_id}/validate")
    r = await api.post(f"/v1/content/sessions/{session_id}/accept")
    version_id = r.json()["data"]["version_id"]

    _register_all_models()
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'lineage.db'}", echo=False
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        wb = AnvilWorkbench(session)
        await wb.content_lineage.record_run_ref(
            version_id=version_id,
            mlflow_run_id="run_xyz789",
            corpus_ref=f"corpus:{corpus_id}",
        )
        await session.commit()

    r = await api.get(f"/v1/content/versions/{version_id}/lineage")
    assert r.status_code == 200, r.text
    data = r.json()["data"]

    run_ids = [ref["mlflow_run_id"] for ref in data["run_refs"]]
    assert "run_xyz789" in run_ids
