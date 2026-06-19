"""Tests for mlflow capability detection."""

from anvil.services.tracking.mlflow_capabilities import (
    TrackingCapabilities,
    detect_capabilities,
)


def test_detect_capabilities_server_backed():
    caps = detect_capabilities("http://127.0.0.1:5000")
    assert caps.server_backed is True
    assert caps.mlflow_version.startswith("3.")
    assert isinstance(caps.genai_datasets, bool)


def test_detect_capabilities_file_store():
    caps = detect_capabilities("sqlite:///./mlruns/mlflow.db")
    assert caps.server_backed is False
    assert caps.genai_datasets is False


def test_detect_capabilities_genai_unavailable(monkeypatch):
    import builtins

    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "mlflow.genai.datasets":
            raise ImportError("no genai")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    caps = detect_capabilities("http://127.0.0.1:5000")
    assert caps.genai_datasets is False


def test_detect_capabilities_version():
    caps = detect_capabilities("http://127.0.0.1:5000")
    parts = caps.mlflow_version.split(".")
    assert len(parts) >= 2
    int(parts[0])
    int(parts[1])
