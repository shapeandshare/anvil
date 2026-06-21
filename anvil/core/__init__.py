# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Stdlib-only training engine for small transformer language models.

``anvil.core`` contains the zero-dependency training engine — the
fundamental transformer implementation with RoPE, SwiGLU MLP, and
RMSNorm, plus a pure-Python autograd engine and byte-level tokenizer.
All modules in this package have no third-party Python dependencies.
"""
