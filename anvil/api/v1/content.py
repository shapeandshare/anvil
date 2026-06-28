# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Content repository management endpoints for v1 API.

Provides REST endpoints for versioned content corpora, ingestion
sessions, version management, and training-data composition.
Endpoints are added in phases per US1-US9.

Envelope
--------
All endpoints return ``{"data": ..., "error": None}`` on success
or raise ``HTTPException`` on error.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from starlette.responses import StreamingResponse

from ...api.deps import get_workbench
from ...db.models.content_source import ContentSource
from ...services.content.ingest_status import IngestStatus
from ...workbench import AnvilWorkbench
from .schemas_content import (
    AcceptOut,
    CompositionSpecItem,
    ContentCorpusCreate,
    ContentCorpusOut,
    ContentVersionOut,
    FreezeVersionBody,
    ImportJobOut,
    ImportStart,
    LockBody,
    LockOut,
    RevertBody,
    SessionOpenBody,
    SessionOut,
    TagBody,
    ValidationReportOut,
)
from .schemas_misc import CreateSourceBody

router = APIRouter()
"""APIRouter: Content repository routes, mounted under
``/v1/content`` via the parent v1 router."""

# Module-level SSE event queue for injection lifecycle events.
# Pushed to by IngestionService.accept() and consumed by the
# ``/content/stream/injection`` SSE endpoint.
_injection_queue: asyncio.Queue[dict[str, str]] = asyncio.Queue(maxsize=128)
"""asyncio.Queue: SSE event queue for injection lifecycle events.

Bounded at 128 entries to prevent unbounded memory growth when the SSE
consumer is disconnected or slow.  When full, new events are silently
dropped — injection events are low-frequency and loss-tolerant.
"""


def _slugify(name: str) -> str:
    """Derive a URL-safe slug from a corpus name."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "corpus"


# ── Corpora ──────────────────────────────────────────────────────────────


@router.post("/content/corpora")
async def create_corpus(
    body: ContentCorpusCreate,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Create a new versioned content corpus.

    Accepts corpus configuration and provenance metadata. Delegates
    to the ``CorpusService`` (T041) via ``workbench.content_corpora``.

    Parameters
    ----------
    body : ContentCorpusCreate
        Corpus creation parameters.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        Corpus data wrapped in ``{"data": ..., "error": None}``.

    Raises
    ------
    HTTPException
        If validation fails (422).
    """
    slug = body.slug or _slugify(body.name)
    try:
        corpus = await workbench.content_corpora.create(
            name=body.name,
            slug=slug,
            description=body.description,
            chunking_strategy=body.chunking_strategy,
            block_size=body.block_size,
            chunk_overlap=body.chunk_overlap,
            source_description=body.declared_source,
            attribution_text=body.attribution,
        )
        await workbench.session.commit()
    except ValueError as exc:
        await workbench.session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "data": _corpus_to_out(corpus).model_dump(),
        "error": None,
    }


