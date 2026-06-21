# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for the core autograd engine."""

import math

from anvil.core.autograd import Value


def test_silu_forward():
    """T003: Value.silu() forward matches x * sigmoid(x)."""
    for x in [-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0, 3.0]:
        v = Value(x)
        result = v.silu()
        expected = x * (1 / (1 + math.exp(-x)))
        assert abs(result.data - expected) < 1e-6


def test_silu_gradient():
    """T003: Value.silu() backward matches numerical gradient."""
    for x in [-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0]:
        v = Value(x)
        loss = v.silu()
        loss.backward()
        # Analytical gradient: sigma(x) + x * sigma(x) * (1 - sigma(x))
        s = 1 / (1 + math.exp(-x))
        expected_grad = s + x * s * (1 - s)
        assert abs(v.grad - expected_grad) < 1e-6


def test_silu_gradient_numerical():
    """T003: Value.silu() backward matches finite-difference approximation."""
    eps = 1e-6
    for x in [-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0]:
        v = Value(x)
        loss = v.silu()
        loss.backward()
        analytical = v.grad

        # Numerical gradient: (f(x+eps) - f(x-eps)) / (2*eps)
        f_plus = (x + eps) * (1 / (1 + math.exp(-(x + eps))))
        f_minus = (x - eps) * (1 / (1 + math.exp(-(x - eps))))
        numerical = (f_plus - f_minus) / (2 * eps)

        assert abs(analytical - numerical) < 1e-4
