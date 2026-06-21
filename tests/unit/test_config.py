# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for anvil.config.get_config()."""

import os

import pytest

from anvil import config as _cfg_mod
from anvil.config import (
    get_config,
    get_mlflow_browser_uri,
    get_mlflow_uri,
    set_resolved_mlflow_uri,
)

# Test fixture IP addresses — these are intentionally hardcoded test values
# used only in assertions and mock setups, not in production code.
_RESOLVED_URI_IP: str = "192.168.1.50"
_REQUEST_HOST_IP: str = "192.168.1.10"
_IPV4_IP: str = "10.0.0.5"


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
    monkeypatch.setenv("ANVIL_MLFLOW_URI", "http://custom:5001")
    get_config.cache_clear()
    try:
        cfg = get_config()
        assert cfg["mlflow_uri"] == "http://custom:5001"
    finally:
        get_config.cache_clear()


def test_get_mlflow_uri_returns_resolved_uri_when_set():
    original = _cfg_mod._resolved_mlflow_uri
    set_resolved_mlflow_uri(f"http://{_RESOLVED_URI_IP}:5000")
    try:
        assert get_mlflow_uri() == f"http://{_RESOLVED_URI_IP}:5000"
    finally:
        _cfg_mod._resolved_mlflow_uri = original


def test_get_mlflow_uri_returns_config_when_no_resolved():
    original = _cfg_mod._resolved_mlflow_uri
    _cfg_mod._resolved_mlflow_uri = None
    try:
        assert get_mlflow_uri() == get_config()["mlflow_uri"]
    finally:
        _cfg_mod._resolved_mlflow_uri = original


def test_mlflow_disable_local_defaults_false_for_localhost():
    cfg = get_config()
    assert cfg["mlflow_disable_local"] is False


def test_mlflow_disable_local_explicit_true(monkeypatch):
    monkeypatch.setenv("ANVIL_MLFLOW_DISABLE_LOCAL", "true")
    get_config.cache_clear()
    try:
        cfg = get_config()
        assert cfg["mlflow_disable_local"] is True
    finally:
        get_config.cache_clear()


def test_mlflow_disable_local_explicit_false(monkeypatch):
    monkeypatch.setenv("ANVIL_MLFLOW_DISABLE_LOCAL", "false")
    get_config.cache_clear()
    try:
        cfg = get_config()
        assert cfg["mlflow_disable_local"] is False
    finally:
        get_config.cache_clear()


def test_mlflow_disable_local_remote_uri_no_env_var_stays_false(monkeypatch):
    """A remote URI alone does NOT disable local server — must set env var."""
    monkeypatch.setenv("ANVIL_MLFLOW_URI", "https://mlflow.example.com")
    get_config.cache_clear()
    try:
        cfg = get_config()
        assert cfg["mlflow_disable_local"] is False
        assert cfg["mlflow_uri"] == "https://mlflow.example.com"
    finally:
        get_config.cache_clear()


class _FakeRequest:
    """Minimal request stub for testing get_mlflow_browser_uri."""

    def __init__(self, host_header: str):
        self.headers = {"host": host_header}


def test_get_mlflow_browser_uri_uses_request_host():
    request = _FakeRequest(f"{_REQUEST_HOST_IP}:8080")
    uri = get_mlflow_browser_uri(request)
    assert uri == f"http://{_REQUEST_HOST_IP}:5001"


def test_get_mlflow_browser_uri_localhost():
    request = _FakeRequest("localhost:8080")
    uri = get_mlflow_browser_uri(request)
    assert uri == "http://localhost:5001"


def test_get_mlflow_browser_uri_no_port_in_host():
    request = _FakeRequest("myhost.local")
    uri = get_mlflow_browser_uri(request)
    assert uri == "http://myhost.local:5001"


def test_get_mlflow_browser_uri_ipv4_no_port():
    request = _FakeRequest(_IPV4_IP)
    uri = get_mlflow_browser_uri(request)
    assert uri == f"http://{_IPV4_IP}:5001"
