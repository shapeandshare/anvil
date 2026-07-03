"""Tests for shared enum types in services._shared.

Covers small StrEnum classes that define domain constants but contain
no complex logic.  Each test validates member values and type identity.
"""

from __future__ import annotations

from anvil.services._shared.device_type import DeviceType
from anvil.services._shared.evaluation_status import EvaluationRunStatus
from anvil.services._shared.fine_tune_dataset_status import FineTuneDatasetStatus
from anvil.services._shared.model_import_job_status import ModelImportJobStatus
from anvil.services._shared.runnable_status import RunnableStatus
from anvil.services._shared.serialization_type import SerializationType
from anvil.services._shared.source_type import SourceType
from anvil.services._shared.tokenizer_family import TokenizerFamily


class TestDeviceType:
    """DeviceType enum values and to_torch_device conversion."""

    def test_member_values(self) -> None:
        assert DeviceType.CPU.value == "cpu"
        assert DeviceType.CUDA.value == "cuda"
        assert DeviceType.MPS.value == "mps"

    def test_to_torch_device_cpu(self) -> None:
        assert DeviceType.CPU.to_torch_device() == "cpu"

    def test_to_torch_device_cuda(self) -> None:
        assert DeviceType.CUDA.to_torch_device() == "cuda:0"

    def test_to_torch_device_mps(self) -> None:
        assert DeviceType.MPS.to_torch_device() == "mps"


class TestEvaluationRunStatus:
    """EvaluationRunStatus enum values."""

    def test_member_values(self) -> None:
        assert EvaluationRunStatus.PENDING.value == "pending"
        assert EvaluationRunStatus.RUNNING.value == "running"
        assert EvaluationRunStatus.COMPLETED.value == "completed"
        assert EvaluationRunStatus.FAILED.value == "failed"


class TestFineTuneDatasetStatus:
    """FineTuneDatasetStatus enum values."""

    def test_member_values(self) -> None:
        assert FineTuneDatasetStatus.PREPARING.value == "preparing"
        assert FineTuneDatasetStatus.READY.value == "ready"
        assert FineTuneDatasetStatus.FAILED.value == "failed"


class TestModelImportJobStatus:
    """ModelImportJobStatus enum values."""

    def test_member_values(self) -> None:
        assert ModelImportJobStatus.QUEUED.value == "queued"
        assert ModelImportJobStatus.RESOLVING.value == "resolving"
        assert ModelImportJobStatus.COMPLETE.value == "complete"
        assert ModelImportJobStatus.FAILED.value == "failed"


class TestRunnableStatus:
    """RunnableStatus enum values."""

    def test_member_values(self) -> None:
        assert RunnableStatus.RUNNABLE.value == "runnable"
        assert RunnableStatus.TRACK_ONLY.value == "track_only"


class TestSerializationType:
    """SerializationType enum values."""

    def test_member_values(self) -> None:
        assert SerializationType.CHAR_JSON.value == "char_json"
        assert SerializationType.HF_FAST.value == "hf_fast"
        assert SerializationType.SENTENCEPIECE.value == "sentencepiece"


class TestSourceType:
    """SourceType enum values."""

    def test_member_values(self) -> None:
        assert SourceType.HUGGINGFACE.value == "huggingface"
        assert SourceType.LOCAL.value == "local"


class TestTokenizerFamily:
    """TokenizerFamily enum values."""

    def test_member_values(self) -> None:
        assert TokenizerFamily.CHAR.value == "char"
        assert TokenizerFamily.SUBWORD.value == "subword"
