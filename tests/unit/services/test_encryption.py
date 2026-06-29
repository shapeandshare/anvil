"""Unit tests for the AES-256-GCM encryption service."""

import pytest
from anvil.services._shared.encryption import EncryptionService


class TestEncryptionService:
    """Encrypt/decrypt roundtrip, key generation, and tamper detection."""

    def test_encrypt_decrypt_roundtrip(self, tmp_path) -> None:
        key_file = tmp_path / ".master_key"
        key_file.write_text("test-master-key-32bytes-token-urlsafe")
        svc = EncryptionService(key_path=str(key_file))
        plaintext = "hf_token_abc123"
        token = svc.encrypt(plaintext)
        assert token != plaintext
        assert svc.decrypt(token) == plaintext

    def test_different_nonces_per_encryption(self, tmp_path) -> None:
        key_file = tmp_path / ".master_key"
        key_file.write_text("test-master-key-32bytes-token-urlsafe")
        svc = EncryptionService(key_path=str(key_file))
        t1 = svc.encrypt("same-value")
        t2 = svc.encrypt("same-value")
        assert t1 != t2

    def test_wrong_key_fails(self, tmp_path) -> None:
        key1_file = tmp_path / "key1"
        key1_file.write_text("aaa-key-32bytes-token-urlsafe-aaa")
        key2_file = tmp_path / "key2"
        key2_file.write_text("bbb-key-32bytes-token-urlsafe-bbb")
        svc1 = EncryptionService(key_path=str(key1_file))
        svc2 = EncryptionService(key_path=str(key2_file))
        token = svc1.encrypt("secret")
        with pytest.raises(ValueError, match=".*"):
            svc2.decrypt(token)

    def test_tampered_ciphertext_raises(self, tmp_path) -> None:
        key_file = tmp_path / ".master_key"
        key_file.write_text("test-master-key-32bytes-token-urlsafe")
        svc = EncryptionService(key_path=str(key_file))
        token = svc.encrypt("secret")
        # Flip a byte in the base64 payload
        mangled = token[:-1] + ("A" if token[-1] != "A" else "B")
        with pytest.raises(ValueError, match=".*"):
            svc.decrypt(mangled)

    def test_generates_key_on_first_boot(self, tmp_path) -> None:
        key_file = tmp_path / ".master_key"
        assert not key_file.exists()
        svc = EncryptionService(key_path=str(key_file))
        assert key_file.exists()
        assert key_file.stat().st_mode & 0o777 == 0o600
        token = svc.encrypt("auto-gen-key-test")
        assert svc.decrypt(token) == "auto-gen-key-test"