# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for per-step metrics, divergence detection, and throughput.

Covers the neutral signal-instrumentation value objects and the rolling
throughput / divergence helpers used by ``TrainingService`` (feature
015-theme-engine, US2).
"""

import pytest
from pydantic import ValidationError

from anvil.core.step_observation import CoreStepObservation
from anvil.services.training.divergence_error import DivergenceError
from anvil.services.training.divergence_reason import DivergenceReason
from anvil.services.training.step_metrics import StepMetrics
from anvil.services.training.throughput import ThroughputTracker, classify_divergence


def test_step_metrics_accepts_nullable_signal_fields():
    m = StepMetrics(step=1, loss=2.5, device="cpu", elapsed_sec=1.0)
    assert m.grad_norm is None
    assert m.tokens_per_sec is None


def test_step_metrics_forbids_theme_specific_extras():
    with pytest.raises(ValidationError):
        StepMetrics(step=1, loss=2.5, device="cpu", elapsed_sec=1.0, disturbance=0.9)


def test_core_step_observation_carries_tokens_and_optional_grad_norm():
    obs = CoreStepObservation(step=3, loss=1.2, tokens=16, grad_norm=None)
    assert obs.tokens == 16
    assert obs.grad_norm is None


def test_classify_divergence_detects_nan_and_inf():
    assert classify_divergence(float("nan")) is DivergenceReason.LOSS_NAN
    assert classify_divergence(float("inf")) is DivergenceReason.LOSS_INF
    assert classify_divergence(-float("inf")) is DivergenceReason.LOSS_INF
    assert classify_divergence(2.5) is None


def test_divergence_error_carries_step_and_reason():
    err = DivergenceError(step=42, reason=DivergenceReason.LOSS_NAN)
    assert err.step == 42
    assert err.reason is DivergenceReason.LOSS_NAN


def test_tokens_per_sec_is_rolling_sum_over_window_not_batch_times_ctx():
    tracker = ThroughputTracker(window=10)
    t = 100.0
    tracker.record(tokens=10, now=t)
    assert tracker.tokens_per_sec is None
    tracker.record(tokens=30, now=t + 1.0)
    assert tracker.tokens_per_sec == pytest.approx(40.0)


def test_tokens_per_sec_handles_variable_per_step_tokens():
    tracker = ThroughputTracker(window=10)
    base = 0.0
    tracker.record(tokens=5, now=base)
    tracker.record(tokens=7, now=base + 1.0)
    tracker.record(tokens=12, now=base + 2.0)
    assert tracker.tokens_per_sec == pytest.approx(12.0)


def test_throughput_steps_per_sec_and_none_until_two_samples():
    tracker = ThroughputTracker(window=20)
    tracker.record(tokens=8, now=0.0)
    assert tracker.steps_per_sec is None
    tracker.record(tokens=8, now=0.5)
    assert tracker.steps_per_sec == pytest.approx(2.0)


def test_eta_none_until_rate_available():
    tracker = ThroughputTracker(window=20)
    tracker.record(tokens=8, now=0.0)
    assert tracker.eta_sec(step=0, total_steps=100) is None
