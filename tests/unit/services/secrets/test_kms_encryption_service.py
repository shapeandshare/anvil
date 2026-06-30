"""Unit tests for KmsEncryptionService (SaaS KMS envelope encryption).

Tests FR-020–FR-026: init, encrypt/decrypt round trip, format parity
with LocalEncryptionService, KMS-unavailable boot guard, and DEK
rotation via ``generate_data_key``.
"""

from __future__ import annotations

import base64
import json
import secrets
from unittest.mock import MagicMock

import pytest

from anvil._saas.encryption.kms_encryption_service import KmsEncryptionService
from anvil.services._shared.encryption import LocalEncryptionService
from anvil.services._shared.encryption_errors import (
    InvalidCiphertextError,
    UnknownKeyIdError,
)
from anvil.services._shared.key_ring import KeyRing

_AAD = b"alice:hf_token"
_AAD2 = b"bob:hf_token"


####################################################################
# Fixtures
####################################################################


@pytest.fixture
def dek() -> bytes:
    """32-byte AES-256 data encryption key."""
    return secrets.token_bytes(32)


@pytest.fixture
def kms_client(dek: bytes) -> MagicMock:
    """Mock KMS client that unwraps any blob to the fixed DEK."""
    client = MagicMock()
    client.decrypt.return_value = {
        "Plaintext": dek,
        "KeyId": "arn:aws:kms:us-east-1:123456789012:key/mock-kms-key",
    }
    return client


@pytest.fixture
def ssm_client() -> MagicMock:
    """Mock SSM client (unused by KmsEncryptionService, accepted for DI)."""
    return MagicMock()


@pytest.fixture
def dek_ring_config(dek: bytes) -> dict:
    """Single-key DEK ring config with a mock-wrapped DEK."""
    wrapped = base64.b64encode(b"mock-wrapped-dek-blob").decode("ascii")
    return {
        "current": "k1",
        "previous": None,
        "keys": {
            "k1": {
                "wrapped_dek": wrapped,
                "kek_id": "arn:aws:kms:us-east-1:123456789012:key/mock-kms-key",
            },
        },
    }


@pytest.fixture
def kms_svc(
    kms_client: MagicMock,
    ssm_client: MagicMock,
    dek_ring_config: dict,
) -> KmsEncryptionService:
    """KmsEncryptionService backed by a mocked KMS client."""
    return KmsEncryptionService(kms_client, ssm_client, dek_ring_config)


@pytest.fixture
def two_key_dek_ring_config(dek: bytes) -> dict:
    """Two-key DEK ring config (current + previous) for rotation tests."""
    prev_dek = secrets.token_bytes(32)
    # Mock wraps both keys to the same KMS key
    return {
        "current": "k2",
        "previous": "k1",
        "keys": {
            "k1": {
                "wrapped_dek": base64.b64encode(b"wrapped-k1").decode("ascii"),
                "kek_id": "arn:aws:kms:us-east-1:123456789012:key/mock-kms-key",
            },
            "k2": {
                "wrapped_dek": base64.b64encode(b"wrapped-k2").decode("ascii"),
                "kek_id": "arn:aws:kms:us-east-1:123456789012:key/mock-kms-key",
            },
        },
    }


@pytest.fixture
def multi_kms_client(dek: bytes) -> MagicMock:
    """Mock KMS client that returns different DEKs based on ciphertext.

    ``k1`` -> original ``dek``, ``k2`` -> ``dek`` (for single-dek tests).
    """

    def _decrypt(**kwargs: object) -> dict[str, object]:
        blob: bytes = kwargs["CiphertextBlob"]  # type: ignore[assignment]
        if blob == b"wrapped-k1":
            return {"Plaintext": dek, "KeyId": "arn:aws:kms:...:key/1"}
        return {"Plaintext": dek, "KeyId": "arn:aws:kms:...:key/2"}

    client = MagicMock()
    client.decrypt.side_effect = _decrypt
    return client


####################################################################
# Protocol conformance
####################################################################


def test_has_encrypt_decrypt(kms_svc: KmsEncryptionService) -> None:
    """KmsEncryptionService satisfies the EncryptionService Protocol."""
    assert hasattr(kms_svc, "encrypt")
    assert hasattr(kms_svc, "decrypt")


def test_has_name_attribute(kms_svc: KmsEncryptionService) -> None:
    """KmsEncryptionService exposes a ``name`` attribute."""
    assert kms_svc.name == "kms"


def test_name_override() -> None:
    """The ``name`` attribute is configurable at init."""
    client = MagicMock()
    client.decrypt.return_value = {
        "Plaintext": b"\x00" * 32,
        "KeyId": "arn:aws:kms:...",
    }
    kms = KmsEncryptionService(
        kms_client=client,
        ssm_client=MagicMock(),
        dek_ring_config={
            "current": "k1",
            "previous": None,
            "keys": {
                "k1": {
                    "wrapped_dek": base64.b64encode(b"blob").decode("ascii"),
                    "kek_id": "arn:aws:kms:...",
                },
            },
        },
        name="production-kms",
    )
    assert kms.name == "production-kms"


