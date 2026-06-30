"""Unit tests for KeyRing."""

from __future__ import annotations

import json
import secrets
from pathlib import Path

import pytest

from anvil.services._shared.key_ring import KeyRing, UnknownKeyIdError


@pytest.fixture
def ring() -> KeyRing:
    k1 = "k1-uuid"
    k2 = "k2-uuid"
    return KeyRing(
        current=k1,
        previous=k2,
        keys={k1: secrets.token_bytes(32), k2: secrets.token_bytes(32)},
    )


def test_resolve_returns_key_material(ring: KeyRing) -> None:
    material = ring.resolve("k1-uuid")
    assert len(material) == 32


def test_resolve_unknown_kid_raises(ring: KeyRing) -> None:
    with pytest.raises(UnknownKeyIdError, match="unknown-kid"):
        ring.resolve("unknown-kid")


def test_generate_adds_new_key(ring: KeyRing) -> None:
    assert len(ring.keys) == 2
    new_kid = ring.generate()
    assert len(ring.keys) == 3
    assert new_kid in ring.keys
    assert len(ring.keys[new_kid]) == 32


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    ring = KeyRing(current="c1", previous=None, keys={"c1": secrets.token_bytes(32)})
    path = tmp_path / "key_ring.json"
    ring.save(path)
    loaded = KeyRing.load(path)
    assert loaded.current == "c1"
    assert loaded.previous is None
    assert loaded.keys["c1"] == ring.keys["c1"]


def test_save_and_load_with_previous(tmp_path: Path) -> None:
    k1 = secrets.token_bytes(32)
    k2 = secrets.token_bytes(32)
    ring = KeyRing(current="c1", previous="p1", keys={"c1": k1, "p1": k2})
    path = tmp_path / "key_ring.json"
    ring.save(path)
    loaded = KeyRing.load(path)
    assert loaded.current == "c1"
    assert loaded.previous == "p1"
    assert loaded.keys["c1"] == k1
    assert loaded.keys["p1"] == k2


def test_load_auto_generates_when_no_file(tmp_path: Path) -> None:
    path = tmp_path / "nonexistent.json"
    ring = KeyRing.load(path)
    assert ring.current is not None
    assert ring.previous is None
    assert len(ring.keys) == 1
    assert ring.current in ring.keys
    assert path.exists()


def test_load_auto_generated_file_is_valid_json(tmp_path: Path) -> None:
    path = tmp_path / "auto.json"
    KeyRing.load(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "current" in data
    assert "keys" in data
    assert len(data["keys"]) == 1


def test_file_permissions_0600(tmp_path: Path) -> None:
    ring = KeyRing(current="c1", previous=None, keys={"c1": secrets.token_bytes(32)})
    path = tmp_path / "key_ring.json"
    ring.save(path)
    assert path.stat().st_mode & 0o777 == 0o600


def test_generate_creates_uuid4_keys() -> None:
    ring = KeyRing(current="c1", previous=None, keys={"c1": secrets.token_bytes(32)})
    kid = ring.generate()
    # UUID4 format: 8-4-4-4-12 hex digits
    parts = kid.split("-")
    assert len(parts) == 5
    assert len(parts[0]) == 8
    assert len(parts[4]) == 12
