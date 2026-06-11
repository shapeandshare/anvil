from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from microgpt.api.deps import get_db_session
from microgpt.db.models.training_config import Dataset
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
        raise HTTPException(status_code=404, detail="Dataset not found")
    return {
        "id": d.id,
        "name": d.name,
        "filename": d.filename,
        "vocabulary_size": d.vocabulary_size,
        "document_count": d.document_count,
    }


@router.post("/datasets/upload")
async def upload_dataset(
    file: UploadFile,
    session: AsyncSession = Depends(get_db_session),
):
    content = await file.read()
    text = content.decode("utf-8")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    vocab = len(set("".join(lines)))

    dataset = Dataset(
        name=file.filename or "untitled",
        filename=file.filename or "untitled",
        file_path="",
        vocabulary_size=vocab,
        document_count=len(lines),
    )
    session.add(dataset)
    await session.commit()
    await session.refresh(dataset)

    return {
        "id": dataset.id,
        "name": dataset.name,
        "document_count": len(lines),
        "vocabulary_size": vocab,
    }


@router.delete("/datasets/{id}")
async def delete_dataset(id: int, svc: DatasetService = Depends(get_service)):
    await svc.delete_dataset(id)
    return {"status": "deleted"}