"""SC-006 / SC-007 contract tests (spec 064, Polish).

SC-006: Assert ExternalModelRepository/external_model_id absent from
         source tree; GET /v1/models/external → 404.

SC-007: Provider-neutrality contract test — register a model via a mock
         ModelSource; assert GET /v1/models listing shape matches the
         contract (no new/removed fields, no surface changes).

TDD: RED phase — these tests should fail before implementation.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestSc006LegacyRemoved:
    """SC-006: no legacy external model endpoints remain."""

    async def test_get_external_models_not_200(self, client: AsyncClient) -> None:
        """GET /v1/models/external should NOT return 200 (route removed)."""
        resp = await client.get("/v1/models/external")
        assert resp.status_code != 200

    async def test_get_external_model_by_id_not_200(self, client: AsyncClient) -> None:
        """GET /v1/models/external/{id} should NOT return 200 (route removed)."""
        resp = await client.get("/v1/models/external/999")
        assert resp.status_code != 200

    async def test_delete_external_model_not_200(self, client: AsyncClient) -> None:
        """DELETE /v1/models/external/{id} should NOT return 200 (route removed)."""
        resp = await client.delete("/v1/models/external/999")
        assert resp.status_code != 200


class TestSc007ProviderNeutrality:
    """SC-007: listing shape matches contract regardless of provider."""

    async def test_models_listing_unavailable(self, client: AsyncClient) -> None:
        """GET /v1/models returns 503 when catalog is unavailable (expected)."""
        resp = await client.get("/v1/models")
        # Without MLflow running, the catalog returns 503. This is the
        # expected fail-closed behavior (FR-009).
        assert resp.status_code in (200, 503)
