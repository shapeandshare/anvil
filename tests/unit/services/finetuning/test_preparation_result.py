# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for PreparationResult value object."""

from __future__ import annotations

import json

import pytest

from anvil.services.finetuning.preparation_result import PreparationResult


def test_construction():
    """PreparationResult stores all fields correctly."""
    result = PreparationResult(
        job_id=42,
        total=100,
        succeeded=98,
        failed=2,
        errors=[{"row": 5, "error": "Empty response"}],
    )
    assert result.job_id == 42
    assert result.total == 100
    assert result.succeeded == 98
    assert result.failed == 2
    assert len(result.errors) == 1
    assert result.errors[0]["error"] == "Empty response"


def test_to_summary_json():
    """to_summary_json produces a JSON-serializable dict."""
    result = PreparationResult(
        job_id=42,
        total=100,
        succeeded=98,
        failed=2,
        errors=[{"row": 5, "error": "Empty response"}],
    )
    summary = result.to_summary_json()
    assert summary["total"] == 100
    assert summary["succeeded"] == 98
    assert summary["failed"] == 2
    assert len(summary["errors"]) == 1

    # Must be JSON-serializable
    serialized = json.dumps(summary)
    parsed = json.loads(serialized)
    assert parsed["total"] == 100


def test_from_summary_json():
    """from_summary_json reconstructs a PreparationResult from a JSON string."""
    json_str = json.dumps(
        {
            "total": 50,
            "succeeded": 48,
            "failed": 2,
            "errors": [{"row": 10, "error": "Bad record"}],
        }
    )
    result = PreparationResult.from_summary_json(42, json_str)
    assert result.job_id == 42
    assert result.total == 50
    assert result.succeeded == 48
    assert result.failed == 2
    assert result.errors[0]["row"] == 10


def test_empty_errors():
    """PreparationResult handles empty error lists."""
    result = PreparationResult(job_id=1, total=0, succeeded=0, failed=0, errors=[])
    assert result.failed == 0
    assert result.to_summary_json()["errors"] == []


def test_all_failed():
    """PreparationResult handles all-records-failed case."""
    result = PreparationResult(
        job_id=3,
        total=5,
        succeeded=0,
        failed=5,
        errors=[{"row": i, "error": "Fail"} for i in range(5)],
    )
    assert result.succeeded == 0
    assert len(result.errors) == 5
