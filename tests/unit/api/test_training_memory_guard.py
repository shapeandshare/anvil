"""Tests for the pre-flight GPU memory (OOM) guard on /training/start."""

import pytest
from httpx import ASGITransport, AsyncClient

from anvil.api.app import app
from anvil.db.base import Base
from anvil.db.session import async_engine
from anvil.gpu import GpuInfo
from anvil.services._shared.device_type import DeviceType


@pytest.fixture
async def db_ready():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def _tiny_cuda():
    return GpuInfo(
        available=True,
        backend="cuda",
        device_name="TinyGPU",
        memory_total_gb=0.5,
        memory_available_gb=0.3,
    )


@pytest.mark.asyncio
async def test_oom_config_rejected_with_422(db_ready, monkeypatch):
    from anvil.api.v1 import training as training_module

    monkeypatch.setattr(training_module, "detect_gpu", _tiny_cuda)
    monkeypatch.setattr(
        "anvil.services.compute.resolve._detect_device",
        lambda: DeviceType.CUDA,
    )

    svc = training_module.svc
    running_before = svc._running

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/training/start",
            json={
                "n_embd": 256,
                "n_layer": 12,
                "n_head": 8,
                "block_size": 512,
                "num_steps": 1,
            },
        )

    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "OOM" in detail
    assert "GB" in detail
    assert svc._running == running_before


@pytest.mark.asyncio
async def test_oom_guard_skipped_for_cpu(db_ready, monkeypatch):
    from anvil.api.v1 import training as training_module

    called = {"detect": False}

    def _should_not_block():
        called["detect"] = True
        return _tiny_cuda()

    monkeypatch.setattr(training_module, "detect_gpu", _should_not_block)
    monkeypatch.setattr(
        "anvil.services.compute.resolve._detect_device",
        lambda: DeviceType.CPU,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/training/start",
            json={
                "n_embd": 256,
                "n_layer": 12,
                "n_head": 8,
                "block_size": 512,
                "num_steps": 1,
            },
        )

    assert resp.status_code != 422