@router.get("/content/corpora")
async def list_corpora(
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """List all versioned content corpora.

    Parameters
    ----------
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        List of ``ContentCorpusOut`` dicts and ``"error": None``.
    """
    corpora = await workbench.content_corpus_repo.get_all()
    return {
        "data": [_corpus_to_out(c).model_dump() for c in corpora],
        "error": None,
    }


@router.get("/content/corpora/{corpus_id}")
async def get_corpus(
    corpus_id: int,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Get a single versioned content corpus by ID.

    Parameters
    ----------
    corpus_id : int
        The corpus primary key.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        Corpus data wrapped in ``{"data": ..., "error": None}``.

    Raises
    ------
    HTTPException
        If the corpus is not found (404).
    """
    corpus = await workbench.content_corpus_repo.get(corpus_id)
    if corpus is None:
        raise HTTPException(status_code=404, detail="Corpus not found")
    return {
        "data": _corpus_to_out(corpus).model_dump(),
        "error": None,
    }


@router.delete("/content/corpora/{corpus_id}")
async def delete_corpus(
    corpus_id: int,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Delete a versioned content corpus by ID.

    Parameters
    ----------
    corpus_id : int
        The corpus primary key.
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
    deleted = await workbench.content_corpus_repo.delete(corpus_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Corpus not found")
    await workbench.session.commit()
    return {"data": {"status": "deleted"}, "error": None}


@router.get("/content/corpora/{corpus_id}/versions")
async def list_corpus_versions(
    corpus_id: int,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """List all versions of a content corpus.

    Parameters
    ----------
    corpus_id : int
        The corpus primary key.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        List of ``ContentVersionOut`` dicts and ``"error": None``.
    """
    versions = await workbench.content_version_repo.list_by_corpus(corpus_id)
    return {
        "data": [_version_to_out(v).model_dump() for v in versions],
        "error": None,
    }


# ── Sources ──────────────────────────────────────────────────────────────


@router.post("/content/sources")
async def create_source(
    body: CreateSourceBody,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Create a new content source.

    Parameters
    ----------
    body : CreateSourceBody
        Request body with ``slug``, ``name``, and optional ``kind``.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        Source data wrapped in ``{"data": ..., "error": None}``.

    Raises
    ------
    HTTPException
        If validation fails (422).
    """
    try:
        source = ContentSource(
            slug=body.slug,
            name=body.name,
            kind=body.kind,
        )
        source = await workbench.content_source_repo.add(source)
        await workbench.session.commit()
    except (ValueError, KeyError) as exc:
        await workbench.session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "data": {
            "id": source.id,
            "slug": source.slug,
            "name": source.name,
            "kind": source.kind,
        },
        "error": None,
    }


@router.get("/content/sources")
async def list_sources(
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """List all content sources.

    Parameters
    ----------
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        List of source dicts and ``"error": None``.
    """
    sources = await workbench.content_source_repo.get_all()
    return {
        "data": [
            {
                "id": s.id,
                "slug": s.slug,
                "name": s.name,
                "kind": s.kind,
            }
            for s in sources
        ],
        "error": None,
    }


# ── Sessions ─────────────────────────────────────────────────────────────


@router.post("/content/sessions", responses={404: {"description": "Session not found"}})
async def open_session(
    body: SessionOpenBody,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Open a new ingestion session for a corpus.

    Creates an isolated staging area where content can be uploaded,
    validated, and either accepted or abandoned.

    Parameters
    ----------
    body : SessionOpenBody
        Session open parameters (``corpus_id``, ``source`` slug).
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        ``SessionOut`` data wrapped in ``{"data": ..., "error": None}``.

    Raises
    ------
    HTTPException
        If the corpus or source is not found (404), or if the
        ingestion service rejects the request (422).
    """
    corpus = await workbench.content_corpus_repo.get(body.corpus_id)
    if corpus is None:
        raise HTTPException(status_code=404, detail="Corpus not found")

    source = await workbench.content_source_repo.get_by_slug(body.source)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Source '{body.source}' not found")

    await workbench.content_store.ensure_corpus(corpus.slug)
    try:
        ref = await workbench.content_ingestion.open_session(corpus.id, source.id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await workbench.session.commit()

    session = await workbench.content_ingest_session_repo.get(ref.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "data": SessionOut(
            id=session.id,
            corpus_id=session.corpus_id,
            source_id=session.source_id,
            status=session.status,
            staged_entry_count=session.staged_entry_count,
            problems_json=session.problems_json,
            opened_at=session.opened_at,
        ).model_dump(),
        "error": None,
    }


@router.post("/content/sessions/{session_id}/stage")
async def stage_file(
    session_id: int,
    path: str,
    file: UploadFile,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Stage a file into an open ingestion session.

    Accepts a multipart file upload, stores the content as a
    content-addressed blob, and records the staged entry.

    Parameters
    ----------
    id : int
        The session primary key.
    path : str
        Relative path for the entry within the session.
    file : UploadFile
        The uploaded file content.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        ``StagedEntry`` data wrapped in ``{"data": ..., "error": None}``.

    Raises
    ------
    HTTPException
        If the session is not found (404) or not open (422).
    """
    session = await workbench.content_ingest_session_repo.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status != IngestStatus.OPEN:
        raise HTTPException(
            status_code=422,
            detail=f"Session is not open (status: {session.status})",
        )

    content = await file.read()

    async def _stream() -> AsyncIterator[bytes]:
        yield content

    staged = await workbench.content_ingestion.stage(session_id, path, _stream())
    await workbench.session.commit()

    return {
        "data": {
            "path": staged.path,
            "content_hash": staged.content_hash,
            "size_bytes": staged.size_bytes,
        },
        "error": None,
    }


@router.post("/content/sessions/{session_id}/validate")
async def validate_session(
    session_id: int,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Run validation gates over a session's staged content.

    Parameters
    ----------
    id : int
        The session primary key.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        ``ValidationReportOut`` wrapped in ``{"data": ..., "error": None}``.

    Raises
    ------
    HTTPException
        If the session is not found (404).
    """
    session = await workbench.content_ingest_session_repo.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    report = await workbench.content_ingestion.validate(session_id)
    await workbench.session.commit()

    return {
        "data": ValidationReportOut(
            ok=report.ok,
            problems=[p.model_dump() for p in report.problems],
        ).model_dump(),
        "error": None,
    }


@router.post("/content/sessions/{session_id}/accept")
async def accept_session(
    session_id: int,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Accept staged content and fold it into the canonical corpus.

    Creates a new immutable version containing all staged entries.

    Parameters
    ----------
    id : int
        The session primary key.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        ``AcceptOut`` wrapped in ``{"data": ..., "error": None}``.

    Raises
    ------
    HTTPException
        If the session is not found (404), or if governance gate
        blocks the accept (422).
    """
    session = await workbench.content_ingest_session_repo.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status not in (IngestStatus.OPEN, IngestStatus.VALIDATING):
        raise HTTPException(
            status_code=422,
            detail=f"Cannot accept session in status '{session.status}'",
        )

    try:
        result = await workbench.content_ingestion.accept(session_id)
        await workbench.session.commit()
    except ValueError as exc:
        await workbench.session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Push SSE event for the injection stream.
    # Silently drop if the queue is full (consumer disconnected).
    try:
        _injection_queue.put_nowait(
            {
                "event": "accepted",
                "data": json.dumps(
                    {
                        "session_id": session_id,
                        "version_id": result.version_id,
                        "version_number": result.version_number,
                        "entry_count": result.entry_count,
                    }
                ),
            }
        )
    except asyncio.QueueFull:
        pass

    return {
        "data": AcceptOut(
            version_id=result.version_id,
            manifest_digest=result.manifest_digest,
            version_number=result.version_number,
            entry_count=result.entry_count,
            total_bytes=result.total_bytes,
        ).model_dump(),
        "error": None,
    }


@router.post("/content/sessions/{session_id}/abandon")
async def abandon_session(
    session_id: int,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Abandon an ingestion session without accepting its content.

    Marks the session as failed and discards staged entries.

    Parameters
    ----------
    id : int
        The session primary key.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        Abandon status and ``"error": None``.

    Raises
    ------
    HTTPException
        If the session is not found (404).
    """
    session = await workbench.content_ingest_session_repo.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    await workbench.content_ingest_session_repo.update_status(
        session_id, IngestStatus.FAILED
    )
    await workbench.session.commit()
    return {"data": {"status": "abandoned"}, "error": None}


@router.get("/content/sessions")
async def list_active_sessions(
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """List all active ingestion sessions.

    Parameters
    ----------
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        List of ``SessionOut`` dicts and ``"error": None``.
    """
    sessions = await workbench.content_ingest_session_repo.list_active()
    return {
        "data": [
            SessionOut(
                id=s.id,
                corpus_id=s.corpus_id,
                source_id=s.source_id,
                status=s.status,
                staged_entry_count=s.staged_entry_count,
                problems_json=s.problems_json,
                opened_at=s.opened_at,
            ).model_dump()
            for s in sessions
        ],
        "error": None,
    }


# ── Versions ─────────────────────────────────────────────────────────────


@router.post("/content/corpora/{corpus_id}/freeze")
async def freeze_version(
    corpus_id: int,
    body: FreezeVersionBody | None = None,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Freeze a new immutable version of a corpus.

    When ``body.composition`` is ``None``, snapshots the current HEAD
    content into a new version record.  When *composition* is provided,
    delegates to ``CompositionService.freeze()`` to create a weighted
    composition version.

    Parameters
    ----------
    corpus_id : int
        The corpus primary key.
    body : FreezeVersionBody, optional
        Optional note, label, and composition specification.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        ``ContentVersionOut`` wrapped in ``{"data": ..., "error": None}``.

    Raises
    ------
    HTTPException
        If the corpus is not found (404), or the composition spec
        is invalid (422).
    """
    corpus = await workbench.content_corpus_repo.get(corpus_id)
    if corpus is None:
        raise HTTPException(status_code=404, detail="Corpus not found")

    if body is not None and body.composition is not None:
        # Delegate to CompositionService for weighted composition.
        spec = [
            {"content_hash": item.content_hash, "weight": item.weight}
            for item in body.composition
        ]
        try:
            version = await workbench.content_composition.freeze(corpus_id, spec)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    else:
        version = await workbench.content_store.freeze_version(
            corpus_slug=corpus.slug,
        )

    await workbench.session.commit()

    return {
        "data": ContentVersionOut(
            id=version.version_id,
            corpus_id=corpus_id,
            version_number=version.version_number,
            manifest_digest=version.manifest_digest,
            label=version.label or (body.label if body else None),
            entry_count=0,
            total_bytes=0,
            created_at=datetime.now(UTC),
        ).model_dump(),
        "error": None,
    }


@router.post("/content/corpora/{corpus_id}/composition/preview")
async def composition_preview(
    corpus_id: int,
    entries: list[CompositionSpecItem],
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Preview the token/byte contribution of a composition spec.

    Accepts a list of ``CompositionSpecItem`` dicts and returns a
    per-source breakdown of bytes and estimated tokens for the
    proposed composition.

    Parameters
    ----------
    corpus_id : int
        The corpus primary key.
    entries : list[CompositionSpecItem]
        Composition specification entries.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        Preview data wrapped in ``{"data": ..., "error": None}``.

    Raises
    ------
    HTTPException
        If the corpus is not found (404).
    """
    corpus = await workbench.content_corpus_repo.get(corpus_id)
    if corpus is None:
        raise HTTPException(status_code=404, detail="Corpus not found")

    spec = [
        {"content_hash": item.content_hash, "weight": item.weight} for item in entries
    ]
    try:
        result = await workbench.content_composition.preview(corpus_id, spec)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {"data": result, "error": None}


@router.get("/content/stream/composition")
async def stream_composition(
    _workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> StreamingResponse:
    """SSE event stream for composition preview updates.

    Placeholder endpoint (T073a) — clients connect and receive a
    heartbeat keep-alive every 30 seconds.  Live preview updates
    will be wired when the UI consumer is built (US5 T082a).

    Parameters
    ----------
    _workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    StreamingResponse
        SSE stream with ``text/event-stream`` content type.
    """

    async def event_stream() -> AsyncIterator[str]:
        """Generator that yields SSE heartbeats every 30 seconds."""
        while True:
            await asyncio.sleep(30)
            yield "event: heartbeat\ndata: {}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/content/versions/{version_id}/tag")
async def tag_version(
    version_id: int,
    body: TagBody,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Tag a content version (FR-023).

    Parameters
    ----------
    version_id : int
        The version primary key.
    body : TagBody
        Tag name.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        Tagged version data and ``"error": None``.

    Raises
    ------
    HTTPException
        If the version is not found (404).
    """
    version = await workbench.content_version_repo.get(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")

    try:
        await workbench.content_corpora.tag(version_id, body.name)
        await workbench.session.commit()
    except ValueError as exc:
        await workbench.session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "data": {
            "id": version_id,
            "tag": body.name,
        },
        "error": None,
    }


@router.get("/content/versions/{version_id}")
async def get_version(
    version_id: int,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Get version detail including entries.

    Parameters
    ----------
    version_id : int
        The version primary key.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        Version data with ``entries`` list and ``"error": None``.

    Raises
    ------
    HTTPException
        If the version is not found (404).
    """
    version = await workbench.content_version_repo.get(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")

    entries = await workbench.content_version_repo.get_entries(version_id)

    out = _version_to_out(version).model_dump()
    out["entries"] = [
        {
            "id": e.id,
            "path": e.path,
            "content_hash": e.content_hash,
            "size_bytes": e.size_bytes,
        }
        for e in entries
    ]

    return {"data": out, "error": None}


@router.get("/content/versions/{version_id}/lineage")
async def get_version_lineage(
    version_id: int,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Get version lineage including sources and run refs.

    Returns sources (from the ingestion session that created the
    version) and MLflow run references (from ``VersionRunRef``).

    Parameters
    ----------
    version_id : int
        The version primary key.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        Lineage data with ``sources``, ``run_refs``, and
        ``"error": None``.

    Raises
    ------
    HTTPException
        If the version is not found (404).
    """
    version = await workbench.content_version_repo.get(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")

    run_refs = await workbench.content_version_repo.get_run_refs(version_id)

    # Look up the source that produced this version via the
    # accepted session.
    session = await workbench.content_ingest_session_repo.get_by_accepted_version(
        version_id
    )
    sources: list[dict[str, Any]] = []
    if session is not None and session.source_id is not None:
        source = await workbench.content_source_repo.get(session.source_id)
        if source is not None:
            sources.append(
                {
                    "id": source.id,
                    "slug": source.slug,
                    "name": source.name,
                    "kind": source.kind,
                }
            )

    # Also collect source slugs from entries that have a source_id.
    entries = await workbench.content_version_repo.get_entries(version_id)
    entry_source_ids = {e.source_id for e in entries if e.source_id is not None}
    for src_id in entry_source_ids:
        if src_id not in {s["id"] for s in sources}:
            src = await workbench.content_source_repo.get(src_id)
            if src is not None:
                sources.append(
                    {
                        "id": src.id,
                        "slug": src.slug,
                        "name": src.name,
                        "kind": src.kind,
                    }
                )

    return {
        "data": {
            "version_id": version_id,
            "sources": sources,
            "run_refs": [
                {
                    "mlflow_run_id": r.mlflow_run_id,
                    "corpus_ref": r.corpus_ref,
                }
                for r in run_refs
            ],
        },
        "error": None,
    }


# ── Injection SSE stream ────────────────────────────────────────────────


@router.get("/content/stream/injection")
async def injection_event_stream(
    _workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> StreamingResponse:
    """SSE event stream for ingestion session lifecycle events.

    Pushes real-time ``accepted`` events when an ingestion session is
    accepted, with the ``session_id`` and ``version_id`` in the event
    data.  A heartbeat is sent every 30 seconds to keep the connection
    alive.

    Parameters
    ----------
    _workbench : AnvilWorkbench
        Injected session-bound workbench (unused placeholder).

    Returns
    -------
    StreamingResponse
        SSE stream with ``text/event-stream`` content type.
    """

    async def event_stream() -> AsyncIterator[str]:
        """Generator that yields SSE events from ``_injection_queue``
        or heartbeats every 30 seconds.
        """
        while True:
            try:
                msg = await asyncio.wait_for(_injection_queue.get(), timeout=30)
                yield f"event: {msg['event']}\ndata: {msg['data']}\n\n"
            except TimeoutError:
                yield "event: heartbeat\ndata: {}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Revert ───────────────────────────────────────────────────────────────


@router.post("/content/corpora/{corpus_id}/revert")
async def revert_corpus(
    corpus_id: int,
    body: RevertBody,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Revert a corpus to a prior version.

    Creates a new HEAD that is a copy of the target version.

    Parameters
    ----------
    corpus_id : int
        The corpus primary key.
    body : RevertBody
        Revert parameters including ``to_version_id``.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        Revert status and ``"error": None``.

    Raises
    ------
    HTTPException
        If the corpus or target version is not found (404), or if
        the target version belongs to a different corpus (422).
    """
    corpus = await workbench.content_corpus_repo.get(corpus_id)
    if corpus is None:
        raise HTTPException(status_code=404, detail="Corpus not found")

    target = await workbench.content_version_repo.get(body.to_version_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Target version not found")
    if target.corpus_id != corpus_id:
        raise HTTPException(
            status_code=422,
            detail="Target version does not belong to this corpus",
        )

    target_version_number = target.version_number
    try:
        ref = await workbench.content_corpora.revert(corpus_id, body.to_version_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "data": {
            "status": "reverted",
            "new_version_id": ref.version_id,
            "version_number": ref.version_number,
            "reverted_to_version": target_version_number,
        },
        "error": None,
    }


# ── Locking ──────────────────────────────────────────────────────────────


@router.post("/content/locks")
async def acquire_lock(
    body: LockBody,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Acquire an advisory content lock.

    Parameters
    ----------
    body : LockBody
        Lock parameters (``scope``, ``holder``).
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        ``LockOut`` data wrapped in ``{"data": ..., "error": None}``.

    Raises
    ------
    HTTPException
        If the lock cannot be acquired (409).
    """
    # Check for existing active lock on this scope
    existing = await workbench.content_locks.list_active()
    for lock in existing:
        if lock.scope == body.scope:
            raise HTTPException(
                status_code=409,
                detail=f"Lock already held on scope '{body.scope}' by '{lock.holder}'",
            )

    new_lock = await workbench.content_locks.acquire(body.scope, body.holder)
    await workbench.session.commit()

    return {
        "data": LockOut(
            id=new_lock.id,
            scope=new_lock.scope,
            holder=new_lock.holder,
            state=new_lock.state,
            acquired_at=new_lock.acquired_at,
            released_at=new_lock.released_at,
        ).model_dump(),
        "error": None,
    }


@router.post("/content/locks/{lock_id}/release")
async def release_lock(
    lock_id: int,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Release an advisory content lock.

    Parameters
    ----------
    lock_id : int
        The lock primary key.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        Release status and ``"error": None``.

    Raises
    ------
    HTTPException
        If the lock is not found (404).
    """
    lock = await workbench.content_lock_repo.get(lock_id)
    if lock is None:
        raise HTTPException(status_code=404, detail="Lock not found")

    await workbench.content_locks.release(lock_id)
    await workbench.session.commit()
    return {"data": {"status": "released"}, "error": None}


@router.get("/content/locks")
async def list_locks(
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """List all active advisory content locks.

    Parameters
    ----------
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        List of ``LockOut`` dicts and ``"error": None``.
    """
    locks = await workbench.content_locks.list_active()
    return {
        "data": [
            LockOut(
                id=lock.id,
                scope=lock.scope,
                holder=lock.holder,
                state=lock.state,
                acquired_at=lock.acquired_at,
                released_at=lock.released_at,
            ).model_dump()
            for lock in locks
        ],
        "error": None,
    }


@router.get("/content/stream/locks")
async def stream_locks(
    _workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> StreamingResponse:
    """SSE event stream for lock lifecycle notifications.

    Placeholder endpoint (US7) — clients connect and receive a
    heartbeat keep-alive every 30 seconds.  Live lock acquire/release
    events will be wired when the UI consumer is built.

    Parameters
    ----------
    _workbench : AnvilWorkbench
        Injected session-bound workbench (unused placeholder).

    Returns
    -------
    StreamingResponse
        SSE stream with ``text/event-stream`` content type.
    """

    async def event_stream() -> AsyncIterator[str]:
        """Generator that yields SSE heartbeats every 30 seconds."""
        while True:
            await asyncio.sleep(30)
            yield "event: heartbeat\ndata: {}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Import jobs (US6) ────────────────────────────────────────────────────


@router.post("/content/imports")
async def start_import(
    body: ImportStart,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Start a new declarative content import job.

    Opens an ingestion session through the ``IngestionService`` on
    behalf of the import job and persists a new ``ImportJob`` record.
    The caller can later stage content through the job's linked
    session, run validation gates, and accept or abandon the session.

    Parameters
    ----------
    body : ImportStart
        Import start parameters (``corpus_id``, ``source`` slug,
        ``config`` dict).
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        ``ImportJobOut`` data wrapped in ``{"data": ..., "error": None}``.

    Raises
    ------
    HTTPException
        If the source or corpus is not found (404 / 422).
    """
    try:
        job = await workbench.content_imports.start(
            corpus_id=body.corpus_id,
            source_slug=body.source,
            config=body.config,
        )
        await workbench.session.commit()
    except ValueError as exc:
        await workbench.session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "data": _import_job_to_out(job).model_dump(),
        "error": None,
    }


@router.get("/content/imports")
async def list_import_jobs(
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, Any]:
    """List all import jobs ordered by creation time (newest first).

    Parameters
    ----------
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        List of ``ImportJobOut`` records wrapped in
        ``{"data": ..., "error": None}``.
    """
    jobs = await workbench.content_imports.list()
    return {
        "data": [_import_job_to_out(j).model_dump() for j in jobs],
        "error": None,
    }


@router.get("/content/imports/{job_id}")
async def get_import_job(
    job_id: int,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Get the current status of an import job.

    Parameters
    ----------
    job_id : int
        The import job primary key.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        ``ImportJobOut`` data wrapped in ``{"data": ..., "error": None}``.

    Raises
    ------
    HTTPException
        If the job is not found (404).
    """
    job = await workbench.content_imports.status(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Import job not found")

    return {
        "data": _import_job_to_out(job).model_dump(),
        "error": None,
    }


@router.get("/content/stream/import")
async def stream_import(
    _workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> StreamingResponse:
    """SSE event stream for import job progress updates.

    Placeholder endpoint (US6) — clients connect and receive a
    heartbeat keep-alive every 30 seconds.  Live import progress
    events will be wired in a future US when the UI consumer is
    built.

    Parameters
    ----------
    _workbench : AnvilWorkbench
        Injected session-bound workbench (unused placeholder).

    Returns
    -------
    StreamingResponse
        SSE stream with ``text/event-stream`` content type.
    """

    async def event_stream() -> AsyncIterator[str]:
        """Generator that yields SSE heartbeats every 30 seconds."""
        while True:
            await asyncio.sleep(30)
            yield "event: heartbeat\ndata: {}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Helpers ──────────────────────────────────────────────────────────────


def _corpus_to_out(corpus: Any) -> ContentCorpusOut:
    """Convert a ``ContentCorpus`` ORM instance to a ``ContentCorpusOut``
    schema.

    Parameters
    ----------
    corpus : ContentCorpus
        The ORM instance to convert.

    Returns
    -------
    ContentCorpusOut
        The API output schema.
    """
    return ContentCorpusOut(
        id=corpus.id,
        slug=corpus.slug,
        name=corpus.name,
        description=corpus.description,
        chunking_strategy=corpus.chunking_strategy,
        block_size=corpus.block_size,
        chunk_overlap=corpus.chunk_overlap,
        status=corpus.status,
        file_count=getattr(corpus, "file_count", 0),
        document_count=getattr(corpus, "document_count", 0),
        created_at=corpus.created_at,
    )


def _version_to_out(version: Any) -> ContentVersionOut:
    """Convert a ``ContentVersion`` ORM instance to a
    ``ContentVersionOut`` schema.

    Parameters
    ----------
    version : ContentVersion
        The ORM instance to convert.

    Returns
    -------
    ContentVersionOut
        The API output schema.
    """
    return ContentVersionOut(
        id=version.id,
        corpus_id=version.corpus_id,
        version_number=version.version_number,
        manifest_digest=version.manifest_digest,
        label=version.label,
        entry_count=version.entry_count,
        total_bytes=version.total_bytes,
        tag=version.label,
        created_at=version.created_at,
    )


def _import_job_to_out(job: Any) -> ImportJobOut:
    """Convert an ``ImportJob`` ORM instance to an ``ImportJobOut``
    schema.

    Parameters
    ----------
    job : ImportJob
        The ORM instance to convert.

    Returns
    -------
    ImportJobOut
        The API output schema.
    """
    return ImportJobOut(
        id=job.id,
        corpus_id=job.corpus_id,
        source_id=job.source_id,
        config_json=job.config_json,
        status=job.status,
        session_id=job.session_id,
        message=job.message,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )
