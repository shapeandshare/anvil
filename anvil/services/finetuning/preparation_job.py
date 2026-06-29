# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Preparation job runner — async background task for fine-tune dataset preparation."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models.curation_operation import CurationOperation
from ...db.repositories.curation_operation_repository import CurationOperationRepository
from ...db.repositories.fine_tune_datasets import FineTuneDatasetRepository
from ...services._shared.fine_tune_dataset_status import FineTuneDatasetStatus
from ...storage.interface import FileStore
from .dataset_preparation_service import DatasetPreparationService, validate_record
from .preparation_result import PreparationResult


async def run_preparation(
    session: AsyncSession,
    fine_tune_dataset_id: int,
    records: list[dict[str, Any]],
    template_string: str,
    bos_token: str,
    record_type: str = "sft",
    batch_size: int = 1000,
    store: FileStore | None = None,
    output_path: str | None = None,
) -> PreparationResult:
    """Execute a fine-tune dataset preparation job.

    Validates and renders records in batches (skip-and-continue), writes the
    rendered output as JSONL to *store* (when provided), persists the summary
    report, and transitions the ``FineTuneDataset`` status to ``ready``.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session for database operations.
    fine_tune_dataset_id : int
        The ``FineTuneDataset`` entry being prepared.
    records : list[dict]
        Parsed JSONL records to process.
    template_string : str
        The chat template string to apply.
    bos_token : str
        Beginning-of-sequence token.
    record_type : str
        ``"sft"`` or ``"preference"`` — selects the rendering strategy.
    batch_size : int
        Number of records per batch (default ``1000``).
    store : FileStore, optional
        Destination store for the rendered JSONL output. When ``None``, no
        output file is written (rendering still runs for counts).
    output_path : str, optional
        Logical path for the prepared JSONL output within *store*.

    Returns
    -------
    PreparationResult
        Summary with total/succeeded/failed counts and per-record errors.
    """
    repo = FineTuneDatasetRepository(session)
    total = len(records)
    all_errors: list[dict[str, Any]] = []
    rendered_outputs: list[dict[str, Any]] = []

    for batch_start in range(0, total, batch_size):
        batch = records[batch_start : batch_start + batch_size]
        for i, record in enumerate(batch):
            row_index = batch_start + i
            errors: list[dict[str, Any]] = []
            validated = validate_record(record, row_index, errors)
            if validated is None:
                all_errors.extend(errors)
                continue

            output = _render_record(validated, template_string, bos_token, record_type)
            if output is None:
                all_errors.append(
                    {"row": row_index, "error": "Rendering produced no output"}
                )
                continue
            rendered_outputs.append({"original": validated, "rendered": output})

    succeeded = len(rendered_outputs)
    failed = total - succeeded

    prepared_file_path: str | None = None
    if store is not None and output_path is not None:
        await _write_jsonl(store, output_path, rendered_outputs)
        prepared_file_path = output_path

    result = PreparationResult(
        job_id=fine_tune_dataset_id,
        total=total,
        succeeded=succeeded,
        failed=failed,
        errors=all_errors,
    )

    now = datetime.now(UTC)
    await repo.update_status(
        id=fine_tune_dataset_id,
        status=FineTuneDatasetStatus.READY,
        record_count=succeeded,
        prepared_file_path=prepared_file_path,
        summary_json=json.dumps(result.to_summary_json()),
        started_at=now,
        finished_at=now,
    )

    ftd = await repo.get(fine_tune_dataset_id)
    if ftd is not None:
        op_repo = CurationOperationRepository(session)
        await op_repo.add(
            CurationOperation(
                dataset_id=ftd.dataset_id,
                operation_type="prepare",
                parameters=f'{{"fine_tune_dataset_id": {fine_tune_dataset_id}}}',
                sample_count_before=total,
                sample_count_after=succeeded,
            )
        )

    await session.commit()

    return result


def _render_record(
    record: dict[str, Any],
    template_string: str,
    bos_token: str,
    record_type: str,
) -> object | None:
    """Render a validated record according to its type."""
    if record_type == "preference":
        return DatasetPreparationService.render_preference(
            record, template_string, bos_token=bos_token
        )
    return DatasetPreparationService.render_sft(
        record, template_string, bos_token=bos_token
    )


async def _write_jsonl(
    store: FileStore,
    path: str,
    rows: list[dict[str, Any]],
) -> None:
    """Serialize *rows* to JSONL and write them to *store* at *path*."""
    payload = "\n".join(json.dumps(row) for row in rows).encode("utf-8")

    async def _stream() -> AsyncIterator[bytes]:
        yield payload

    await store.put(path, _stream())
