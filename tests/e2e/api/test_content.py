# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for the content repository router.

Exercises the full versioned content lifecycle — create corpus,
register sources, open ingestion sessions, stage content,
validate, accept, freeze immutable versions, tag, manage locks,
import jobs, and SSE event streams.

Content endpoints return envelope::

    {"data": {...}, "error": None}
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_content_create_corpus(client):
    """Create a versioned content corpus via POST /v1/content/corpora."""
    r = await client.post(
        "/v1/content/corpora",
        json={"name": "e2e-content-corpus"},
    )
    assert (
        r.status_code == 200
    ), f"POST /v1/content/corpora: expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert body["error"] is None
    assert body["data"]["id"] is not None
    assert body["data"]["name"] == "e2e-content-corpus"


@pytest.mark.asyncio
async def test_content_get_corpus(client):
    """GET a single content corpus and list all corpora."""
    # Create
    r = await client.post(
        "/v1/content/corpora",
        json={"name": "get-e2e-corpus"},
    )
    assert r.status_code == 200
    corpus_id = r.json()["data"]["id"]

    # Get single
    r = await client.get(f"/v1/content/corpora/{corpus_id}")
    assert (
        r.status_code == 200
    ), f"GET /v1/content/corpora/{corpus_id}: expected 200, got {r.status_code}"
    body = r.json()
    assert body["error"] is None
    assert body["data"]["id"] == corpus_id
    assert body["data"]["name"] == "get-e2e-corpus"

    # List all
    r = await client.get("/v1/content/corpora")
    assert r.status_code == 200
    body = r.json()
    assert body["error"] is None
    assert isinstance(body["data"], list)
    ids = [c["id"] for c in body["data"]]
    assert corpus_id in ids, f"Expected corpus {corpus_id} in list, got {ids}"


@pytest.mark.asyncio
async def test_content_delete_corpus(client):
    """DELETE a content corpus then verify it is gone."""
    # Create
    r = await client.post(
        "/v1/content/corpora",
        json={"name": "delete-e2e-corpus"},
    )
    assert r.status_code == 200
    corpus_id = r.json()["data"]["id"]

    # Delete
    r = await client.delete(f"/v1/content/corpora/{corpus_id}")
    assert (
        r.status_code == 200
    ), f"DELETE /v1/content/corpora/{corpus_id}: expected 200, got {r.status_code}"
    body = r.json()
    assert body["error"] is None
    assert body["data"]["status"] == "deleted"

    # Verify gone
    r = await client.get(f"/v1/content/corpora/{corpus_id}")
    assert r.status_code == 404, (
        f"GET /v1/content/corpora/{corpus_id} after delete: expected 404, "
        f"got {r.status_code}: {r.text}"
    )


