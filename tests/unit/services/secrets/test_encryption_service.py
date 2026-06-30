"""Unit tests for EncryptionService Protocol and LocalEncryptionService."""

from __future__ import annotations

import json
import secrets
from typing import Protocol

import pytest

from anvil.services._shared.encryption import EncryptionService, LocalEncryptionService
from anvil.services._shared.encryption_errors import (
    InvalidCiphertextError,
    UnknownKeyIdError,
)
from anvil.services._shared.key_ring import KeyRing


@pytest.fixture
def ring() -> KeyRing:
    return KeyRing(
        current="k1",
        previous=None,
        keys={"k1": secrets.token_bytes(32)},
    )


@pytest.fixture
def enc_svc(ring: KeyRing) -> LocalEncryptionService:
    return LocalEncryptionService(ring)


_AAD_ALICE = b"alice:hf_token"
_AAD_BOB = b"bob:hf_token"


def test_protocol_structural_typing() -> None:
    """Any class with encrypt/decrypt signatures satisfies the Protocol."""
    assert hasattr(LocalEncryptionService, "encrypt")
    assert hasattr(LocalEncryptionService, "decrypt")


def test_encrypt_decrypt_round_trip(enc_svc: LocalEncryptionService) -> None:
    token = enc_svc.encrypt("my-secret-value", _AAD_ALICE)
    result = enc_svc.decrypt(token, _AAD_ALICE)
    assert result == "my-secret-value"


def test_envelope_format(enc_svc: LocalEncryptionService) -> None:
    token = enc_svc.encrypt("hello", _AAD_ALICE)
    data = json.loads(token)
    assert data["v"] == 1
    assert data["alg"] == "aes-256-gcm"
    assert data["kid"] == "k1"
    assert len(data["n"]) > 0
    assert len(data["ct"]) > 0


def test_aad_mismatch_fails(enc_svc: LocalEncryptionService) -> None:
    token = enc_svc.encrypt("my-secret", _AAD_ALICE)
    with pytest.raises(InvalidCiphertextError):
        enc_svc.decrypt(token, _AAD_BOB)


def test_tampered_ciphertext_fails(enc_svc: LocalEncryptionService) -> None:
    token = enc_svc.encrypt("my-secret", _AAD_ALICE)
    data = json.loads(token)
    ct_bytes = bytearray(__import__("base64").b64decode(data["ct"]))
    ct_bytes[-1] ^= 0xFF
    data["ct"] = __import__("base64").b64encode(bytes(ct_bytes)).decode("ascii")
    tampered = json.dumps(data)
    with pytest.raises(InvalidCiphertextError):
        enc_svc.decrypt(tampered, _AAD_ALICE)


def test_unknown_kid_fails(ring: KeyRing) -> None:
    """An envelope with a kid not in the ring raises UnknownKeyIdError."""
    svc = LocalEncryptionService(ring)
    token = svc.encrypt("hello", _AAD_ALICE)
    ring.keys.pop("k1")
    ring.current = "k2"
    ring.keys["k2"] = secrets.token_bytes(32)
    with pytest.raises(UnknownKeyIdError, match="k1"):
        svc.decrypt(token, _AAD_ALICE)


def test_anv_il_master_secret_seeds_ring(tmp_path: pytest.TempPathFactory) -> None:
    """ANVIL_MASTER_SECRET env var seeds the key ring and is popped."""
    import os

    hex_key = secrets.token_hex(32)
    os.environ["ANVIL_MASTER_SECRET"] = hex_key
    path = tmp_path / "key_ring.json"
    ring = KeyRing.load(path, seed_from_env="ANVIL_MASTER_SECRET")
    assert "ANVIL_MASTER_SECRET" not in os.environ
    assert ring.current in ring.keys
    assert len(ring.keys[ring.current]) == 32


def test_unique_nonces(enc_svc: LocalEncryptionService) -> None:
    """Each encryption produces a different nonce."""
    t1 = json.loads(enc_svc.encrypt("hello", _AAD_ALICE))
    t2 = json.loads(enc_svc.encrypt("hello", _AAD_ALICE))
    assert t1["n"] != t2["n"]


def test_different_keys_produce_different_envelopes() -> None:
    ring = KeyRing(
        current="k1",
        previous=None,
        keys={"k1": secrets.token_bytes(32)},
    )
    svc = LocalEncryptionService(ring)
    t1 = svc.encrypt("value", b"alice:key1")
    t2 = svc.encrypt("value", b"bob:key2")
    assert t1 != t2
