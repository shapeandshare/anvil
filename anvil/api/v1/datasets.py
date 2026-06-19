"""Dataset management endpoints for v1 API.

Provides CRUD, import, export, curation, and cloning operations for training
datasets. Supports multiple import formats (txt, csv, jsonl), curation
operations (dedup, filter, regex replace), and export to standard formats.
"""

import asyncio
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.responses import StreamingResponse

from anvil.api.deps import get_db_session
from anvil.api.v1.schemas import (
    CloneDatasetBody,
    CreateDatasetBody,
    CreateFromCorpusBody,
    FilterBody,
    ImportBody,
    ReplaceBody,
    UpdateDatasetBody,
    UpdateSampleBody,
)
from anvil.db.models.curation_operation import CurationOperation as CurationOpModel
from anvil.db.models.dataset import Dataset
from anvil.db.repositories.corpora import CorpusRepository
from anvil.db.repositories.curation import SampleRepository
from anvil.db.repositories.curation_operation_repository import (
    CurationOperationRepository,
)
from anvil.db.repositories.datasets import DatasetRepository
from anvil.services.corpora import CorpusService
from anvil.services.corpus_loader import CorpusLoader
from anvil.services.dataset_curation import DatasetCurationService
from anvil.services.dataset_export import DatasetExportService
from anvil.services.dataset_import import DatasetImportService
from anvil.services.datasets import DatasetService
from anvil.services.tracking import TrackingService
from anvil.storage.local import LocalFileStore

router = APIRouter()
tracking_svc = TrackingService()


async def get_service(session: AsyncSession = Depends(get_db_session)):
    """FastAPI dependency providing a configured ``DatasetService``.

    Parameters
    ----------
    session : AsyncSession
        An async SQLAlchemy session, injected by FastAPI.

    Returns
    -------
    DatasetService
        A service instance wired to a ``DatasetRepository``.
    """
    repo = DatasetRepository(session)
    return DatasetService(repo)


