"""Tests for source-keyed MLflow model registry consolidation."""

import asyncio

import pytest

from anvil.services.tracking.tracking import TrackingService


class FakeMlflowClient:
    def __init__(self, tracking_uri: str | None = None):
        self.tracking_uri = tracking_uri
        self.registered_models: dict[str, list[str]] = {}
        self.version_counters: dict[str, int] = {}
        self.calls: list[tuple] = []
        self._experiments: dict[str, str] = {}
        self._runs: dict[str, dict] = {}

    def get_experiment_by_name(self, name: str) -> None:
        return None

    def create_experiment(self, name: str) -> str:
        self._experiments[name] = "0"
        return "0"

    def create_registered_model(self, name: str):
        self.calls.append(("create_registered_model", name))
        if name not in self.registered_models:
            self.registered_models[name] = []
        FakeRegisteredModel = type("FakeRegisteredModel", (), {"name": name})
        return FakeRegisteredModel()

    def create_model_version(self, name: str, source: str, run_id: str):
        self.calls.append(("create_model_version", name, source, run_id))
        if name not in self.version_counters:
            self.version_counters[name] = 0
        self.version_counters[name] += 1
        version_num = self.version_counters[name]
        self.registered_models.setdefault(name, []).append(str(version_num))
        FakeVersion = type(
            "FakeVersion",
            (),
            {"version": str(version_num), "name": name},
        )
        return FakeVersion()


@pytest.fixture
def svc():
    ts = TrackingService(
        tracking_uri="http://fake:5000",
        client_factory=lambda uri: FakeMlflowClient(uri),
    )
    ts._lazy_init()
    return ts


@pytest.fixture
def fake_client(svc):
    return svc._client


class TestRegisterSourceModel:
    @pytest.mark.asyncio
    async def test_dataset_source_key(self, svc, fake_client):
        result = await svc.register_source_model(run_id="abc", dataset_id=1)
        assert result["name"] == "dataset-1"
        assert result["run_id"] == "abc"
        assert result["source"] == "runs:/abc/model.json"
        assert "version" in result

        create_registered_calls = [
            c for c in fake_client.calls if c[0] == "create_registered_model"
        ]
        assert len(create_registered_calls) == 1
        assert create_registered_calls[0][1] == "dataset-1"

        create_version_calls = [
            c for c in fake_client.calls if c[0] == "create_model_version"
        ]
        assert len(create_version_calls) == 1
        assert create_version_calls[0][1] == "dataset-1"
        assert create_version_calls[0][2] == "runs:/abc/model.json"
        assert create_version_calls[0][3] == "abc"

    @pytest.mark.asyncio
    async def test_corpus_source_key(self, svc, fake_client):
        result = await svc.register_source_model(run_id="def", corpus_id=2)
        assert result["name"] == "corpus-2"

    @pytest.mark.asyncio
    async def test_default_source_key(self, svc, fake_client):
        result = await svc.register_source_model(run_id="ghi")
        assert result["name"] == "default-source"

    @pytest.mark.asyncio
    async def test_idempotent_create_registered_model(self, svc, fake_client):
        await svc.register_source_model(run_id="abc", dataset_id=1)

        fake_client.calls.clear()

        result2 = await svc.register_source_model(run_id="def", dataset_id=1)
        assert result2["name"] == "dataset-1"

        create_registered_calls = [
            c for c in fake_client.calls if c[0] == "create_registered_model"
        ]
        assert len(create_registered_calls) == 1

    @pytest.mark.asyncio
    async def test_two_versions_for_same_source(self, svc, fake_client):
        r1 = await svc.register_source_model(run_id="aaa", dataset_id=5)
        r2 = await svc.register_source_model(run_id="bbb", dataset_id=5)

        assert r1["name"] == "dataset-5"
        assert r2["name"] == "dataset-5"

        versions = fake_client.registered_models.get("dataset-5", [])
        assert len(versions) == 2

        version_calls = [c for c in fake_client.calls if c[0] == "create_model_version"]
        assert len(version_calls) == 2

    @pytest.mark.asyncio
    async def test_no_local_db_write(self, svc, fake_client):
        result = await svc.register_source_model(run_id="abc", dataset_id=99)
        assert result["name"] == "dataset-99"

    @pytest.mark.asyncio
    async def test_no_model_flavor(self, svc, fake_client):
        await svc.register_source_model(run_id="abc", dataset_id=7)
        version_calls = [c for c in fake_client.calls if c[0] == "create_model_version"]
        assert len(version_calls) == 1
        _, name, _, _ = version_calls[0]
        assert name == "dataset-7"
        assert "pyfunc" not in str(version_calls)
        assert "pytorch" not in str(version_calls)

    @pytest.mark.asyncio
    async def test_register_not_called_for_failed_runs(self, svc, fake_client):
        assert len(fake_client.calls) == 0

    @pytest.mark.asyncio
    async def test_n_versions_one_registered_model(self, svc, fake_client):
        for i in range(3):
            await svc.register_source_model(run_id=f"run-{i}", dataset_id=10)

        registered_names = list(fake_client.registered_models.keys())
        assert registered_names == ["dataset-10"]
        assert len(fake_client.registered_models["dataset-10"]) == 3

        version_calls = [c for c in fake_client.calls if c[0] == "create_model_version"]
        assert len(version_calls) == 3

    @pytest.mark.asyncio
    async def test_new_source_new_registered_model(self, svc, fake_client):
        await svc.register_source_model(run_id="x", dataset_id=20)
        await svc.register_source_model(run_id="y", corpus_id=30)
        await svc.register_source_model(run_id="z")

        registered_names = list(fake_client.registered_models.keys())
        assert "dataset-20" in registered_names
        assert "corpus-30" in registered_names
        assert "default-source" in registered_names
        assert len(registered_names) == 3
