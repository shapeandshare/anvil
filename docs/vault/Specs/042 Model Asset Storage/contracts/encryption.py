# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Encryption contract for UserSecret value protection.

Uses AES-256-GCM via the ``cryptography`` library (already in the
dependency tree as a transitive dep of mlflow). The master key is
derived from the ``ANVIL_MASTER_SECRET`` env var, or auto-generated
and persisted with ``0600`` permissions on first boot (same pattern
as ``ApiKeyStore``).
"""

from __future__ import annotations

from typing import Protocol


class EncryptionService(Protocol):
    """Encrypts and decrypts secret values for the UserSecret model.

    The implementation uses AES-256-GCM with a random 96-bit nonce.
    Ciphertext is returned as base64-encoded ``nonce + ciphertext``.
    """

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string.

        Returns a base64-encoded token containing nonce + ciphertext.
        """
        ...

    def decrypt(self, token: str) -> str:
        """Decrypt a base64-encoded token back to plaintext.

        Raises
        ------
        DecryptionError
            If the token is malformed, the key is wrong, or integrity
            check fails (AEAD authentication tag mismatch).
        """
        ...
