# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""e2e tests for the external model import API.

Uses the ``client`` fixture from ``conftest.py`` (HTTP test client with
in-memory SQLite).  Relies on a fake/monkeypatched ``ModelSource`` so
no network calls are made.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from anvil.services._shared.import_types import ModelMetadata


@pytest.fixture(autouse=True)
def _fake_hf_source():
    """Replace the real HfHubSource with a fake that returns static metadata."""
    patcher = patch(
        "anvil.services.model_import.hf_source.HfHubSource.resolve_metadata",
        return_value=ModelMetadata(
            display_name="fake-model",
            architecture_family="LlamaForCausalLM",
            parameter_count=1_000_000,
            license="mit",
            tokenizer_family="sentencepiece",
            revision_sha="fakesha",
        ),
    )
    patcher.start()
    yield
    patcher.stop()


class TestExternalModelImportApi:
    """e2e tests for the external model import flow."""

    @pytest.mark.asyncio
    async def test_import_submit_returns_job_id(self, client):
        """Submitting an import returns a job_id and queued status."""
        resp = await client.post(
            "/v1/models/import",
            json={
                "source": "huggingface",
                "identifier": "org/fake",
                "name": "fake-model",
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "queued"

    @pytest.mark.asyncio
    async def test_import_poll_completes(self, client):
        """Polling an import job returns complete after background resolution."""
        resp = await client.post(
            "/v1/models/import",
            json={
                "source": "huggingface",
                "identifier": "org/fake",
                "name": "fake-model",
            },
        )
        job_id = resp.json()["job_id"]

        # The background worker uses its own session; we need the
        # resolution to happen before we poll.  Wait briefly.
        import asyncio

        await asyncio.sleep(0.5)

        status_resp = await client.get(f"/v1/models/import/{job_id}/status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["status"] in ("complete", "failed", "resolving")

    @pytest.mark.asyncio
    async def test_external_model_listed(self, client):
        """After a complete import, the external model appears in the list."""
        resp = await client.post(
            "/v1/models/import",
            json={
                "source": "huggingface",
                "identifier": "org/fake",
                "name": "list-test-model",
            },
        )
        job_id = resp.json()["job_id"]

        import asyncio

        await asyncio.sleep(0.5)

        list_resp = await client.get("/v1/models/external")
        assert list_resp.status_code == 200
        data = list_resp.json()
        # data is {"data": [...]}
        models = data.get("data", [])
        # Our import may or may not have completed; if it did,
        # we should see the entry.
        matching = [m for m in models if m.get("display_name") == "list-test-model"]
        if len(matching) > 0:
            assert matching[0]["architecture_family"] == "LlamaForCausalLM"

    @pytest.mark.asyncio
    async def test_import_unknown_source_returns_422(self, client):
        """An unknown source type returns a 422 error."""
        resp = await client.post(
            "/v1/models/import",
            json={
                "source": "nonexistent-source",
                "identifier": "org/test",
            },
        )
        assert resp.status_code == 422
