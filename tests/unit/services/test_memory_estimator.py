"""Tests for the training memory estimator and OOM prediction."""

from anvil.gpu import GpuInfo
from anvil.services.training.memory_estimator import (
    MemoryEstimate,
    _compute_param_count,
    _format_count,
    estimate_training_memory,
)


class TestComputeParamCount:
    def test_matches_known_small_config(self):
        intermediate = int(8 * 16 / 3)
        embeddings = 2 * 50 * 16 + 16
        per_layer = 4 * 16 * 16 + 3 * intermediate * 16 + 2 * 16
        assert _compute_param_count(50, 16, 4, 1) == embeddings + per_layer

    def test_scales_with_layers(self):
        one = _compute_param_count(50, 16, 4, 1)
        two = _compute_param_count(50, 16, 4, 2)
        per_layer = 4 * 16 * 16 + 3 * int(8 * 16 / 3) * 16 + 2 * 16
        assert two - one == per_layer


class TestFormatCount:
    def test_millions(self):
        assert _format_count(9_500_000) == "9.5M"

    def test_thousands(self):
        assert _format_count(4_700) == "4.7K"

    def test_plain(self):
        assert _format_count(500) == "500"


class TestCpuMode:
    def test_cpu_never_ooms_and_has_no_available(self):
        est = estimate_training_memory(vocab_size=50)
        assert est.would_oom is False
        assert est.available_bytes is None
        assert est.available_mb is None
        assert est.available_gb is None
        assert est.utilization_pct is None
        assert any("CPU training" in w for w in est.warnings)

    def test_breakdown_components(self):
        est = estimate_training_memory(
            vocab_size=50, n_embd=16, n_head=4, n_layer=1, block_size=16
        )
        assert est.gradients_bytes == est.weights_bytes
        assert est.optimizer_bytes == est.weights_bytes * 2
        assert est.total_bytes == (
            est.weights_bytes
            + est.gradients_bytes
            + est.optimizer_bytes
            + est.kv_cache_bytes
        )
        assert est.peak_bytes == est.total_bytes * 2
        assert est.peak_mb == est.peak_bytes / (1024**2)
        assert est.peak_gb == est.peak_bytes / (1024**3)
        assert est.total_mb == est.total_bytes / (1024**2)

    def test_to_dict_with_no_gpu(self):
        d = estimate_training_memory(vocab_size=50).to_dict()
        assert d["available_mb"] is None
        assert d["available_gb"] is None
        assert d["utilization_pct"] is None
        assert d["would_oom"] is False
        assert d["param_count_formatted"].endswith("K")


class TestCudaPaths:
    def _cuda(self, total_gb, avail_gb):
        return GpuInfo(
            available=True,
            backend="cuda",
            device_name="TestGPU",
            memory_total_gb=total_gb,
            memory_available_gb=avail_gb,
        )

    def test_safe_run_within_range(self):
        est = estimate_training_memory(
            vocab_size=50,
            n_embd=16,
            n_head=4,
            n_layer=1,
            block_size=16,
            gpu_info=self._cuda(16, 14),
        )
        assert est.would_oom is False
        assert est.device_backend == "cuda"
        assert est.device_name == "TestGPU"
        assert est.utilization_pct is not None
        assert est.utilization_pct < 75

    def test_oom_when_peak_exceeds_block_threshold(self):
        est = estimate_training_memory(
            vocab_size=200,
            n_embd=256,
            n_head=8,
            n_layer=12,
            block_size=512,
            gpu_info=self._cuda(0.5, 0.3),
        )
        assert est.would_oom is True
        assert any("OOM" in w for w in est.warnings)

    def test_warn_band_between_75_and_90(self):
        base = estimate_training_memory(
            vocab_size=200,
            n_embd=128,
            n_head=4,
            n_layer=4,
            block_size=256,
            gpu_info=self._cuda(64, 64),
        )
        peak_gb = base.peak_bytes / (1024**3)
        avail_gb = peak_gb / 0.80
        est = estimate_training_memory(
            vocab_size=200,
            n_embd=128,
            n_head=4,
            n_layer=4,
            block_size=256,
            gpu_info=self._cuda(avail_gb, avail_gb),
        )
        assert est.would_oom is False
        assert est.utilization_pct is not None
        assert 75 <= est.utilization_pct < 90
        assert any("close to limit" in w for w in est.warnings)

    def test_cuda_without_available_falls_back_then_no_info(self):
        est = estimate_training_memory(
            vocab_size=50,
            gpu_info=GpuInfo(
                available=True,
                backend="cuda",
                device_name="NoMem",
                memory_total_gb=None,
                memory_available_gb=None,
            ),
        )
        assert est.available_bytes is None
        assert any("Could not determine" in w for w in est.warnings)
        assert any("memory info not available" in w for w in est.warnings)


class TestMpsPath:
    def test_mps_uses_total_as_ceiling(self):
        est = estimate_training_memory(
            vocab_size=200,
            n_embd=128,
            n_head=4,
            n_layer=4,
            block_size=256,
            gpu_info=GpuInfo(
                available=True,
                backend="mps",
                device_name="M3",
                memory_total_gb=16,
                memory_available_gb=None,
            ),
        )
        assert est.available_gb == 16.0
        assert est.device_backend == "mps"


class TestUnavailableGpu:
    def test_unavailable_gpu_falls_back_to_cpu(self):
        est = estimate_training_memory(
            vocab_size=50,
            gpu_info=GpuInfo(available=False),
        )
        assert est.would_oom is False
        assert any("CPU training" in w for w in est.warnings)


class TestToDictWithGpu:
    def test_to_dict_populates_gpu_fields(self):
        d = estimate_training_memory(
            vocab_size=50,
            gpu_info=GpuInfo(
                available=True,
                backend="cuda",
                device_name="TestGPU",
                memory_total_gb=16,
                memory_available_gb=14,
            ),
        ).to_dict()
        assert d["available_mb"] is not None
        assert d["available_gb"] == 14.0
        assert d["device_backend"] == "cuda"
        assert d["utilization_pct"] is not None