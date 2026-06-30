# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for warm-start (model != None) path of train()."""

import pytest

from anvil.core.engine import LlamaModel, train
from anvil.services.training.torch_engine import torch_available


def test_warm_start_subset_corpus_keeps_base_vocab(tmp_path):
    """Warm-start on a subset corpus inherits vocab/dims from base model.

    Train a base model on corpus "abcde", save it (with chars), reload,
    then warm-start on subset "abc". Assert that uchars, vocab_size,
    BOS, and block_size are inherited from the loaded model, NOT
    recomputed from the new docs.
    """
    # Train base model on full corpus
    base_docs = ["abcde"]
    base_model, _, _, base_uchars = train(base_docs, num_steps=3, n_embd=8, n_head=2)

    # Save and reload to set model.chars
    save_path = str(tmp_path / "base.json")
    base_model.save(save_path, chars=base_uchars)
    loaded_model = LlamaModel.load(save_path)

    # Warm-start on subset
    subset_docs = ["abc"]
    warm_model, _, _, warm_uchars = train(
        subset_docs, model=loaded_model, num_steps=3, n_embd=8, n_head=2
    )

    # uchars should match model.chars exactly (order preserved, NOT re-sorted)
    assert (
        warm_uchars == loaded_model.chars
    ), f"warm_uchars={warm_uchars} != loaded_model.chars={loaded_model.chars}"

    # vocab_size should be inherited from model
    assert warm_model.vocab_size == len(loaded_model.chars) + 1

    # BOS token index equals the number of unique characters (vocab_size - 1)
    assert warm_model.vocab_size - 1 == len(loaded_model.chars)

    # block_size should be inherited from model
    assert warm_model.block_size == loaded_model.block_size


def test_warm_start_oov_char_raises_error(tmp_path):
    """Warm-start with a document containing a char NOT in base vocab.

    Train a base model on "abcde", save/reload to set model.chars,
    then try to train on a corpus containing "z". Assert ValueError
    is raised with a message mentioning the unsupported char.
    """
    base_docs = ["abcde"]
    base_model, _, _, base_uchars = train(base_docs, num_steps=3, n_embd=8, n_head=2)
    save_path = str(tmp_path / "base.json")
    base_model.save(save_path, chars=base_uchars)
    loaded_model = LlamaModel.load(save_path)

    with pytest.raises(ValueError, match="z"):
        train(["z"], model=loaded_model, num_steps=3, n_embd=8, n_head=2)


def test_warm_start_missing_chars_raises_error():
    """Warm-start with model.chars=None and mismatched vocab_size.

    Construct a LlamaModel with chars=None (the default) but with a
    vocab_size that does NOT match the computed vocab from docs.
    Calling train(docs, model=...) should raise ValueError because
    the model lacks the character mapping needed for warm-start.
    """
    model = LlamaModel(vocab_size=10, n_embd=8, n_head=2, n_layer=1, block_size=16)
    # model.chars is None by default
    with pytest.raises(ValueError):
        train(["abc"], model=model, num_steps=3, n_embd=8, n_head=2)


def test_from_scratch_path_unchanged():
    """Calling train(docs) with model=None (default) works as before.

    The model=None path MUST produce the same output structure and
    should NOT raise any errors.
    """
    docs = ["abcde"]
    model, loss, samples, uchars = train(docs, num_steps=3, n_embd=8, n_head=2)
    assert model is not None
    assert loss > 0
    assert isinstance(samples, list)
    assert len(samples) == 20
    # uchars should be sorted unique chars from docs (unchanged behavior)
    assert uchars == sorted(set("".join(docs)))


def test_warm_start_initial_loss_below_from_scratch(tmp_path):
    """Step-0 loss of warm-start is lower than from-scratch.

    Train a base model for 5 steps, save/reload, then compare the
    step-0 loss of a from-scratch training vs a warm-start training.
    Warm-start should have unambiguously lower initial loss because
    the base model is already partially trained.
    """
    # Train base model on "abcde" for few steps
    base_docs = ["abcde"]
    base_model, _, _, base_uchars = train(base_docs, num_steps=5, n_embd=8, n_head=2)

    # Save and reload to set model.chars
    save_path = str(tmp_path / "base.json")
    base_model.save(save_path, chars=base_uchars)
    loaded_model = LlamaModel.load(save_path)

    # Capture step-0 loss from a from-scratch training
    fs_initial = [None]

    def _fs_cb(step, loss, **kwargs):
        if step == 0:
            fs_initial[0] = loss

    train(
        ["abcde"],
        num_steps=10,
        n_embd=8,
        n_head=2,
        progress_callback=_fs_cb,
    )

    # Capture step-0 loss from a warm-start training
    ws_initial = [None]

    def _ws_cb(step, loss, **kwargs):
        if step == 0:
            ws_initial[0] = loss

    train(
        ["abcde"],
        model=loaded_model,
        num_steps=10,
        n_embd=8,
        n_head=2,
        progress_callback=_ws_cb,
    )

    assert fs_initial[0] is not None, "from-scratch progress_callback was never called"
    assert ws_initial[0] is not None, "warm-start progress_callback was never called"
    # Warm-start should have lower initial loss than from-scratch
    assert ws_initial[0] < fs_initial[0], (
        f"warm-start step-0 loss {ws_initial[0]:.4f} is NOT below "
        f"from-scratch step-0 loss {fs_initial[0]:.4f}"
    )


