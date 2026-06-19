"""System test configuration for anvil pip-installed runtime validation.

Provides httpx client fixture and docker compose exec helper.
"""
from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

import httpx
import pytest

BASE_URL = "http://localhost:8080"
COMPOSE_SERVICE = "anvil"
COMPOSE_FILE = "compose.yaml"


@pytest.fixture(scope="session")
def client() -> httpx.Client:
    """HTTP client pointed at the running anvil compose service."""
    return httpx.Client(base_url=BASE_URL, timeout=30.0)


@pytest.fixture(scope="session")
def compose_dir() -> Path:
    """Directory containing compose.yaml."""
    return Path.cwd()


def compose_exec(cmd: str, compose_dir: Path | None = None) -> subprocess.CompletedProcess:
    """Run a command inside the compose service and return the result."""
    workdir = compose_dir or Path.cwd()
    full_cmd = [
        "docker", "compose",
        "-f", str(workdir / COMPOSE_FILE),
        "exec", "-T", COMPOSE_SERVICE,
    ] + shlex.split(cmd)
    return subprocess.run(
        full_cmd,
        capture_output=True,
        text=True,
        timeout=30,
    )