@pytest.mark.asyncio
async def test_content_full_lifecycle(client):
    """Run the full content repository lifecycle end-to-end.

    Steps: create corpus -> create source -> open session -> stage
    -> validate -> accept -> freeze -> get version -> get lineage.
    """
    # 1. Create corpus
    r = await client.post(
        "/v1/content/corpora",
        json={"name": "lifecycle-corpus"},
    )
    assert r.status_code == 200, f"Failed to create corpus: {r.text}"
    corpus_id = r.json()["data"]["id"]

    # 2. Create source
    r = await client.post(
        "/v1/content/sources",
        json={
            "slug": "lifecycle-source",
            "name": "Lifecycle Source",
            "kind": "manual",
        },
    )
    assert r.status_code == 200, f"Failed to create source: {r.text}"
    source_id = r.json()["data"]["id"]
    assert source_id is not None

    # 3. Open ingestion session
    r = await client.post(
        "/v1/content/sessions",
        json={
            "corpus_id": corpus_id,
            "source": "lifecycle-source",
        },
    )
    assert r.status_code == 200, f"Failed to open session: {r.text}"
    session_id = r.json()["data"]["id"]
    assert session_id is not None

    # 4. Stage content via multipart upload
    r = await client.post(
        f"/v1/content/sessions/{session_id}/stage",
        params={"path": "hello.txt"},
        files={"file": ("hello.txt", b"Hello, content repository!", "text/plain")},
    )
    assert r.status_code == 200, f"Failed to stage file: {r.text}"
    staged = r.json()
    assert staged["error"] is None
    assert staged["data"]["path"] == "hello.txt"
    assert staged["data"]["content_hash"] is not None
    assert staged["data"]["size_bytes"] > 0

    # 5. Validate the session
    r = await client.post(f"/v1/content/sessions/{session_id}/validate")
    assert r.status_code == 200, f"Failed to validate session: {r.text}"
    report = r.json()
    assert report["error"] is None
    # Validation may pass or have non-blocking problems; just verify shape
    assert "ok" in report["data"]
    assert "problems" in report["data"]

    # 6. Accept (atomic fold into canonical HEAD)
    r = await client.post(f"/v1/content/sessions/{session_id}/accept")
    assert r.status_code == 200, f"Failed to accept session: {r.text}"
    accept_body = r.json()
    assert accept_body["error"] is None
    assert accept_body["data"]["version_id"] is not None
    assert accept_body["data"]["manifest_digest"] is not None
    assert accept_body["data"]["entry_count"] >= 1

    # 7. Freeze an immutable version
    r = await client.post(f"/v1/content/corpora/{corpus_id}/freeze")
    assert r.status_code == 200, f"Failed to freeze version: {r.text}"
    version = r.json()
    assert version["error"] is None
    version_id = version["data"]["id"]
    assert version_id is not None
    assert version["data"]["version_number"] is not None

    # 8. Get the frozen version
    r = await client.get(f"/v1/content/versions/{version_id}")
    assert r.status_code == 200, f"Failed to get version {version_id}: {r.text}"
    version_detail = r.json()
    assert version_detail["error"] is None
    assert version_detail["data"]["id"] == version_id

    # 9. Get version lineage
    r = await client.get(f"/v1/content/versions/{version_id}/lineage")
    assert (
        r.status_code == 200
    ), f"Failed to get lineage for version {version_id}: {r.text}"
    lineage = r.json()
    assert lineage["error"] is None
    assert lineage["data"]["version_id"] == version_id
    assert "sources" in lineage["data"]
    assert "run_refs" in lineage["data"]


@pytest.mark.asyncio
async def test_content_tag(client):
    """Tag a content version via POST /v1/content/versions/{id}/tag."""
    # Create corpus
    r = await client.post(
        "/v1/content/corpora",
        json={"name": "tag-e2e-corpus"},
    )
    assert r.status_code == 200
    corpus_id = r.json()["data"]["id"]

    # Create source
    r = await client.post(
        "/v1/content/sources",
        json={
            "slug": "tag-source",
            "name": "Tag Source",
            "kind": "manual",
        },
    )
    assert r.status_code == 200

    # Open session
    r = await client.post(
        "/v1/content/sessions",
        json={
            "corpus_id": corpus_id,
            "source": "tag-source",
        },
    )
    assert r.status_code == 200
    session_id = r.json()["data"]["id"]

    # Stage
    r = await client.post(
        f"/v1/content/sessions/{session_id}/stage",
        params={"path": "data.txt"},
        files={"file": ("data.txt", b"tag test content", "text/plain")},
    )
    assert r.status_code == 200

    # Accept
    r = await client.post(f"/v1/content/sessions/{session_id}/accept")
    assert r.status_code == 200
    accept_body = r.json()
    version_id = accept_body["data"]["version_id"]

    # Tag the version created by accept
    r = await client.post(
        f"/v1/content/versions/{version_id}/tag",
        json={"name": "v1.0"},
    )
    assert r.status_code == 200, f"Failed to tag version {version_id}: {r.text}"
    tag_body = r.json()
    assert tag_body["error"] is None
    assert tag_body["data"]["id"] == version_id
    assert tag_body["data"]["tag"] == "v1.0"


