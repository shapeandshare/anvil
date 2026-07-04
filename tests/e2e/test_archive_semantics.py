"""e2e tests for archive semantics (spec 064, US4).

Tests that ``DELETE /v1/models/{name}/versions/{version}`` archives
the entry, removes it from active listings, and preserves it for
referencing records.

TDD: RED phase — these tests should fail before implementation.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestArchiveRoute:
    """Verify DELETE /v1/models/{name}/versions/{version} archive route."""

    async def test_delete_unknown_model_returns_404(self, client: AsyncClient) -> None:
        """Archiving a non-existent model should 404."""
        resp = await client.delete("/v1/models/does-not-exist/versions/1")
        assert resp.status_code == 404