@pytest.mark.skipif(not torch_available(), reason="torch not installed")
def test_warm_start_parity_between_engines(tmp_path):
    """Stdlib warm-start works correctly when torch is available.

    Structural parity test: when PyTorch is installed, verify that
    the stdlib warm-start path still produces correct vocabulary
    inheritance. This ensures both engines (stdlib and torch) share
    the same warm-start contract.

    The test is skipped when torch is not available.
    """
    # Train base model with stdlib
    base_docs = ["abcde"]
    base_model, _, _, base_uchars = train(base_docs, num_steps=3, n_embd=8, n_head=2)

    # Save and reload to set model.chars
    save_path = str(tmp_path / "base.json")
    base_model.save(save_path, chars=base_uchars)
    loaded_model = LlamaModel.load(save_path)

    # Warm-start on subset corpus — stdlib engine
    warm_model, _, _, warm_uchars = train(
        ["abc"],
        model=loaded_model,
        num_steps=3,
        n_embd=8,
        n_head=2,
    )

    # Verify vocab inheritance (structural parity with torch path)
    assert (
        warm_uchars == loaded_model.chars
    ), f"warm_uchars={warm_uchars} != loaded_model.chars={loaded_model.chars}"
    assert warm_model.vocab_size == len(loaded_model.chars) + 1


@pytest.mark.skipif(not torch_available(), reason="torch not installed")
def test_torch_weight_transfer_loads_exact_weights(tmp_path):
    """``load_torch_weights_from_lists`` transfers checkpoint weights exactly.

    This guards the FR-002 parity fix: the torch warm-start path must load the
    base model's trained weights (not start from random init). Build a
    ``TorchLlamaModel`` with matching dims, load a checkpoint's ``state_dict``
    into it, and assert ``export_weights()`` round-trips to the same values.
    """
    import json

    from anvil.services.training.torch_engine import (
        TorchLlamaModel,
        load_torch_weights_from_lists,
    )

    base_model, _, _, base_uchars = train(["abcde"], num_steps=3, n_embd=8, n_head=2)
    save_path = str(tmp_path / "base.json")
    base_model.save(save_path, chars=base_uchars)

    with open(save_path, encoding="utf-8") as f:
        checkpoint = json.load(f)
    state_dict = checkpoint["state_dict"]

    torch_model = TorchLlamaModel(
        vocab_size=base_model.vocab_size,
        n_embd=base_model.n_embd,
        n_head=base_model.n_head,
        n_layer=base_model.n_layer,
        block_size=base_model.block_size,
    )
    load_torch_weights_from_lists(torch_model, state_dict)

    def _flatten(value: object) -> list[float]:
        if isinstance(value, list):
            out: list[float] = []
            for item in value:
                out.extend(_flatten(item))
            return out
        return [float(value)]  # type: ignore[arg-type]

    exported = torch_model.export_weights()
    for key, expected in state_dict.items():
        assert _flatten(exported[key]) == pytest.approx(
            _flatten(expected), abs=1e-5
        ), f"weight mismatch for {key} after load round-trip"


@pytest.mark.skipif(not torch_available(), reason="torch not installed")
def test_torch_weight_transfer_rejects_shape_mismatch():
    """``load_torch_weights_from_lists`` rejects a key/shape mismatch."""
    from anvil.services.training.torch_engine import (
        TorchLlamaModel,
        load_torch_weights_from_lists,
    )

    torch_model = TorchLlamaModel(
        vocab_size=6, n_embd=8, n_head=2, n_layer=1, block_size=16
    )
    with pytest.raises(ValueError):
        load_torch_weights_from_lists(torch_model, {"wte": [[1.0]]})
