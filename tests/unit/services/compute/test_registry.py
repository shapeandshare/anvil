# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for compute backend registry."""


import pytest

from anvil.services.compute.compute_backend_unavailable import ComputeBackendUnavailable


class _FakeBackend:
    def __init__(self, name: str = "fake", available: bool = True):
        self.name = name
        self._available = available

    def is_available(self) -> bool:
        return self._available

    async def run(self, docs, config, *, progress_callback, stop_check):
        from anvil.services.compute.compute_status import ComputeStatus
        from anvil.services.compute.result import ComputeResult

        return ComputeResult(status=ComputeStatus.COMPLETED)


def test_register_and_get():
    from anvil.services.compute.registry import get_backend, register

    register("test-fake", lambda: _FakeBackend("test-fake"))
    backend = get_backend("test-fake")
    assert backend.name == "test-fake"
    assert backend.is_available() is True


def test_get_unknown_raises():
    from anvil.services.compute.registry import get_backend

    with pytest.raises(ComputeBackendUnavailable):
        get_backend("nonexistent")


def test_available_backends():
    from anvil.services.compute.registry import available_backends, register

    register("test-available", lambda: _FakeBackend("test-available", available=True))
    register(
        "test-unavailable", lambda: _FakeBackend("test-unavailable", available=False)
    )

    backends = available_backends()
    avail = {b["value"]: b["available"] for b in backends}
    assert avail.get("test-available") is True
    assert avail.get("test-unavailable") is False


def test_available_backends_handles_factory_failure():
    from anvil.services.compute.registry import available_backends, register

    def _failing():
        raise RuntimeError("fail")

    register("test-crash", _failing)
    backends = available_backends()
    crashed = [b for b in backends if b["value"] == "test-crash"]
    assert len(crashed) == 1
    assert crashed[0]["available"] is False


def test_get_passes_deps():
    from anvil.services.compute.registry import get_backend, register

    class _DepFake:
        name = "dep-fake"

        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def is_available(self):
            return True

        async def run(self, docs, config, *, progress_callback, stop_check):
            from anvil.services.compute.compute_status import ComputeStatus
            from anvil.services.compute.result import ComputeResult

            return ComputeResult(status=ComputeStatus.COMPLETED)

    register("dep-fake", lambda **kw: _DepFake(**kw))
    backend = get_backend("dep-fake", foo="bar")
    assert backend.name == "dep-fake"
