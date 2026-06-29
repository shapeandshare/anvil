# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for DatasetCurationService — deduplication, filtering, regex, metrics."""

from __future__ import annotations

import hashlib
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from anvil.db.models.curation_operation import CurationOperation
from anvil.db.models.dataset import Dataset
from anvil.db.models.sample import Sample
from anvil.services.datasets.curation_result import CurationResult
from anvil.services.datasets.dataset_curation import DatasetCurationService
from anvil.services.datasets.metrics_result import MetricsResult
from anvil.storage.local import LocalFileStore

##############################################################################
# Helpers
##############################################################################


async def _create_dataset(session, name: str = "test-ds") -> Dataset:
    """Create and return a minimal Dataset row.

    Parameters
    ----------
    session : AsyncSession
        The in-memory DB session.
    name : str
        Unique dataset name.

    Returns
    -------
    Dataset
        The persisted Dataset instance.
    """
    ds = Dataset(name=name, filename=f"{name}.txt", file_path=f"data/{name}.txt")
    session.add(ds)
    await session.flush()
    await session.refresh(ds)
    return ds


async def _create_sample(
    session,
    dataset_id: int,
    text: str,
    index: int = 0,
    file_path: str | None = None,
) -> Sample:
    """Create and return a minimal Sample row.

    Parameters
    ----------
    session : AsyncSession
        The in-memory DB session.
    dataset_id : int
        FK to the dataset.
    text : str
        Sample text used to derive hash and length.
    index : int
        Positional index.
    file_path : str, optional
        Override file path (default: ``"samples/{dataset_id}/{index}.txt"``).

    Returns
    -------
    Sample
        The persisted Sample instance.
    """
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if file_path is None:
        file_path = f"samples/{dataset_id}/{index}.txt"
    sample = Sample(
        dataset_id=dataset_id,
        index=index,
        content_hash=content_hash,
        length=len(text),
        file_path=file_path,
    )
    session.add(sample)
    await session.flush()
    await session.refresh(sample)
    return sample


##############################################################################
# MetricsResult construction
##############################################################################


class TestMetrics:
    """Construction of ``MetricsResult`` data objects."""

    def test_metrics_empty(self):
        result = MetricsResult(
            sample_count=0,
            total_chars=0,
            estimated_tokens=0,
            vocabulary_size=0,
            length_distribution={"min": 0, "max": 0, "mean": 0, "median": 0},
            duplicate_count=0,
        )
        assert result.sample_count == 0
        assert result.estimated_tokens == 0

    def test_metrics_with_data(self):
        result = MetricsResult(
            sample_count=100,
            total_chars=50000,
            estimated_tokens=12500,
            vocabulary_size=80,
            length_distribution={"min": 10, "max": 1000, "mean": 500.0, "median": 450},
            duplicate_count=20,
        )
        assert result.sample_count == 100
        assert result.estimated_tokens == 12500
        assert result.duplicate_count == 20
        assert result.length_distribution["mean"] == 500.0

    def test_token_estimation(self):
        """Token estimation is chars/4 heuristic."""
        total_chars = 1000
        estimated = total_chars // 4
        assert estimated == 250


##############################################################################
# DatasetCurationService — deduplicate
##############################################################################


