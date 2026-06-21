# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""HTTP-level integration tests for the content repository API.

Drives the real FastAPI content router end-to-end via an ASGI transport
(no app lifespan, so MLflow/demo-bootstrap are not started). The
``get_workbench`` dependency is overridden to bind to a temporary SQLite
database and a temporary content directory, exercising the real endpoints,
services, store, and repositories together.
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
from anvil.api.deps import get_workbench
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
    """Yield an HTTP client bound to the content router on a temp DB + content dir."""
    monkeypatch.setenv("ANVIL_CONTENT_DIR", str(tmp_path / "content"))
    get_config.cache_clear()

    _register_all_models()
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'api.db'}", echo=False
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
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    await engine.dispose()
    get_config.cache_clear()


@pytest.mark.asyncio
async def test_full_http_reproducibility_flow(api: httpx.AsyncClient) -> None:
    """Create corpus -> source -> session -> stage -> validate -> accept -> version."""
    r = await api.post(
        "/v1/content/corpora",
        json={"name": "Shakespeare", "declared_source": "Gutenberg"},
    )
    assert r.status_code == 200, r.text
    corpus = r.json()["data"]
    assert corpus["slug"] == "shakespeare"
    corpus_id = corpus["id"]

    r = await api.post(
        "/v1/content/sources",
        json={"slug": "manual", "name": "Manual", "kind": "manual"},
    )
    assert r.status_code == 200, r.text

    r = await api.post(
        "/v1/content/sessions",
        json={"corpus_id": corpus_id, "source": "manual"},
    )
    assert r.status_code == 200, r.text
    session_id = r.json()["data"]["id"]

    r = await api.post(
        f"/v1/content/sessions/{session_id}/stage",
        params={"path": "sonnet1.txt"},
        files={"file": ("sonnet1.txt", b"shall i compare thee", "text/plain")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["size_bytes"] == len(b"shall i compare thee")

    r = await api.post(f"/v1/content/sessions/{session_id}/validate")
    assert r.status_code == 200, r.text
    assert r.json()["data"]["ok"] is True

    r = await api.post(f"/v1/content/sessions/{session_id}/accept")
    assert r.status_code == 200, r.text
    accept = r.json()["data"]
    assert accept["entry_count"] == 1
    assert len(accept["manifest_digest"]) == 64

    r = await api.get(f"/v1/content/corpora/{corpus_id}/versions")
    assert r.status_code == 200, r.text
    versions = r.json()["data"]
    assert len(versions) == 1
    assert versions[0]["manifest_digest"] == accept["manifest_digest"]


async def _ingest_one(
    api: httpx.AsyncClient, corpus_id: int, path: str, data: bytes
) -> dict:
    """Open a session, stage one file, validate, and accept; return the accept payload."""
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


@pytest.mark.asyncio
async def test_http_tag_and_revert(api: httpx.AsyncClient) -> None:
    """Tagging a version and reverting a corpus work over HTTP (FR-023/FR-011)."""
    corpus_id = (
        await api.post("/v1/content/corpora", json={"name": "Reverttest"})
    ).json()["data"]["id"]
    await api.post(
        "/v1/content/sources",
        json={"slug": "manual", "name": "Manual", "kind": "manual"},
    )

    a1 = await _ingest_one(api, corpus_id, "a.txt", b"alpha")
    await _ingest_one(api, corpus_id, "b.txt", b"beta")

    r = await api.post(
        f"/v1/content/versions/{a1['version_id']}/tag", json={"name": "v1-stable"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["tag"] == "v1-stable"

    r = await api.post(
        f"/v1/content/corpora/{corpus_id}/revert",
        json={"to_version_id": a1["version_id"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "reverted"

    versions = (await api.get(f"/v1/content/corpora/{corpus_id}/versions")).json()[
        "data"
    ]
    assert len(versions) == 3


@pytest.mark.asyncio
async def test_http_corpus_listing_and_404(api: httpx.AsyncClient) -> None:
    """Listing returns created corpora; unknown corpus yields 404."""
    await api.post("/v1/content/corpora", json={"name": "Corpus One"})
    await api.post("/v1/content/corpora", json={"name": "Corpus Two"})

    r = await api.get("/v1/content/corpora")
    assert r.status_code == 200, r.text
    assert len(r.json()["data"]) == 2

    r = await api.get("/v1/content/corpora/99999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_http_open_session_unknown_corpus_404(
    api: httpx.AsyncClient,
) -> None:
    """Opening a session against a missing corpus yields 404."""
    await api.post(
        "/v1/content/sources",
        json={"slug": "manual", "name": "Manual", "kind": "manual"},
    )
    r = await api.post(
        "/v1/content/sessions",
        json={"corpus_id": 12345, "source": "manual"},
    )
    assert r.status_code == 404
