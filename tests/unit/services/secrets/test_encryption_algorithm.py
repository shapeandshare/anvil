"""Unit tests for EncryptionAlgorithm StrEnum."""

from __future__ import annotations

from anvil.services._shared.encryption_algorithm import EncryptionAlgorithm


def test_enum_values() -> None:
    assert EncryptionAlgorithm.AES_256_GCM == "aes-256-gcm"


def test_enum_membership() -> None:
    assert "aes-256-gcm" in EncryptionAlgorithm.__members__.values()
    assert EncryptionAlgorithm.AES_256_GCM in EncryptionAlgorithm.__members__.values()
