# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for the torch training engine.

Verifies that ``torch_Tensor`` is importable at runtime (not hidden behind
``TYPE_CHECKING``) and that ``train_torch`` functions correctly.
"""

import pytest

from anvil.core.torch_engine import (
    _TORCH_AVAILABLE,
    torch_available,
    torch_Tensor,
    train_torch,
)


def test_torch_tensor_importable_at_runtime():
    """torch_Tensor must be importable outside TYPE_CHECKING.

    Regression guard: ``torch.Tensor`` was previously aliased inside
    ``if TYPE_CHECKING:`` but used at runtime via ``cast(torch_Tensor, ...)``
    on line 323, causing ``NameError`` when the torch backend ran.
    """
    # torch_Tensor should be available as a class, not just a type alias
    assert torch_Tensor is not None
    # It should be torch.Tensor
    assert torch_Tensor.__name__ == "Tensor"


@pytest.mark.skipif(not _TORCH_AVAILABLE, reason="torch not installed")
def test_torch_available_true():
    """torch_available() returns True when torch is importable."""
    assert torch_available() is True


@pytest.mark.skipif(not _TORCH_AVAILABLE, reason="torch not installed")
def test_train_torch_runs():
    """train_torch runs a small model end-to-end without error."""
    docs = ["hello world"]
    raw_weights, final_loss, samples, uchars = train_torch(
        docs,
        device="cpu",
        num_steps=3,
        n_embd=8,
        n_head=4,
        n_layer=1,
        block_size=8,
    )
    assert isinstance(final_loss, float)
    assert final_loss > 0
    assert len(samples) == 20
    assert len(uchars) > 0
    assert raw_weights is not None
    assert "wte" in raw_weights