@router.get("/datasets/{id}/curate")
async def curate_dataset_page(
    id: int,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """Render the dataset curation page.

    Parameters
    ----------
    id : int
        The dataset ID.
    request : Request
        The incoming HTTP request.
    session : AsyncSession
        Injected database session.

    Returns
    -------
    TemplateResponse
        The rendered ``dataset_curation.html`` template.

    Raises
    ------
    HTTPException
        If the dataset is not found (404).
    """
    repo = DatasetRepository(session)
    dataset = await repo.get(id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return request.app.state.templates.TemplateResponse(
        request,
        "dataset_curation.html",
        {"dataset": _serialize(dataset)},
    )


def _serialize(d: Dataset) -> dict:
    """Serialize a dataset ORM object to a plain dict.

    Parameters
    ----------
    d : Dataset
        The dataset ORM instance.

    Returns
    -------
    dict
        Serialized dataset with ``id``, ``name``, ``description``,
        ``filename``, ``sample_count``, ``total_size_bytes``, ``status``,
        ``curation_version``, ``vocabulary_size``, ``document_count``,
        ``created_at``, and ``updated_at``.
    """
    return {
        "id": d.id,
        "name": d.name,
        "description": d.description,
        "filename": d.filename,
        "sample_count": d.sample_count,
        "total_size_bytes": d.total_size_bytes,
        "status": d.status,
        "curation_version": d.curation_version,
        "vocabulary_size": d.vocabulary_size,
        "document_count": d.document_count,
        "created_at": str(d.created_at),
        "updated_at": str(d.updated_at),
    }


@router.get("/datasets")
async def list_datasets(
    svc: DatasetService = Depends(get_service),
    q: str | None = Query(None, description="Search datasets by name"),
):
    """List all datasets, optionally filtered by search query.

    Parameters
    ----------
    svc : DatasetService
        Injected dataset service.
    q : str | None, optional
        Search query to filter datasets by name.

    Returns
    -------
    dict
        List of serialized datasets and ``"error": None``.
    """
    if q:
        datasets = await svc.search_datasets(q)
    else:
        datasets = await svc.list_datasets()
    return {"data": {"datasets": [_serialize(d) for d in datasets]}, "error": None}


@router.get("/datasets/{id}")
async def get_dataset(id: int, svc: DatasetService = Depends(get_service)):
    """Get a single dataset by ID.

    Parameters
    ----------
    id : int
        The dataset ID.
    svc : DatasetService
        Injected dataset service.

    Returns
    -------
    dict
        Serialized dataset data and ``"error": None``.

    Raises
    ------
    HTTPException
        If the dataset is not found (404).
    """
    d = await svc.get_dataset(id)
    if d is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return {"data": _serialize(d), "error": None}


@router.post("/datasets")
async def create_dataset(
    body: CreateDatasetBody,
    svc: DatasetService = Depends(get_service),
):
    """Create a new empty dataset.

    Parameters
    ----------
    body : CreateDatasetBody
        Request body with ``name`` and optional ``description``.
    svc : DatasetService
        Injected dataset service.

    Returns
    -------
    dict
        Serialized new dataset and ``"error": None``.

    Raises
    ------
    HTTPException
        If the name is empty (422).
    """
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="Dataset name must not be empty")
    dataset = await svc.create_dataset(body.name.strip(), body.description)
    return {"data": _serialize(dataset), "error": None}


@router.put("/datasets/{id}")
async def update_dataset(
    id: int,
    body: UpdateDatasetBody,
    svc: DatasetService = Depends(get_service),
):
    """Update an existing dataset's name and/or description.

    Parameters
    ----------
    id : int
        The dataset ID.
    body : UpdateDatasetBody
        Request body with optional ``name`` and ``description``.
    svc : DatasetService
        Injected dataset service.

    Returns
    -------
    dict
        Serialized updated dataset and ``"error": None``.

    Raises
    ------
    HTTPException
        If the dataset is not found (404).
    """
    d = await svc.update_dataset(id, name=body.name, description=body.description)
    if d is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return {"data": _serialize(d), "error": None}


@router.post("/datasets/upload")
async def upload_dataset(
    file: UploadFile,
    session: AsyncSession = Depends(get_db_session),
):
    """Upload a dataset file and create a dataset record.

    Reads the uploaded file as UTF-8 text, counts lines and vocabulary size,
    and creates a dataset. Also logs a lifecycle event via ``TrackingService``.

    Parameters
    ----------
    file : UploadFile
        The uploaded file.
    session : AsyncSession
        Injected database session.

    Returns
    -------
    dict
        Serialized new dataset and ``"error": None``.
    """
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

    # Track dataset creation in MLflow
    try:
        if not tracking_svc.is_degraded:
            await tracking_svc.log_dataset_lifecycle_event(
                dataset_id=dataset.id,
                event_type="create",
                params={
                    "name": dataset.name,
                    "vocabulary_size": dataset.vocabulary_size,
                    "sample_count": dataset.sample_count,
                    "total_size_bytes": dataset.total_size_bytes,
                },
            )
    except Exception:
        pass

    return {"data": _serialize(dataset), "error": None}


@router.delete("/datasets/{id}")
async def delete_dataset(
    id: int,
    svc: DatasetService = Depends(get_service),
    force: bool = Query(False, description="Force delete demo dataset"),
):
    """Delete a dataset by ID.

    Protects demo datasets from accidental deletion unless ``force=true``.
    Also logs a lifecycle event via ``TrackingService``.

    Parameters
    ----------
    id : int
        The dataset ID.
    svc : DatasetService
        Injected dataset service.
    force : bool, optional
        Force deletion of demo-protected datasets. Defaults to ``False``.

    Returns
    -------
    dict
        Deletion confirmation message and ``"error": None``.

    Raises
    ------
    HTTPException
        If the dataset is not found (404) or is demo-protected (409).
    """
    ds = await svc.get_dataset(id)
    if ds is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if ds.name.startswith("Demo - ") and not force:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Dataset '{ds.name}' is a bundled demo dataset. "
                "Deleting it will free the name for re-import via 'anvil bootstrap-datasets'. "
                "Set force=true to confirm deletion."
            ),
        )
    try:
        await svc.delete_dataset(id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    try:
        if not tracking_svc.is_degraded:
            await tracking_svc.log_dataset_lifecycle_event(
                dataset_id=id,
                event_type="delete",
            )
    except Exception:
        pass

    return {"data": {"message": "Dataset deleted"}, "error": None}


@router.post("/datasets/{id}/clone")
async def clone_dataset(
    id: int,
    body: CloneDatasetBody,
    session: AsyncSession = Depends(get_db_session),
):
    """Clone an existing dataset into a new dataset.

    POST /datasets/{id}/clone

    Copies all active samples from the source dataset into a newly created
    dataset. Validates that the source dataset exists, has samples to clone,
    and that the new name does not already exist.

    Parameters
    ----------
    id : int
        The source dataset ID to clone.
    body : CloneDatasetBody
        Request body with ``name`` for the new dataset and optional ``description``.
    session : AsyncSession
        Injected database session.

    Returns
    -------
    dict
        Serialized new cloned dataset and ``"error": None``.

    Raises
    ------
    HTTPException
        If the source dataset is not found (404), has no samples (422),
        the new name is empty (422), or the new name already exists (422).
    """
    ds_repo = DatasetRepository(session)
    source = await ds_repo.get(id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source dataset not found")

    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Dataset name must not be empty")
    if await ds_repo.get_by_name(name):
        raise HTTPException(
            status_code=422,
            detail=f"Dataset name '{name}' already exists",
        )

    sample_repo = SampleRepository(session)
    source_samples = await sample_repo.get_active_texts(id)
    if not source_samples:
        raise HTTPException(
            status_code=422,
            detail="Source dataset has no active samples to clone",
        )

    store = LocalFileStore("data/datasets")

    docs = []
    for sample in source_samples:
        text_bytes = b""
        async for chunk in store.get(sample.file_path):
            text_bytes += chunk
        docs.append(text_bytes.decode("utf-8"))

    ds_svc = DatasetService(ds_repo)
    new_dataset = await ds_svc.create_dataset(
        name=name,
        description=body.description or source.description,
    )

    import_svc = DatasetImportService(session, new_dataset.id, store)
    await import_svc.commit_docs_import(
        docs=docs,
        source_label=f"clone:dataset-{id}",
        source_format="clone",
    )

    await session.refresh(new_dataset)

    try:
        if not tracking_svc.is_degraded:
            await tracking_svc.log_dataset_lifecycle_event(
                dataset_id=new_dataset.id,
                event_type="create",
                params={"name": new_dataset.name, "cloned_from": id},
            )
    except Exception:
        pass

    return {"data": _serialize(new_dataset), "error": None}


@router.post("/datasets/{id}/import")
async def import_dataset(
    id: int,
    body: ImportBody,
    session: AsyncSession = Depends(get_db_session),
):
    """Import raw text into an existing dataset.

    POST /datasets/{id}/import

    Accepts raw text content and a format specifier, then commits the import
    to the specified dataset. Logs an import lifecycle event via ``TrackingService``.

    Parameters
    ----------
    id : int
        The target dataset ID.
    body : ImportBody
        Request body with ``format`` (e.g. ``"txt"``, ``"csv"``, ``"jsonl"``)
        and ``text`` content to import.
    session : AsyncSession
        Injected database session.

    Returns
    -------
    dict
        Import result with ``import_source_id``, ``rows_imported``,
        ``errors``, and ``preview``, plus ``"error": None``.

    Raises
    ------
    HTTPException
        If the dataset is not found (404) or the import fails (404).
    """
    svc = DatasetImportService(session, id)
    try:
        result = await svc.commit_import(body.text, body.format)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        if not tracking_svc.is_degraded:
            await tracking_svc.log_dataset_lifecycle_event(
                dataset_id=id,
                event_type="import",
                params={"format": body.format},
            )
    except Exception:
        pass

    return {
        "data": {
            "import_source_id": result.import_source_id,
            "rows_imported": result.rows_imported,
            "errors": result.errors,
            "preview": result.preview,
        },
        "error": None,
    }


@router.post("/datasets/{id}/import-corpus")
async def import_dataset_from_corpus(
    id: int,
    body: dict,
    session: AsyncSession = Depends(get_db_session),
):
    """Import documents from a corpus into an existing dataset.

    POST /datasets/{id}/import-corpus

    Loads documents from a specified corpus and imports them into the target
    dataset. The corpus must exist and contain loadable documents.

    Parameters
    ----------
    id : int
        The target dataset ID.
    body : dict
        Request body with ``corpus_id`` specifying the source corpus.
    session : AsyncSession
        Injected database session.

    Returns
    -------
    dict
        Import result with ``import_source_id``, ``rows_imported``, and
        ``errors``, plus ``"error": None``.

    Raises
    ------
    HTTPException
        If ``corpus_id`` is missing (422), the corpus is not found (404),
        or loading fails (404).
    """
    corpus_id = body.get("corpus_id")
    if not corpus_id:
        raise HTTPException(status_code=422, detail="corpus_id required")
    repo = CorpusRepository(session)
    loader = CorpusLoader()
    svc = CorpusService(repo, loader)
    try:
        docs = await svc.load_docs(corpus_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    import_svc = DatasetImportService(session, id)
    result = await import_svc.commit_corpus_import(docs)
    return {
        "data": {
            "import_source_id": result.import_source_id,
            "rows_imported": result.rows_imported,
            "errors": result.errors,
        },
        "error": None,
    }


@router.post("/datasets/from-corpus")
async def create_dataset_from_corpus(
    body: CreateFromCorpusBody,
    session: AsyncSession = Depends(get_db_session),
):
    """Create a new dataset by ingesting and chunking content from a corpus.

    POST /datasets/from-corpus

    Loads files from a corpus, applies the specified chunking strategy
    (windowed, file, or line), and creates a new dataset with the resulting
    chunks. Validates chunking parameters and corpus existence.

    Parameters
    ----------
    body : CreateFromCorpusBody
        Request body with ``corpus_id``, ``name``, optional ``description``,
        ``chunking_strategy`` (``"windowed"``, ``"file"``, or ``"line"``),
        optional ``block_size`` (required for ``"windowed"``), and
        ``chunk_overlap``.
    session : AsyncSession
        Injected database session.

    Returns
    -------
    dict
        Serialized newly created dataset and ``"error": None``.

    Raises
    ------
    HTTPException
        If the corpus is not found (404), the dataset name is empty (422),
        the name already exists (422), ``block_size`` is missing for
        windowed chunking (422), or the chunking strategy is unsupported (422).
    """
    corpus_repo = CorpusRepository(session)
    corpus = await corpus_repo.get(body.corpus_id)
    if corpus is None:
        raise HTTPException(status_code=404, detail="Corpus not found")

    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Dataset name must not be empty")
    ds_repo = DatasetRepository(session)
    if await ds_repo.get_by_name(name):
        raise HTTPException(
            status_code=422,
            detail=f"Dataset name '{name}' already exists",
        )

    if body.chunking_strategy == "windowed" and body.block_size is None:
        raise HTTPException(
            status_code=422,
            detail="block_size is required when chunking_strategy is 'windowed'",
        )
    if body.chunking_strategy not in ("line", "windowed", "file"):
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported chunking strategy: {body.chunking_strategy}",
        )

    inc = json.loads(corpus.include_patterns) if corpus.include_patterns else None
    exc = json.loads(corpus.exclude_patterns) if corpus.exclude_patterns else None

    loader = CorpusLoader()
    load_result = loader.ingest(
        root_path=corpus.root_path,
        include_patterns=inc,
        exclude_patterns=exc,
        chunking_strategy=body.chunking_strategy,
        chunk_overlap=body.chunk_overlap,
        block_size=body.block_size,
    )

    docs = []
    for f in load_result.files:
        file_path = f["relative_path"]
        full_path = corpus.root_path.rstrip("/") + "/" + file_path.lstrip("/")
        try:
            text = await asyncio.to_thread(
                lambda full_path=full_path: open(full_path, encoding="utf-8").read()
            )
        except (FileNotFoundError, UnicodeDecodeError):
            continue

        if body.chunking_strategy == "line":
            for line in text.splitlines():
                stripped = line.strip()
                if stripped:
                    docs.append(stripped)
        elif body.chunking_strategy == "file":
            docs.append(text)
        else:
            from anvil.services.chunking.window_chunker import FixedSizeWindowChunker

            bs = body.block_size  # validated non-None for windowed above
            assert bs is not None
            chunker = FixedSizeWindowChunker(
                block_size=bs,
                overlap=body.chunk_overlap,
            )
            for chunk in chunker.chunk(text):
                docs.append(chunk)

    ds_svc = DatasetService(ds_repo)
    new_dataset = await ds_svc.create_dataset(
        name=name,
        description=body.description or f"Re-chunked from corpus '{corpus.name}'",
    )

    import_svc = DatasetImportService(session, new_dataset.id)
    await import_svc.commit_docs_import(
        docs=docs,
        source_label=f"corpus:{body.corpus_id}",
        source_format="docs",
    )

    await session.refresh(new_dataset)

    try:
        if not tracking_svc.is_degraded:
            await tracking_svc.log_dataset_lifecycle_event(
                dataset_id=new_dataset.id,
                event_type="create",
                params={
                    "name": new_dataset.name,
                    "source": "corpus",
                    "corpus_id": body.corpus_id,
                },
            )
    except Exception:
        pass

    return {"data": _serialize(new_dataset), "error": None}


@router.get("/datasets/{id}/preview-import")
async def preview_import(
    id: int,
    format: str = Query(...),
    text: str = Query(...),
    session: AsyncSession = Depends(get_db_session),
):
    """Preview how text content will be parsed before actual import.

    GET /datasets/{id}/preview-import

    Returns a preview of parsed results and any errors that would occur
    when importing the given text with the specified format.

    Parameters
    ----------
    id : int
        The dataset ID (used for service construction).
    format : str
        Import format to preview (e.g. ``"txt"``, ``"csv"``, ``"jsonl"``).
    text : str
        Raw text content to preview.
    session : AsyncSession
        Injected database session.

    Returns
    -------
    dict
        Preview of parsed results with ``preview`` and ``errors`` lists,
        plus ``"error": None``.
    """
    svc = DatasetImportService(session, id)
    preview, errors = await svc.preview_import(text, format)
    return {"data": {"preview": preview, "errors": errors}, "error": None}


@router.get("/datasets/{id}/samples")
async def list_samples(
    id: int,
    offset: int = Query(0),
    limit: int = Query(50),
    search: str | None = Query(None),
    session: AsyncSession = Depends(get_db_session),
):
    """List samples for a dataset with pagination and search.

    GET /datasets/{id}/samples

    Returns a paginated list of active samples for the specified dataset.
    Each sample includes a text preview (first 200 characters), length,
    and content hash.

    Parameters
    ----------
    id : int
        The dataset ID.
    offset : int, optional
        Number of samples to skip. Defaults to ``0``.
    limit : int, optional
        Maximum samples to return. Defaults to ``50``.
    search : str | None, optional
        Optional search string to filter samples.
    session : AsyncSession
        Injected database session.

    Returns
    -------
    dict
        List of sample objects with ``id``, ``index``, ``text_preview``,
        ``length``, ``content_hash``, plus ``total``, ``offset``, ``limit``,
        and ``"error": None``.
    """
    repo = SampleRepository(session)
    samples, total = await repo.get_active_by_dataset(id, offset, limit, search)
    store = LocalFileStore("data/datasets")
    result = []
    for s in samples:
        text_bytes = b""
        async for chunk in store.get(s.file_path):
            text_bytes += chunk
            if len(text_bytes) >= 200:
                break
        text_preview = text_bytes.decode("utf-8")[:200]
        result.append(
            {
                "id": s.id,
                "index": s.index,
                "text_preview": text_preview,
                "length": s.length,
                "content_hash": s.content_hash,
            }
        )
    return {
        "data": {"samples": result, "total": total, "offset": offset, "limit": limit},
        "error": None,
    }


@router.put("/datasets/{id}/samples/{sample_id}")
async def update_sample(
    id: int,
    sample_id: int,
    body: UpdateSampleBody,
    session: AsyncSession = Depends(get_db_session),
):
    """Update the text content of a single dataset sample.

    PUT /datasets/{id}/samples/{sample_id}

    Replaces the content of an existing sample with new text, updates its
    length and content hash, and records an individual edit curation operation.

    Parameters
    ----------
    id : int
        The dataset ID.
    sample_id : int
        The sample ID to update.
    body : UpdateSampleBody
        Request body with new ``text`` content.
    session : AsyncSession
        Injected database session.

    Returns
    -------
    dict
        Updated sample info with ``sample_id`` and ``length``, plus
        ``"error": None``.

    Raises
    ------
    HTTPException
        If the sample is not found (404) or does not belong to the dataset.
    """
    repo = SampleRepository(session)
    sample = await repo.get(sample_id)
    if sample is None or sample.dataset_id != id:
        raise HTTPException(status_code=404, detail="Sample not found")

    store = LocalFileStore("data/datasets")

    async def _text_stream(text: str):
        """Convert string to UTF-8 byte chunks for storage.

        Parameters
        ----------
        text : str
            The text content to encode.

        Yields
        ------
        bytes
            UTF-8 encoded chunks of the input text.
        """
        yield text.encode("utf-8")

    await store.put(sample.file_path, _text_stream(body.text))
    sample.length = len(body.text)
    sample.content_hash = hashlib.sha256(body.text.encode("utf-8")).hexdigest()

    op_repo = CurationOperationRepository(session)
    op = CurationOpModel(
        dataset_id=id,
        operation_type="individual_edit",
        parameters=None,
        sample_count_before=0,
        sample_count_after=0,
    )
    await op_repo.add(op)
    await session.commit()

    return {"data": {"sample_id": sample.id, "length": sample.length}, "error": None}


@router.delete("/datasets/{id}/samples/{sample_id}")
async def delete_dataset_sample(
    id: int,
    sample_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """Delete a single sample from a dataset.

    DELETE /datasets/{id}/samples/{sample_id}

    Removes the specified sample from the dataset via the curation service.

    Parameters
    ----------
    id : int
        The dataset ID.
    sample_id : int
        The sample ID to delete.
    session : AsyncSession
        Injected database session.

    Returns
    -------
    dict
        Confirmation message and ``"error": None``.

    Raises
    ------
    HTTPException
        If the sample is not found (404).
    """
    svc = DatasetCurationService(session, id)
    try:
        await svc.delete_sample(sample_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    await session.commit()
    return {"data": {"message": "Sample removed"}, "error": None}


@router.post("/datasets/{id}/curate/dedup")
async def curate_dedup(
    id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """Remove duplicate samples from a dataset.

    POST /datasets/{id}/curate/dedup

    Deduplicates samples in the dataset based on content hash, removing
    exact duplicates. Logs a curation event via ``TrackingService``.

    Parameters
    ----------
    id : int
        The dataset ID.
    session : AsyncSession
        Injected database session.

    Returns
    -------
    dict
        Deduplication result with ``operation_id``, ``samples_removed``,
        ``samples_before``, ``samples_after``, and ``"error": None``.

    Raises
    ------
    HTTPException
        If the dataset is not found (404).
    """
    svc = DatasetCurationService(session, id)
    try:
        result = await svc.deduplicate()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    await session.commit()

    try:
        if not tracking_svc.is_degraded:
            await tracking_svc.log_dataset_lifecycle_event(
                dataset_id=id,
                event_type="curate",
                params={"operation": "dedup", "removed_count": result.samples_removed},
            )
    except Exception:
        pass

    return {
        "data": {
            "operation_id": result.operation_id,
            "samples_removed": result.samples_removed,
            "samples_before": result.samples_before,
            "samples_after": result.samples_after,
        },
        "error": None,
    }


@router.post("/datasets/{id}/curate/filter")
async def curate_filter(
    id: int,
    body: FilterBody,
    session: AsyncSession = Depends(get_db_session),
):
    """Filter dataset samples by length constraints.

    POST /datasets/{id}/curate/filter

    Removes samples that fall outside the specified minimum and/or maximum
    length bounds. Logs a curation event via ``TrackingService``.

    Parameters
    ----------
    id : int
        The dataset ID.
    body : FilterBody
        Request body with optional ``min_length`` and ``max_length``
        character bounds.
    session : AsyncSession
        Injected database session.

    Returns
    -------
    dict
        Filter result with ``operation_id``, ``samples_removed``,
        ``samples_before``, ``samples_after``, and ``"error": None``.

    Raises
    ------
    HTTPException
        If the dataset is not found (404).
    """
    svc = DatasetCurationService(session, id)
    try:
        result = await svc.filter_by_length(body.min_length, body.max_length)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    await session.commit()

    try:
        if not tracking_svc.is_degraded:
            await tracking_svc.log_dataset_lifecycle_event(
                dataset_id=id,
                event_type="curate",
                params={"operation": "filter", "removed_count": result.samples_removed},
            )
    except Exception:
        pass

    return {
        "data": {
            "operation_id": result.operation_id,
            "samples_removed": result.samples_removed,
            "samples_before": result.samples_before,
            "samples_after": result.samples_after,
        },
        "error": None,
    }


@router.post("/datasets/{id}/curate/replace")
async def curate_replace(
    id: int,
    body: ReplaceBody,
    session: AsyncSession = Depends(get_db_session),
):
    """Apply regex replacement across all dataset samples.

    POST /datasets/{id}/curate/replace

    Matches the specified regex pattern across all samples and replaces
    matches with the given replacement string. Logs a curation event via
    ``TrackingService``.

    Parameters
    ----------
    id : int
        The dataset ID.
    body : ReplaceBody
        Request body with ``pattern`` (regex), ``replacement`` string,
        and optional ``case_sensitive`` flag.
    session : AsyncSession
        Injected database session.

    Returns
    -------
    dict
        Replace result with ``operation_id``, ``samples_affected``,
        ``samples_before``, ``samples_after``, and ``"error": None``.

    Raises
    ------
    HTTPException
        If the dataset is not found (404).
    """
    svc = DatasetCurationService(session, id)
    try:
        result = await svc.regex_replace(
            body.pattern, body.replacement, body.case_sensitive
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    await session.commit()

    try:
        if not tracking_svc.is_degraded:
            await tracking_svc.log_dataset_lifecycle_event(
                dataset_id=id,
                event_type="curate",
                params={"operation": "replace"},
            )
    except Exception:
        pass

    return {
        "data": {
            "operation_id": result["operation_id"],
            "samples_affected": result["samples_affected"],
            "samples_before": result["samples_before"],
            "samples_after": result["samples_after"],
        },
        "error": None,
    }


@router.get("/datasets/{id}/metrics")
async def get_metrics(
    id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """Get statistical metrics for a dataset.

    GET /datasets/{id}/metrics

    Computes and returns aggregate statistics about the dataset including
    sample count, total characters, estimated tokens, vocabulary size,
    length distribution, and duplicate count.

    Parameters
    ----------
    id : int
        The dataset ID.
    session : AsyncSession
        Injected database session.

    Returns
    -------
    dict
        Dataset metrics including ``sample_count``, ``total_chars``,
        ``estimated_tokens``, ``vocabulary_size``, ``length_distribution``,
        ``duplicate_count``, and ``"error": None``.
    """
    svc = DatasetCurationService(session, id)
    result = await svc.get_metrics()
    return {
        "data": {
            "sample_count": result.sample_count,
            "total_chars": result.total_chars,
            "estimated_tokens": result.estimated_tokens,
            "vocabulary_size": result.vocabulary_size,
            "length_distribution": result.length_distribution,
            "duplicate_count": result.duplicate_count,
        },
        "error": None,
    }


@router.get("/datasets/{id}/export")
async def export_dataset(
    id: int,
    format: str = Query(...),
    session: AsyncSession = Depends(get_db_session),
):
    """Export a dataset to a downloadable file stream.

    GET /datasets/{id}/export

    Exports the dataset content in the specified format (``txt``, ``csv``,
    or ``jsonl``) as a streaming HTTP response with a
    ``Content-Disposition`` header for file download.

    Parameters
    ----------
    id : int
        The dataset ID.
    format : str
        Export format: ``"txt"``, ``"csv"``, or ``"jsonl"``.
    session : AsyncSession
        Injected database session.

    Returns
    -------
    StreamingResponse
        Streaming response with the exported content in the requested format.

    Raises
    ------
    HTTPException
        If the format is not supported (422).
    """
    if format not in ("txt", "csv", "jsonl"):
        raise HTTPException(
            status_code=422, detail="Unsupported format. Use txt, csv, or jsonl."
        )
    svc = DatasetExportService(session, id)
    content_type = {
        "txt": "text/plain",
        "csv": "text/csv",
        "jsonl": "application/x-ndjson",
    }[format]
    if format == "txt":
        generator = svc.export_txt()
    elif format == "csv":
        generator = svc.export_csv()
    else:
        generator = svc.export_jsonl()

    async def bytes_gen():
        """Convert string chunks to UTF-8 byte chunks for streaming.

        Yields
        ------
        bytes
            UTF-8 encoded string chunks from the export generator.
        """
        async for chunk in generator:
            yield chunk.encode("utf-8")

    return StreamingResponse(
        bytes_gen(),
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="dataset_{id}.{format}"'
        },
    )


@router.get("/datasets/{id}/operations")
async def list_operations(
    id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """List all curation operations applied to a dataset.

    GET /datasets/{id}/operations

    Returns a complete history of curation operations performed on the
    dataset, including operation type, parameters, sample counts before
    and after, and timestamps.

    Parameters
    ----------
    id : int
        The dataset ID.
    session : AsyncSession
        Injected database session.

    Returns
    -------
    dict
        List of operation objects with ``id``, ``operation_type``,
        ``parameters``, ``sample_count_before``, ``sample_count_after``,
        ``created_at``, and ``"error": None``.
    """
    repo = CurationOperationRepository(session)
    ops = await repo.get_by_dataset(id)
    return {
        "data": {
            "operations": [
                {
                    "id": op.id,
                    "operation_type": op.operation_type,
                    "parameters": op.parameters,
                    "sample_count_before": op.sample_count_before,
                    "sample_count_after": op.sample_count_after,
                    "created_at": str(op.created_at),
                }
                for op in ops
            ]
        },
        "error": None,
    }
