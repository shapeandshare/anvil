# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ChatTemplateService — CRUD and default-template derivation for chat templates."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models.chat_template import ChatTemplate
from ...db.repositories.chat_templates import ChatTemplateRepository
from .._shared.tokenizer_family import TokenizerFamily

# A simple built-in default chat template for tokenizer families that have
# no explicit template. Used as FR-005(c) fallback.
_BUILTIN_DEFAULTS: dict[str, str] = {
    TokenizerFamily.CHAR.value: ("{{ instruction }}\n{{ response }}"),
    TokenizerFamily.SUBWORD.value: (
        "{{ bos_token }}"
        "{% for message in messages %}"
        "{{ message['content'] }}"
        "{% endfor %}"
    ),
}


class ChatTemplateService:
    """Service for managing fine-tuning chat templates.

    Provides CRUD operations for ``ChatTemplate`` entries and
    deterministic default-template derivation from a base model's
    attached tokenizer (FR-005).

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session for all database operations.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ChatTemplateRepository(session)

    async def create(
        self,
        name: str,
        template_string: str,
        tokenizer_family: str,
        description: str | None = None,
        base_model_ref: int | None = None,
    ) -> ChatTemplate:
        """Create a new chat template after validating inputs.

        Parameters
        ----------
        name : str
            Unique template name.
        template_string : str
            The template string (must be non-empty).
        tokenizer_family : str
            Must be a valid ``TokenizerFamily`` value.
        description : str, optional
            Optional human-readable description.
        base_model_ref : int, optional
            FK to the base model this template originates from.

        Returns
        -------
        ChatTemplate
            The newly created and persisted template.

        Raises
        ------
        ValueError
            If the template name already exists, the template_string is
            empty, or the tokenizer_family is invalid.
        """
        stripped = template_string.strip()
        if not stripped:
            msg = "template_string must be non-empty"
            raise ValueError(msg)

        if tokenizer_family not in TokenizerFamily._value2member_map_:
            msg = f"invalid tokenizer_family: {tokenizer_family}"
            raise ValueError(msg)

        try:
            existing = await self._repo.get_by_name(name)
            if existing is not None:
                msg = f"template '{name}' already exists"
                raise ValueError(msg)

            template = ChatTemplate(
                name=name,
                template_string=stripped,
                tokenizer_family=tokenizer_family,
                description=description,
                base_model_ref=base_model_ref,
            )
            saved = await self._repo.add(template)
            await self._session.commit()
            return saved
        except IntegrityError as exc:
            await self._session.rollback()
            msg = f"template '{name}' already exists"
            raise ValueError(msg) from exc

    async def get(self, template_id: int) -> ChatTemplate | None:
        """Retrieve a template by primary key.

        Parameters
        ----------
        template_id : int
            Template primary key.

        Returns
        -------
        ChatTemplate | None
            The matching template, or ``None``.
        """
        return await self._repo.get(template_id)

    async def get_by_name(self, name: str) -> ChatTemplate | None:
        """Retrieve a template by its unique name.

        Parameters
        ----------
        name : str
            Template name to search for.

        Returns
        -------
        ChatTemplate | None
            Matching template, or ``None``.
        """
        return await self._repo.get_by_name(name)

    async def list_(
        self,
        tokenizer_family: str | None = None,
        status: str | None = None,
    ) -> Sequence[ChatTemplate]:
        """List templates, optionally filtered.

        Parameters
        ----------
        tokenizer_family : str, optional
            Filter by tokenizer family.
        status : str, optional
            Filter by status.

        Returns
        -------
        Sequence[ChatTemplate]
            Matching templates ordered by creation time.
        """
        all_templates = await self._repo.get_all()
        filtered = list(all_templates)
        if tokenizer_family is not None:
            filtered = [t for t in filtered if t.tokenizer_family == tokenizer_family]
        if status is not None:
            filtered = [t for t in filtered if t.status == status]
        return filtered

    async def get_default_template_for_model(
        self,
        base_model_ref: int | None,
        tokenizer_family: str,
    ) -> tuple[ChatTemplate, str | None]:
        """Derive or return a default chat template for a base model.

        Implements FR-005: (b) model-derived template → (c) built-in default.
        The default is persisted as a labeled ``ChatTemplate`` entry on first
        use (lazy derivation), so models imported before this feature are
        also covered.

        Parameters
        ----------
        base_model_ref : int or None
            The base model's primary key. When ``None``, no model-derived
            template can be read.
        tokenizer_family : str
            The tokenizer family for template selection.

        Returns
        -------
        tuple[ChatTemplate, str | None]
            A tuple of (template, warning). The warning is non-None when a
            built-in default is used instead of a model-derived template.
        """
        # (b): attempt model-derived template
        if base_model_ref is not None:
            derived = await self._get_model_derived_template(
                base_model_ref, tokenizer_family
            )
            if derived is not None:
                return derived, None

        # (c): built-in default — persist on first use
        default_name = f"__builtin_default_{tokenizer_family}"
        existing = await self._repo.get_by_name(default_name)
        if existing is not None:
            return existing, None

        template_str = _BUILTIN_DEFAULTS.get(
            tokenizer_family,
            "{{ instruction }}\n{{ response }}",
        )
        template = ChatTemplate(
            name=default_name,
            template_string=template_str,
            tokenizer_family=tokenizer_family,
            status="active",
            description=(
                f"Built-in default template for '{tokenizer_family}' "
                f"tokenizer family. Automatically generated — the base "
                f"model did not provide a chat template."
            ),
        )
        saved = await self._repo.add(template)
        await self._session.commit()
        warning = (
            f"Base model has no chat template; using built-in default "
            f"('{default_name}')."
        )
        return saved, warning

    async def _get_model_derived_template(
        self,
        base_model_ref: int,
        tokenizer_family: str,
    ) -> ChatTemplate | None:
        """Attempt to derive the template from the model's attached tokenizer.

        This reads the model's default chat template from its tokenizer
        config and persists it as a ``ChatTemplate`` entry if present.

        For HuggingFace tokenizers, the chat template is stored in
        ``tokenizer.json`` at ``model.metadata.chat_template``. Access
        requires the ``[finetune]`` extra; if unavailable, this degrades
        to a warning (FR-003).

        Parameters
        ----------
        base_model_ref : int
            The base model primary key.
        tokenizer_family : str
            The tokenizer family to validate against.

        Returns
        -------
        ChatTemplate or None
            The persisted model-derived template, or ``None`` if the model
            does not provide a chat template.
        """
        # TODO(053): Implement tokenizer-based derivation.
        # Requires loading the ExternalModel, reading its artifact directory,
        # and extracting the chat template from the tokenizer config.
        # This is deferred to the implementation sprint — the built-in default
        # fallback (FR-005c) covers all cases in the interim.
        return None
