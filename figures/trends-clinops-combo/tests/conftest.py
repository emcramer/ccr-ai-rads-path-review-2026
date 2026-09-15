"""Shared test setup.

Puts ``src`` on the import path so the suite runs from the project root with a
plain ``pytest``, and builds the two input directories from the sibling
projects' own recorded fixtures.

This project has no fixtures of its own, on purpose. It draws no marks and holds
no data; a table invented here to test it would be testing a schema that belongs
to somebody else, and would go stale the first time that schema moved. The
fixtures below are copied out of the siblings' suites, so a schema change breaks
this suite in the same commit it breaks theirs.

No test in this suite touches the network.
"""

from __future__ import annotations

import shutil
import socket
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

FIGURES_ROOT = PROJECT_ROOT.parent
TRENDS_FIXTURES = FIGURES_ROOT / "trends-figure" / "tests" / "fixtures"
CLINOPS_FIXTURES = FIGURES_ROOT / "clinical-operations" / "tests" / "fixtures"

#: The real processed tables, for the tests that have to see the figure the
#: manuscript will actually carry -- label collisions depend on the data.
REAL_TRENDS_INPUT = FIGURES_ROOT / "trends-figure" / "data" / "processed"
REAL_CLINOPS_INPUT = FIGURES_ROOT / "clinical-operations" / "data" / "processed"


@pytest.fixture(scope="session")
def trends_dir(tmp_path_factory) -> Path:
    """The trends project's measured tables, under the names its loader expects."""
    from trends.plotting import io

    target = tmp_path_factory.mktemp("trends")
    shutil.copy(
        TRENDS_FIXTURES / "plot_combination_counts_measured.csv",
        target / io.COMBINATION_COUNTS,
    )
    shutil.copy(
        TRENDS_FIXTURES / "plot_theme_year_counts_measured.csv", target / io.THEME_YEAR_COUNTS
    )
    return target


@pytest.fixture(scope="session")
def clinops_dir(tmp_path_factory) -> Path:
    """The clinical-operations fixtures, which already carry the expected names."""
    from clinops.plotting import io

    target = tmp_path_factory.mktemp("clinops")
    for name in (io.CUMULATIVE_BY_YEAR, io.PATHWAY_BY_DOMAIN, io.AUTHORIZATIONS):
        shutil.copy(CLINOPS_FIXTURES / name, target / name)
    return target


@pytest.fixture(scope="session")
def real_inputs() -> tuple[Path, Path]:
    """The two projects' real processed directories, or a skip if either is absent."""
    for directory in (REAL_TRENDS_INPUT, REAL_CLINOPS_INPUT):
        if not directory.exists():
            pytest.skip(f"{directory} is not present; run the sibling pipeline first")
    return REAL_TRENDS_INPUT, REAL_CLINOPS_INPUT


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Fail any test that tries to open a socket.

    Nothing in this project fetches anything -- it reads two directories and
    draws -- and this makes that a fact rather than a habit.
    """

    def refuse(*args, **kwargs):
        raise AssertionError("This test tried to reach the network.")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