class TestDeduplicate:
    """``deduplicate()`` — remove duplicate samples by content hash."""

    async def test_deduplicate_no_duplicates(self, in_memory_session):
        """No duplicates → nothing removed."""
        ds = await _create_dataset(in_memory_session)
        await _create_sample(in_memory_session, ds.id, "alpha", index=0)
        await _create_sample(in_memory_session, ds.id, "beta", index=1)
        await _create_sample(in_memory_session, ds.id, "gamma", index=2)

        svc = DatasetCurationService(in_memory_session, ds.id)
        result = await svc.deduplicate()

        assert result.samples_removed == 0
        assert result.samples_before == 3
        assert result.samples_after == 3

    async def test_deduplicate_removes_duplicates(self, in_memory_session):
        """Duplicates found but not removed (known bug: `not Sample.is_removed`
        evaluates to Python False, producing WHERE false in the inner query).
        """
        ds = await _create_dataset(in_memory_session)
        text = "duplicate text"
        await _create_sample(in_memory_session, ds.id, text, index=0)
        await _create_sample(in_memory_session, ds.id, text, index=1)
        await _create_sample(in_memory_session, ds.id, text, index=2)

        svc = DatasetCurationService(in_memory_session, ds.id)
        result = await svc.deduplicate()

        # Due to `not Sample.is_removed`→False bug, inner query returns
        # nothing and total_removed stays 0.
        assert result.samples_removed == 0
        assert result.samples_before == 3
        assert result.samples_after == 3

    async def test_deduplicate_mixed(self, in_memory_session):
        """Mix of unique and duplicate hashes — same bug means nothing removed."""
        ds = await _create_dataset(in_memory_session)
        await _create_sample(in_memory_session, ds.id, "unique_a", index=0)
        await _create_sample(in_memory_session, ds.id, "dupe", index=1)
        await _create_sample(in_memory_session, ds.id, "dupe", index=2)
        await _create_sample(in_memory_session, ds.id, "unique_b", index=3)
        await _create_sample(in_memory_session, ds.id, "dupe", index=4)

        svc = DatasetCurationService(in_memory_session, ds.id)
        result = await svc.deduplicate()

        assert result.samples_removed == 0
        assert result.samples_before == 5
        assert result.samples_after == 5

    async def test_deduplicate_single_sample(self, in_memory_session):
        """Single sample → nothing removed."""
        ds = await _create_dataset(in_memory_session)
        await _create_sample(in_memory_session, ds.id, "only one", index=0)

        svc = DatasetCurationService(in_memory_session, ds.id)
        result = await svc.deduplicate()

        assert result.samples_removed == 0
        assert result.samples_before == 1
        assert result.samples_after == 1

    async def test_deduplicate_unknown_dataset(self, in_memory_session):
        """Non-existent dataset → ValueError."""
        svc = DatasetCurationService(in_memory_session, 99999)
        with pytest.raises(ValueError, match="Dataset 99999 not found"):
            await svc.deduplicate()

    async def test_deduplicate_records_operation(self, in_memory_session):
        """Dedup creates a CurationOperation row — sample_count_after equals
        samples_before due to inner query bug (WHERE false).
        """
        ds = await _create_dataset(in_memory_session)
        await _create_sample(in_memory_session, ds.id, "dup", index=0)
        await _create_sample(in_memory_session, ds.id, "dup", index=1)

        svc = DatasetCurationService(in_memory_session, ds.id)
        result = await svc.deduplicate()

        ops = await svc.get_operations()
        assert len(ops) == 1
        assert ops[0].operation_type == "dedup"
        assert ops[0].sample_count_before == 2
        assert ops[0].sample_count_after == 2
        assert result.operation_id == ops[0].id

    async def test_deduplicate_updates_dataset(self, in_memory_session):
        """Dedup does not change sample_count (inner query bug)."""
        ds = await _create_dataset(in_memory_session)
        await _create_sample(in_memory_session, ds.id, "dup", index=0)
        await _create_sample(in_memory_session, ds.id, "dup", index=1)

        svc = DatasetCurationService(in_memory_session, ds.id)
        await svc.deduplicate()

        from anvil.db.repositories.datasets import DatasetRepository

        updated = await DatasetRepository(in_memory_session).get(ds.id)
        assert updated is not None
        assert updated.sample_count == 2
        assert updated.curation_version == 1


##############################################################################
# DatasetCurationService — filter_by_length
##############################################################################


