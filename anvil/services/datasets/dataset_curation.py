# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Dataset curation service — deduplication, length filtering, regex replacement.

Provides the ``DatasetCurationService`` class for curating dataset samples:
deduplicating by content hash, filtering by length bounds, applying regex
substitutions, and computing dataset metrics.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncGenerator, Sequence
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import ColumnElement

from ...db.models.curation_operation import CurationOperation
from ...db.models.sample import Sample
from ...db.repositories.curation import SampleRepository
from ...db.repositories.curation_operation_repository import CurationOperationRepository
from ...db.repositories.datasets import DatasetRepository
from ...storage.local import LocalFileStore
from ..governance.audit_action import AuditAction
from ..governance.audit_outcome import AuditOutcome
from .curation_result import CurationResult
from .metrics_result import MetricsResult

if TYPE_CHECKING:
    from ...workspace.workspace_paths import WorkspacePaths
    from ..governance.audit_service import AuditService


class DatasetCurationService:
    """Business logic for curating dataset samples.

    Supports deduplication by content hash, filtering by character
    length bounds, regex-based text replacement, individual sample
    deletion, and metrics computation.
    """

    def __init__(
        self,
        session: AsyncSession,
        dataset_id: int,
        store: LocalFileStore | None = None,
        paths: WorkspacePaths | None = None,
    ):
        """Initialise the curation service.

        Parameters
        ----------
        session : AsyncSession
            SQLAlchemy async session for database access.
        dataset_id : int
            ID of the dataset to curate.
        store : LocalFileStore, optional
            File store for reading/writing sample content.  When
            ``None`` and *paths* is provided the store is rooted at
            ``paths.datasets_dir``, otherwise it falls back to
            ``"data/datasets"``.
        paths : WorkspacePaths, optional
            When provided with no explicit *store*, the store is created
            from ``paths.datasets_dir``.
        """
        self._session = session
        self._dataset_id = dataset_id
        if store is not None:
            self._store = store
        elif paths is not None:
            self._store = LocalFileStore(str(paths.datasets_dir))
        else:
            self._store = LocalFileStore("data/datasets")
        self._sample_repo = SampleRepository(session)
        self._op_repo = CurationOperationRepository(session)
        self._dataset_repo = DatasetRepository(session)

    async def deduplicate(self, audit: AuditService | None = None) -> CurationResult:
        """Remove duplicate samples by content hash.

        For each content hash with multiple occurrences, keeps the
        earliest sample (by ``index``) and marks the rest as removed.
        Records a ``"dedup"`` curation operation and updates the
        dataset metadata.

        Parameters
        ----------
        audit : AuditService, optional
            The hash-chained audit service. If provided, a ``curate``
            event is appended to the audit trail.

        Returns
        -------
        CurationResult
            Outcome with sample counts before and after deduplication.

        Raises
        ------
        ValueError
            If the dataset is not found.
        """
        dataset = await self._dataset_repo.get(self._dataset_id)
        if dataset is None:
            raise ValueError(f"Dataset {self._dataset_id} not found")

        samples_before = await self._sample_repo.count_active(self._dataset_id)
        duplicates = await self._sample_repo.find_duplicate_hashes(self._dataset_id)

        total_removed = 0
        for content_hash, _count in duplicates:
            kept_one = False
            result = await self._session.execute(
                __import__("sqlalchemy")
                .select(Sample)
                .where(
                    Sample.dataset_id == self._dataset_id,
                    not Sample.is_removed,
                    Sample.content_hash == content_hash,
                )
                .order_by(Sample.index)
            )
            dupe_samples: Sequence[Sample] = result.scalars().all()
            for s in dupe_samples:
                if not kept_one:
                    kept_one = True
                    continue
                s.is_removed = True
                total_removed += 1

        samples_after = samples_before - total_removed

        op = CurationOperation(
            dataset_id=self._dataset_id,
            operation_type="dedup",
            parameters="{}",
            sample_count_before=samples_before,
            sample_count_after=samples_after,
        )
        op = await self._op_repo.add(op)

        await self._session.flush()

        dataset.sample_count = samples_after
        dataset.curation_version = (dataset.curation_version or 0) + 1
        await self._dataset_repo.update(dataset)

        if audit is not None:
            await audit.record(
                action_type=AuditAction.CURATE.value,
                target_type="dataset",
                target_id=str(self._dataset_id),
                actor="system",
                outcome=AuditOutcome.SUCCESS.value,
                params={"operation": "dedup", "samples_removed": total_removed},
            )

        return CurationResult(
            operation_id=op.id,
            samples_removed=total_removed,
            samples_before=samples_before,
            samples_after=samples_after,
        )

    async def filter_by_length(
        self,
        min_length: int | None = None,
        max_length: int | None = None,
        audit: AuditService | None = None,
    ) -> CurationResult:
        """Remove samples outside a character-length range.

        Marks samples with ``length < min_length`` or
        ``length > max_length`` as removed. Records a
        ``"length_filter"`` curation operation.

        Parameters
        ----------
        min_length : int, optional
            Minimum character length. Samples shorter than this are
            removed. ``None`` means no lower bound.
        max_length : int, optional
            Maximum character length. Samples longer than this are
            removed. ``None`` means no upper bound.
        audit : AuditService, optional
            The hash-chained audit service. If provided, a ``curate``
            event is appended to the audit trail.

        Returns
        -------
        CurationResult
            Outcome with sample counts before and after filtering.

        Raises
        ------
        ValueError
            If the dataset is not found.
        """
        dataset = await self._dataset_repo.get(self._dataset_id)
        if dataset is None:
            raise ValueError(f"Dataset {self._dataset_id} not found")

        samples_before = await self._sample_repo.count_active(self._dataset_id)
        conditions: list[ColumnElement[bool]] = [sa.not_(Sample.is_removed)]
        if min_length is not None:
            conditions.append(Sample.length < min_length)
        if max_length is not None:
            conditions.append(Sample.length > max_length)

        result = await self._session.execute(
            sa.select(Sample).where(
                Sample.dataset_id == self._dataset_id,
                *conditions,
            )
        )
        to_remove: Sequence[Sample] = result.scalars().all()
        total_removed = len(to_remove)
        for s in to_remove:
            s.is_removed = True

        samples_after = samples_before - total_removed

        op = CurationOperation(
            dataset_id=self._dataset_id,
            operation_type="length_filter",
            parameters=json.dumps({"min_length": min_length, "max_length": max_length}),
            sample_count_before=samples_before,
            sample_count_after=samples_after,
        )
        op = await self._op_repo.add(op)
        await self._session.flush()

        dataset.sample_count = samples_after
        dataset.curation_version = (dataset.curation_version or 0) + 1
        await self._dataset_repo.update(dataset)

        if audit is not None:
            await audit.record(
                action_type=AuditAction.CURATE.value,
                target_type="dataset",
                target_id=str(self._dataset_id),
                actor="system",
                outcome=AuditOutcome.SUCCESS.value,
                params={
                    "operation": "length_filter",
                    "samples_removed": total_removed,
                },
            )

        return CurationResult(
            operation_id=op.id,
            samples_removed=total_removed,
            samples_before=samples_before,
            samples_after=samples_after,
        )

    async def regex_replace(
        self,
        pattern: str,
        replacement: str,
        case_sensitive: bool = True,
        audit: AuditService | None = None,
    ) -> dict[str, Any]:
        """Apply a regex substitution to all active sample texts.

        Reads each sample from the file store, applies the regex
        replacement, and writes back the modified text. Updates the
        sample length and content hash after modification.

        Parameters
        ----------
        pattern : str
            Regular expression pattern to search for.
        replacement : str
            Replacement string (may reference capture groups).
        case_sensitive : bool
            Whether the regex match is case-sensitive. Defaults to
            ``True``.
        audit : AuditService, optional
            The hash-chained audit service. If provided, a ``curate``
            event is appended to the audit trail.

        Returns
        -------
        dict
            Outcome dict with keys ``"operation_id"``,
            ``"samples_affected"``, ``"samples_before"``,
            ``"samples_after"``.

        Raises
        ------
        ValueError
            If the dataset is not found.
        """
        dataset = await self._dataset_repo.get(self._dataset_id)
        if dataset is None:
            raise ValueError(f"Dataset {self._dataset_id} not found")

        flags = 0 if case_sensitive else re.IGNORECASE
        compiled = re.compile(pattern, flags)

        result = await self._session.execute(
            sa.select(Sample).where(
                Sample.dataset_id == self._dataset_id,
                sa.not_(Sample.is_removed),
            )
        )
        active: Sequence[Sample] = result.scalars().all()

        samples_before = len(active)
        samples_affected = 0
        samples_after = samples_before

        for s in active:
            full_path = s.file_path
            text_bytes = b""
            async for chunk in self._store.get(full_path):
                text_bytes += chunk
            old_text = text_bytes.decode("utf-8")
            new_text = compiled.sub(replacement, old_text)
            if new_text != old_text:
                samples_affected += 1
                await self._store.put(full_path, self._text_stream(new_text))
                s.length = len(new_text)
                s.content_hash = (
                    __import__("hashlib").sha256(new_text.encode("utf-8")).hexdigest()
                )

        op = CurationOperation(
            dataset_id=self._dataset_id,
            operation_type="regex_replace",
            parameters=json.dumps(
                {
                    "pattern": pattern,
                    "replacement": replacement,
                    "case_sensitive": case_sensitive,
                }
            ),
            sample_count_before=samples_before,
            sample_count_after=samples_after,
        )
        op = await self._op_repo.add(op)
        await self._session.flush()

        dataset.curation_version = (dataset.curation_version or 0) + 1
        await self._dataset_repo.update(dataset)

        if audit is not None:
            await audit.record(
                action_type=AuditAction.CURATE.value,
                target_type="dataset",
                target_id=str(self._dataset_id),
                actor="system",
                outcome=AuditOutcome.SUCCESS.value,
                params={
                    "operation": "regex_replace",
                    "samples_affected": samples_affected,
                },
            )

        return {
            "operation_id": op.id,
            "samples_affected": samples_affected,
            "samples_before": samples_before,
            "samples_after": samples_after,
        }

    async def delete_sample(
        self, sample_id: int, audit: AuditService | None = None
    ) -> CurationResult:
        """Mark a single sample as removed by its ID.

        Records an ``"individual_delete"`` curation operation.

        Parameters
        ----------
        sample_id : int
            ID of the sample to delete.
        audit : AuditService, optional
            The hash-chained audit service. If provided, a ``curate``
            event is appended to the audit trail.

        Returns
        -------
        CurationResult
            Outcome with the single sample removed.

        Raises
        ------
        ValueError
            If the dataset or sample is not found, or if the sample
            does not belong to this dataset.
        """
        dataset = await self._dataset_repo.get(self._dataset_id)
        if dataset is None:
            raise ValueError(f"Dataset {self._dataset_id} not found")

        sample = await self._sample_repo.get(sample_id)
        if sample is None or sample.dataset_id != self._dataset_id:
            raise ValueError(
                f"Sample {sample_id} not found in dataset {self._dataset_id}"
            )

        samples_before = await self._sample_repo.count_active(self._dataset_id)

        op = CurationOperation(
            dataset_id=self._dataset_id,
            operation_type="individual_delete",
            parameters=json.dumps({"sample_id": sample_id}),
            sample_count_before=samples_before,
            sample_count_after=samples_before - 1,
        )
        op = await self._op_repo.add(op)
        await self._session.flush()

        sample.is_removed = True
        sample.removed_by_op_id = op.id

        dataset.sample_count = samples_before - 1
        dataset.curation_version = (dataset.curation_version or 0) + 1
        await self._dataset_repo.update(dataset)

        if audit is not None:
            await audit.record(
                action_type=AuditAction.CURATE.value,
                target_type="dataset",
                target_id=str(self._dataset_id),
                actor="system",
                outcome=AuditOutcome.SUCCESS.value,
                params={"operation": "individual_delete", "sample_id": sample_id},
            )

        return CurationResult(
            operation_id=op.id,
            samples_removed=1,
            samples_before=samples_before,
            samples_after=samples_before - 1,
        )

    async def get_metrics(self) -> MetricsResult:
        """Compute aggregate statistics for the dataset.

        Counts active samples, sums character lengths, estimates token
        count, computes unique content hashes, and calculates length
        distribution (min, max, mean, median).

        Returns
        -------
        MetricsResult
            Dataset metrics including sample count, total characters,
            estimated tokens, vocabulary size, length distribution,
            and duplicate count.
        """
        result = await self._session.execute(
            sa.select(Sample).where(
                Sample.dataset_id == self._dataset_id,
                sa.not_(Sample.is_removed),
            )
        )
        active: Sequence[Sample] = result.scalars().all()

        sample_count = len(active)
        if sample_count == 0:
            return MetricsResult(
                sample_count=0,
                total_chars=0,
                estimated_tokens=0,
                vocabulary_size=0,
                length_distribution={"min": 0, "max": 0, "mean": 0, "median": 0},
                duplicate_count=0,
            )

        lengths = [s.length for s in active]
        total_chars = sum(lengths)
        estimated_tokens = total_chars // 4

        unique_hashes = {s.content_hash for s in active}
        vocabulary_size = len(unique_hashes)
        duplicate_count = sample_count - vocabulary_size

        sorted_lengths = sorted(lengths)
        mean = total_chars / sample_count
        median = sorted_lengths[sample_count // 2] if sample_count else 0

        return MetricsResult(
            sample_count=sample_count,
            total_chars=total_chars,
            estimated_tokens=estimated_tokens,
            vocabulary_size=vocabulary_size,
            length_distribution={
                "min": min(lengths),
                "max": max(lengths),
                "mean": round(mean, 1),
                "median": median,
            },
            duplicate_count=duplicate_count,
        )

    async def _text_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """Async generator yielding encoded text as byte chunks.

        Parameters
        ----------
        text : str
            The text to encode.

        Yields
        ------
        bytes
            UTF-8 encoded text content.
        """
        yield text.encode("utf-8")
