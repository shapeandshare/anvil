from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from microgpt.api.deps import get_db_session
from microgpt.db.repositories.corpora import CorpusRepository
from microgpt.services.corpora import CorpusService
from microgpt.services.corpus_loader import CorpusLoader
from microgpt.services.tracking import TrackingService

WORKSPACE_ROOTS = [
    os.path.expanduser("~/Workbench/Repositories"),
    os.path.expanduser("~/Projects"),
    os.path.expanduser("~/Repositories"),
    os.path.expanduser("~/code"),
    os.path.expanduser("~/src"),
    os.path.expanduser("~"),
]

router = APIRouter()
tracking_svc = TrackingService()


async def get_service(session: AsyncSession = Depends(get_db_session)):
    repo = CorpusRepository(session)
    loader = CorpusLoader()
    return CorpusService(repo, loader)


@router.post("/corpora")
async def create_corpus(
    body: dict,
    svc: CorpusService = Depends(get_service),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        name = body["name"].strip()
        root_path = body["root_path"].strip()
        inc = body.get("include_patterns")
        exc = body.get("exclude_patterns")
        if inc:
            inc = [p.strip() for p in inc]
        if exc:
            exc = [p.strip() for p in exc]
        corpus = await svc.create(
            name=name,
            root_path=root_path,
            description=body.get("description"),
            include_patterns=inc,
            exclude_patterns=exc,
            chunking_strategy=body.get("chunking_strategy", "windowed"),
            chunk_overlap=body.get("chunk_overlap", 0.5),
            block_size=body.get("block_size", 16),
        )

        # Commit so MLflow tracking (which opens its own DB session) can read the corpus
        await session.commit()

        mlflow_run_id = await tracking_svc.start_run(
            run_name=f"corpus-create-{corpus.id}",
            params={
                "name": corpus.name,
                "root_path": corpus.root_path,
                "chunking_strategy": str(corpus.chunking_strategy),
                "chunk_overlap": str(corpus.chunk_overlap),
                "block_size": str(corpus.block_size),
            },
            engine_backend="corpus",
            device="n/a",
        )
        if mlflow_run_id:
            await tracking_svc.log_corpus_input(
                mlflow_run_id, corpus_id=corpus.id,
            )
            await tracking_svc.finish_run(mlflow_run_id)

    except ValueError as exc:
        await session.rollback()
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
    if corpus.errors:
        try:
            d["errors"] = json.loads(corpus.errors)
        except (json.JSONDecodeError, TypeError):
            pass
    return {"data": d, "error": None}


@router.delete("/corpora/{id}")
async def delete_corpus(id: int, svc: CorpusService = Depends(get_service)):
    deleted = await svc.delete(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Corpus not found")
    return {"data": {"status": "deleted"}, "error": None}


@router.post("/corpora/{id}/ingest")
async def ingest_corpus(
    id: int,
    max_files: int = 10000,
    svc: CorpusService = Depends(get_service),
):
    try:
        corpus, errors = await svc.ingest(id, max_files)
    except (ValueError, NotADirectoryError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    mlflow_run_id = await tracking_svc.start_run(
        run_name=f"corpus-ingest-{corpus.id}",
        params={
            "name": corpus.name,
            "file_count": str(corpus.file_count),
            "document_count": str(corpus.document_count),
            "root_path": corpus.root_path,
            "chunking_strategy": str(corpus.chunking_strategy),
        },
        engine_backend="corpus",
        device="n/a",
    )
    if mlflow_run_id:
        await tracking_svc.log_corpus_input(
            mlflow_run_id, corpus_id=corpus.id,
        )
        await tracking_svc.finish_run(mlflow_run_id)

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
            "errors": errors,
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


@router.post("/corpora/resolve-path")
async def resolve_path(body: dict):
    folder_name = body.get("folder_name", "").strip()
    if not folder_name:
        raise HTTPException(status_code=422, detail="folder_name required")
    for root in WORKSPACE_ROOTS:
        candidate = Path(root) / folder_name
        if candidate.is_dir():
            return {"data": {"path": str(candidate.resolve()), "root": root}, "error": None}
    return {
        "data": {"path": None, "root": None},
        "error": None,
    }


@router.post("/corpora/analyze-path")
async def analyze_path(body: dict):
    root_path = body["path"].strip()
    inc = body.get("include_patterns")
    exc = body.get("exclude_patterns")

    loader = CorpusLoader()
    try:
        result = loader.scan(root_path, inc, exc)
    except NotADirectoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    sizes = sorted(result.sizes)
    file_count = result.file_count
    total_bytes = result.total_bytes
    avg_bytes = round(total_bytes / file_count) if file_count else 0
    median_bytes = sizes[file_count // 2] if file_count else 0

    recommendations = _build_recommendations(result)

    return {
        "data": {
            "file_count": file_count,
            "total_bytes": total_bytes,
            "avg_bytes": avg_bytes,
            "median_bytes": median_bytes,
            "language_breakdown": dict(
                sorted(result.language_map.items(), key=lambda x: -x[1])
            ),
            "language_stats": _build_language_stats(result),
            "recommendations": recommendations,
        },
        "error": None,
    }


def _build_language_stats(scan) -> dict:
    stats = {}
    for lang, sizes in scan.language_sizes.items():
        sorted_sizes = sorted(sizes)
        avg = sum(sizes) / len(sizes) if sizes else 0
        median = sorted_sizes[len(sorted_sizes) // 2] if sorted_sizes else 0
        stats[lang] = {
            "files": len(sizes),
            "avg_bytes": round(avg),
            "median_bytes": median,
        }
    return stats


def _build_recommendations(scan) -> list[dict]:
    file_count = scan.file_count
    total_bytes = scan.total_bytes
    sizes = sorted(scan.sizes)
    avg_bytes = total_bytes / file_count if file_count else 0
    median_bytes = sizes[file_count // 2] if file_count else 0
    top_langs = sorted(scan.language_map.items(), key=lambda x: -x[1])
    lang_sizes = scan.language_sizes or {}

    CODE_LANGS = {"Python", "JavaScript", "TypeScript", "Go", "Rust", "Java", "C", "C++", "Ruby", "Shell"}
    DOC_LANGS = {"Markdown", "Text"}
    DATA_LANGS = {"JSON", "YAML"}

    code_count = sum(scan.language_map.get(l, 0) for l in CODE_LANGS)
    doc_count = sum(scan.language_map.get(l, 0) for l in DOC_LANGS)
    data_count = sum(scan.language_map.get(l, 0) for l in DATA_LANGS)

    code_avg = 0
    code_sizes = []
    for lang in CODE_LANGS:
        if lang in lang_sizes:
            code_sizes.extend(lang_sizes[lang])
    if code_sizes:
        code_avg = sum(code_sizes) / len(code_sizes)

    doc_avg = 0
    doc_sizes = []
    for lang in DOC_LANGS:
        if lang in lang_sizes:
            doc_sizes.extend(lang_sizes[lang])
    if doc_sizes:
        doc_avg = sum(doc_sizes) / len(doc_sizes)

    is_code_heavy = code_count > doc_count and code_count > data_count
    is_doc_heavy = doc_count > code_count and doc_avg > 5000
    is_data_oriented = data_count > code_count and data_count > doc_count

    recs: list[dict] = []

    is_mixed = sum(1 for c in [code_count > 100, doc_count > 100, data_count > 100]) > 1

    if is_mixed:
        recs.append({
            "strategy": None,
            "block_size": None,
            "overlap": None,
            "label": "Mixed repo — create separate corpora per type for best results",
            "estimated_docs": None,
            "detail": "{} code files (avg {}KB), {} doc files (avg {}KB), {} data files. Use include filters (e.g. `*.py`) to create focused corpora with optimal strategies per type.".format(
                code_count, round(code_avg / 1024, 1) if code_avg else 0,
                doc_count, round(doc_avg / 1024, 1) if doc_avg else 0,
                data_count,
            ),
        })

    if is_code_heavy and code_avg < 10240:
        recs.append({
            "strategy": "file",
            "block_size": None,
            "overlap": None,
            "label": "Code files as one doc each ({} files, avg {}KB)".format(
                code_count, round(code_avg / 1024, 1)
            ),
            "estimated_docs": file_count,
            "detail": "Source files are natural atomic training units. Each file becomes one doc, preserving function and class boundaries.",
        })
    elif is_doc_heavy or (is_code_heavy and code_avg >= 10240):
        recs.append({
            "strategy": "windowed",
            "block_size": 1024,
            "overlap": 0.25,
            "label": "Large files split into 1KB windows (avg {}KB)".format(
                round(doc_avg / 1024, 1) if is_doc_heavy else round(code_avg / 1024, 1)
            ),
            "estimated_docs": int(file_count * max(1, (avg_bytes - 1024) / 768 + 1)),
            "detail": "Files are large — split into 1024-char windows with 25% overlap for meaningful context chunks.",
        })

    recs.append({
        "strategy": "file",
        "block_size": None,
        "overlap": None,
        "label": "Each file as one doc ({} files)".format(file_count),
        "estimated_docs": file_count,
        "detail": "Simplest approach. Best when files are coherent units (code, articles).",
    })

    for bs in (64, 256, 1024):
        overlap = 0.25
        stride = int(bs * (1 - overlap))
        docs_per_file = max(1, (avg_bytes - bs) // stride + 1) if avg_bytes > bs else 1
        estimated_docs = file_count * docs_per_file
        recs.append({
            "strategy": "windowed",
            "block_size": bs,
            "overlap": overlap,
            "label": "{} char windows".format(bs),
            "estimated_docs": estimated_docs,
            "detail": "Sliding window, {} char stride. Good balance of granularity and doc count.".format(stride),
        })

    if is_data_oriented or data_count > 0:
        recs.append({
            "strategy": "line",
            "block_size": None,
            "overlap": None,
            "label": "Line-by-line ({} data files)".format(data_count),
            "estimated_docs": None,
            "detail": "Each non-empty line is a doc. Best for JSONL, logs, CSV where each line is independent.",
        })

    return recs


def _corpus_to_dict(corpus) -> dict:
    d = {
        "id": corpus.id,
        "name": corpus.name,
        "description": corpus.description,
        "root_path": corpus.root_path,
        "chunking_strategy": corpus.chunking_strategy,
        "chunk_overlap": corpus.chunk_overlap,
        "block_size": corpus.block_size,
        "file_count": corpus.file_count,
        "document_count": corpus.document_count,
        "created_at": str(corpus.created_at),
    }
    if corpus.errors:
        try:
            parsed = json.loads(corpus.errors)
            if isinstance(parsed, list) and len(parsed) > 0:
                d["error_count"] = len(parsed)
        except (json.JSONDecodeError, TypeError):
            pass
    return d