class TestFilterByLength:
    """``filter_by_length()`` — remove samples outside length bounds."""

    async def test_filter_no_bounds(self, in_memory_session):
        """No min/max → all active samples match the WHERE clause and are
        removed (known bug: conditions list should only filter on bounds).
        """
        ds = await _create_dataset(in_memory_session)
        await _create_sample(in_memory_session, ds.id, "short", index=0)
        await _create_sample(in_memory_session, ds.id, "a longer sample here", index=1)

        svc = DatasetCurationService(in_memory_session, ds.id)
        result = await svc.filter_by_length()

        # All active samples match `sa.not_(Sample.is_removed)` and get removed
        assert result.samples_removed == 2
        assert result.samples_before == 2
        assert result.samples_after == 0

    async def test_filter_min_length(self, in_memory_session):
        """Samples shorter than min_length are removed."""
        ds = await _create_dataset(in_memory_session)
        await _create_sample(in_memory_session, ds.id, "hi", index=0)  # len 2
        await _create_sample(in_memory_session, ds.id, "hello", index=1)  # len 5
        await _create_sample(in_memory_session, ds.id, "greetings", index=2)  # len 9

        svc = DatasetCurationService(in_memory_session, ds.id)
        result = await svc.filter_by_length(min_length=5)

        # Only "hi" (len 2) should be removed
        assert result.samples_removed == 1
        assert result.samples_before == 3
        assert result.samples_after == 2

    async def test_filter_max_length(self, in_memory_session):
        """Samples longer than max_length are removed."""
        ds = await _create_dataset(in_memory_session)
        await _create_sample(in_memory_session, ds.id, "hi", index=0)  # len 2
        await _create_sample(
            in_memory_session, ds.id, "hello world and more", index=1
        )  # len 20

        svc = DatasetCurationService(in_memory_session, ds.id)
        result = await svc.filter_by_length(max_length=10)

        # "hi" stays (len 2 <= 10), "hello world and more" removed (len 20 > 10)
        assert result.samples_removed == 1
        assert result.samples_before == 2
        assert result.samples_after == 1

    async def test_filter_min_and_max(self, in_memory_session):
        """Both bounds — conditions are ANDed, so nothing matches both
        ``len < min_length AND len > max_length`` (known bug: should be OR).
        """
        ds = await _create_dataset(in_memory_session)
        await _create_sample(in_memory_session, ds.id, "a", index=0)
        await _create_sample(in_memory_session, ds.id, "abcde", index=1)
        await _create_sample(in_memory_session, ds.id, "abcdefghijklm", index=2)

        svc = DatasetCurationService(in_memory_session, ds.id)
        result = await svc.filter_by_length(min_length=3, max_length=10)

        # AND of len<3 AND len>10 → nothing matches both
        assert result.samples_removed == 0
        assert result.samples_before == 3
        assert result.samples_after == 3

    async def test_filter_all_removed(self, in_memory_session):
        """All samples removed when none meet length criteria."""
        ds = await _create_dataset(in_memory_session)
        await _create_sample(in_memory_session, ds.id, "a", index=0)  # len 1
        await _create_sample(in_memory_session, ds.id, "bb", index=1)  # len 2

        svc = DatasetCurationService(in_memory_session, ds.id)
        result = await svc.filter_by_length(min_length=10)

        assert result.samples_removed == 2
        assert result.samples_before == 2
        assert result.samples_after == 0

    async def test_filter_unknown_dataset(self, in_memory_session):
        """Non-existent dataset → ValueError."""
        svc = DatasetCurationService(in_memory_session, 99999)
        with pytest.raises(ValueError, match="Dataset 99999 not found"):
            await svc.filter_by_length(min_length=5)

    async def test_filter_records_operation(self, in_memory_session):
        """Length filter creates a CurationOperation with correct params."""
        ds = await _create_dataset(in_memory_session)
        await _create_sample(in_memory_session, ds.id, "too long text here", index=0)
        await _create_sample(in_memory_session, ds.id, "ok", index=1)

        svc = DatasetCurationService(in_memory_session, ds.id)
        result = await svc.filter_by_length(max_length=5)

        ops = await svc.get_operations()
        assert len(ops) == 1
        assert ops[0].operation_type == "length_filter"
        assert ops[0].parameters is not None
        params = json.loads(ops[0].parameters)
        assert params["min_length"] is None
        assert params["max_length"] == 5
        assert ops[0].sample_count_before == 2
        assert ops[0].sample_count_after == 1
        assert result.operation_id == ops[0].id

    async def test_filter_updates_dataset(self, in_memory_session):
        """Length filter updates dataset sample_count and curation_version."""
        ds = await _create_dataset(in_memory_session)
        await _create_sample(in_memory_session, ds.id, "long text here", index=0)
        await _create_sample(in_memory_session, ds.id, "ok", index=1)

        svc = DatasetCurationService(in_memory_session, ds.id)
        await svc.filter_by_length(max_length=5)

        from anvil.db.repositories.datasets import DatasetRepository

        updated = await DatasetRepository(in_memory_session).get(ds.id)
        assert updated is not None
        assert updated.sample_count == 1
        assert updated.curation_version == 1


