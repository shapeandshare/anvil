# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for evaluation dataset API endpoints.

Covers create, append, and retrieve operations for eval datasets
via the /v1/eval-datasets/* routes.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from anvil.services._shared.capability_unavailable import CapabilityUnavailable
from anvil.services.tracking.tracking import TrackingService


class TestCreateEvalDataset:
    """Tests for POST /v1/eval-datasets."""

    async def test_creates_dataset_successfully(self, client):
        """Happy path: dataset created successfully."""
        with patch.object(
            TrackingService,
            "create_eval_dataset",
            return_value="MockDataset(id=1)",
        ):
            resp = await client.post(
                "/v1/eval-datasets",
                json={"name": "test-dataset"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["name"] == "test-dataset"
        assert data["dataset"] is not None

    async def test_creates_dataset_with_tags(self, client):
        """Happy path: dataset created with optional tags."""
        with patch.object(
            TrackingService,
            "create_eval_dataset",
            return_value="MockDataset(id=2)",
        ):
            resp = await client.post(
                "/v1/eval-datasets",
                json={"name": "tagged-dataset", "tags": {"env": "test"}},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["name"] == "tagged-dataset"

    async def test_returns_capability_unavailable(self, client):
        """Returns available=False when TrackingService raises CapabilityUnavailable."""
        with patch.object(
            TrackingService,
            "create_eval_dataset",
            side_effect=CapabilityUnavailable("MLflow 3.x required"),
        ):
            resp = await client.post(
                "/v1/eval-datasets",
                json={"name": "no-mlflow-ds"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
        assert "reason" in data

    async def test_rejects_empty_name(self, client):
        """Pydantic validation: empty name returns 422."""
        resp = await client.post("/v1/eval-datasets", json={"name": ""})
        assert resp.status_code == 422

    async def test_rejects_missing_name(self, client):
        """Pydantic validation: missing name returns 422."""
        resp = await client.post("/v1/eval-datasets", json={})
        assert resp.status_code == 422

    async def test_rejects_extra_fields(self, client):
        """Pydantic validation: extra fields are forbidden."""
        resp = await client.post(
            "/v1/eval-datasets",
            json={"name": "ok", "unknown": "field"},
        )
        assert resp.status_code == 422


class TestAppendEvalRecords:
    """Tests for POST /v1/eval-datasets/{name}/records."""

    async def test_appends_records_successfully(self, client):
        """Happy path: records appended to an existing dataset."""
        with patch.object(
            TrackingService,
            "append_eval_records",
            return_value=3,
        ):
            resp = await client.post(
                "/v1/eval-datasets/my-ds/records",
                json={"records": [{"q": "a"}, {"q": "b"}, {"q": "c"}]},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["appended"] == 3

    async def test_returns_capability_unavailable(self, client):
        """Returns available=False when TrackingService raises CapabilityUnavailable."""
        with patch.object(
            TrackingService,
            "append_eval_records",
            side_effect=CapabilityUnavailable("MLflow 3.x required"),
        ):
            resp = await client.post(
                "/v1/eval-datasets/my-ds/records",
                json={"records": [{"q": "a"}]},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False

    async def test_rejects_empty_records(self, client):
        """Accepts empty records list."""
        with patch.object(
            TrackingService,
            "append_eval_records",
            return_value=0,
        ):
            resp = await client.post(
                "/v1/eval-datasets/my-ds/records",
                json={"records": []},
            )
        assert resp.status_code == 200


class TestGetEvalDataset:
    """Tests for GET /v1/eval-datasets/{name}."""

    async def test_retrieves_dataset_successfully(self, client):
        """Happy path: existing dataset retrieved by name."""
        with patch.object(
            TrackingService,
            "get_eval_dataset",
            return_value="MockDataset(id=1)",
        ):
            resp = await client.get("/v1/eval-datasets/my-ds")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["name"] == "my-ds"

    async def test_returns_404_when_not_found(self, client):
        """Returns 404 when the dataset does not exist."""
        with patch.object(
            TrackingService,
            "get_eval_dataset",
            return_value=None,
        ):
            resp = await client.get("/v1/eval-datasets/ghost-ds")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    async def test_returns_capability_unavailable(self, client):
        """Returns available=False when capability is unavailable."""
        with patch.object(
            TrackingService,
            "get_eval_dataset",
            side_effect=CapabilityUnavailable("MLflow 3.x required"),
        ):
            resp = await client.get("/v1/eval-datasets/no-mlflow")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
