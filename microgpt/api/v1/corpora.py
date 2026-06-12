from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from microgpt.api.deps import get_db_session
from microgpt.db.repositories.corpora import CorpusRepository
from microgpt.services.corpora import CorpusService
from microgpt.services.corpus_loader import CorpusLoader

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db_session)):
    repo = CorpusRepository(session)
    loader = CorpusLoader()
    return CorpusService(repo, loader)


@router.post("/corpora")
async def create_corpus(body: dict, svc: CorpusService = Depends(get_service)):
    try:
        corpus = await svc.create(
            name=body["name"],
            root_path=body["root_path"],
            description=body.get("description"),
            include_patterns=body.get("include_patterns"),
            exclude_patterns=body.get("exclude_patterns"),
            chunking_strategy=body.get("chunking_strategy", "windowed"),
            chunk_overlap=body.get("chunk_overlap", 0.5),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"data": _corpus_to_dict(corpus), "error": None}


@router.get("/corpora")
async def list_corpora(svc: CorpusService = Depends(get_service)):
    corpora = await svc.list()
    return {
        "data": [_corpus_to_dict(c) for c in corpora],
        "error": None,
    }


@router.get("/corpora/{id}")
async def get_corpus(id: int, svc: CorpusService = Depends(get_service)):
    corpus = await svc.get(id)
    if corpus is None:
        raise HTTPException(status_code=404, detail="Corpus not found")
    lang_map = None
    if corpus.language_map:
        try:
            lang_map = json.loads(corpus.language_map)
        except json.JSONDecodeError:
            pass
    d = _corpus_to_dict(corpus)
    d["language_map"] = lang_map
    return {"data": d, "error": None}


@router.delete("/corpora/{id}")
async def delete_corpus(id: int, svc: CorpusService = Depends(get_service)):
    deleted = await svc.delete(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Corpus not found")
    return {"data": {"status": "deleted"}, "error": None}


@router.post("/corpora/{id}/ingest")
async def ingest_corpus(id: int, svc: CorpusService = Depends(get_service)):
    try:
        corpus = await svc.ingest(id)
    except (ValueError, NotADirectoryError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    lang_map = None
    if corpus.language_map:
        try:
            lang_map = json.loads(corpus.language_map)
        except json.JSONDecodeError:
            pass
    return {
        "data": {
            "corpus_id": corpus.id,
            "file_count": corpus.file_count,
            "document_count": corpus.document_count,
            "language_map": lang_map,
            "errors": [],
        },
        "error": None,
    }


@router.get("/corpora/{id}/files")
async def list_corpus_files(
    id: int,
    language: str | None = None,
    svc: CorpusService = Depends(get_service),
):
    files = await svc.get_files(id, language)
    return {
        "data": [
            {
                "id": f.id,
                "corpus_id": f.corpus_id,
                "relative_path": f.relative_path,
                "language": f.language,
                "line_count": f.line_count,
                "char_count": f.char_count,
                "chunk_count": f.chunk_count,
                "size_bytes": f.size_bytes,
            }
            for f in files
        ],
        "error": None,
    }


@router.get("/corpora/{id}/files/{file_id}")
async def get_corpus_file(
    id: int,
    file_id: int,
    svc: CorpusService = Depends(get_service),
):
    f = await svc.get_file(file_id)
    if f is None or f.corpus_id != id:
        raise HTTPException(status_code=404, detail="File not found")
    return {
        "data": {
            "id": f.id,
            "corpus_id": f.corpus_id,
            "relative_path": f.relative_path,
            "language": f.language,
            "line_count": f.line_count,
            "char_count": f.char_count,
            "chunk_count": f.chunk_count,
            "encoding": f.encoding,
            "size_bytes": f.size_bytes,
        },
        "error": None,
    }


def _corpus_to_dict(corpus) -> dict:
    return {
        "id": corpus.id,
        "name": corpus.name,
        "description": corpus.description,
        "root_path": corpus.root_path,
        "chunking_strategy": corpus.chunking_strategy,
        "chunk_overlap": corpus.chunk_overlap,
        "file_count": corpus.file_count,
        "document_count": corpus.document_count,
        "created_at": str(corpus.created_at),
    }