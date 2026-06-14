"""Tests for ModelRegistryService."""

import pytest

from anvil.db.models.registry import RegisteredModel
from anvil.db.repositories.models import ModelRepository
from anvil.services.models import ModelRegistryService


@pytest.mark.asyncio
async def test_register_new_model(session):
    repo = ModelRepository(session)
    svc = ModelRegistryService(repo)

    result = await svc.register_model(
        experiment_id=1,
        name="test-model",
        description="test description",
        final_loss=1.234,
        dataset_name="test-dataset",
        hyperparameters={"n_layer": 2, "n_embd": 32},
    )
    assert result["name"] == "test-model"
    assert result["version"] == 1
    assert result["experiment_id"] == 1
    assert result["final_loss"] == 1.234
    assert result["dataset_name"] == "test-dataset"


@pytest.mark.asyncio
async def test_register_existing_model_auto_increments_version(session):
    repo = ModelRepository(session)
    svc = ModelRegistryService(repo)

    await repo.add(RegisteredModel(name="existing-model"))

    r1 = await svc.register_model(experiment_id=1, name="existing-model")
    assert r1["version"] == 1

    r2 = await svc.register_model(experiment_id=2, name="existing-model")
    assert r2["version"] == 2


@pytest.mark.asyncio
async def test_list_models(session):
    repo = ModelRepository(session)
    svc = ModelRegistryService(repo)

    await svc.register_model(experiment_id=1, name="model-a")
    await svc.register_model(experiment_id=2, name="model-b")

    models = await svc.list_models()
    assert len(models) == 2


@pytest.mark.asyncio
async def test_list_models_with_search(session):
    repo = ModelRepository(session)
    svc = ModelRegistryService(repo)

    await svc.register_model(experiment_id=1, name="shakespeare-gpt")
    await svc.register_model(experiment_id=2, name="python-gpt")

    results = await svc.list_models(search="shakespeare")
    assert len(results) == 1
    assert results[0]["name"] == "shakespeare-gpt"


@pytest.mark.asyncio
async def test_get_model(session):
    repo = ModelRepository(session)
    svc = ModelRegistryService(repo)

    await svc.register_model(experiment_id=1, name="model-detail", final_loss=0.5)
    models = await svc.list_models()
    model_id = models[0]["id"]

    detail = await svc.get_model(model_id)
    assert detail is not None
    assert detail["name"] == "model-detail"
    assert len(detail["versions"]) == 1


@pytest.mark.asyncio
async def test_get_nonexistent_model(session):
    repo = ModelRepository(session)
    svc = ModelRegistryService(repo)

    assert await svc.get_model(999) is None


@pytest.mark.asyncio
async def test_get_version(session):
    repo = ModelRepository(session)
    svc = ModelRegistryService(repo)

    await svc.register_model(experiment_id=1, name="get-version", final_loss=0.5)
    models = await svc.list_models()
    model_id = models[0]["id"]

    v = await svc.get_version(model_id, 1)
    assert v is not None
    assert v["experiment_id"] == 1
    assert v["final_loss"] == 0.5


@pytest.mark.asyncio
async def test_delete_model(session):
    repo = ModelRepository(session)
    svc = ModelRegistryService(repo)

    await svc.register_model(experiment_id=1, name="delete-model")
    models = await svc.list_models()
    assert len(models) == 1

    name = await svc.delete_model(models[0]["id"])
    assert name == "delete-model"
    assert await svc.list_models() == []


@pytest.mark.asyncio
async def test_delete_version(session):
    repo = ModelRepository(session)
    svc = ModelRegistryService(repo)

    await svc.register_model(experiment_id=1, name="versioned-model")
    await svc.register_model(experiment_id=2, name="versioned-model")
    models = await svc.list_models()
    model_id = models[0]["id"]

    detail = await svc.get_model(model_id)
    assert len(detail["versions"]) == 2

    name = await svc.delete_version(model_id, 1)
    assert name == "versioned-model"
    detail = await svc.get_model(model_id)
    assert len(detail["versions"]) == 1


@pytest.mark.asyncio
async def test_get_inference_models(session):
    repo = ModelRepository(session)
    svc = ModelRegistryService(repo)

    await svc.register_model(experiment_id=1, name="infer-model", final_loss=1.0)
    infer_models = await svc.get_inference_models()
    assert len(infer_models) == 1
    assert infer_models[0]["name"] == "infer-model"
    assert infer_models[0]["version"] == 1