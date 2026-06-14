from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from anvil.db.models.registry import ModelVersion, RegisteredModel


class ModelRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, model_id: int) -> RegisteredModel | None:
        return await self._session.get(RegisteredModel, model_id)

    async def get_all(self, search: str | None = None) -> Sequence[RegisteredModel]:
        stmt = select(RegisteredModel).order_by(RegisteredModel.created_at.desc())
        if search:
            stmt = stmt.where(RegisteredModel.name.ilike(f"%{search}%"))
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_name(self, name: str) -> RegisteredModel | None:
        result = await self._session.execute(
            select(RegisteredModel).where(RegisteredModel.name == name)
        )
        return result.scalar_one_or_none()

    async def add(self, model: RegisteredModel) -> RegisteredModel:
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return model

    async def delete(self, model_id: int) -> None:
        await self._session.execute(
            delete(ModelVersion).where(ModelVersion.model_id == model_id)
        )
        await self._session.execute(
            delete(RegisteredModel).where(RegisteredModel.id == model_id)
        )

    async def get_versions(self, model_id: int) -> Sequence[ModelVersion]:
        result = await self._session.execute(
            select(ModelVersion)
            .where(ModelVersion.model_id == model_id)
            .order_by(ModelVersion.version.desc())
        )
        return result.scalars().all()

    async def get_version(self, model_id: int, version: int) -> ModelVersion | None:
        result = await self._session.execute(
            select(ModelVersion).where(
                ModelVersion.model_id == model_id,
                ModelVersion.version == version,
            )
        )
        return result.scalar_one_or_none()

    async def add_version(self, version: ModelVersion) -> ModelVersion:
        self._session.add(version)
        await self._session.flush()
        await self._session.refresh(version)
        return version

    async def delete_version(self, model_id: int, version: int) -> None:
        await self._session.execute(
            delete(ModelVersion).where(
                ModelVersion.model_id == model_id,
                ModelVersion.version == version,
            )
        )

    async def get_next_version_number(self, model_id: int) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(ModelVersion.version), 0) + 1).where(
                ModelVersion.model_id == model_id
            )
        )
        val = result.scalar()
        return val if val is not None else 1

    async def get_model_with_versions(self, model_id: int) -> RegisteredModel | None:
        result = await self._session.execute(
            select(RegisteredModel)
            .where(RegisteredModel.id == model_id)
            .options(selectinload(RegisteredModel.versions))
        )
        return result.scalar_one_or_none()
