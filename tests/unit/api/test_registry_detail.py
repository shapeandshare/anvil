# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for model registry detail routes.

Tests ``get_model``, ``get_version``, ``delete_version``,
``delete_model``, and ``list_registered_models`` with mocked
``TrackingService`` and ``MlflowClient`` module-level imports.
"""

from __future__ import annotations

from unittest.mock import ANY, AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from mlflow.exceptions import MlflowException

from anvil.api.app import app
from anvil.api.deps import get_api_key_store

API_KEY = ""


@pytest.fixture(autouse=True)
def _api_key() -> None:
    global API_KEY
    API_KEY = get_api_key_store().key or ""


def _patch_mlflow_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch MlflowClient in the registry module to avoid real MLflow calls."""
    from anvil.api.v1 import registry as registry_module

    class _FakeMlflowClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def get_registered_model(self, name: str) -> object:
            raise MlflowException("Not found")

        def search_model_versions(self, filter_str: str) -> list:
            return []

        def get_run(self, run_id: str) -> object:
            raise MlflowException("Not found")

        def delete_model_version(self, name: str, version: str) -> None:
            raise MlflowException("Version not found or could not be deleted")

        def delete_registered_model(self, name: str) -> None:
            raise MlflowException("Model not found or could not be deleted")

    monkeypatch.setattr(
        registry_module, "MlflowClient", lambda *a, **kw: _FakeMlflowClient()
    )


def _make_fake_registered_model(
    name: str = "dataset-test-data",
    versions: list | None = None,
) -> MagicMock:
    """Build a fake MLflow registered model object."""
    rm = MagicMock()
    rm.name = name
    rm.description = "A test model"
    rm.creation_timestamp = 1700000000000
    rm.latest_versions = versions or []
    return rm


def _make_fake_model_version(
    version: int = 1,
    run_id: str = "mlflow_run_1",
    source: str = "mlflow-artifacts:/0/abc/artifacts",
) -> MagicMock:
    """Build a fake MLflow model version object."""
    mv = MagicMock()
    mv.version = str(version)
    mv.run_id = run_id
    mv.source = source
    mv.creation_timestamp = 1700000000000
    mv.current_stage = "None"
    return mv


def _make_fake_mlflow_run(params: dict | None = None) -> MagicMock:
    """Build a fake MLflow Run object with data."""
    run = MagicMock()
    run.data.params = params or {}
    run.data.metrics = {"final_loss": 0.123}
    run.data.tags = {
        "anvil.experiment_id": "42",
        "anvil.warm_start": "true",
        "anvil.base_model_ref": "1",
    }
    return run


######################################################################
# list_registered_models
######################################################################


