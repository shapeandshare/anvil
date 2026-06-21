# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for supervisor MLflowService config integration."""

from anvil.config import get_config
from anvil.supervisor.services import MLflowService


def test_mlflow_service_backend_store_from_config():
    svc = MLflowService()
    cfg = get_config()
    expected = cfg["mlflow_backend_store_uri"]
    assert expected.startswith("sqlite:///")
    actual = svc._backend_store_uri
    assert actual == expected


def test_mlflow_service_tracking_uri_from_config():
    svc = MLflowService()
    cfg = get_config()
    assert svc.tracking_uri == cfg["mlflow_uri"]
    assert svc.tracking_uri == "http://127.0.0.1:5001"
    assert svc.port == 5001


def test_mlflow_service_no_hardcoded_sqlite_path():
    svc = MLflowService()
    assert "sqlite:///./mlruns" not in svc.tracking_uri
    assert "sqlite:///./mlruns" not in svc._backend_store_uri
