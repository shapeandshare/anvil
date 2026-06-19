"""Compute backend abstraction layer.

Defines a protocol for remote compute backends (Modal, local torch,
local stdlib) and provides resolution logic for selecting and
instantiating the appropriate backend at runtime.
"""
