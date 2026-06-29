# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for CoreStepObservation NamedTuple.

Verifies construction, field defaults, attribute access, type
annotations, and serialization (tuple unpacking, dict conversion).
"""

from __future__ import annotations

from anvil.core.step_observation import CoreStepObservation


def test_constructor_sets_all_fields() -> None:
    """All positional fields are set in order."""
    obs = CoreStepObservation(42, 1.5, 512, 0.75)
    assert obs.step == 42
    assert obs.loss == 1.5
    assert obs.tokens == 512
    assert obs.grad_norm == 0.75


def test_grad_norm_can_be_none() -> None:
    """grad_norm is typed as float | None and can be None."""
    obs = CoreStepObservation(0, 0.0, 0, None)
    assert obs.grad_norm is None


def test_loss_can_be_non_finite() -> None:
    """Loss field accepts nan and inf values (edge case for divergence)."""
    import math

    obs_nan = CoreStepObservation(1, math.nan, 100, None)
    assert math.isnan(obs_nan.loss)

    obs_inf = CoreStepObservation(2, math.inf, 100, None)
    assert math.isinf(obs_inf.loss)


def test_tuple_unpacking() -> None:
    """CoreStepObservation is a tuple and supports unpacking."""
    obs = CoreStepObservation(10, 2.5, 256, 0.3)
    step, loss, tokens, grad_norm = obs
    assert step == 10
    assert loss == 2.5
    assert tokens == 256
    assert grad_norm == 0.3


def test_index_access() -> None:
    """Fields are accessible by position (tuple behaviour)."""
    obs = CoreStepObservation(5, 3.0, 128, None)
    assert obs[0] == 5
    assert obs[1] == 3.0
    assert obs[2] == 128
    assert obs[3] is None


def test_len() -> None:
    """NamedTuple has correct length."""
    obs = CoreStepObservation(0, 0.0, 0, None)
    assert len(obs) == 4


def test_equality() -> None:
    """Two identical observations are equal."""
    a = CoreStepObservation(1, 0.5, 64, 0.1)
    b = CoreStepObservation(1, 0.5, 64, 0.1)
    assert a == b


def test_inequality() -> None:
    """Observations with different fields are not equal."""
    a = CoreStepObservation(1, 0.5, 64, 0.1)
    b = CoreStepObservation(2, 0.5, 64, 0.1)
    assert a != b


def test_as_dict_via_private_fields() -> None:
    """CoreStepObservation has NamedTuple._as_dict() for serialization."""
    obs = CoreStepObservation(3, 1.2, 200, 0.05)
    d = obs._asdict()
    assert d == {"step": 3, "loss": 1.2, "tokens": 200, "grad_norm": 0.05}


def test_repr() -> None:
    """CoreStepObservation has a human-readable repr."""
    obs = CoreStepObservation(7, 0.9, 300, 0.15)
    r = repr(obs)
    assert "CoreStepObservation" in r
    assert "step=7" in r
    assert "loss=0.9" in r
    assert "tokens=300" in r
    assert "grad_norm=0.15" in r


def test_zero_values() -> None:
    """Edge case: all fields zero is valid."""
    obs = CoreStepObservation(0, 0.0, 0, 0.0)
    assert obs.step == 0
    assert obs.loss == 0.0
    assert obs.tokens == 0
    assert obs.grad_norm == 0.0