@pytest.mark.asyncio
async def test_content_locks(client):
    """Acquire, list, and release advisory content locks."""
    # Acquire lock
    r = await client.post(
        "/v1/content/locks",
        json={
            "scope": "corpus:e2e-lock-test",
            "holder": "e2e-tester",
        },
    )
    assert r.status_code == 200, f"Failed to acquire lock: {r.text}"
    lock_body = r.json()
    assert lock_body["error"] is None
    lock_id = lock_body["data"]["id"]
    assert lock_id is not None
    assert lock_body["data"]["scope"] == "corpus:e2e-lock-test"
    assert lock_body["data"]["holder"] == "e2e-tester"
    assert lock_body["data"]["state"] == "held"

    # List locks — should include the new lock
    r = await client.get("/v1/content/locks")
    assert r.status_code == 200, f"Failed to list locks: {r.text}"
    list_body = r.json()
    assert list_body["error"] is None
    assert isinstance(list_body["data"], list)
    lock_ids = [lk["id"] for lk in list_body["data"]]
    assert lock_id in lock_ids, f"Expected lock {lock_id} in list, got {lock_ids}"

    # Release the lock
    r = await client.post(f"/v1/content/locks/{lock_id}/release")
    assert r.status_code == 200, f"Failed to release lock {lock_id}: {r.text}"
    release_body = r.json()
    assert release_body["error"] is None
    assert release_body["data"]["status"] == "released"


@pytest.mark.asyncio
async def test_content_imports(client):
    """Start and query a declarative content import job.

    Requires a corpus and source to exist before starting the import.
    """
    # Create corpus
    r = await client.post(
        "/v1/content/corpora",
        json={"name": "import-e2e-corpus"},
    )
    assert r.status_code == 200
    corpus_id = r.json()["data"]["id"]

    # Create source
    r = await client.post(
        "/v1/content/sources",
        json={
            "slug": "import-source",
            "name": "Import Source",
            "kind": "manual",
        },
    )
    assert r.status_code == 200

    # Start import job
    r = await client.post(
        "/v1/content/imports",
        json={
            "corpus_id": corpus_id,
            "source": "import-source",
            "config": {"uri": "test://import", "filter": "*.txt"},
        },
    )
    assert r.status_code == 200, f"Failed to start import: {r.text}"
    import_body = r.json()
    assert import_body["error"] is None
    import_id = import_body["data"]["id"]
    assert import_id is not None
    assert import_body["data"]["corpus_id"] == corpus_id
    assert import_body["data"]["session_id"] is not None

    # List imports
    r = await client.get("/v1/content/imports")
    assert r.status_code == 200, f"Failed to list imports: {r.text}"
    list_body = r.json()
    assert list_body["error"] is None
    assert isinstance(list_body["data"], list)

    # Get single import job
    r = await client.get(f"/v1/content/imports/{import_id}")
    assert r.status_code == 200, f"Failed to get import {import_id}: {r.text}"
    get_body = r.json()
    assert get_body["error"] is None
    assert get_body["data"]["id"] == import_id


@pytest.mark.asyncio
async def test_content_sse_stream(client):
    """Connect to the content repository SSE event stream.

    The composition stream sends heartbeat events every 30 s; just
    verify the endpoint responds with 200.
    """
    async with client.stream("GET", "/v1/content/stream/composition") as response:
        assert response.status_code == 200, (
            "Expected 200 from composition SSE stream, " f"got {response.status_code}"
        )


@pytest.mark.asyncio
async def test_content_errors(client):
    """Verify error responses for invalid content requests."""
    # POST with missing required name → 422
    r = await client.post("/v1/content/corpora", json={})
    assert (
        r.status_code == 422
    ), f"Expected 422 for missing name, got {r.status_code}: {r.text}"

    # GET non-existent corpus → 404
    r = await client.get("/v1/content/corpora/99999")
    assert (
        r.status_code == 404
    ), f"Expected 404 for non-existent corpus, got {r.status_code}: {r.text}"