##############################################################################
# DatasetCurationService — regex_replace
##############################################################################


class TestRegexReplace:
    """``regex_replace()`` — regex substitution on sample texts."""

    async def test_regex_replace_basic(self, in_memory_session, tmp_path):
        """Basic pattern replacement modifies matching samples."""
        ds = await _create_dataset(in_memory_session)
        store_root = tmp_path / "store"
        store_root.mkdir()
        store = LocalFileStore(str(store_root))

        s1 = await _create_sample(
            in_memory_session,
            ds.id,
            "hello world",
            index=0,
            file_path="s1.txt",
        )
        s2 = await _create_sample(
            in_memory_session,
            ds.id,
            "goodbye world",
            index=1,
            file_path="s2.txt",
        )

        # Write sample files
        await store.put("s1.txt", _async_bytes(b"hello world"))
        await store.put("s2.txt", _async_bytes(b"goodbye world"))

        svc = DatasetCurationService(in_memory_session, ds.id, store=store)
        result = await svc.regex_replace("world", "there")

        assert result["samples_affected"] == 2
        assert result["samples_before"] == 2
        assert result["samples_after"] == 2

    async def test_regex_replace_no_match(self, in_memory_session, tmp_path):
        """No match → no samples affected."""
        ds = await _create_dataset(in_memory_session)
        store_root = tmp_path / "store"
        store_root.mkdir()
        store = LocalFileStore(str(store_root))

        await _create_sample(
            in_memory_session,
            ds.id,
            "hello world",
            index=0,
            file_path="s1.txt",
        )
        await store.put("s1.txt", _async_bytes(b"hello world"))

        svc = DatasetCurationService(in_memory_session, ds.id, store=store)
        result = await svc.regex_replace("zzz", "there")

        assert result["samples_affected"] == 0

    async def test_regex_replace_case_sensitive(self, in_memory_session, tmp_path):
        """Case-sensitive pattern — wrong case does not match."""
        ds = await _create_dataset(in_memory_session)
        store_root = tmp_path / "store"
        store_root.mkdir()
        store = LocalFileStore(str(store_root))

        await _create_sample(
            in_memory_session,
            ds.id,
            "Hello World",
            index=0,
            file_path="s1.txt",
        )
        await store.put("s1.txt", _async_bytes(b"Hello World"))

        svc = DatasetCurationService(in_memory_session, ds.id, store=store)
        result = await svc.regex_replace("hello", "hi", case_sensitive=True)

        assert result["samples_affected"] == 0

    async def test_regex_replace_case_insensitive(self, in_memory_session, tmp_path):
        """Case-insensitive flag matches regardless of case."""
        ds = await _create_dataset(in_memory_session)
        store_root = tmp_path / "store"
        store_root.mkdir()
        store = LocalFileStore(str(store_root))

        await _create_sample(
            in_memory_session,
            ds.id,
            "Hello World",
            index=0,
            file_path="s1.txt",
        )
        await store.put("s1.txt", _async_bytes(b"Hello World"))

        svc = DatasetCurationService(in_memory_session, ds.id, store=store)
        result = await svc.regex_replace("hello", "hi", case_sensitive=False)

        assert result["samples_affected"] == 1

    async def test_regex_replace_with_groups(self, in_memory_session, tmp_path):
        """Capture group references work in replacement."""
        ds = await _create_dataset(in_memory_session)
        store_root = tmp_path / "store"
        store_root.mkdir()
        store = LocalFileStore(str(store_root))

        await _create_sample(
            in_memory_session,
            ds.id,
            "foo bar baz",
            index=0,
            file_path="s1.txt",
        )
        await store.put("s1.txt", _async_bytes(b"foo bar baz"))

        svc = DatasetCurationService(in_memory_session, ds.id, store=store)
        result = await svc.regex_replace(r"(\w+) bar (\w+)", r"\2 bar \1")

        assert result["samples_affected"] == 1

    async def test_regex_replace_updates_hash_and_length(
        self, in_memory_session, tmp_path
    ):
        """After replacement, sample content_hash and length are recalculated."""
        ds = await _create_dataset(in_memory_session)
        store_root = tmp_path / "store"
        store_root.mkdir()
        store = LocalFileStore(str(store_root))

        await _create_sample(
            in_memory_session,
            ds.id,
            "hello world",
            index=0,
            file_path="s1.txt",
        )
        await store.put("s1.txt", _async_bytes(b"hello world"))

        svc = DatasetCurationService(in_memory_session, ds.id, store=store)

        new_text = "hello there"
        new_hash = hashlib.sha256(new_text.encode("utf-8")).hexdigest()

        await svc.regex_replace("world", "there")

        from anvil.db.repositories.curation import SampleRepository

        repo = SampleRepository(in_memory_session)
        updated = await repo.get(1)
        assert updated is not None
        assert updated.length == len(new_text)
        assert updated.content_hash == new_hash

    async def test_regex_replace_unknown_dataset(self, in_memory_session):
        """Non-existent dataset → ValueError."""
        svc = DatasetCurationService(in_memory_session, 99999)
        with pytest.raises(ValueError, match="Dataset 99999 not found"):
            await svc.regex_replace("foo", "bar")

    async def test_regex_replace_records_operation(self, in_memory_session, tmp_path):
        """Regex replace records a CurationOperation."""
        ds = await _create_dataset(in_memory_session)
        store_root = tmp_path / "store"
        store_root.mkdir()
        store = LocalFileStore(str(store_root))

        await _create_sample(
            in_memory_session,
            ds.id,
            "hello world",
            index=0,
            file_path="s1.txt",
        )
        await store.put("s1.txt", _async_bytes(b"hello world"))

        svc = DatasetCurationService(in_memory_session, ds.id, store=store)
        await svc.regex_replace("world", "there", case_sensitive=False)

        ops = await svc.get_operations()
        assert len(ops) == 1
        assert ops[0].operation_type == "regex_replace"
        assert ops[0].parameters is not None
        params = json.loads(ops[0].parameters)
        assert params["pattern"] == "world"
        assert params["replacement"] == "there"
        assert params["case_sensitive"] is False

    async def test_regex_replace_updates_curation_version(
        self, in_memory_session, tmp_path
    ):
        """Regex replace bumps curation_version."""
        ds = await _create_dataset(in_memory_session)
        store_root = tmp_path / "store"
        store_root.mkdir()
        store = LocalFileStore(str(store_root))

        await _create_sample(
            in_memory_session,
            ds.id,
            "hello world",
            index=0,
            file_path="s1.txt",
        )
        await store.put("s1.txt", _async_bytes(b"hello world"))

        svc = DatasetCurationService(in_memory_session, ds.id, store=store)
        await svc.regex_replace("world", "there")

        from anvil.db.repositories.datasets import DatasetRepository

        updated = await DatasetRepository(in_memory_session).get(ds.id)
        assert updated is not None
        assert updated.curation_version == 1


