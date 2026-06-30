# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""UserSecret ORM entity for encrypted per-user secrets."""

from __future__ import annotations

from sqlalchemy import Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..timestamp_mixin import TimestampMixin


class UserSecret(Base, TimestampMixin):
    """An encrypted per-user secret value (e.g. HuggingFace token).

    Secrets are scoped by ``user_id`` and ``key`` (unique together).
    Values are encrypted at rest using AES-256-GCM via the
    ``cryptography`` library.

    Attributes
    ----------
    id : int
        Primary key, auto-increment.
    user_id : str
        User identifier (255 chars).
    key : str
        Secret key name, e.g. ``"hf_token"`` (100 chars). Unique per user.
    key_id : str
        Encryption key identifier (UUID, 36 chars). Indexed for
        re-encryption sweep queries.
    encrypted_value : str
        AES-256-GCM encrypted, base64-encoded value.
    created_at : datetime
        TimestampMixin: row creation time.
    updated_at : datetime
        TimestampMixin: row last-update time.
    """

    __tablename__ = "user_secrets"
    __table_args__ = (
        UniqueConstraint("user_id", "key", name="uq_user_secrets_user_key"),
        Index("ix_user_secrets_key_id", "key_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    key_id: Mapped[str] = mapped_column(String(36), nullable=False, server_default="")
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
