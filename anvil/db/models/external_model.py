# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ExternalModel ORM entity for the external model registry."""

from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...services._shared.asset_state import AssetState
from ...services._shared.runnable_status import RunnableStatus
from ...services._shared.source_type import SourceType
from ..base import Base
from ..timestamp_mixin import TimestampMixin


class ExternalModel(Base, TimestampMixin):
    """A metadata-only entry for an externally-sourced model.

    Tracks an imported model's identity, origin, architecture, license,
    and runnability — all stored *before* any weight download occurs.

    Attributes
    ----------
    id : int
        Primary key, auto-increment.
    display_name : str
        Human-readable name for the registry entry.
    source_type : str
        Origin source (``SourceType`` value, 20 chars).
    source_identifier : str
        Source-specific identifier (HF repo ID or local path, 255 chars).
    architecture_family : str
        Model architecture (e.g. ``"LlamaForCausalLM"``, 100 chars).
    parameter_count : int
        Total parameters (0 if unknown).
    license : str
        SPDX license identifier (100 chars).
    tokenizer_family : str
        Tokenizer type (e.g. ``"sentencepiece"``, 100 chars).
    revision_sha : str
        Source revision or commit SHA (255 chars).
    runnable_status : str
        ``RunnableStatus`` value indicating execution eligibility.
    runnable_reason : str | None
        Plain-text explanation if not runnable.
    asset_availability : str
        ``AssetState`` value indicating asset download status.
    config_json : str | None
        Raw model configuration as JSON text.
    created_at : datetime
        TimestampMixin: row creation time.
    updated_at : datetime
        TimestampMixin: row last-update time.
    """

    __tablename__ = "external_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SourceType.HUGGINGFACE
    )
    source_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    architecture_family: Mapped[str] = mapped_column(String(100), nullable=False)
    parameter_count: Mapped[int] = mapped_column(Integer, nullable=False)
    license: Mapped[str] = mapped_column(String(100), nullable=False)
    tokenizer_family: Mapped[str] = mapped_column(String(100), nullable=False)
    revision_sha: Mapped[str] = mapped_column(String(255), nullable=False)
    runnable_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RunnableStatus.RUNNABLE
    )
    runnable_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    asset_availability: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AssetState.METADATA_ONLY
    )
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