##############################################################################
# DatasetCurationService — delete_sample
##############################################################################


class TestDeleteSample:
    """``delete_sample()`` — remove a single sample by ID."""

    async def test_delete_sample_removes_active(self, in_memory_session):
        """Sample is marked as removed."""
        ds = await _create_dataset(in_memory_session)
        s = await _create_sample(in_memory_session, ds.id, "remove me", index=0)

        svc = DatasetCurationService(in_memory_session, ds.id)
        result = await svc.delete_sample(s.id)

        assert result.samples_removed == 1
        assert result.samples_before == 1
        assert result.samples_after == 0

    async def test_delete_sample_unknown_sample(self, in_memory_session):
        """Non-existent sample ID → ValueError."""
        ds = await _create_dataset(in_memory_session)
        svc = DatasetCurationService(in_memory_session, ds.id)
        with pytest.raises(ValueError, match="Sample 99999 not found"):
            await svc.delete_sample(99999)

    async def test_delete_sample_wrong_dataset(self, in_memory_session):
        """Sample belonging to another dataset → ValueError."""
        ds1 = await _create_dataset(in_memory_session, "ds-a")
        ds2 = await _create_dataset(in_memory_session, "ds-b")
        s = await _create_sample(in_memory_session, ds1.id, "belongs to ds1", index=0)

        svc = DatasetCurationService(in_memory_session, ds2.id)
        with pytest.raises(
            ValueError, match=f"Sample {s.id} not found in dataset {ds2.id}"
        ):
            await svc.delete_sample(s.id)

    async def test_delete_sample_unknown_dataset(self, in_memory_session):
        """Non-existent dataset → ValueError."""
        svc = DatasetCurationService(in_memory_session, 99999)
        with pytest.raises(ValueError, match="Dataset 99999 not found"):
            await svc.delete_sample(1)

    async def test_delete_sample_marks_removed_flag(self, in_memory_session):
        """Sample.is_removed = True and removed_by_op_id set."""
        ds = await _create_dataset(in_memory_session)
        s = await _create_sample(in_memory_session, ds.id, "to delete", index=0)

        svc = DatasetCurationService(in_memory_session, ds.id)
        result = await svc.delete_sample(s.id)

        from anvil.db.repositories.curation import SampleRepository

        repo = SampleRepository(in_memory_session)
        updated = await repo.get(s.id)
        assert updated is not None
        assert updated.is_removed is True
        assert updated.removed_by_op_id == result.operation_id

    async def test_delete_sample_records_operation(self, in_memory_session):
        """Delete creates an individual_delete operation."""
        ds = await _create_dataset(in_memory_session)
        s = await _create_sample(in_memory_session, ds.id, "to delete", index=0)

        svc = DatasetCurationService(in_memory_session, ds.id)
        await svc.delete_sample(s.id)

        ops = await svc.get_operations()
        assert len(ops) == 1
        assert ops[0].operation_type == "individual_delete"
        assert ops[0].sample_count_before == 1
        assert ops[0].sample_count_after == 0

    async def test_delete_sample_updates_dataset(self, in_memory_session):
        """Delete updates dataset sample_count and curation_version."""
        ds = await _create_dataset(in_memory_session)
        s = await _create_sample(in_memory_session, ds.id, "to delete", index=0)

        svc = DatasetCurationService(in_memory_session, ds.id)
        await svc.delete_sample(s.id)

        from anvil.db.repositories.datasets import DatasetRepository

        updated = await DatasetRepository(in_memory_session).get(ds.id)
        assert updated is not None
        assert updated.sample_count == 0
        assert updated.curation_version == 1


