# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Cross-domain encryption-related exception classes.

Canonical error types for the encryption subsystem. All modules
in the encryption envelope import from this file.
"""

from __future__ import annotations


class UnknownKeyIdError(KeyError):
    """Envelope ``kid`` not found in the active key ring."""


class InvalidAadError(ValueError):
    """AAD mismatch — the supplied AAD does not match encryption-time AAD."""


class InvalidCiphertextError(ValueError):
    """Ciphertext was tampered with or decryption key is wrong."""


class InvalidEnvelopeError(ValueError):
    """Stored envelope token is malformed or fails validation."""


class RotationInProgressError(RuntimeError):
    """A rotation is already in progress; ``rotate()`` refused."""


class SweepIncompleteError(RuntimeError):
    """``expire_previous()`` refused because rows still reference the previous key."""
