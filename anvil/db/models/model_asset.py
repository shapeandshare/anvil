# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ModelAsset ORM entity for per-file asset tracking."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..timestamp_mixin import TimestampMixin


class ModelAssetType(StrEnum):
    """Type of model asset file.

    Attributes
    ----------
    WEIGHTS : str
        Model weight file (safetensors shard) (``"weights"``).
    TOKENIZER : str
        Tokenizer data file (``"tokenizer"``).
    CONFIG : str
        Model configuration file (``"config"``).
    """

    WEIGHTS = "weights"
    TOKENIZER = "tokenizer"
    CONFIG = "config"


class ModelAssetStatus(StrEnum):
    """Lifecycle state of a single model asset file.

    Attributes
    ----------
    PENDING : str
        Asset discovered but download not started (``"pending"``).
    DOWNLOADING : str
        Asset is being downloaded (``"downloading"``).
    AVAILABLE : str
        Download complete and SHA-256 verified (``"available"``).
    UNAVAILABLE : str
        Download failed or unrecoverable error (``"unavailable"``).
    CHECKSUM_MISMATCH : str
        Download completed but SHA-256 does not match (``"checksum_mismatch"``).
    """

    PENDING = "pending"
    DOWNLOADING = "downloading"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    CHECKSUM_MISMATCH = "checksum_mismatch"


class ModelAsset(Base, TimestampMixin):
    """A single file asset (weight shard, tokenizer, or config) for a model.

    One row per file. The model is considered fully available only when
    **all** of its ``ModelAsset`` rows reach ``AVAILABLE``.

    Attributes
    ----------
    id : int
        Primary key, auto-increment.
    external_model_id : int
        FK to ``external_models.id`` (ON DELETE CASCADE).
    asset_type : str
        ``ModelAssetType`` value (20 chars).
    filename : str
        Original filename from the upstream source (255 chars).
    storage_path : str | None
        Relative path within the store, set when ``AVAILABLE``.
    sha256 : str | None
        SHA-256 content hash, set when ``AVAILABLE`` (64 chars).
    size_bytes : int
        Total file size in bytes.
    downloaded_bytes : int
        Bytes downloaded so far (for resume + progress).
    source_url : str | None
        Upstream download URL for resume support.
    format : str | None
        Format identifier (e.g. ``"safetensors"``, ``"json"``).
    status : str
        ``ModelAssetStatus`` value (20 chars).
    created_at : datetime
        TimestampMixin: row creation time.
    updated_at : datetime
        TimestampMixin: row last-update time.
    """

    __tablename__ = "model_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_model_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("external_models.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_type: Mapped[str] = mapped_column(String(20), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    downloaded_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    format: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ModelAssetStatus.PENDING
    )
