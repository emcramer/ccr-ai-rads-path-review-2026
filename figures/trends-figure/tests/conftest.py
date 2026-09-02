"""Shared test setup.

Puts ``src`` on the import path, so the suite runs from the project root with a
plain ``pytest`` and no install step, and offers the recorded fixture to any
test that wants it.

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


@pytest.fixture(scope="session")
def sample_xml() -> bytes:
    """The recorded efetch response used across the parsing tests."""
    return (FIXTURE_DIR / "pubmed_sample.xml").read_bytes()


@pytest.fixture(scope="session")
def sample_records(sample_xml: bytes) -> dict[str, dict]:
    """The fixture parsed into rows, keyed by PMID."""
    from trends.parse import iter_records

    return {row["pmid"]: row for row in iter_records(sample_xml, "pubmed_sample.xml")}


@pytest.fixture
def valid_config_text() -> str:
    """A minimal corpus config that passes every check."""
    return (
        "version: 3\n"
        "date_range:\n"
        '  start: "2015/01/01"\n'
        '  end: "2026/09/01"\n'
        "retrieval:\n"
        "  db: pubmed\n"
        '  tool: "ccr-trends-figure"\n'
        '  email: "ericscrum@gmail.com"\n'
        "  batch_size: 200\n"
        "  requests_per_second: 3\n"
        "query: |\n"
        "  # a comment line, dropped\n"
        "  artificial intelligence[Title/Abstract]\n"
        "  AND pathology[Title/Abstract]\n"
    )


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Fail any test that tries to open a socket.

    The suite must run on a plane and must not put load on NCBI. Every request
    in it is served by a stub, and this makes that a fact rather than a habit.
    """

    def refuse(*args, **kwargs):
        raise AssertionError(
            "This test tried to reach the network. Tests must use a stub session."
        )

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
