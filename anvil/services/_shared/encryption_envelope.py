# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Self-describing encryption envelope model.

The envelope carries all metadata needed to decrypt: schema version,
algorithm identifier, key id, nonce, and ciphertext — so stored
values are self-describing and rotatable.
"""

from __future__ import annotations

import base64
import json

from pydantic import BaseModel, field_validator

from .encryption_algorithm import EncryptionAlgorithm


class EncryptionEnvelope(BaseModel):
    """Self-describing JSON envelope for encrypted secret values.

    Fields
    ------
    v : int
        Schema version. Currently ``1``. Bumped on AAD scheme changes.
    alg : str
        Algorithm identifier from ``EncryptionAlgorithm`` (e.g. ``"aes-256-gcm"``).
    kid : str
        Key identifier — references a key in the active ``KeyRing``.
    n : str
        Base64-encoded 96-bit (12-byte) random nonce.
    ct : str
        Base64-encoded AES-256-GCM ciphertext (includes GCM auth tag).
    """

    v: int = 1
    alg: str = EncryptionAlgorithm.AES_256_GCM
    kid: str
    n: str
    ct: str

    @field_validator("v")
    @classmethod
    def _version_must_be_1(cls, value: int) -> int:
        if value != 1:
            raise ValueError(f"Unsupported envelope version: {value}")
        return value

    @field_validator("alg")
    @classmethod
    def _alg_must_be_known(cls, value: str) -> str:
        if value not in EncryptionAlgorithm.__members__.values():
            raise ValueError(f"Unknown algorithm: {value}")
        return value

    @field_validator("n")
    @classmethod
    def _nonce_must_be_12_bytes(cls, value: str) -> str:
        try:
            decoded = base64.b64decode(value)
        except Exception as exc:
            raise ValueError("Nonce is not valid base64") from exc
        if len(decoded) != 12:
            raise ValueError(f"Nonce must be exactly 12 bytes, got {len(decoded)}")
        return value

    @field_validator("ct")
    @classmethod
    def _ct_must_be_valid_base64(cls, value: str) -> str:
        try:
            base64.b64decode(value)
        except Exception as exc:
            raise ValueError("Ciphertext is not valid base64") from exc
        return value

    def to_token(self) -> str:
        """Serialize the envelope to a JSON string.

        Returns
        -------
        str
            Canonical JSON representation with sorted keys.
        """
        return self.model_dump_json(by_alias=False)

    @classmethod
    def from_token(cls, token: str) -> EncryptionEnvelope:
        """Deserialize a JSON string into an ``EncryptionEnvelope``.

        Parameters
        ----------
        token : str
            JSON string produced by :meth:`to_token`.

        Returns
        -------
        EncryptionEnvelope
            The parsed and validated envelope.

        Raises
        ------
        ValueError
            If the token is not valid JSON or fails field validation.
        """
        try:
            data = json.loads(token)
        except json.JSONDecodeError as exc:
            raise ValueError("Envelope token is not valid JSON") from exc
        return cls.model_validate(data)
