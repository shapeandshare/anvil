"""Unit tests for EncryptionEnvelope Pydantic model."""

from __future__ import annotations

import base64
import json

import pytest
from pydantic import ValidationError

from anvil.services._shared.encryption_envelope import EncryptionEnvelope


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


_VALID_NONCE = _b64(b"\x00" * 12)
_VALID_CT = _b64(b"\x01" * 32)


def test_round_trip() -> None:
    env = EncryptionEnvelope(kid="k1", n=_VALID_NONCE, ct=_VALID_CT)
    token = env.to_token()
    restored = EncryptionEnvelope.from_token(token)
    assert restored.v == 1
    assert restored.alg == "aes-256-gcm"
    assert restored.kid == "k1"
    assert restored.n == _VALID_NONCE
    assert restored.ct == _VALID_CT


def test_from_token_canonical_json() -> None:
    token = json.dumps(
        {"v": 1, "alg": "aes-256-gcm", "kid": "k1", "n": _VALID_NONCE, "ct": _VALID_CT}
    )
    env = EncryptionEnvelope.from_token(token)
    assert env.kid == "k1"


def test_rejects_bad_nonce_length() -> None:
    bad_nonce = _b64(b"\x00" * 8)  # 8 bytes, not 12
    with pytest.raises(ValueError, match="exactly 12 bytes"):
        EncryptionEnvelope(kid="k1", n=bad_nonce, ct=_VALID_CT)


def test_rejects_malformed_base64_nonce() -> None:
    with pytest.raises(ValidationError):
        EncryptionEnvelope(kid="k1", n="!!!not-base64!!!", ct=_VALID_CT)


def test_rejects_malformed_base64_ct() -> None:
    with pytest.raises(ValidationError):
        EncryptionEnvelope(kid="k1", n=_VALID_NONCE, ct="!!!not-base64!!!")


def test_rejects_unknown_algorithm() -> None:
    with pytest.raises(ValueError, match="Unknown algorithm"):
        EncryptionEnvelope(
            v=1, alg="aes-128-gcm", kid="k1", n=_VALID_NONCE, ct=_VALID_CT
        )


def test_rejects_bad_version() -> None:
    with pytest.raises(ValueError, match="Unsupported envelope version"):
        EncryptionEnvelope(v=2, kid="k1", n=_VALID_NONCE, ct=_VALID_CT)


def test_from_token_rejects_non_json() -> None:
    with pytest.raises(ValueError, match="not valid JSON"):
        EncryptionEnvelope.from_token("not-json")
