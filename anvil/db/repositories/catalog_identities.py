# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Repository for ``CatalogIdentity`` CRUD operations.

The identity triple dedup guard is the only transactional uniqueness
mechanism for model imports.  The MLflow registry has no transactions,
so this table is the lock (FR-005).
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...services.catalog.model_ref import ModelRef
from ..models.catalog_identity import CatalogIdentity


class CatalogIdentityRepository:
    """Async CRUD repository for ``CatalogIdentity`` entries.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session bound to the application database.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        source_type: str,
        source_identifier: str,
        revision_sha: str,
        registry_model_name: str,
    ) -> CatalogIdentity:
        """Insert a new identity guard row.

        If a row with the same triple already exists, raises
        ``IntegrityError`` (UNIQUE constraint) — the caller must catch
        this and resolve against the existing entry.

        Parameters
        ----------
        source_type : str
            Provider type.
        source_identifier : str
            Provider-specific identifier.
        revision_sha : str
            Provider revision SHA.
        registry_model_name : str
            Catalog name derived for this identity.

        Returns
        -------
        CatalogIdentity
            The newly created identity row.

        Raises
        ------
        IntegrityError
            If the identity triple already exists.
        """
        identity = CatalogIdentity(
            source_type=source_type,
            source_identifier=source_identifier,
            revision_sha=revision_sha,
            registry_model_name=registry_model_name,
        )
        self._session.add(identity)
        await self._session.flush()
        return identity

    async def find_by_triple(
        self,
        source_type: str,
        source_identifier: str,
        revision_sha: str,
    ) -> CatalogIdentity | None:
        """Look up an identity guard row by its triple.

        Parameters
        ----------
        source_type : str
            Provider type.
        source_identifier : str
            Provider-specific identifier.
        revision_sha : str
            Provider revision SHA.

        Returns
        -------
        CatalogIdentity or None
            Matching row, or ``None`` if the triple is unknown.
        """
        result = await self._session.execute(
            select(CatalogIdentity).where(
                CatalogIdentity.source_type == source_type,
                CatalogIdentity.source_identifier == source_identifier,
                CatalogIdentity.revision_sha == revision_sha,
            )
        )
        return result.scalar_one_or_none()

    async def set_version(
        self, identity_id: int, version: int
    ) -> CatalogIdentity | None:
        """Update the registry version on an existing identity row.

        Parameters
        ----------
        identity_id : int
            Primary key of the identity row.
        version : int
            The catalog model version number assigned by the registry.

        Returns
        -------
        CatalogIdentity or None
            Updated row, or ``None`` if not found.
        """
        identity = await self._session.get(CatalogIdentity, identity_id)
        if identity is None:
            return None
        identity.registry_model_version = version
        await self._session.flush()
        return identity

    async def get_model_ref(self, identity_id: int) -> ModelRef | None:
        """Resolve a ModelRef from an identity row.

        Parameters
        ----------
        identity_id : int
            Primary key of the identity row.

        Returns
        -------
        ModelRef or None
            The model reference, or ``None`` if the row is not found
            or the version is not yet set.
        """
        identity = await self._session.get(CatalogIdentity, identity_id)
        if identity is None or identity.registry_model_version is None:
            return None
        return ModelRef(
            name=identity.registry_model_name,
            version=identity.registry_model_version,
        )

    async def find_all(
        self,
    ) -> Sequence[CatalogIdentity]:
        """Return all identity rows (for reconciliation / admin).

        Returns
        -------
        Sequence[CatalogIdentity]
        """
        result = await self._session.execute(select(CatalogIdentity))
        return result.scalars().all()

    async def find_latest_by_source_identifier(
        self,
        source_type: str,
        source_identifier: str,
    ) -> CatalogIdentity | None:
        """Find the most recently created identity by source type and identifier.

        Useful for UI pages that need to resolve an import job's source
        identifier to a catalog identity without knowing the exact
        revision SHA.  Returns the latest-created match.

        Parameters
        ----------
        source_type : str
            Provider type (e.g. ``"huggingface"``, ``"local"``).
        source_identifier : str
            Provider-specific identifier (e.g. HuggingFace repo ID).

        Returns
        -------
        CatalogIdentity | None
            The most recent matching identity, or ``None``.
        """
        result = await self._session.execute(
            select(CatalogIdentity)
            .where(
                CatalogIdentity.source_type == source_type,
                CatalogIdentity.source_identifier == source_identifier,
            )
            .order_by(CatalogIdentity.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
