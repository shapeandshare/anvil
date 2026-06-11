from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from microgpt.api.deps import get_db_session
from microgpt.db.repositories.datasets import DatasetRepository
from microgpt.services.datasets import DatasetService

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db_session)):
    repo = DatasetRepository(session)
    return DatasetService(repo)


@router.get("/datasets")
async def list_datasets(svc: DatasetService = Depends(get_service)):
    datasets = await svc.list_datasets()
    return {
        "datasets": [
            {
                "id": d.id,
                "name": d.name,
                "filename": d.filename,
                "vocabulary_size": d.vocabulary_size,
                "document_count": d.document_count,
                "created_at": str(d.created_at),
            }
            for d in datasets
        ]
    }


@router.get("/datasets/{id}")
async def get_dataset(id: int, svc: DatasetService = Depends(get_service)):
    d = await svc.get_dataset(id)
    if d is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Dataset not found")
    return {
        "id": d.id,
        "name": d.name,
        "filename": d.filename,
        "vocabulary_size": d.vocabulary_size,
        "document_count": d.document_count,
    }


@router.delete("/datasets/{id}")
async def delete_dataset(id: int, svc: DatasetService = Depends(get_service)):
    await svc.delete_dataset(id)
    return {"status": "deleted"}
