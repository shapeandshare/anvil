"""e2e tests for adapter merge and export.

Tests the HTTP API endpoints for non-destructive merge and the full
merge+export pipeline.  Uses the ``client`` fixture from ``conftest.py``
(in-memory SQLite).  ``peft`` / ``transformers`` are mocked at the
service level since they live behind the ``[finetune]`` extra.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Patch merge service dependencies ──────────────────────────────────

_MODULE = "anvil.services.training.merge_service"


@pytest.fixture(autouse=True)
def _patch_backend_deps():
    """Mock peft/transformers so merge operations don't need them."""
    patches = [
        patch(f"{_MODULE}._MERGE_DEPS_AVAILABLE", True),
        patch(f"{_MODULE}.AutoModelForCausalLM", create=True),
        patch(f"{_MODULE}.PeftModel", create=True),
    ]
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()


# ── Fixtures to create test data ─────────────────────────────────────


@pytest.fixture
async def test_external_model(client):
    """Create a test external model via the API."""
    from datetime import datetime, timezone

    from anvil.db.base import Base
    from anvil.db.models.external_model import ExternalModel
    from anvil.db.session import AsyncSessionLocal, async_engine

    # Create tables if not already created by client fixture timing
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        model = ExternalModel(
            display_name="e2e-test-model",
            source_type="huggingface",
            source_identifier="org/e2e-test",
            architecture_family="LlamaForCausalLM",
            parameter_count=1_000_000,
            license="mit",
            tokenizer_family="sentencepiece",
            revision_sha="e2e-test-sha",
            runnable_status="runnable",
        )
        session.add(model)
        await session.commit()
        await session.refresh(model)
        yield model.id


@pytest.fixture
async def test_adapter(test_external_model):
    """Create a test LoRA adapter for the external model."""
    from datetime import datetime, timezone

    from anvil.db.models.lora_adapter import LoRAAdapter
    from anvil.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        adapter = LoRAAdapter(
            external_model_id=test_external_model,
            run_id=42,
            adapter_id="e2e-adapter",
            label="e2e test adapter",
            method="lora",
            storage_path=f"models/{test_external_model}/adapters/e2e-adapter/",
            lora_rank=8,
            lora_alpha=16.0,
            lora_target_modules='["q_proj","v_proj"]',
            lora_dropout=0.1,
            lora_bias="none",
            final_loss=0.05,
            final_step=100,
        )
        session.add(adapter)
        await session.commit()
        await session.refresh(adapter)
        yield adapter


# ── Tests ─────────────────────────────────────────────────────────────


