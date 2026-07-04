"""Unit tests for CatalogIdentityRepository."""
# pylint: disable=missing-function-docstring

import pytest
from sqlalchemy.exc import IntegrityError

from anvil.db.repositories.catalog_identities import CatalogIdentityRepository
from anvil.services.catalog.model_ref import ModelRef


@pytest.mark.asyncio
async def test_add_and_find_by_triple(in_memory_session) -> None:
    repo = CatalogIdentityRepository(in_memory_session)
    identity = await repo.add(
        source_type="huggingface",
        source_identifier="org/model",
        revision_sha="abc123",
        registry_model_name="hf--org-model",
    )
    assert identity.id > 0
    assert identity.registry_model_version is None

    found = await repo.find_by_triple("huggingface", "org/model", "abc123")
    assert found is not None
    assert found.id == identity.id


@pytest.mark.asyncio
async def test_unique_constraint(in_memory_session) -> None:
    repo = CatalogIdentityRepository(in_memory_session)
    await repo.add(
        source_type="huggingface",
        source_identifier="org/model",
        revision_sha="abc123",
        registry_model_name="hf--org-model",
    )
    with pytest.raises(IntegrityError):
        await repo.add(
            source_type="huggingface",
            source_identifier="org/model",
            revision_sha="abc123",
            registry_model_name="hf--org-model",
        )


@pytest.mark.asyncio
async def test_find_by_triple_returns_none(in_memory_session) -> None:
    repo = CatalogIdentityRepository(in_memory_session)
    result = await repo.find_by_triple("huggingface", "unknown", "nope")
    assert result is None


@pytest.mark.asyncio
async def test_set_version(in_memory_session) -> None:
    repo = CatalogIdentityRepository(in_memory_session)
    identity = await repo.add(
        source_type="huggingface",
        source_identifier="org/model",
        revision_sha="abc123",
        registry_model_name="hf--org-model",
    )
    updated = await repo.set_version(identity.id, 2)
    assert updated is not None
    assert updated.registry_model_version == 2


@pytest.mark.asyncio
async def test_get_model_ref(in_memory_session) -> None:
    repo = CatalogIdentityRepository(in_memory_session)
    identity = await repo.add(
        source_type="huggingface",
        source_identifier="org/model",
        revision_sha="abc123",
        registry_model_name="hf--org-model",
    )
    # Before version is set, get_model_ref returns None
    ref = await repo.get_model_ref(identity.id)
    assert ref is None

    await repo.set_version(identity.id, 1)
    ref = await repo.get_model_ref(identity.id)
    assert ref is not None
    assert ref.name == "hf--org-model"
    assert ref.version == 1


@pytest.mark.asyncio
async def test_get_model_ref_not_found(in_memory_session) -> None:
    repo = CatalogIdentityRepository(in_memory_session)
    result = await repo.get_model_ref(9999)
    assert result is None