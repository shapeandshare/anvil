"""Tests for microgpt.config.get_config()."""

import os

from microgpt.config import get_config


def test_mlflow_uri_defaults_to_http():
    cfg = get_config()
    assert cfg["mlflow_uri"] == "http://127.0.0.1:5000"


def test_mlflow_backend_store_uri_is_absolute_sqlite():
    cfg = get_config()
    uri = cfg["mlflow_backend_store_uri"]
    assert uri.startswith("sqlite:///")
    assert "/./" not in uri
    assert "mlruns/mlflow.db" in uri


def test_mlflow_uri_env_override(monkeypatch):
    monkeypatch.setenv("MICROGPT_MLFLOW_URI", "http://custom:5001")
    get_config.cache_clear()
    try:
        cfg = get_config()
        assert cfg["mlflow_uri"] == "http://custom:5001"
    finally:
        get_config.cache_clear()
