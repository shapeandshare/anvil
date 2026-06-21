# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Compute backend abstraction layer.

Defines a protocol for remote compute backends (Modal, local torch,
local stdlib) and provides resolution logic for selecting and
instantiating the appropriate backend at runtime.
"""
