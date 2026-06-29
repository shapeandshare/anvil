# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Repository for ``ModelAsset`` CRUD operations."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.model_asset import ModelAsset


class ModelAssetRepository:
    """Async CRUD repository for ``ModelAsset`` entries.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session bound to the application database.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_model(self, model_id: int) -> Sequence[ModelAsset]:
        """Return all assets for a given external model.

        Parameters
        ----------
        model_id : int
            Foreign key to ``ExternalModel``.

        Returns
        -------
        Sequence[ModelAsset]
            All asset rows for the model.
        """
        stmt = (
            select(ModelAsset)
            .where(ModelAsset.external_model_id == model_id)
            .order_by(ModelAsset.id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_model_and_type(
        self, model_id: int, asset_type: str
    ) -> Sequence[ModelAsset]:
        """Return assets for a model filtered by type.

        Parameters
        ----------
        model_id : int
            Foreign key to ``ExternalModel``.
        asset_type : str
            ``ModelAssetType`` value to filter by.

        Returns
        -------
        Sequence[ModelAsset]
            Matching asset rows.
        """
        stmt = (
            select(ModelAsset)
            .where(
                ModelAsset.external_model_id == model_id,
                ModelAsset.asset_type == asset_type,
            )
            .order_by(ModelAsset.id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def add(self, asset: ModelAsset) -> ModelAsset:
        """Persist a new model asset row.

        Parameters
        ----------
        asset : ModelAsset
            Unsaved asset instance.

        Returns
        -------
        ModelAsset
            The saved asset with generated fields populated.
        """
        self._session.add(asset)
        await self._session.flush()
        await self._session.refresh(asset)
        return asset

    async def update_status(
        self,
        id: int,
        status: str,
        *,
        sha256: str | None = None,
        storage_path: str | None = None,
    ) -> ModelAsset | None:
        """Update the lifecycle status of an asset.

        Parameters
        ----------
        id : int
            Asset primary key.
        status : str
            New ``ModelAssetStatus`` value.
        sha256 : str | None
            SHA-256 hash, set when ``AVAILABLE``.
        storage_path : str | None
            Storage path, set when ``AVAILABLE``.

        Returns
        -------
        ModelAsset | None
            The updated asset, or ``None`` if not found.
        """
        asset = await self._session.get(ModelAsset, id)
        if asset is None:
            return None
        asset.status = status
        if sha256 is not None:
            asset.sha256 = sha256
        if storage_path is not None:
            asset.storage_path = storage_path
        await self._session.flush()
        await self._session.refresh(asset)
        return asset

    async def update_progress(
        self, id: int, downloaded_bytes: int
    ) -> ModelAsset | None:
        """Update byte-level download progress for an asset.

        Parameters
        ----------
        id : int
            Asset primary key.
        downloaded_bytes : int
            Bytes downloaded so far.

        Returns
        -------
        ModelAsset | None
            The updated asset, or ``None`` if not found.
        """
        asset = await self._session.get(ModelAsset, id)
        if asset is None:
            return None
        asset.downloaded_bytes = downloaded_bytes
        await self._session.flush()
        await self._session.refresh(asset)
        return asset
