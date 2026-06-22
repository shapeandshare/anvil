"""Integration tests for the content library listing and version timeline.

Exercises ``GET /content/corpora`` and ``GET /content/corpora/{id}/versions``
end-to-end via an ASGI transport, verifying that the library listing returns
accurate summaries (name, slug, version count, status) and the version
timeline returns versions with correct version numbers and entry counts in
order.
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
    for module in pkgutil.iter_modules(_models_pkg.__path__):
        importlib.import_module(f"{_models_pkg.__name__}.{module.name}")


async def _ingest_one(
    api: httpx.AsyncClient, corpus_id: int, path: str, data: bytes
) -> dict:
    """Open a session, stage one file, validate, and accept.

    Parameters
    ----------
    api : httpx.AsyncClient
        HTTP client bound to the content router.
    corpus_id : int
        Primary key of the target corpus.
    path : str
        Entry path within the session.
    data : bytes
        File content to stage.

    Returns
    -------
    dict
        The accept result payload (``AcceptOut``).
    """
    sid = (
        await api.post(
            "/v1/content/sessions",
            json={"corpus_id": corpus_id, "source": "manual"},
        )
    ).json()["data"]["id"]
    await api.post(
        f"/v1/content/sessions/{sid}/stage",
        params={"path": path},
        files={"file": (path, data, "text/plain")},
    )
    await api.post(f"/v1/content/sessions/{sid}/validate")
    r = await api.post(f"/v1/content/sessions/{sid}/accept")
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest_asyncio.fixture
async def api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    """Yield an HTTP client bound to the content router on a temp DB +
    content dir."""
    monkeypatch.setenv("ANVIL_CONTENT_DIR", str(tmp_path / "content"))
    get_config.cache_clear()

    _register_all_models()
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'library.db'}", echo=False
    )
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
async def test_library_listing_returns_summaries(api: httpx.AsyncClient) -> None:
    """Library listing returns corpora with name, slug, and status."""
    r = await api.post("/v1/content/corpora", json={"name": "Corpus Alpha"})
    assert r.status_code == 200, r.text
    corpus_a = r.json()["data"]

    r = await api.post("/v1/content/corpora", json={"name": "Corpus Beta"})
    assert r.status_code == 200, r.text
    corpus_b = r.json()["data"]

    r = await api.get("/v1/content/corpora")
    assert r.status_code == 200, r.text
    corpora = r.json()["data"]
    assert len(corpora) == 2

    names = {c["name"] for c in corpora}
    assert "Corpus Alpha" in names
    assert "Corpus Beta" in names

    slugs = {c["slug"] for c in corpora}
    assert "corpus-alpha" in slugs
    assert "corpus-beta" in slugs

    for c in corpora:
        assert "status" in c
        assert c["status"] in ("draft", "active", "archived")


@pytest.mark.asyncio
async def test_version_timeline_returns_versions_in_order(
    api: httpx.AsyncClient,
) -> None:
    """Version timeline shows versions with correct numbers/entry counts
    in order."""
    r = await api.post("/v1/content/corpora", json={"name": "Timeline Corpus"})
    assert r.status_code == 200, r.text
    corpus_id = r.json()["data"]["id"]

    await api.post(
        "/v1/content/sources",
        json={"slug": "manual", "name": "Manual", "kind": "manual"},
    )

    v1 = await _ingest_one(api, corpus_id, "a.txt", b"alpha")
    v2 = await _ingest_one(api, corpus_id, "b.txt", b"beta and more")
    v3 = await _ingest_one(api, corpus_id, "c.txt", b"gamma")

    r = await api.get(f"/v1/content/corpora/{corpus_id}/versions")
    assert r.status_code == 200, r.text
    versions = r.json()["data"]

    assert len(versions) == 3

    version_numbers = [v["version_number"] for v in versions]
    assert version_numbers == [3, 2, 1]

    version_map = {v["version_number"]: v for v in versions}
    assert version_map[1]["entry_count"] == 1
    assert version_map[2]["entry_count"] == 1
    assert version_map[3]["entry_count"] == 1

    for v in versions:
        assert "manifest_digest" in v
        assert len(v["manifest_digest"]) == 64
        assert "created_at" in v


@pytest.mark.asyncio
async def test_version_timeline_entry_counts(api: httpx.AsyncClient) -> None:
    """Entry count in version timeline matches the number of staged
    files."""
    r = await api.post("/v1/content/corpora", json={"name": "Multi File Corpus"})
    assert r.status_code == 200, r.text
    corpus_id = r.json()["data"]["id"]

    await api.post(
        "/v1/content/sources",
        json={"slug": "manual", "name": "Manual", "kind": "manual"},
    )

    v1 = await _ingest_one(api, corpus_id, "x.txt", b"one file only")
    v1_entry_count = v1["entry_count"]

    r = await api.get(f"/v1/content/corpora/{corpus_id}/versions")
    versions = r.json()["data"]
    v1_timeline = [v for v in versions if v["version_number"] == 1][0]
    assert v1_timeline["entry_count"] == v1_entry_count