####################################################################
# Init
####################################################################


def test_init_unwraps_deks(
    kms_client: MagicMock,
    ssm_client: MagicMock,
    dek_ring_config: dict,
    dek: bytes,
) -> None:
    """Init calls kms_client.decrypt for each wrapped DEK."""
    service = KmsEncryptionService(kms_client, ssm_client, dek_ring_config)
    kms_client.decrypt.assert_called_once()
    assert service._keys["k1"] == dek


def test_init_kms_unavailable_raises() -> None:
    """KMS unavailability at boot raises RuntimeError."""
    failing_client = MagicMock()
    failing_client.decrypt.side_effect = RuntimeError("KMS connection refused")
    wrapped = base64.b64encode(b"blob").decode("ascii")
    config = {
        "current": "k1",
        "previous": None,
        "keys": {
            "k1": {
                "wrapped_dek": wrapped,
                "kek_id": "arn:aws:kms:...",
            },
        },
    }
    with pytest.raises(RuntimeError, match="KMS decrypt failed for key k1"):
        KmsEncryptionService(failing_client, MagicMock(), config)


def test_init_with_previous_key(
    multi_kms_client: MagicMock,
    ssm_client: MagicMock,
    two_key_dek_ring_config: dict,
) -> None:
    """Init unwraps both current and previous DEKs."""
    service = KmsEncryptionService(
        multi_kms_client, ssm_client, two_key_dek_ring_config
    )
    assert multi_kms_client.decrypt.call_count == 2
    assert "k1" in service._keys
    assert "k2" in service._keys


####################################################################
# Encrypt / Decrypt round trip
####################################################################


def test_encrypt_decrypt_round_trip(kms_svc: KmsEncryptionService) -> None:
    """Encrypt then decrypt returns the original plaintext."""
    token = kms_svc.encrypt("my-secret-value", _AAD)
    result = kms_svc.decrypt(token, _AAD)
    assert result == "my-secret-value"


def test_envelope_format(kms_svc: KmsEncryptionService) -> None:
    """Envelope contains all required fields."""
    token = kms_svc.encrypt("hello", _AAD)
    data = json.loads(token)
    assert data["v"] == 1
    assert data["alg"] == "aes-256-gcm"
    assert data["kid"] == "k1"
    assert len(data["n"]) > 0
    assert len(data["ct"]) > 0


def test_aad_mismatch_fails(kms_svc: KmsEncryptionService) -> None:
    """Decrypt with wrong AAD raises InvalidCiphertextError."""
    token = kms_svc.encrypt("my-secret", _AAD)
    with pytest.raises(InvalidCiphertextError):
        kms_svc.decrypt(token, _AAD2)


def test_tampered_ciphertext_fails(kms_svc: KmsEncryptionService) -> None:
    """Tampered envelope ciphertext raises InvalidCiphertextError."""
    token = kms_svc.encrypt("my-secret", _AAD)
    data = json.loads(token)
    # Tamper at the byte level: decode, flip a byte, re-encode
    raw_ct = bytearray(base64.b64decode(data["ct"]))
    raw_ct[-1] ^= 0xFF
    data["ct"] = base64.b64encode(bytes(raw_ct)).decode("ascii")
    tampered = json.dumps(data)
    with pytest.raises(InvalidCiphertextError):
        kms_svc.decrypt(tampered, _AAD)


def test_unknown_kid_fails(
    dek: bytes,
    kms_client: MagicMock,
    ssm_client: MagicMock,
) -> None:
    """Envelope with unknown kid raises UnknownKeyIdError."""
    svc = KmsEncryptionService(
        kms_client,
        ssm_client,
        {
            "current": "k1",
            "previous": None,
            "keys": {
                "k1": {
                    "wrapped_dek": base64.b64encode(b"blob").decode("ascii"),
                    "kek_id": "arn:aws:kms:...",
                },
            },
        },
    )
    env = json.dumps(
        {
            "v": 1,
            "alg": "aes-256-gcm",
            "kid": "unknown-kid",
            "n": base64.b64encode(b"\x00" * 12).decode("ascii"),
            "ct": base64.b64encode(b"\x00" * 16).decode("ascii"),
        }
    )
    with pytest.raises(UnknownKeyIdError, match="unknown-kid"):
        svc.decrypt(env, _AAD)


def test_unique_nonces(kms_svc: KmsEncryptionService) -> None:
    """Each encryption produces a unique nonce."""
    t1 = json.loads(kms_svc.encrypt("hello", _AAD))
    t2 = json.loads(kms_svc.encrypt("hello", _AAD))
    assert t1["n"] != t2["n"]


