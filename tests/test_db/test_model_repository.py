"""Tests for ModelRepository."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from microgpt.db.models.registry import ModelVersion, RegisteredModel
from microgpt.db.repositories.models import ModelRepository


@pytest.mark.asyncio
async def test_add_and_get_model(session: AsyncSession):
    repo = ModelRepository(session)
    model = RegisteredModel(name="test-model", description="test desc")
    created = await repo.add(model)
    assert created.id is not None
    assert created.name == "test-model"

    fetched = await repo.get(created.id)
    assert fetched is not None
    assert fetched.name == "test-model"
    assert fetched.description == "test desc"


@pytest.mark.asyncio
async def test_get_all_models(session: AsyncSession):
    repo = ModelRepository(session)
    await repo.add(RegisteredModel(name="model-a"))
    await repo.add(RegisteredModel(name="model-b"))
    models = await repo.get_all()
    assert len(models) == 2


@pytest.mark.asyncio
async def test_get_all_with_search(session: AsyncSession):
    repo = ModelRepository(session)
    await repo.add(RegisteredModel(name="shakespeare-gpt"))
    await repo.add(RegisteredModel(name="python-gpt"))
    results = await repo.get_all(search="shakespeare")
    assert len(results) == 1
    assert results[0].name == "shakespeare-gpt"


@pytest.mark.asyncio
async def test_get_by_name(session: AsyncSession):
    repo = ModelRepository(session)
    await repo.add(RegisteredModel(name="unique-name"))
    found = await repo.get_by_name("unique-name")
    assert found is not None
    assert found.name == "unique-name"

    not_found = await repo.get_by_name("nonexistent")
    assert not_found is None


@pytest.mark.asyncio
async def test_delete_model(session: AsyncSession):
    repo = ModelRepository(session)
    model = await repo.add(RegisteredModel(name="delete-me"))
    model_id = model.id
    await repo.delete(model_id)
    assert await repo.get(model_id) is None


@pytest.mark.asyncio
async def test_version_numbering(session: AsyncSession):
    repo = ModelRepository(session)
    model = await repo.add(RegisteredModel(name="versioned-model"))
    next_v = await repo.get_next_version_number(model.id)
    assert next_v == 1

    v1 = ModelVersion(model_id=model.id, version=1, experiment_id=1, artifact_path="/tmp/1.json")
    await repo.add_version(v1)
    next_v = await repo.get_next_version_number(model.id)
    assert next_v == 2


@pytest.mark.asyncio
async def test_add_and_get_versions(session: AsyncSession):
    repo = ModelRepository(session)
    model = await repo.add(RegisteredModel(name="multi-version"))
    mv1 = ModelVersion(model_id=model.id, version=1, experiment_id=1, artifact_path="/tmp/v1.json", final_loss=1.5)
    mv2 = ModelVersion(model_id=model.id, version=2, experiment_id=2, artifact_path="/tmp/v2.json", final_loss=0.5)
    await repo.add_version(mv1)
    await repo.add_version(mv2)

    versions = await repo.get_versions(model.id)
    assert len(versions) == 2
    assert versions[0].version == 2  # desc order

    v1 = await repo.get_version(model.id, 1)
    assert v1 is not None
    assert v1.final_loss == 1.5


@pytest.mark.asyncio
async def test_delete_version(session: AsyncSession):
    repo = ModelRepository(session)
    model = await repo.add(RegisteredModel(name="del-version"))
    v1 = ModelVersion(model_id=model.id, version=1, experiment_id=1, artifact_path="/tmp/v1.json")
    await repo.add_version(v1)
    await repo.delete_version(model.id, 1)
    assert await repo.get_version(model.id, 1) is None


@pytest.mark.asyncio
async def test_get_model_with_versions(session: AsyncSession):
    repo = ModelRepository(session)
    model = await repo.add(RegisteredModel(name="with-versions"))
    v1 = ModelVersion(model_id=model.id, version=1, experiment_id=1, artifact_path="/tmp/v1.json")
    await repo.add_version(v1)

    loaded = await repo.get_model_with_versions(model.id)
    assert loaded is not None
    assert len(loaded.versions) == 1