class TestListRegisteredModels:
    """Tests for ``GET /v1/registry/models``."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_list_with_search_filter(monkeypatch: pytest.MonkeyPatch) -> None:
        """Search query is forwarded to TrackingService.list_registered_models."""
        from anvil.api.v1 import registry as registry_module

        mock_tracking = AsyncMock()
        mock_tracking.list_registered_models.return_value = [
            {"name": "dataset-test-data", "version": 1},
            {"name": "dataset-other", "version": 2},
        ]
        monkeypatch.setattr(registry_module, "TrackingService", lambda: mock_tracking)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.get("/v1/registry/models", params={"search": "test"})

        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert len(data["models"]) == 2
        mock_tracking.list_registered_models.assert_called_once_with(search="test")

    @staticmethod
    @pytest.mark.asyncio
    async def test_list_without_search(monkeypatch: pytest.MonkeyPatch) -> None:
        """No search param passes None to TrackingService."""
        from anvil.api.v1 import registry as registry_module

        mock_tracking = AsyncMock()
        mock_tracking.list_registered_models.return_value = []
        monkeypatch.setattr(registry_module, "TrackingService", lambda: mock_tracking)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.get("/v1/registry/models")

        assert resp.status_code == 200
        mock_tracking.list_registered_models.assert_called_once_with(search=None)


######################################################################
# get_model
######################################################################


class TestGetModel:
    """Tests for ``GET /v1/registry/models/{model_id}``."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_get_model_by_integer_id(monkeypatch: pytest.MonkeyPatch) -> None:
        """Integer model_id resolves via convention-based lookup."""
        from anvil.api.v1 import registry as registry_module

        mock_tracking = AsyncMock()
        mock_tracking.list_registered_models.return_value = [
            {"name": "dataset-other"},
            {"name": "dataset-42"},
            {"name": "corpus-42"},
        ]
        monkeypatch.setattr(registry_module, "TrackingService", lambda: mock_tracking)

        rm = _make_fake_registered_model(name="dataset-42")
        mv1 = _make_fake_model_version(version=1)

        class FakeMlflowClient:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            def get_registered_model(self, name: str) -> object:
                return rm

            def search_model_versions(self, filter_str: str) -> list:
                return [mv1]

            def get_run(self, run_id: str) -> object:
                return _make_fake_mlflow_run()

        monkeypatch.setattr(
            registry_module,
            "MlflowClient",
            lambda *a, **kw: FakeMlflowClient(),
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.get("/v1/registry/models/42")

        assert (
            resp.status_code == 200
        ), f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["name"] == "dataset-42"
        assert len(data["versions"]) == 1
        assert data["versions"][0]["version"] == 1
        assert data["versions"][0]["final_loss"] == 0.123
        assert data["versions"][0]["lineage"] is not None
        assert data["versions"][0]["lineage"]["warm_start"] == "true"

    @staticmethod
    @pytest.mark.asyncio
    async def test_get_model_by_string_id(monkeypatch: pytest.MonkeyPatch) -> None:
        """String model_id is used directly as MLflow model name."""
        from anvil.api.v1 import registry as registry_module

        mock_tracking = AsyncMock()
        mock_tracking.list_registered_models.return_value = []
        monkeypatch.setattr(registry_module, "TrackingService", lambda: mock_tracking)

        rm = _make_fake_registered_model(name="my-custom-model")
        mv1 = _make_fake_model_version(version=1)

        class FakeMlflowClient:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            def get_registered_model(self, name: str) -> object:
                return rm

            def search_model_versions(self, filter_str: str) -> list:
                return [mv1]

            def get_run(self, run_id: str) -> object:
                return _make_fake_mlflow_run()

        monkeypatch.setattr(
            registry_module,
            "MlflowClient",
            lambda *a, **kw: FakeMlflowClient(),
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.get("/v1/registry/models/my-custom-model")

        assert resp.status_code == 200
        assert resp.json()["name"] == "my-custom-model"

    @staticmethod
    @pytest.mark.asyncio
    async def test_get_model_404(monkeypatch: pytest.MonkeyPatch) -> None:
        """Nonexistent model returns 404."""
        from anvil.api.v1 import registry as registry_module

        mock_tracking = AsyncMock()
        mock_tracking.list_registered_models.return_value = []
        monkeypatch.setattr(registry_module, "TrackingService", lambda: mock_tracking)

        class FakeMlflowClient:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            def get_registered_model(self, name: str) -> object:
                raise MlflowException("Not found")

            def search_model_versions(self, filter_str: str) -> list:
                raise MlflowException("Not found")

        monkeypatch.setattr(
            registry_module,
            "MlflowClient",
            lambda *a, **kw: FakeMlflowClient(),
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.get("/v1/registry/models/nonexistent")

        assert resp.status_code == 404
        assert "Model not found" in resp.json().get("detail", "")


######################################################################
# get_version
######################################################################


class TestGetVersion:
    """Tests for ``GET /v1/registry/models/{model_id}/versions/{version}``."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_get_version_success(monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns version details for a specific version."""
        from anvil.api.v1 import registry as registry_module

        mock_tracking = AsyncMock()
        mock_tracking.list_registered_models.return_value = [
            {"name": "dataset-42"},
        ]
        monkeypatch.setattr(registry_module, "TrackingService", lambda: mock_tracking)

        mv1 = _make_fake_model_version(version=1)

        class FakeMlflowClient:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            def search_model_versions(self, filter_str: str) -> list:
                return [mv1]

            def get_run(self, run_id: str) -> object:
                return _make_fake_mlflow_run()

        monkeypatch.setattr(
            registry_module,
            "MlflowClient",
            lambda *a, **kw: FakeMlflowClient(),
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.get("/v1/registry/models/42/versions/1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == 1
        assert data["final_loss"] == 0.123
        assert data["experiment_id"] == 42

    @staticmethod
    @pytest.mark.asyncio
    async def test_get_version_404_model_not_found(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Nonexistent model returns 404."""
        from anvil.api.v1 import registry as registry_module

        mock_tracking = AsyncMock()
        mock_tracking.list_registered_models.return_value = []
        monkeypatch.setattr(registry_module, "TrackingService", lambda: mock_tracking)

        class FakeMlflowClient:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            def search_model_versions(self, filter_str: str) -> list:
                raise MlflowException("Not found")

        monkeypatch.setattr(
            registry_module,
            "MlflowClient",
            lambda *a, **kw: FakeMlflowClient(),
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.get("/v1/registry/models/nonexistent/versions/1")

        assert resp.status_code == 404

    @staticmethod
    @pytest.mark.asyncio
    async def test_get_version_404_version_not_found(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Nonexistent version within existing model returns 404."""
        from anvil.api.v1 import registry as registry_module

        mock_tracking = AsyncMock()
        mock_tracking.list_registered_models.return_value = [
            {"name": "dataset-42"},
        ]
        monkeypatch.setattr(registry_module, "TrackingService", lambda: mock_tracking)
        _patch_mlflow_client(monkeypatch)

        mv1 = _make_fake_model_version(version=1)

        # Override MlflowClient.search_model_versions to return version 1 only
        class _FakeClient:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            def search_model_versions(self, filter_str: str) -> list:
                return [mv1]

        monkeypatch.setattr(
            registry_module, "MlflowClient", lambda *a, **kw: _FakeClient()
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.get("/v1/registry/models/42/versions/999")

        assert resp.status_code == 404
        assert "Version not found" in resp.json().get("detail", "")


######################################################################
# delete_version
######################################################################


class TestDeleteVersion:
    """Tests for ``DELETE /v1/registry/models/{model_id}/versions/{version}``."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_delete_version_success(monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns 200 with confirmation message."""
        from anvil.api.v1 import registry as registry_module

        mock_tracking = AsyncMock()
        mock_tracking.list_registered_models.return_value = [
            {"name": "dataset-42"},
        ]
        monkeypatch.setattr(registry_module, "TrackingService", lambda: mock_tracking)

        delete_called = False

        class FakeMlflowClient:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            def delete_model_version(self, name: str, version: str) -> None:
                nonlocal delete_called
                delete_called = True

        monkeypatch.setattr(
            registry_module,
            "MlflowClient",
            lambda *a, **kw: FakeMlflowClient(),
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.delete("/v1/registry/models/42/versions/1")

        assert resp.status_code == 200
        assert delete_called
        assert "deleted" in resp.json().get("message", "")

    @staticmethod
    @pytest.mark.asyncio
    async def test_delete_version_404(monkeypatch: pytest.MonkeyPatch) -> None:
        """MlflowException during delete returns 404."""
        from anvil.api.v1 import registry as registry_module

        mock_tracking = AsyncMock()
        mock_tracking.list_registered_models.return_value = [
            {"name": "dataset-42"},
        ]
        monkeypatch.setattr(registry_module, "TrackingService", lambda: mock_tracking)

        class FakeMlflowClient:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            def delete_model_version(self, name: str, version: str) -> None:
                raise MlflowException("Version not found")

        monkeypatch.setattr(
            registry_module,
            "MlflowClient",
            lambda *a, **kw: FakeMlflowClient(),
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.delete("/v1/registry/models/42/versions/999")

        assert resp.status_code == 404
        assert "not found" in resp.json().get("detail", "").lower()

    @staticmethod
    @pytest.mark.asyncio
    async def test_delete_version_model_404(monkeypatch: pytest.MonkeyPatch) -> None:
        """Nonexistent model returns 404."""
        from anvil.api.v1 import registry as registry_module

        mock_tracking = AsyncMock()
        mock_tracking.list_registered_models.return_value = []
        monkeypatch.setattr(registry_module, "TrackingService", lambda: mock_tracking)
        _patch_mlflow_client(monkeypatch)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.delete("/v1/registry/models/nonexistent/versions/1")

        assert resp.status_code == 404


######################################################################
# delete_model
######################################################################


class TestDeleteModel:
    """Tests for ``DELETE /v1/registry/models/{model_id}``."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_delete_model_success(monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns 200 with confirmation message."""
        from anvil.api.v1 import registry as registry_module

        mock_tracking = AsyncMock()
        mock_tracking.list_registered_models.return_value = [
            {"name": "dataset-42"},
        ]
        monkeypatch.setattr(registry_module, "TrackingService", lambda: mock_tracking)

        delete_called = False

        class FakeMlflowClient:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            def delete_registered_model(self, name: str) -> None:
                nonlocal delete_called
                delete_called = True

        monkeypatch.setattr(
            registry_module,
            "MlflowClient",
            lambda *a, **kw: FakeMlflowClient(),
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.delete("/v1/registry/models/42")

        assert resp.status_code == 200
        assert delete_called
        assert "deleted" in resp.json().get("message", "")

    @staticmethod
    @pytest.mark.asyncio
    async def test_delete_model_404(monkeypatch: pytest.MonkeyPatch) -> None:
        """MlflowException during delete returns 404."""
        from anvil.api.v1 import registry as registry_module

        mock_tracking = AsyncMock()
        mock_tracking.list_registered_models.return_value = [
            {"name": "dataset-42"},
        ]
        monkeypatch.setattr(registry_module, "TrackingService", lambda: mock_tracking)

        class FakeMlflowClient:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            def delete_registered_model(self, name: str) -> None:
                raise MlflowException("Model not found")

        monkeypatch.setattr(
            registry_module,
            "MlflowClient",
            lambda *a, **kw: FakeMlflowClient(),
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.delete("/v1/registry/models/99999")

        assert resp.status_code == 404

    @staticmethod
    @pytest.mark.asyncio
    async def test_delete_model_not_found_by_id(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Nonexistent model ID returns 404."""
        from anvil.api.v1 import registry as registry_module

        mock_tracking = AsyncMock()
        mock_tracking.list_registered_models.return_value = []
        monkeypatch.setattr(registry_module, "TrackingService", lambda: mock_tracking)
        _patch_mlflow_client(monkeypatch)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.delete("/v1/registry/models/nonexistent")

        assert resp.status_code == 404
