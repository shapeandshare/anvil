# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ChatTemplateRepository."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.base import Base
from anvil.db.models.chat_template import ChatTemplate
from anvil.db.repositories.chat_templates import ChatTemplateRepository
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
async def test_add_and_get(db_session: AsyncSession):
    """Adding a ChatTemplate and retrieving it by ID returns the same entry."""
    repo = ChatTemplateRepository(db_session)

    template = ChatTemplate(
        name="test-template",
        template_string="{{ bos_token }}{% for message in messages %}{{ message['content'] }}{% endfor %}",
        tokenizer_family="subword",
        description="A test template",
    )
    saved = await repo.add(template)
    assert saved.id is not None
    assert saved.name == "test-template"

    fetched = await repo.get(saved.id)
    assert fetched is not None
    assert fetched.template_string == template.template_string


@pytest.mark.asyncio
async def test_unique_name_enforced(db_session: AsyncSession):
    """Creating two templates with the same name raises an integrity error."""
    repo = ChatTemplateRepository(db_session)

    template = ChatTemplate(
        name="duplicate-name",
        template_string="{{ bos_token }}",
        tokenizer_family="char",
    )
    await repo.add(template)
    await db_session.commit()

    duplicate = ChatTemplate(
        name="duplicate-name",
        template_string="{{ bos_token }}",
        tokenizer_family="char",
    )
    with pytest.raises(Exception):
        await repo.add(duplicate)
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_get_by_name(db_session: AsyncSession):
    """get_by_name returns the matching template or None."""
    repo = ChatTemplateRepository(db_session)

    template = ChatTemplate(
        name="find-me",
        template_string="{{ bos_token }}",
        tokenizer_family="char",
    )
    await repo.add(template)

    found = await repo.get_by_name("find-me")
    assert found is not None
    assert found.id == template.id

    not_found = await repo.get_by_name("nonexistent")
    assert not_found is None


@pytest.mark.asyncio
async def test_get_by_tokenizer_family(db_session: AsyncSession):
    """get_by_tokenizer_family returns templates matching the family."""
    repo = ChatTemplateRepository(db_session)

    t1 = ChatTemplate(name="a", template_string="{{ x }}", tokenizer_family="char")
    t2 = ChatTemplate(name="b", template_string="{{ x }}", tokenizer_family="subword")
    t3 = ChatTemplate(
        name="c",
        template_string="{{ x }}",
        tokenizer_family="char",
        status="deprecated",
    )
    await repo.add(t1)
    await repo.add(t2)
    await repo.add(t3)

    char_templates = await repo.get_by_tokenizer_family("char")
    names = {t.name for t in char_templates}
    assert "a" in names
    assert "c" in names
    assert "b" not in names

    subword_templates = await repo.get_by_tokenizer_family("subword")
    assert len(subword_templates) == 1
    assert subword_templates[0].name == "b"
