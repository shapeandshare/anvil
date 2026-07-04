"""e2e tests for the model import → catalog registration flow (spec 064).

Tests that ``POST /v1/models/import`` submits a job, the background worker
registers the model in the MLflow Model Catalog, and the job status response
includes ``registry_model_name`` / ``registry_model_version``.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from anvil.services._shared.import_types import ModelMetadata, ModelSourceError
from anvil.services.catalog.model_ref import ModelRef


@pytest.fixture(autouse=True)
def _fake_dependencies():
    """Replace HF source and catalog service with fakes."""
    patches = [
        patch(
            "anvil.services.model_import.hf_source.HfHubSource.resolve_metadata",
            return_value=ModelMetadata(
                display_name="fake-model",
                architecture_family="LlamaForCausalLM",
                parameter_count=1_000_000,
                license="mit",
                tokenizer_family="sentencepiece",
                revision_sha="fakesha",
            ),
        ),
        patch(
            "anvil.services.catalog.model_catalog_service.ModelCatalogService"
            ".register_external_model",
            return_value=ModelRef(name="hf--fake-model", version=1),
        ),
    ]
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()


class TestImportCatalogE2E:
    """e2e tests for the import → catalog flow."""

    @pytest.mark.asyncio
    async def test_import_submit_returns_job_id(self, client):
        """Submitting an import returns a job_id and queued status."""
        resp = await client.post(
            "/v1/models/import",
            json={
                "source": "huggingface",
                "identifier": "org/fake-model",
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "queued"

    @pytest.mark.asyncio
    async def test_import_poll_has_registry_fields(self, client):
        """Polling a completed import returns registry_model_name/version."""
        resp = await client.post(
            "/v1/models/import",
            json={
                "source": "huggingface",
                "identifier": "org/fake-model",
            },
        )
        job_id = resp.json()["job_id"]

        # Allow the background worker to complete.
        await asyncio.sleep(0.5)

        status_resp = await client.get(f"/v1/models/import/{job_id}/status")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["status"] == "complete"
        assert data["registry_model_name"] is not None
        assert data["registry_model_version"] is not None
        # No external_model_id in the response
        assert "external_model_id" not in data

    @pytest.mark.asyncio
    async def test_list_jobs_includes_registry_fields(self, client):
        """Listing jobs includes registry_model_name/version."""
        resp = await client.post(
            "/v1/models/import",
            json={
                "source": "huggingface",
                "identifier": "org/fake-list",
            },
        )
        await asyncio.sleep(0.5)

        list_resp = await client.get("/v1/models/import/jobs")
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert "data" in data
        for job in data["data"]:
            if job["job_id"] == resp.json()["job_id"]:
                assert job["registry_model_name"] is not None
                assert job["registry_model_version"] is not None
                # No external_model_id in the response
                assert "external_model_id" not in job
                return
        pytest.fail("Job not found in list")

    @pytest.mark.asyncio
    async def test_import_failure_sets_error_code(self, client):
        """A source error produces a failed status with error_code."""
        with patch(
            "anvil.services.model_import.hf_source.HfHubSource.resolve_metadata",
            side_effect=ModelSourceError(
                code="network_error",
                message="Connection failed",
                source="huggingface",
            ),
        ):
            resp = await client.post(
                "/v1/models/import",
                json={
                    "source": "huggingface",
                    "identifier": "org/offline",
                },
            )
            job_id = resp.json()["job_id"]
            await asyncio.sleep(0.5)

            status_resp = await client.get(f"/v1/models/import/{job_id}/status")
            data = status_resp.json()
            assert data["status"] == "failed"
            assert data["error_code"] == "network_error"
            # No registry fields on failure
            assert data["registry_model_name"] is None
            assert data["registry_model_version"] is None

    @pytest.mark.asyncio
    async def test_retry_creates_new_job(self, client):
        """Retrying a failed import creates a new queued job."""
        with patch(
            "anvil.services.model_import.hf_source.HfHubSource.resolve_metadata",
            side_effect=ModelSourceError(
                code="network_error",
                message="Connection failed",
                source="huggingface",
            ),
        ):
            resp = await client.post(
                "/v1/models/import",
                json={
                    "source": "huggingface",
                    "identifier": "org/retry-me",
                },
            )
            original_id = resp.json()["job_id"]
            await asyncio.sleep(0.5)

            retry_resp = await client.post(
                f"/v1/models/import/{original_id}/retry"
            )
            assert retry_resp.status_code == 202
            retry_data = retry_resp.json()
            assert retry_data["status"] == "queued"
            assert retry_data["job_id"] != original_id