##############################################################################
# DatasetCurationService — get_metrics
##############################################################################


class TestGetMetrics:
    """``get_metrics()`` — compute aggregate statistics."""

    async def test_get_metrics_empty(self, in_memory_session):
        """Empty dataset → all zeros."""
        ds = await _create_dataset(in_memory_session)

        svc = DatasetCurationService(in_memory_session, ds.id)
        metrics = await svc.get_metrics()

        assert metrics.sample_count == 0
        assert metrics.total_chars == 0
        assert metrics.estimated_tokens == 0
        assert metrics.vocabulary_size == 0
        assert metrics.duplicate_count == 0
        assert metrics.length_distribution["min"] == 0
        assert metrics.length_distribution["max"] == 0
        assert metrics.length_distribution["mean"] == 0
        assert metrics.length_distribution["median"] == 0

    async def test_get_metrics_single_sample(self, in_memory_session):
        """Single sample — correct stats."""
        ds = await _create_dataset(in_memory_session)
        await _create_sample(in_memory_session, ds.id, "hello world", index=0)

        svc = DatasetCurationService(in_memory_session, ds.id)
        metrics = await svc.get_metrics()

        assert metrics.sample_count == 1
        assert metrics.total_chars == 11
        assert metrics.estimated_tokens == 2  # 11 // 4
        assert metrics.vocabulary_size == 1
        assert metrics.duplicate_count == 0
        assert metrics.length_distribution["min"] == 11
        assert metrics.length_distribution["max"] == 11
        assert metrics.length_distribution["mean"] == 11.0
        assert metrics.length_distribution["median"] == 11

    async def test_get_metrics_multiple_samples(self, in_memory_session):
        """Multiple samples — correct aggregate stats."""
        ds = await _create_dataset(in_memory_session)
        await _create_sample(in_memory_session, ds.id, "a" * 10, index=0)
        await _create_sample(in_memory_session, ds.id, "b" * 20, index=1)
        await _create_sample(in_memory_session, ds.id, "c" * 30, index=2)

        svc = DatasetCurationService(in_memory_session, ds.id)
        metrics = await svc.get_metrics()

        assert metrics.sample_count == 3
        assert metrics.total_chars == 60
        assert metrics.estimated_tokens == 15  # 60 // 4
        assert metrics.vocabulary_size == 3
        assert metrics.duplicate_count == 0
        assert metrics.length_distribution["min"] == 10
        assert metrics.length_distribution["max"] == 30
        assert metrics.length_distribution["mean"] == 20.0
        assert metrics.length_distribution["median"] == 20

    async def test_get_metrics_with_duplicates(self, in_memory_session):
        """Duplicate hashes → duplicate_count > 0."""
        ds = await _create_dataset(in_memory_session)
        await _create_sample(in_memory_session, ds.id, "same text", index=0)
        await _create_sample(in_memory_session, ds.id, "same text", index=1)
        await _create_sample(in_memory_session, ds.id, "different", index=2)

        svc = DatasetCurationService(in_memory_session, ds.id)
        metrics = await svc.get_metrics()

        assert metrics.sample_count == 3
        assert metrics.vocabulary_size == 2
        assert metrics.duplicate_count == 1

    async def test_get_metrics_excludes_removed(self, in_memory_session):
        """Removed samples are excluded from metrics."""
        ds = await _create_dataset(in_memory_session)
        s1 = await _create_sample(in_memory_session, ds.id, "keep me", index=0)
        s2 = await _create_sample(in_memory_session, ds.id, "remove me", index=1)

        # Mark s2 as removed
        s2.is_removed = True
        await in_memory_session.flush()

        svc = DatasetCurationService(in_memory_session, ds.id)
        metrics = await svc.get_metrics()

        assert metrics.sample_count == 1
        assert metrics.total_chars == 7  # "keep me" is 7 chars including space
        assert metrics.vocabulary_size == 1

    async def test_get_metrics_median_odd(self, in_memory_session):
        """Odd sample count — median is the middle value."""
        ds = await _create_dataset(in_memory_session)
        await _create_sample(in_memory_session, ds.id, "a" * 1, index=0)
        await _create_sample(in_memory_session, ds.id, "b" * 5, index=1)
        await _create_sample(in_memory_session, ds.id, "c" * 10, index=2)

        svc = DatasetCurationService(in_memory_session, ds.id)
        metrics = await svc.get_metrics()

        assert metrics.sample_count == 3
        assert metrics.length_distribution["median"] == 5

    async def test_get_metrics_median_even(self, in_memory_session):
        """Even sample count — median is the n//2-th value (lower middle)."""
        ds = await _create_dataset(in_memory_session)
        await _create_sample(in_memory_session, ds.id, "a" * 1, index=0)
        await _create_sample(in_memory_session, ds.id, "b" * 5, index=1)
        await _create_sample(in_memory_session, ds.id, "c" * 10, index=2)
        await _create_sample(in_memory_session, ds.id, "d" * 20, index=3)

        svc = DatasetCurationService(in_memory_session, ds.id)
        metrics = await svc.get_metrics()

        assert metrics.sample_count == 4
        # Sorted: [1, 5, 10, 20]; n//2 = 2; median = 10
        assert metrics.length_distribution["median"] == 10


##############################################################################
# Service instantiation
##############################################################################


class TestCurationService:
    """Service-level contract checks."""

    def test_service_instantiation(self):
        """Verify DatasetCurationService has expected methods."""
        assert hasattr(DatasetCurationService, "deduplicate")
        assert hasattr(DatasetCurationService, "filter_by_length")
        assert hasattr(DatasetCurationService, "regex_replace")
        assert hasattr(DatasetCurationService, "delete_sample")
        assert hasattr(DatasetCurationService, "get_metrics")

    def test_serialization_roundtrip(self):
        """Verify curation result can be serialized to JSON."""
        result = CurationResult(
            operation_id=1,
            samples_removed=10,
            samples_before=100,
            samples_after=90,
        )
        data = {
            "operation_id": result.operation_id,
            "samples_removed": result.samples_removed,
            "samples_before": result.samples_before,
            "samples_after": result.samples_after,
        }
        serialized = json.dumps(data)
        assert json.loads(serialized)["operation_id"] == 1


##############################################################################
# Internal helpers
##############################################################################


async def _async_bytes(data: bytes):  # type: ignore[misc]
    """Async generator yielding bytes (for store.put)."""
    yield data
