# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ChatTemplate ORM model for fine-tuning chat templates."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..timestamp_mixin import TimestampMixin


class ChatTemplate(Base, TimestampMixin):
    """A chat template for rendering prompt→response pairs during fine-tuning.

    Maps to the ``chat_templates`` table. Each row represents a Jinja-like
    template string that formats instruction examples into the token structure
    expected by a base model.

    Attributes
    ----------
    id : int
        Primary key, auto-increment.
    name : str
        Unique human-readable template name (255 chars max).
    template_string : str
        The Jinja-like template string (HuggingFace chat-template syntax).
    tokenizer_family : str
        Tokenizer family this template is valid for (20 chars max).
    base_model_ref : int or None
        Foreign key to ``external_models.id`` indicating the source model.
    status : str
        Template lifecycle status (default ``"active"``, 20 chars max).
    description : str or None
        Optional human-readable description.
    created_at : datetime
        TimestampMixin: row creation time.
    updated_at : datetime
        TimestampMixin: row last-update time.
    """

    __tablename__ = "chat_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    template_string: Mapped[str] = mapped_column(Text, nullable=False)
    tokenizer_family: Mapped[str] = mapped_column(String(20), nullable=False)
    base_model_ref: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("external_models.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="active")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