class TestMergeEndpoint:
    """``POST /models/{id}/adapters/{adapter_id}/merge``."""

    @pytest.mark.asyncio
    async def test_merge_returns_path(
        self,
        client,
        test_external_model: int,
        test_adapter,
    ):
        """Calling merge endpoint returns merged_path."""
        with patch(
            f"{_MODULE}.AdapterMergeService.merge",
            new=AsyncMock(return_value="models/1/merged/e2e-adapter/"),
        ):
            resp = await client.post(
                f"/v1/models/{test_external_model}/adapters/e2e-adapter/merge"
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "merged_path" in data

    @pytest.mark.asyncio
    async def test_adapter_still_listed_after_merge(
        self,
        client,
        test_external_model: int,
        test_adapter,
    ):
        """After merge, the adapter still appears in the list (non-destructive)."""
        with patch(
            f"{_MODULE}.AdapterMergeService.merge",
            new=AsyncMock(return_value="models/1/merged/e2e-adapter/"),
        ):
            resp = await client.post(
                f"/v1/models/{test_external_model}/adapters/e2e-adapter/merge"
            )
        assert resp.status_code == 200

        # Verify adapter still listed
        list_resp = await client.get(f"/v1/models/{test_external_model}/adapters")
        assert list_resp.status_code == 200
        adapters = list_resp.json()
        ids = [a["adapter_id"] for a in adapters]
        assert "e2e-adapter" in ids, "Adapter should still be listed after merge"

    @pytest.mark.asyncio
    async def test_merge_missing_adapter_404(
        self,
        client,
        test_external_model: int,
    ):
        """Merge endpoint returns 404 for non-existent adapter."""
        resp = await client.post(
            f"/v1/models/{test_external_model}/adapters/nonexistent/merge"
        )
        assert resp.status_code == 404


class TestAdapterListEndpoint:
    """``GET /models/{id}/adapters`` — verifying non-destructive preserve."""

    @pytest.mark.asyncio
    async def test_list_includes_adapter_details(
        self,
        client,
        test_external_model: int,
        test_adapter,
    ):
        """The adapter list endpoint returns full details including merged_at."""
        resp = await client.get(f"/v1/models/{test_external_model}/adapters")
        assert resp.status_code == 200
        data = resp.json()
        matching = [a for a in data if a["adapter_id"] == "e2e-adapter"]
        assert len(matching) == 1
        assert matching[0]["method"] == "lora"
        assert matching[0]["lora_rank"] == 8
        # merged_at should be None (not yet merged)
        assert matching[0]["merged_at"] is None

    @pytest.mark.asyncio
    async def test_get_single_adapter(
        self,
        client,
        test_external_model: int,
        test_adapter,
    ):
        """GET a single adapter returns full details."""
        resp = await client.get(
            f"/v1/models/{test_external_model}/adapters/e2e-adapter"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["adapter_id"] == "e2e-adapter"
        assert data["storage_path"] is not None

    @pytest.mark.asyncio
    async def test_get_missing_adapter_404(
        self,
        client,
        test_external_model: int,
    ):
        """GET a non-existent adapter returns 404."""
        resp = await client.get(
            f"/v1/models/{test_external_model}/adapters/nonexistent"
        )
        assert resp.status_code == 404


class TestMergeAndExportEndpoint:
    """``POST /models/{id}/adapters/{adapter_id}/merge-and-export``."""

    @pytest.mark.asyncio
    async def test_merge_and_export_returns_path_and_lineage(
        self,
        client,
        test_external_model: int,
        test_adapter,
    ):
        """Calling merge-and-export endpoint returns path and lineage."""
        with patch(
            f"{_MODULE}.AdapterMergeService.merge_and_export",
            new=AsyncMock(
                return_value={
                    "path": f"models/{test_external_model}/merged/e2e-adapter/",
                    "lineage": {
                        "registered": True,
                        "registry_name": "adapter-merge-e2e-adapter",
                        "registry_version": "1",
                        "run_id": "mlflow_001",
                    },
                }
            ),
        ):
            resp = await client.post(
                f"/v1/models/{test_external_model}/adapters/e2e-adapter/merge-and-export"
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "path" in data
        assert "lineage" in data
        assert data["lineage"]["registered"] is True

    @pytest.mark.asyncio
    async def test_adapter_still_listed_after_merge_and_export(
        self,
        client,
        test_external_model: int,
        test_adapter,
    ):
        """After merge-and-export, the adapter still appears in the list."""
        with patch(
            f"{_MODULE}.AdapterMergeService.merge_and_export",
            new=AsyncMock(
                return_value={
                    "path": f"models/{test_external_model}/merged/e2e-adapter/",
                    "lineage": {"registered": True},
                }
            ),
        ):
            resp = await client.post(
                f"/v1/models/{test_external_model}/adapters/e2e-adapter/merge-and-export"
            )
        assert resp.status_code == 200

        list_resp = await client.get(f"/v1/models/{test_external_model}/adapters")
        assert list_resp.status_code == 200
        adapters = list_resp.json()
        ids = [a["adapter_id"] for a in adapters]
        assert "e2e-adapter" in ids

    @pytest.mark.asyncio
    async def test_merge_and_export_missing_adapter_404(
        self,
        client,
        test_external_model: int,
    ):
        """Merge-and-export returns 404 for non-existent adapter."""
        resp = await client.post(
            f"/v1/models/{test_external_model}/adapters/nonexistent/merge-and-export"
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_merge_and_export_missing_model_404(
        self,
        client,
    ):
        """Merge-and-export returns 404 for non-existent model."""
        resp = await client.post(
            "/v1/models/99999/adapters/nonexistent/merge-and-export"
        )
        assert resp.status_code == 404
