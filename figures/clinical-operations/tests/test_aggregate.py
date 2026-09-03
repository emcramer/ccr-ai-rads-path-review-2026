"""Aggregation invariants.

The figure is drawn from these three tables and nothing else, so an error here
is an error a reader sees. The invariants worth holding are the ones a plotting
bug or a hand-edit would break: totals that must reconcile, a year axis that
must be dense, a cumulative series that must never decrease, and an ordering
that must be stable between runs.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from clinops.aggregate import (
    AUTHORIZATION_COLUMNS,
    CUMULATIVE_COLUMNS,
    PATHWAY_COLUMNS,
    PATHWAY_ORDER,
    AggregateError,
    build_authorizations,
    build_cumulative_by_year,
    build_pathway_by_domain,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED = PROJECT_ROOT / "data" / "processed"


def labeled_frame(rows: list[dict]) -> pd.DataFrame:
    """Build a labelled table from partial rows, filling the dull fields."""
    filled = []
    for i, row in enumerate(rows):
        record = {
            "submission_number": f"K{i:06d}",
            "decision_date": "2025-01-15",
            "year": 2025,
            "device": f"Device {i}",
            "company": "Acme",
            "panel_lead": "Radiology",
            "product_code": "QDQ",
            "domain": "radiology",
            "category": "radiology_cancer_detection",
            "category_label": "Cancer detection and diagnosis",
            "pathway": "510(k)",
            "regulation_number": "892.2090",
            "counted": True,
        }
        record.update(row)
        filled.append(record)
    return pd.DataFrame(filled)


# --------------------------------------------------------------------------
# authorizations.csv
# --------------------------------------------------------------------------


def test_only_counted_devices_reach_the_authorizations_table():
    frame = build_authorizations(
        labeled_frame([{"counted": True}, {"counted": False}, {"counted": True}])
    )
    assert len(frame) == 2
    assert list(frame.columns) == list(AUTHORIZATION_COLUMNS)


def test_authorization_order_is_stable_between_runs():
    """Two runs over one snapshot must produce identical data.

    Only the `#` provenance header may differ, because it carries a timestamp.
    Without this, a diff between two snapshots shows reordering noise instead of
    what actually changed.
    """
    rows = [
        {"decision_date": "2025-06-01", "submission_number": "K3"},
        {"decision_date": "2024-01-01", "submission_number": "K1"},
        {"decision_date": "2025-06-01", "submission_number": "K2"},
    ]
    first = build_authorizations(labeled_frame(rows))
    second = build_authorizations(labeled_frame(list(reversed(rows))))
    assert list(first["submission_number"]) == ["K1", "K2", "K3"]
    assert list(first["submission_number"]) == list(second["submission_number"])


# --------------------------------------------------------------------------
# cumulative_by_year.csv
# --------------------------------------------------------------------------


def test_the_year_axis_is_dense_over_every_category():
    """The plotting code indexes straight into this table.

    A sparse axis would make a 26-year gap look like missing data rather than
    like zeros, which is the opposite of the point Panel A makes.
    """
    frame = build_cumulative_by_year(
        build_authorizations(
            labeled_frame(
                [
                    {"year": 1995, "category": "pathology", "domain": "pathology"},
                    {"year": 2025, "category": "radiology_cancer_detection"},
                ]
            )
        )
    )
    years = sorted(set(frame["year"]))
    assert years == list(range(1995, 2026))
    assert len(frame) == len(years) * 2
    for category in set(frame["category"]):
        block = frame[frame["category"] == category]
        assert sorted(block["year"]) == years


def test_cumulative_counts_never_decrease():
    frame = build_cumulative_by_year(
        build_authorizations(
            labeled_frame([{"year": y} for y in (2016, 2018, 2018, 2020)])
        )
    )
    for category in set(frame["category"]):
        block = frame[frame["category"] == category].sort_values("year")
        assert block["cumulative_count"].is_monotonic_increasing


def test_the_final_cumulative_value_equals_the_device_count():
    """The number the manuscript quotes is the last point on the curve."""
    rows = [{"year": y} for y in (2016, 2018, 2018, 2020, 2025)]
    authorizations = build_authorizations(labeled_frame(rows))
    frame = build_cumulative_by_year(authorizations)
    block = frame[frame["category"] == "radiology_cancer_detection"]
    assert int(block["cumulative_count"].max()) == len(rows)
    assert int(block["annual_count"].sum()) == len(rows)


def test_a_category_spanning_two_domains_is_rejected():
    """A category maps to exactly one domain.

    If it did not, the domain totals would double-count and the figure's two
    series would overlap. Catch the hand-edit rather than drawing it.
    """
    frame = build_authorizations(
        labeled_frame(
            [
                {"category": "pathology", "domain": "pathology"},
                {"category": "pathology", "domain": "radiology"},
            ]
        )
    )
    with pytest.raises(AggregateError, match="belongs to exactly one domain"):
        build_cumulative_by_year(frame)


def test_an_empty_table_yields_an_empty_frame_with_the_right_columns():
    frame = build_cumulative_by_year(pd.DataFrame(columns=list(AUTHORIZATION_COLUMNS)))
    assert frame.empty
    assert list(frame.columns) == list(CUMULATIVE_COLUMNS)


# --------------------------------------------------------------------------
# pathway_by_domain.csv
# --------------------------------------------------------------------------


def test_pathway_table_is_dense_over_all_three_pathways():
    """A missing pathway emits a zero rather than dropping a bar segment."""
    frame = build_pathway_by_domain(
        build_authorizations(labeled_frame([{"pathway": "510(k)"}]))
    )
    assert set(frame["pathway"]) == set(PATHWAY_ORDER)
    assert list(frame.columns) == list(PATHWAY_COLUMNS)
    assert int(frame["count"].sum()) == 1


def test_pathway_counts_sum_to_the_authorization_count():
    rows = [{"pathway": p} for p in ("510(k)", "510(k)", "De Novo", "PMA")]
    authorizations = build_authorizations(labeled_frame(rows))
    frame = build_pathway_by_domain(authorizations)
    assert int(frame["count"].sum()) == len(authorizations)


# --------------------------------------------------------------------------
# The committed tables must reconcile with each other
# --------------------------------------------------------------------------


@pytest.mark.skipif(
    not (PROCESSED / "authorizations.csv").exists(), reason="no processed tables yet"
)
def test_the_three_committed_tables_reconcile():
    """The figure reads three files; they must agree or it draws a lie."""
    authorizations = pd.read_csv(PROCESSED / "authorizations.csv", comment="#")
    cumulative = pd.read_csv(PROCESSED / "cumulative_by_year.csv", comment="#")
    pathway = pd.read_csv(PROCESSED / "pathway_by_domain.csv", comment="#")

    assert int(pathway["count"].sum()) == len(authorizations)

    finals = (
        cumulative.sort_values("year")
        .groupby("category")["cumulative_count"]
        .last()
        .to_dict()
    )
    assert finals == authorizations.groupby("category").size().to_dict()

    assert int(cumulative["annual_count"].sum()) == len(authorizations)

    years = sorted(set(cumulative["year"]))
    assert years == list(range(min(years), max(years) + 1)), "year axis is not dense"
    for category in set(cumulative["category"]):
        block = cumulative[cumulative["category"] == category].sort_values("year")
        assert block["cumulative_count"].is_monotonic_increasing
        assert sorted(block["year"]) == years
