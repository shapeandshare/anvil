# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Encryption algorithm enumeration for the self-describing envelope."""

from __future__ import annotations

from enum import StrEnum


class EncryptionAlgorithm(StrEnum):
    """Supported symmetric encryption algorithms for secret values.

    Each member corresponds to a specific cipher + mode combination
    used in ``EncryptionEnvelope.alg``.
    """

    AES_256_GCM = "aes-256-gcm"
    """AES-256 in Galois/Counter Mode with a 96-bit random nonce."""
