# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ComputeResult and ComputeStatus."""


from anvil.services.compute.compute_status import ComputeStatus
from anvil.services.compute.result import ComputeResult


class TestComputeStatus:
    def test_enum_values(self):
        assert ComputeStatus.SUBMITTED.value == "submitted"
        assert ComputeStatus.RUNNING.value == "running"
        assert ComputeStatus.COMPLETED.value == "completed"
        assert ComputeStatus.FAILED.value == "failed"

    def test_enum_is_str(self):
        assert isinstance(ComputeStatus.COMPLETED, str)


class TestComputeResult:
    def test_local_defaults(self):
        result = ComputeResult(status=ComputeStatus.COMPLETED)
        assert result.status == ComputeStatus.COMPLETED
        assert result.model is None
        assert result.final_loss is None
        assert result.samples == []
        assert result.uchars == []
        assert result.exported_remotely is False
        assert result.artifact_uris == {}
        assert result.remote_job_id is None
        assert result.error_message is None
        assert result.engine == "stdlib"
        assert result.backend == "local"

    def test_local_with_model(self):
        model = object()
        result = ComputeResult(
            status=ComputeStatus.COMPLETED,
            model=model,
            final_loss=0.5,
            samples=["hello"],
            uchars=["h", "e", "l", "o"],
            engine="torch",
            backend="local",
        )
        assert result.model is model
        assert result.final_loss == 0.5
        assert result.engine == "torch"

    def test_remote_path(self):
        result = ComputeResult(
            status=ComputeStatus.SUBMITTED,
            exported_remotely=True,
            artifact_uris={"safetensors": "s3://bucket/model.safetensors"},
            remote_job_id="job_123",
            remote_mlflow_run_id="run_abc",
            backend="modal",
        )
        assert result.exported_remotely is True
        assert result.artifact_uris["safetensors"] == "s3://bucket/model.safetensors"
        assert result.remote_job_id == "job_123"
        assert result.backend == "modal"

    def test_failed(self):
        result = ComputeResult(
            status=ComputeStatus.FAILED,
            error_message="something broke",
        )
        assert result.status == ComputeStatus.FAILED
        assert result.error_message == "something broke"

    def test_fields_use_factory(self):
        r1 = ComputeResult(status=ComputeStatus.COMPLETED)
        r2 = ComputeResult(status=ComputeStatus.COMPLETED)
        assert r1.samples is not r2.samples
        assert r1.artifact_uris is not r2.artifact_uris
