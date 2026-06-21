# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for the compute backends router."""

import pytest


@pytest.mark.asyncio
async def test_list_backends(client):
    """GET /v1/compute/backends returns the real registered backends.

    Verifies the response is a bare JSON list (no ``{"data": ...}``
    envelope), that ``local-stdlib`` is among the registered backends,
    and that every entry carries the expected schema.
    """
    response = await client.get("/v1/compute/backends")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)

    values = [item["value"] for item in data]
    assert "local-stdlib" in values

    for item in data:
        assert isinstance(item, dict)
        assert "value" in item
        assert isinstance(item["value"], str)
        assert "label" in item
        assert isinstance(item["label"], str)
        assert "available" in item
        assert isinstance(item["available"], bool)
        assert "reason" in item
        assert item["reason"] is None or isinstance(item["reason"], str)
