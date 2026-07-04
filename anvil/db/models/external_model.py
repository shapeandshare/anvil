"""ExternalModel ORM entity — LEGACY, scheduled for removal (SC-006).

This module is retained as a stub to avoid breaking US2-dependent
services (model_import_service, model_asset_service) during the
transition. New code MUST NOT import from this module — use the
catalog identity layer instead.

.. deprecated::
    Use ``CatalogIdentity`` + ``ModelCatalogService`` instead.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...services._shared.asset_state import AssetState
from ...services._shared.runnable_status import RunnableStatus
from ...services._shared.source_type import SourceType
from ..base import Base
from ..timestamp_mixin import TimestampMixin


class ExternalModel(Base, TimestampMixin):
    """A metadata-only entry for an externally-sourced model (LEGACY).

    .. deprecated::
        Use the MLflow Model Catalog (``ModelCatalogService``) instead.
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