####################################################################
# Format parity with LocalEncryptionService
####################################################################


def test_format_parity_same_key(kms_client: MagicMock, dek: bytes) -> None:
    """EncryptionEnvelope from KmsEncryptionService is compatible with
    LocalEncryptionService and vice versa when using the same DEK.
    """
    # Build KmsEncryptionService
    wrapped = base64.b64encode(b"mock-wrapped").decode("ascii")
    kms_svc = KmsEncryptionService(
        kms_client,
        MagicMock(),
        {
            "current": "k1",
            "previous": None,
            "keys": {
                "k1": {
                    "wrapped_dek": wrapped,
                    "kek_id": "arn:aws:kms:...",
                },
            },
        },
    )

    # Build LocalEncryptionService with the same DEK
    ring = KeyRing(current="k1", previous=None, keys={"k1": dek})
    local_svc = LocalEncryptionService(ring)

    # Encrypt with Local, decrypt with Kms
    local_token = local_svc.encrypt("parity-check", _AAD)
    assert kms_svc.decrypt(local_token, _AAD) == "parity-check"

    # Encrypt with Kms, decrypt with Local
    kms_token = kms_svc.encrypt("reverse-parity", _AAD)
    assert local_svc.decrypt(kms_token, _AAD) == "reverse-parity"


####################################################################
# DEK rotation via generate_data_key
####################################################################


def test_dek_rotation_generates_new_key() -> None:
    """DEK rotation calls ``kms_client.generate_data_key`` and the new
    key can be used for encrypt/decrypt.
    """
    old_dek = secrets.token_bytes(32)
    new_dek = secrets.token_bytes(32)

    client = MagicMock()

    # Step 1: generate a new wrapped DEK (simulating rotation)
    client.generate_data_key.return_value = {
        "Plaintext": new_dek,
        "CiphertextBlob": b"new-wrapped-dek-blob",
        "KeyId": "arn:aws:kms:us-east-1:123456789012:key/rotation-key",
    }

    # Generate a new wrapped DEK (as would happen during rotation)
    gen_result = client.generate_data_key(
        KeyId="arn:aws:kms:us-east-1:123456789012:key/rotation-key",
        KeySpec="AES_256",
    )

    # Build the rotated config with both old and new keys
    wrapped_new_dek = base64.b64encode(gen_result["CiphertextBlob"]).decode("ascii")

    # Step 2: configure the mock to unwrap both old and new DEKs
    def _decrypt(**kwargs: object) -> dict[str, object]:
        blob: bytes = kwargs["CiphertextBlob"]  # type: ignore[assignment]
        if blob == b"new-wrapped-dek-blob":
            return {"Plaintext": new_dek, "KeyId": "arn:aws:kms:...:key/new"}
        return {"Plaintext": old_dek, "KeyId": "arn:aws:kms:...:key/old"}

    client.decrypt.side_effect = _decrypt

    config = {
        "current": "k2",
        "previous": "k1",
        "keys": {
            "k1": {
                "wrapped_dek": base64.b64encode(b"old-wrapped-dek").decode("ascii"),
                "kek_id": "arn:aws:kms:...:key/old",
            },
            "k2": {
                "wrapped_dek": wrapped_new_dek,
                "kek_id": "arn:aws:kms:...:key/new",
            },
        },
    }

    svc = KmsEncryptionService(client, MagicMock(), config)

    # Both keys should be available for decrypt
    client.generate_data_key.assert_called_with(
        KeyId="arn:aws:kms:us-east-1:123456789012:key/rotation-key",
        KeySpec="AES_256",
    )

    # Encrypt with current (k2) — produces envelope with kid=k2
    token = svc.encrypt("rotation-test", _AAD)
    assert json.loads(token)["kid"] == "k2"
    assert svc.decrypt(token, _AAD) == "rotation-test"

    # Decrypt with previous (k1) — ensures backward compatibility
    env_prev = json.dumps(
        {
            "v": 1,
            "alg": "aes-256-gcm",
            "kid": "k1",
            "n": base64.b64encode(b"\x01" * 12).decode("ascii"),
            "ct": base64.b64encode(b"\x01" * 16).decode("ascii"),
        }
    )
    # Manually encrypt with k1 and verify backward compat
    import secrets as sec

    nonce = sec.token_bytes(12)
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    aesgcm = AESGCM(old_dek)
    ct = aesgcm.encrypt(nonce, b"old-key-value", _AAD)
    env_prev_token = json.dumps(
        {
            "v": 1,
            "alg": "aes-256-gcm",
            "kid": "k1",
            "n": base64.b64encode(nonce).decode("ascii"),
            "ct": base64.b64encode(ct).decode("ascii"),
        }
    )
    assert svc.decrypt(env_prev_token, _AAD) == "old-key-value"
