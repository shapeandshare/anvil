# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Corpus management endpoints for v1 API.

Provides CRUD and ingestion routes for managing text corpora. A corpus
represents a directory of text files that can be scanned, analyzed, and
ingested as training documents. Supports gitignore-style pattern filtering,
language detection, and chunking strategy configuration.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from ...api.deps import get_workbench
from ...services.datasets.chunking_strategy import ChunkingStrategy
from ...services.datasets.corpus_loader import CorpusLoader
from ...services.tracking.tracking import TrackingService
from ...workbench import AnvilWorkbench
from .schemas_corpus import (
    AnalyzePathBody,
    CreateCorpusBody,
    ForkCorpusBody,
    ResolvePathBody,
)

WORKSPACE_ROOTS = [
    os.path.expanduser("~/Workbench/Repositories"),
    os.path.expanduser("~/Projects"),
    os.path.expanduser("~/Repositories"),
    os.path.expanduser("~/code"),
    os.path.expanduser("~/src"),
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Downloads"),
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~"),
]
"""list[str]: Directories searched when resolving a partial folder name to
an absolute path via the ``/corpora/resolve-path`` endpoint."""

router = APIRouter()
tracking_svc = TrackingService()


@router.post("/corpora")
async def create_corpus(
    body: CreateCorpusBody,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Create a new corpus from a directory path.

    Accepts corpus configuration (name, root path, include/exclude patterns,
    chunking strategy) and creates a corpus record. Also tracks the creation
    event in MLflow with corpus metadata tags.

    Parameters
    ----------
    body : CreateCorpusBody
        Request body with ``name``, ``root_path``, optional patterns,
        description, chunking strategy, overlap, and block size.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        Corpus data and ``"error": None``.

    Raises
    ------
    HTTPException
        If validation fails (422).
    """
    try:
        name = body.name.strip()
        root_path = body.root_path.strip()
        inc = body.include_patterns
        exc = body.exclude_patterns
        if inc:
            inc = [p.strip() for p in inc]
        if exc:
            exc = [p.strip() for p in exc]
        corpus = await workbench.corpora.create(
            name=name,
            root_path=root_path,
            description=body.description,
            include_patterns=inc,
            exclude_patterns=exc,
            chunking_strategy=(
                ChunkingStrategy(body.chunking_strategy)
                if body.chunking_strategy
                else ChunkingStrategy.WINDOWED
            ),
            chunk_overlap=body.chunk_overlap,
            block_size=body.block_size,
        )

        # Commit so MLflow tracking (which opens its own DB session) can read the corpus
        await workbench.session.commit()

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
                mlflow_run_id,
                corpus_id=corpus.id,
            )
            await tracking_svc.finish_run(mlflow_run_id)

        # Phase 1B: enrich corpus tracking with metadata tags
        if mlflow_run_id:
            await tracking_svc.set_tag(mlflow_run_id, "anvil.entity_type", "corpus")
            await tracking_svc.set_tag(mlflow_run_id, "anvil.entity_id", str(corpus.id))
            if corpus.file_count:
                await tracking_svc.set_tag(
                    mlflow_run_id, "anvil.corpus.file_count", str(corpus.file_count)
                )
            if corpus.language_map:
                await tracking_svc.set_tag(
                    mlflow_run_id, "anvil.corpus.language_map", corpus.language_map
                )

    except ValueError as exc:
        await workbench.session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"data": _corpus_to_dict(corpus), "error": None}


@router.post("/corpora/{corpus_id}/fork")
async def fork_corpus(
    corpus_id: int,
    body: ForkCorpusBody,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Create a new corpus variant from an existing one.

    Copies the source corpus's parameters and applies any overrides
    from the request body. The new corpus tracks its lineage via
    ``parent_id``. Does NOT ingest — call ``POST /corpora/{id}/ingest``
    separately.

    Parameters
    ----------
    id : int
        The source corpus ID.
    body : ForkCorpusBody
        Request body with ``name`` and optional overrides.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        Forked corpus data and ``"error": None``.

    Raises
    ------
    HTTPException
        If validation fails (422).
    """
    try:
        name = body.name.strip()
        inc = body.include_patterns
        exc = body.exclude_patterns
        if inc:
            inc = [p.strip() for p in inc]
        if exc:
            exc = [p.strip() for p in exc]
        corpus = await workbench.corpora.fork(
            source_id=corpus_id,
            name=name,
            description=body.description,
            include_patterns=inc,
            exclude_patterns=exc,
            chunking_strategy=(
                ChunkingStrategy(body.chunking_strategy)
                if body.chunking_strategy
                else None
            ),
            chunk_overlap=body.chunk_overlap,
            block_size=body.block_size,
        )

        await workbench.session.commit()

        mlflow_run_id = await tracking_svc.start_run(
            run_name=f"corpus-fork-{corpus.id}",
            params={
                "name": corpus.name,
                "parent_id": str(corpus.parent_id),
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
                mlflow_run_id,
                corpus_id=corpus.id,
            )
            await tracking_svc.finish_run(mlflow_run_id)

        # Phase 1B: enrich fork tracking with lineage tags
        if mlflow_run_id:
            await tracking_svc.set_tag(mlflow_run_id, "anvil.entity_type", "corpus")
            await tracking_svc.set_tag(mlflow_run_id, "anvil.entity_id", str(corpus.id))
            await tracking_svc.set_tag(
                mlflow_run_id, "anvil.corpus.parent_id", str(corpus.parent_id)
            )

    except ValueError as exc:
        await workbench.session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"data": _corpus_to_dict(corpus), "error": None}


@router.get("/corpora")
async def list_corpora(
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, Any]:
    """List all corpora.

    Parameters
    ----------
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        List of corpus dicts and ``"error": None``.
    """
    corpora = await workbench.corpora.list_all()
    return {
        "data": [_corpus_to_dict(c) for c in corpora],
        "error": None,
    }


@router.get("/corpora/{corpus_id}")
async def get_corpus(
    corpus_id: int, workbench: Annotated[AnvilWorkbench, Depends(get_workbench)]
) -> dict[str, Any]:
    """Get a single corpus by ID.

    Parameters
    ----------
    id : int
        The corpus ID.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        Corpus data with parsed ``language_map`` and ``errors``, and
        ``"error": None``.

    Raises
    ------
    HTTPException
        If the corpus is not found (404).
    """
    corpus = await workbench.corpora.get(corpus_id)
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


@router.delete("/corpora/{corpus_id}")
async def delete_corpus(
    corpus_id: int, workbench: Annotated[AnvilWorkbench, Depends(get_workbench)]
) -> dict[str, Any]:
    """Delete a corpus by ID.

    Also logs a lifecycle event via ``TrackingService``.

    Parameters
    ----------
    id : int
        The corpus ID.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        Deletion status and ``"error": None``.

    Raises
    ------
    HTTPException
        If the corpus is not found (404).
    """
    deleted = await workbench.corpora.delete(corpus_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Corpus not found")
    # Phase 1B: lifecycle tracking for delete
    tracking_svc_del = TrackingService()
    if not tracking_svc_del.is_degraded:
        try:
            await tracking_svc_del.log_corpus_lifecycle_event(
                corpus_id=corpus_id,
                event_type="delete",
            )
        except (ValueError, OSError):
            pass
    return {"data": {"status": "deleted"}, "error": None}


@router.post("/corpora/{corpus_id}/ingest")
async def ingest_corpus(
    corpus_id: int,
    max_files: int = 10000,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Ingest files from a corpus directory into documents.

    Scans the corpus root path, reads matching files, and creates chunked
    document records. Tracks the ingest event in MLflow.

    Parameters
    ----------
    id : int
        The corpus ID.
    max_files : int, optional
        Maximum number of files to ingest (default ``10000``).
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        Ingestion results including ``corpus_id``, ``file_count``,
        ``document_count``, ``language_map``, and ``errors``.

    Raises
    ------
    HTTPException
        If the corpus is not found or the path is invalid (422).
    """
    try:
        corpus, errors = await workbench.corpora.ingest(corpus_id, max_files)
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
            mlflow_run_id,
            corpus_id=corpus.id,
        )
        await tracking_svc.finish_run(mlflow_run_id)

    # Phase 1B: enrich ingest tracking with metadata tags
    if mlflow_run_id:
        await tracking_svc.set_tag(mlflow_run_id, "anvil.entity_type", "corpus")
        await tracking_svc.set_tag(mlflow_run_id, "anvil.entity_id", str(corpus.id))
        if corpus.file_count:
            await tracking_svc.set_tag(
                mlflow_run_id, "anvil.corpus.file_count", str(corpus.file_count)
            )
        if corpus.document_count:
            await tracking_svc.set_tag(
                mlflow_run_id, "anvil.corpus.document_count", str(corpus.document_count)
            )

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


@router.get("/corpora/{corpus_id}/files")
async def list_corpus_files(
    corpus_id: int,
    language: str | None = None,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """List files belonging to a corpus, optionally filtered by language.

    Parameters
    ----------
    id : int
        The corpus ID.
    language : str | None, optional
        Filter by language (e.g. ``"Python"``, ``"Markdown"``).
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        List of file metadata dicts and ``"error": None``.
    """
    files = await workbench.corpora.get_files(corpus_id, language)
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


@router.get("/corpora/{corpus_id}/files/{file_id}")
async def get_corpus_file(
    corpus_id: int,
    file_id: int,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Get a single file from a corpus by file ID.

    Parameters
    ----------
    id : int
        The corpus ID.
    file_id : int
        The file ID.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        File metadata and ``"error": None``.

    Raises
    ------
    HTTPException
        If the file is not found (404).
    """
    f = await workbench.corpora.get_file(file_id)
    if f is None or f.corpus_id != corpus_id:
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
async def resolve_path(body: ResolvePathBody) -> dict[str, Any]:
    """Resolve a folder name to an absolute path by searching workspace roots.

    Iterates over ``WORKSPACE_ROOTS`` and returns the first match where
    ``root / folder_name`` is an existing directory.

    Parameters
    ----------
    body : ResolvePathBody
        Request body with ``folder_name``: str — the folder to locate.

    Returns
    -------
    dict
        ``path``: str or None, ``root``: str or None, and ``"error": None``.

    Raises
    ------
    HTTPException
        If ``folder_name`` is empty (422).
    """
    folder_name = body.folder_name.strip()
    if not folder_name:
        raise HTTPException(status_code=422, detail="folder_name required")
    for root in WORKSPACE_ROOTS:
        candidate = Path(root) / folder_name
        if candidate.is_dir():
            return {
                "data": {"path": str(candidate.resolve()), "root": root},
                "error": None,
            }
    return {
        "data": {"path": None, "root": None},
        "error": None,
    }


@router.post("/corpora/analyze-path")
async def analyze_path(body: AnalyzePathBody) -> dict[str, Any]:
    """Analyze a directory path and return file statistics and recommendations.

    Scans the given path using ``CorpusLoader`` and returns file counts,
    size statistics, language breakdown, and chunking strategy recommendations.

    Parameters
    ----------
    body : AnalyzePathBody
        Request body with ``path``, ``include_patterns``, and
        ``exclude_patterns``.

    Returns
    -------
    dict
        Analysis results including ``file_count``, ``total_bytes``,
        ``language_breakdown``, ``recommendations``, and ``"error": None``.

    Raises
    ------
    HTTPException
        If the path is not a directory (422).
    """
    root_path = body.path.strip()
    inc = body.include_patterns
    exc = body.exclude_patterns

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


def _build_language_stats(scan: Any) -> dict[str, Any]:
    """Build per-language statistics from a scan result.

    Parameters
    ----------
    scan : ScanResult
        The result from a ``CorpusLoader`` scan containing per-language
        file size lists.

    Returns
    -------
    dict
        Mapping of language names to dicts with ``files``, ``avg_bytes``,
        and ``median_bytes``.
    """
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


def _collect_file_sizes(lang_sizes: dict[str, list[int]], langs: set[str]) -> list[int]:
    """Collect file sizes for a set of languages from a scan result.

    Parameters
    ----------
    lang_sizes : dict[str, list[int]]
        Mapping of language names to lists of file sizes.
    langs : set[str]
        Languages to collect sizes for.

    Returns
    -------
    list[int]
        Flat list of file sizes for the given languages.
    """
    sizes: list[int] = []
    for lang in langs:
        if lang in lang_sizes:
            sizes.extend(lang_sizes[lang])
    return sizes


def _avg_or_zero(sizes: list[int]) -> float:
    """Return the average of a list, or 0 if empty.

    Parameters
    ----------
    sizes : list[int]
        List of file sizes.

    Returns
    -------
    float
        Average or 0.
    """
    return sum(sizes) / len(sizes) if sizes else 0.0


def _build_recommendations(scan: Any) -> list[dict[str, Any]]:
    """Build chunking strategy recommendations from a scan result.

    Analyzes file type distribution (code vs. docs vs. data), average file
    sizes, and language composition to suggest optimal chunking strategies
    (file-per-doc, windowed, line-by-line) with block sizes and overlap.

    Parameters
    ----------
    scan : ScanResult
        The result from a ``CorpusLoader`` scan.

    Returns
    -------
    list[dict]
        Ordered list of recommendation dicts, each with ``strategy``,
        ``block_size``, ``overlap``, ``label``, ``estimated_docs``,
        and ``detail``.
    """
    file_count = scan.file_count
    total_bytes = scan.total_bytes
    avg_bytes = total_bytes / file_count if file_count else 0
    lang_sizes = scan.language_sizes or {}

    CODE_LANGS = {
        "Python",
        "JavaScript",
        "TypeScript",
        "Go",
        "Rust",
        "Java",
        "C",
        "C++",
        "Ruby",
        "Shell",
    }
    DOC_LANGS = {"Markdown", "Text"}
    DATA_LANGS = {"JSON", "YAML"}

    code_count = sum(scan.language_map.get(l, 0) for l in CODE_LANGS)
    doc_count = sum(scan.language_map.get(l, 0) for l in DOC_LANGS)
    data_count = sum(scan.language_map.get(l, 0) for l in DATA_LANGS)

    code_avg = _avg_or_zero(_collect_file_sizes(lang_sizes, CODE_LANGS))
    doc_avg = _avg_or_zero(_collect_file_sizes(lang_sizes, DOC_LANGS))

    is_code_heavy = code_count > doc_count and code_count > data_count
    is_doc_heavy = doc_count > code_count and doc_avg > 5000
    is_data_oriented = data_count > code_count and data_count > doc_count

    recs: list[dict[str, Any]] = []

    is_mixed = sum(1 for c in [code_count > 100, doc_count > 100, data_count > 100]) > 1

    if is_mixed:
        recs.append(
            {
                "strategy": None,
                "block_size": None,
                "overlap": None,
                "label": "Mixed repo — create separate corpora per type for best results",
                "estimated_docs": None,
                "detail": f"{code_count} code files (avg {round(code_avg / 1024, 1) if code_avg else 0}KB), {doc_count} doc files (avg {round(doc_avg / 1024, 1) if doc_avg else 0}KB), {data_count} data files. Use include filters (e.g. `*.py`) to create focused corpora with optimal strategies per type.",
            }
        )

    if is_code_heavy and code_avg < 10240:
        recs.append(
            {
                "strategy": "file",
                "block_size": None,
                "overlap": None,
                "label": f"Code files as one doc each ({code_count} files, avg {round(code_avg / 1024, 1)}KB)",
                "estimated_docs": file_count,
                "detail": "Source files are natural atomic training units. Each file becomes one doc, preserving function and class boundaries.",
            }
        )
    elif is_doc_heavy or (is_code_heavy and code_avg >= 10240):
        recs.append(
            {
                "strategy": "windowed",
                "block_size": 1024,
                "overlap": 0.25,
                "label": f"Large files split into 1KB windows (avg {round(doc_avg / 1024, 1) if is_doc_heavy else round(code_avg / 1024, 1)}KB)",
                "estimated_docs": int(
                    file_count * max(1, (avg_bytes - 1024) / 768 + 1)
                ),
                "detail": "Files are large — split into 1024-char windows with 25% overlap for meaningful context chunks.",
            }
        )

    recs.append(
        {
            "strategy": "file",
            "block_size": None,
            "overlap": None,
            "label": f"Each file as one doc ({file_count} files)",
            "estimated_docs": file_count,
            "detail": "Simplest approach. Best when files are coherent units (code, articles).",
        }
    )

    for bs in (64, 256, 1024):
        overlap = 0.25
        stride = int(bs * (1 - overlap))
        docs_per_file = max(1, (avg_bytes - bs) // stride + 1) if avg_bytes > bs else 1
        estimated_docs = file_count * docs_per_file
        recs.append(
            {
                "strategy": "windowed",
                "block_size": bs,
                "overlap": overlap,
                "label": f"{bs} char windows",
                "estimated_docs": estimated_docs,
                "detail": f"Sliding window, {stride} char stride. Good balance of granularity and doc count.",
            }
        )

    if is_data_oriented or data_count > 0:
        recs.append(
            {
                "strategy": "line",
                "block_size": None,
                "overlap": None,
                "label": f"Line-by-line ({data_count} data files)",
                "estimated_docs": None,
                "detail": "Each non-empty line is a doc. Best for JSONL, logs, CSV where each line is independent.",
            }
        )

    return recs


def _corpus_to_dict(corpus: Any) -> dict[str, Any]:
    """Serialize a corpus ORM object to a plain dict.

    Parameters
    ----------
    corpus : Corpus
        The corpus ORM instance.

    Returns
    -------
    dict
        Serialized corpus with ``id``, ``name``, ``description``,
        ``root_path``, ``chunking_strategy``, ``chunk_overlap``,
        ``block_size``, ``parent_id``, ``file_count``,
        ``document_count``, and ``created_at``. Includes
        ``error_count`` if errors are present.
    """
    d = {
        "id": corpus.id,
        "name": corpus.name,
        "description": corpus.description,
        "root_path": corpus.root_path,
        "chunking_strategy": corpus.chunking_strategy,
        "chunk_overlap": corpus.chunk_overlap,
        "block_size": corpus.block_size,
        "parent_id": corpus.parent_id,
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
