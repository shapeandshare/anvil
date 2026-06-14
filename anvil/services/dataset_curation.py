import json
import re
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.models.curation import CurationOperation, Sample
from anvil.db.repositories.curation import (
    CurationOperationRepository,
    SampleRepository,
)
from anvil.db.repositories.datasets import DatasetRepository
from anvil.storage.local import LocalFileStore


class CurationResult:
    def __init__(self, operation_id: int, samples_removed: int, samples_before: int, samples_after: int):
        self.operation_id = operation_id
        self.samples_removed = samples_removed
        self.samples_before = samples_before
        self.samples_after = samples_after


class MetricsResult:
    def __init__(self, sample_count: int, total_chars: int, estimated_tokens: int,
                 vocabulary_size: int, length_distribution: dict, duplicate_count: int):
        self.sample_count = sample_count
        self.total_chars = total_chars
        self.estimated_tokens = estimated_tokens
        self.vocabulary_size = vocabulary_size
        self.length_distribution = length_distribution
        self.duplicate_count = duplicate_count


class DatasetCurationService:
    def __init__(
        self,
        session: AsyncSession,
        dataset_id: int,
        store: LocalFileStore | None = None,
    ):
        self._session = session
        self._dataset_id = dataset_id
        self._store = store or LocalFileStore("data/datasets")
        self._sample_repo = SampleRepository(session)
        self._op_repo = CurationOperationRepository(session)
        self._dataset_repo = DatasetRepository(session)

    async def deduplicate(self) -> CurationResult:
        dataset = await self._dataset_repo.get(self._dataset_id)
        if dataset is None:
            raise ValueError(f"Dataset {self._dataset_id} not found")

        samples_before = await self._sample_repo.count_active(self._dataset_id)
        duplicates = await self._sample_repo.find_duplicate_hashes(self._dataset_id)

        total_removed = 0
        for content_hash, count in duplicates:
            kept_one = False
            result = await self._session.execute(
                __import__("sqlalchemy").select(Sample)
                .where(
                    Sample.dataset_id == self._dataset_id,
                    Sample.is_removed == False,
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

        return CurationResult(
            operation_id=op.id,
            samples_removed=total_removed,
            samples_before=samples_before,
            samples_after=samples_after,
        )

    async def filter_by_length(
        self, min_length: int | None = None, max_length: int | None = None
    ) -> CurationResult:
        dataset = await self._dataset_repo.get(self._dataset_id)
        if dataset is None:
            raise ValueError(f"Dataset {self._dataset_id} not found")

        import sqlalchemy as sa

        samples_before = await self._sample_repo.count_active(self._dataset_id)
        conditions = [Sample.is_removed == False]
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
            parameters=json.dumps(
                {"min_length": min_length, "max_length": max_length}
            ),
            sample_count_before=samples_before,
            sample_count_after=samples_after,
        )
        op = await self._op_repo.add(op)
        await self._session.flush()

        dataset.sample_count = samples_after
        dataset.curation_version = (dataset.curation_version or 0) + 1
        await self._dataset_repo.update(dataset)

        return CurationResult(
            operation_id=op.id,
            samples_removed=total_removed,
            samples_before=samples_before,
            samples_after=samples_after,
        )

    async def regex_replace(
        self, pattern: str, replacement: str, case_sensitive: bool = True
    ) -> dict:
        dataset = await self._dataset_repo.get(self._dataset_id)
        if dataset is None:
            raise ValueError(f"Dataset {self._dataset_id} not found")

        import sqlalchemy as sa

        flags = 0 if case_sensitive else re.IGNORECASE
        compiled = re.compile(pattern, flags)

        result = await self._session.execute(
            sa.select(Sample).where(
                Sample.dataset_id == self._dataset_id,
                Sample.is_removed == False,
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
                s.content_hash = __import__("hashlib").sha256(
                    new_text.encode("utf-8")
                ).hexdigest()

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

        return {
            "operation_id": op.id,
            "samples_affected": samples_affected,
            "samples_before": samples_before,
            "samples_after": samples_after,
        }

    async def delete_sample(self, sample_id: int) -> CurationResult:
        dataset = await self._dataset_repo.get(self._dataset_id)
        if dataset is None:
            raise ValueError(f"Dataset {self._dataset_id} not found")

        sample = await self._sample_repo.get(sample_id)
        if sample is None or sample.dataset_id != self._dataset_id:
            raise ValueError(f"Sample {sample_id} not found in dataset {self._dataset_id}")

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

        return CurationResult(
            operation_id=op.id,
            samples_removed=1,
            samples_before=samples_before,
            samples_after=samples_before - 1,
        )

    async def get_metrics(self) -> MetricsResult:
        import sqlalchemy as sa

        result = await self._session.execute(
            sa.select(Sample).where(
                Sample.dataset_id == self._dataset_id,
                Sample.is_removed == False,
            )
        )
        active: Sequence[Sample] = result.scalars().all()

        sample_count = len(active)
        if sample_count == 0:
            return MetricsResult(
                sample_count=0, total_chars=0, estimated_tokens=0,
                vocabulary_size=0,
                length_distribution={"min": 0, "max": 0, "mean": 0, "median": 0},
                duplicate_count=0,
            )

        lengths = [s.length for s in active]
        total_chars = sum(lengths)
        estimated_tokens = total_chars // 4

        unique_hashes = set(s.content_hash for s in active)
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

    async def _text_stream(self, text: str):
        yield text.encode("utf-8")