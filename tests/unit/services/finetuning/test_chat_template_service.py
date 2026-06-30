# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ChatTemplateService."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.base import Base
from anvil.db.session import AsyncSessionLocal, async_engine


@pytest.fixture
async def db_session():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        yield session
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_create_template(db_session: AsyncSession):
    """Creating a chat template stores it and returns it with an id."""
    from anvil.services.finetuning.chat_template_service import ChatTemplateService

    svc = ChatTemplateService(db_session)
    template = await svc.create(
        name="test-template",
        template_string="{{ bos_token }}Hello {{ message }}",
        tokenizer_family="char",
        description="A test template",
    )
    assert template.id is not None
    assert template.name == "test-template"
    assert template.status == "active"

    # Verify via repo
    fetched = await svc.get(template.id)
    assert fetched is not None
    assert fetched.template_string == "{{ bos_token }}Hello {{ message }}"


@pytest.mark.asyncio
async def test_create_duplicate_name_raises(db_session: AsyncSession):
    """Creating two templates with the same name raises a ValueError."""
    from anvil.services.finetuning.chat_template_service import ChatTemplateService

    svc = ChatTemplateService(db_session)
    await svc.create(
        name="duplicate",
        template_string="{{ x }}",
        tokenizer_family="char",
    )
    with pytest.raises(ValueError, match="already exists"):
        await svc.create(
            name="duplicate",
            template_string="{{ y }}",
            tokenizer_family="char",
        )


@pytest.mark.asyncio
async def test_create_empty_template_string_raises(db_session: AsyncSession):
    """Creating a template with an empty template_string raises a ValueError."""
    from anvil.services.finetuning.chat_template_service import ChatTemplateService

    svc = ChatTemplateService(db_session)
    with pytest.raises(ValueError, match="non-empty"):
        await svc.create(
            name="empty-template",
            template_string="",
            tokenizer_family="char",
        )
    with pytest.raises(ValueError, match="non-empty"):
        await svc.create(
            name="empty-template2",
            template_string="   ",
            tokenizer_family="char",
        )


@pytest.mark.asyncio
async def test_create_invalid_tokenizer_family_raises(db_session: AsyncSession):
    """Creating a template with an invalid tokenizer_family raises a ValueError."""
    from anvil.services.finetuning.chat_template_service import ChatTemplateService

    svc = ChatTemplateService(db_session)
    with pytest.raises(ValueError, match="tokenizer_family"):
        await svc.create(
            name="bad-family",
            template_string="{{ x }}",
            tokenizer_family="invalid_family",
        )


@pytest.mark.asyncio
async def test_list_templates(db_session: AsyncSession):
    """list_ returns all templates ordered by creation time."""
    from anvil.services.finetuning.chat_template_service import ChatTemplateService

    svc = ChatTemplateService(db_session)
    t1 = await svc.create(name="a", template_string="{{ a }}", tokenizer_family="char")
    t2 = await svc.create(
        name="b", template_string="{{ b }}", tokenizer_family="subword"
    )

    all_templates = await svc.list_()
    assert len(all_templates) >= 2
    names = [t.name for t in all_templates]
    assert "a" in names
    assert "b" in names


@pytest.mark.asyncio
async def test_list_by_tokenizer_family(db_session: AsyncSession):
    """list_ can filter by tokenizer_family."""
    from anvil.services.finetuning.chat_template_service import ChatTemplateService

    svc = ChatTemplateService(db_session)
    await svc.create(name="a", template_string="{{ a }}", tokenizer_family="char")
    await svc.create(name="b", template_string="{{ b }}", tokenizer_family="subword")

    char = await svc.list_(tokenizer_family="char")
    assert len(char) == 1
    assert char[0].name == "a"


@pytest.mark.asyncio
async def test_get_by_name(db_session: AsyncSession):
    """get_by_name returns the matching template or None."""
    from anvil.services.finetuning.chat_template_service import ChatTemplateService

    svc = ChatTemplateService(db_session)
    await svc.create(name="by-name", template_string="{{ x }}", tokenizer_family="char")

    found = await svc.get_by_name("by-name")
    assert found is not None
    assert found.name == "by-name"

    not_found = await svc.get_by_name("nonexistent")
    assert not_found is None


@pytest.mark.asyncio
async def test_get_default_template_for_model(db_session: AsyncSession):
    """get_default_template_for_model derives and persists a labeled default."""
    from anvil.services.finetuning.chat_template_service import ChatTemplateService

    svc = ChatTemplateService(db_session)

    # A model that has no chat template on its tokenizer → built-in default + warning
    template, warning = await svc.get_default_template_for_model(
        base_model_ref=None,
        tokenizer_family="char",
    )
    assert template is not None
    assert template.name.startswith("__builtin_default_")
    assert warning is not None
    assert "no chat template" in warning.lower()


@pytest.mark.asyncio
async def test_get_returns_none_for_missing(db_session: AsyncSession):
    """Get returns None for a non-existent template ID."""
    from anvil.services.finetuning.chat_template_service import ChatTemplateService

    svc = ChatTemplateService(db_session)
    result = await svc.get(999999)
    assert result is None


@pytest.mark.asyncio
async def test_list_with_no_match_returns_empty(db_session: AsyncSession):
    """list_ with a filter matching no templates returns empty."""
    from anvil.services.finetuning.chat_template_service import ChatTemplateService

    svc = ChatTemplateService(db_session)
    await svc.create(name="a", template_string="{{ a }}", tokenizer_family="char")

    result = await svc.list_(tokenizer_family="nonexistent")
    assert len(result) == 0
    """get_default_template_for_model caches and returns the same persisted default."""
    from anvil.services.finetuning.chat_template_service import ChatTemplateService

    svc = ChatTemplateService(db_session)

    t1, _ = await svc.get_default_template_for_model(
        base_model_ref=None,
        tokenizer_family="char",
    )
    t2, _ = await svc.get_default_template_for_model(
        base_model_ref=None,
        tokenizer_family="char",
    )
    # Same persisted entry, not a new row each time
    assert t1.id == t2.id
