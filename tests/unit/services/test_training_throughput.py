# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ThroughputTracker and classify_divergence.

Pure logic — no mocking needed.
"""

from __future__ import annotations

import math

from anvil.services.training.divergence_reason import DivergenceReason
from anvil.services.training.throughput import ThroughputTracker, classify_divergence


class TestClassifyDivergence:
    def test_nan_loss(self):
        assert classify_divergence(float("nan")) == DivergenceReason.LOSS_NAN

    def test_inf_loss(self):
        assert classify_divergence(float("inf")) == DivergenceReason.LOSS_INF
        assert classify_divergence(float("-inf")) == DivergenceReason.LOSS_INF

    def test_normal_loss_returns_none(self):
        assert classify_divergence(0.5) is None
        assert classify_divergence(100.0) is None
        assert classify_divergence(-1.0) is None


class TestThroughputTracker:
    def test_initially_no_rate(self):
        t = ThroughputTracker(window=20)
        assert t.steps_per_sec is None
        assert t.tokens_per_sec is None
        assert t.eta_sec(0, 100) is None

    def test_single_record_no_rate(self):
        t = ThroughputTracker(window=20)
        t.record(100, 0.0)
        assert t.steps_per_sec is None
        assert t.tokens_per_sec is None

    def test_two_records_computes_rate(self):
        t = ThroughputTracker(window=20)
        t.record(100, 0.0)
        t.record(100, 1.0)
        assert t.steps_per_sec == 1.0
        assert t.tokens_per_sec == 200.0

    def test_eta_sec(self):
        t = ThroughputTracker(window=20)
        t.record(100, 0.0)
        t.record(100, 1.0)
        # step=5, total_steps=10 => remaining=4 steps, rate=1 step/sec => 4 sec
        assert t.eta_sec(5, 10) == 4.0

    def test_eta_sec_no_rate(self):
        t = ThroughputTracker(window=20)
        assert t.eta_sec(0, 100) is None

    def test_eta_sec_completed(self):
        t = ThroughputTracker(window=20)
        t.record(100, 0.0)
        t.record(100, 1.0)
        assert t.eta_sec(100, 100) == 0.0

    def test_window_limits(self):
        t = ThroughputTracker(window=3)
        for i in range(5):
            t.record(10, float(i))
        assert len(t._times) == 3
        assert len(t._tokens) == 3

    def test_zero_elapsed_returns_none(self):
        t = ThroughputTracker(window=20)
        t.record(100, 1.0)
        t.record(200, 1.0)
        assert t.steps_per_sec is None
