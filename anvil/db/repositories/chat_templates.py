# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Repository for ``ChatTemplate`` CRUD operations."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.chat_template import ChatTemplate


class ChatTemplateRepository:
    """Async CRUD repository for ``ChatTemplate`` entries.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session bound to the application database.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: int) -> ChatTemplate | None:
        """Retrieve a chat template by primary key.

        Parameters
        ----------
        id : int
            Template primary key.

        Returns
        -------
        ChatTemplate | None
            The matching template, or ``None`` if not found.
        """
        return await self._session.get(ChatTemplate, id)

    async def get_all(self) -> Sequence[ChatTemplate]:
        """Return all chat templates ordered by creation time (newest first).

        Returns
        -------
        Sequence[ChatTemplate]
            All registered chat templates.
        """
        result = await self._session.execute(
            select(ChatTemplate).order_by(ChatTemplate.created_at.desc())
        )
        return result.scalars().all()

    async def add(self, template: ChatTemplate) -> ChatTemplate:
        """Persist a new chat template.

        Parameters
        ----------
        template : ChatTemplate
            Unsaved template instance.

        Returns
        -------
        ChatTemplate
            The saved template with generated fields populated.
        """
        self._session.add(template)
        await self._session.flush()
        await self._session.refresh(template)
        return template

    async def get_by_name(self, name: str) -> ChatTemplate | None:
        """Look up a template by its unique name.

        Parameters
        ----------
        name : str
            Template name to search for.

        Returns
        -------
        ChatTemplate | None
            Matching template, or ``None`` if no entry with that name exists.
        """
        result = await self._session.execute(
            select(ChatTemplate).where(ChatTemplate.name == name)
        )
        return result.scalar_one_or_none()

    async def get_by_tokenizer_family(
        self, tokenizer_family: str
    ) -> Sequence[ChatTemplate]:
        """Return templates matching a tokenizer family.

        Parameters
        ----------
        tokenizer_family : str
            Tokenizer family to filter by.

        Returns
        -------
        Sequence[ChatTemplate]
            Templates matching the given tokenizer family.
        """
        result = await self._session.execute(
            select(ChatTemplate).where(
                ChatTemplate.tokenizer_family == tokenizer_family
            )
        )
        return result.scalars().all()
