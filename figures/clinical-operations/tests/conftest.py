"""Shared test setup.

Puts ``src`` on the import path, so the suite runs from the project root with a
plain ``pytest`` and no install step.

No test in this suite touches the network.
"""

from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

FIXTURE_DIR = Path(__file__).parent / "fixtures"
CONFIG_DIR = PROJECT_ROOT / "config"


@pytest.fixture(scope="session")
def config_dir() -> Path:
    """The project's configuration directory."""
    return CONFIG_DIR


@pytest.fixture(scope="session")
def oncology_config() -> dict:
    """``config/oncology_codes.yaml`` parsed."""
    import yaml

    return yaml.safe_load((CONFIG_DIR / "oncology_codes.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def source_config() -> dict:
    """``config/source.yaml`` parsed."""
    import yaml

    return yaml.safe_load((CONFIG_DIR / "source.yaml").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Fail any test that tries to open a socket.

    The suite must run offline and must not put load on FDA's servers. Every
    request in it is served by a stub, and this makes that a fact rather than a
    habit.
    """

    def refuse(*args, **kwargs):
        raise AssertionError(
            "This test tried to reach the network. Tests must use a stub session."
        )

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
