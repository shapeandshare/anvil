"""Tests for microgpt.config.get_config()."""

import os

import pytest
from microgpt import config as _cfg_mod
from microgpt.config import get_config, get_mlflow_uri, set_resolved_mlflow_uri


def test_mlflow_uri_defaults_to_http():
    cfg = get_config()
    assert cfg["mlflow_uri"] == "http://127.0.0.1:5001"
    assert cfg["mlflow_port"] == 5001


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


def test_get_mlflow_uri_returns_resolved_uri_when_set():
    original = _cfg_mod._resolved_mlflow_uri
    set_resolved_mlflow_uri("http://192.168.1.50:5000")
    try:
        assert get_mlflow_uri() == "http://192.168.1.50:5000"
    finally:
        _cfg_mod._resolved_mlflow_uri = original


def test_get_mlflow_uri_returns_config_when_no_resolved():
    original = _cfg_mod._resolved_mlflow_uri
    _cfg_mod._resolved_mlflow_uri = None
    try:
        assert get_mlflow_uri() == get_config()["mlflow_uri"]
    finally:
        _cfg_mod._resolved_mlflow_uri = original
