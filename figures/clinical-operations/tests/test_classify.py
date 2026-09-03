"""The oncology rule, applied.

``test_config.py`` checks that the dictionary is well formed. This file checks
that applying it to devices produces the right labels, and that the checks the
report depends on — panel agreement, specialty disagreement, scope coverage —
measure what they claim to measure.

Every test builds its own small snapshot. None of them read the committed one,
so a later FDA snapshot cannot turn these red for reasons that have nothing to
do with the code.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from clinops.classify import (
    EXCLUSION_REASONS,
    LABELED_COLUMNS,
    classify_devices,
)
from clinops.config import load_oncology_codes
from clinops.enrich import Snapshot

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def codes():
    """The project's real code dictionary.

    The rule is the thing under test, so the tests use the real one rather than
    a toy: a test that passes against an invented dictionary says nothing about
    whether the published figure is right.
    """
    return load_oncology_codes(PROJECT_ROOT / "config" / "oncology_codes.yaml")


def make_snapshot(rows: list[dict], classifications: dict | None = None) -> Snapshot:
    """Build a Snapshot from partial device rows, filling the dull fields."""
    filled = []
    for i, row in enumerate(rows):
        record = {
            "submission_number": f"K00000{i}",
            "decision_date": "2025-01-15",
            "year": 2025,
            "device": f"Device {i}",
            "company": "Acme",
            "panel_lead": "Radiology",
            "product_code": "QDQ",
            "pathway": "510(k)",
            "has_classification": True,
            "openfda_regulation_number": "",
            "openfda_medical_specialty_description": "",
            "openfda_device_name": "",
        }
        record.update(row)
        filled.append(record)
    return Snapshot(
        directory=Path("data/raw/test"),
        snapshot_date=date(2026, 3, 30),
        devices=pd.DataFrame(filled),
        classifications=classifications or {},
        codes_without_record=(),
        device_csv_sha256="0" * 64,
        n_device_rows=len(filled),
    )


# --------------------------------------------------------------------------
# The rule
# --------------------------------------------------------------------------


def test_an_oncology_code_is_counted_and_carries_its_assignment(codes):
    result = classify_devices(make_snapshot([{"product_code": "QDQ"}]), codes)
    assert result.n_devices_counted == 1
    row = result.labeled.iloc[0]
    assert row["counted"]
    assert row["domain"] == "radiology"
    assert row["category"] == "radiology_cancer_detection"
    assert row["exclusion_reason"] == ""


def test_a_pathology_code_is_counted_into_the_pathology_domain(codes):
    result = classify_devices(
        make_snapshot([{"product_code": "QPN", "panel_lead": "Pathology"}]), codes
    )
    row = result.labeled.iloc[0]
    assert row["domain"] == "pathology"
    assert row["category"] == "pathology"


def test_a_not_oncology_code_is_excluded_with_that_reason(codes):
    """QBS is fracture detection. It must never be counted."""
    result = classify_devices(make_snapshot([{"product_code": "QBS"}]), codes)
    assert result.n_devices_counted == 0
    assert result.exclusions["code_not_oncology"] == 1


def test_an_indeterminate_code_is_excluded_with_that_reason(codes):
    """QIH is the 274-device generic bucket that makes the count a floor."""
    result = classify_devices(make_snapshot([{"product_code": "QIH"}]), codes)
    assert result.n_devices_counted == 0
    assert result.exclusions["code_indeterminate"] == 1


def test_qfm_is_not_counted(codes):
    """The exclusion most likely to be undone by someone reading code names.

    QFM is named "prioritization software for lesions" and its devices are
    pneumothorax, pulmonary embolism, fracture and trauma triage. Counting it
    would move radiology by 39. See docs/DECISIONS.md, 2026-09-03.
    """
    result = classify_devices(
        make_snapshot([{"product_code": "QFM", "device": "Rayvolve PTX-PE"}]), codes
    )
    assert result.n_devices_counted == 0
    assert result.exclusions["code_not_oncology"] == 1


def test_an_unknown_code_on_an_in_scope_panel_is_flagged_as_a_gap(codes):
    """A code the dictionary has never adjudicated, on a panel the rule covers.

    This reason existing separately from the off-panel one is the whole point:
    an unlisted code on Radiology is a hole in the rule, and on Cardiovascular
    it is expected.
    """
    result = classify_devices(
        make_snapshot([{"product_code": "ZZZ", "panel_lead": "Radiology"}]), codes
    )
    assert result.exclusions["code_unlisted_in_panel"] == 1


def test_an_unknown_code_off_panel_is_not_a_gap(codes):
    result = classify_devices(
        make_snapshot([{"product_code": "ZZZ", "panel_lead": "Cardiovascular"}]), codes
    )
    assert result.exclusions["code_unlisted_off_panel"] == 1
    assert result.exclusions["code_unlisted_in_panel"] == 0


def test_every_excluded_row_carries_exactly_one_known_reason(codes):
    rows = [
        {"product_code": code, "panel_lead": panel}
        for code, panel in [
            ("QDQ", "Radiology"),
            ("QBS", "Radiology"),
            ("QIH", "Radiology"),
            ("ZZZ", "Radiology"),
            ("ZZZ", "Hematology"),
        ]
    ]
    result = classify_devices(make_snapshot(rows), codes)
    excluded = result.labeled[~result.labeled["counted"]]
    assert set(excluded["exclusion_reason"]) <= set(EXCLUSION_REASONS)
    assert (excluded["exclusion_reason"] != "").all()
    assert sum(result.exclusions.values()) == len(excluded)


def test_an_excluded_row_carries_no_half_filled_assignment(codes):
    """An excluded row with a domain would invite summing the wrong column."""
    result = classify_devices(make_snapshot([{"product_code": "QIH"}]), codes)
    row = result.labeled.iloc[0]
    assert row["domain"] == ""
    assert row["category"] == ""
    assert row["pathway"] == ""


def test_a_counted_row_missing_a_pathway_is_excluded_not_written_blank(codes):
    """The frozen schema declares pathway over three values.

    A row that cannot supply one is excluded rather than written as a blank,
    because a blank would flow into `pathway_by_domain.csv` as a fourth
    category.
    """
    result = classify_devices(
        make_snapshot([{"product_code": "QDQ", "pathway": ""}]), codes
    )
    assert result.n_devices_counted == 0
    assert result.exclusions["pathway_unknown"] == 1


def test_the_labeled_table_holds_every_device_counted_or_not(codes):
    """Excluded devices stay in the table.

    Dropping them would shrink the denominator every count is reported against.
    """
    rows = [{"product_code": c} for c in ("QDQ", "QBS", "QIH", "ZZZ")]
    result = classify_devices(make_snapshot(rows), codes)
    assert len(result.labeled) == 4
    assert result.n_devices_in == 4
    assert result.n_devices_counted == 1
    assert list(result.labeled.columns) == list(LABELED_COLUMNS)


# --------------------------------------------------------------------------
# Overrides
# --------------------------------------------------------------------------


def test_the_nmn_override_counts_a_device_openfda_would_misclassify(codes):
    """FDA reassigned NMN after the 1995 AUTOPAP authorization.

    openFDA now returns a reprocessed neurology instrument for it. Without the
    override the device drops out of the figure; with it, the device counts and
    the disagreement is reported rather than hidden.
    """
    snapshot = make_snapshot(
        [
            {
                "product_code": "NMN",
                "panel_lead": "Pathology",
                "device": "AUTOPAP 300 QC",
                "pathway": "PMA",
                "year": 1995,
                "decision_date": "1995-09-29",
                "openfda_medical_specialty_description": "Neurology",
                "openfda_device_name": "Instrument, Clip, Forming/Cutting, Reprocessed",
            }
        ]
    )
    result = classify_devices(snapshot, codes)
    row = result.labeled.iloc[0]
    assert row["counted"]
    assert row["domain"] == "pathology"
    assert row["code_overridden"]


def test_a_specialty_conflict_is_reported_not_silenced(codes):
    """The check exists so a future reassignment surfaces as a report line."""
    snapshot = make_snapshot(
        [
            {
                "product_code": "NMN",
                "panel_lead": "Pathology",
                "pathway": "PMA",
                "openfda_medical_specialty_description": "Neurology",
                "openfda_device_name": "Instrument, Clip, Forming/Cutting, Reprocessed",
            }
        ]
    )
    result = classify_devices(snapshot, codes)
    conflicts = [d for d in result.specialty_disagreements if d["code"] == "NMN"]
    assert len(conflicts) == 1


# --------------------------------------------------------------------------
# Panel agreement — the free second opinion
# --------------------------------------------------------------------------


def test_panel_agreement_counts_a_match(codes):
    rows = [
        {"product_code": "QDQ", "panel_lead": "Radiology"},
        {"product_code": "QPN", "panel_lead": "Pathology"},
    ]
    result = classify_devices(make_snapshot(rows), codes)
    assert result.panel_agreement["radiology"]["n_panel_matches"] == 1
    assert result.panel_agreement["pathology"]["n_panel_matches"] == 1


def test_panel_agreement_reports_a_mismatch_rather_than_filtering_it(codes):
    """A counted device with an unexpected panel must still be counted.

    Making the panel a filter would hide exactly the disagreement the check
    exists to find, and would make the agreement statistic circular.
    """
    result = classify_devices(
        make_snapshot([{"product_code": "QDQ", "panel_lead": "Neurology"}]), codes
    )
    assert result.n_devices_counted == 1
    agreement = result.panel_agreement["radiology"]
    assert agreement["n_panel_matches"] == 0
    assert agreement["n_devices"] == 1
    assert agreement["other_panels"] == {"Neurology": 1}


def test_panel_agreement_is_measured_not_asserted(codes):
    """It must be possible for agreement to be imperfect.

    If a bug made this statistic always 100%, it would corroborate nothing. This
    test fails if the mismatch above ever stops being visible.
    """
    rows = [
        {"product_code": "QDQ", "panel_lead": "Radiology"},
        {"product_code": "QDQ", "panel_lead": "Cardiovascular"},
    ]
    result = classify_devices(make_snapshot(rows), codes)
    assert result.panel_agreement["radiology"]["n_panel_matches"] == 1
    assert result.panel_agreement["radiology"]["n_devices"] == 2
    assert result.panel_agreement["radiology"]["rate"] == 0.5


# --------------------------------------------------------------------------
# The committed snapshot, as a regression on the published numbers
# --------------------------------------------------------------------------


@pytest.mark.skipif(
    not (PROJECT_ROOT / "data" / "processed" / "authorizations.csv").exists(),
    reason="no processed tables yet",
)
def test_the_published_counts_are_what_the_manuscript_quotes():
    """The numbers in the manuscript and the legend come from here.

    A refetch legitimately grows the list, so this reads the committed
    processed table rather than re-running the pipeline. If it fails after a
    deliberate refetch, update it together with every sentence that quotes a
    number -- that coupling is the point.
    """
    frame = pd.read_csv(
        PROJECT_ROOT / "data" / "processed" / "authorizations.csv", comment="#"
    )
    assert frame.groupby("category").size().to_dict() == {
        "pathology": 8,
        "radiology_cancer_detection": 107,
        "radiology_radiation_therapy": 86,
    }
    assert frame.groupby("domain").size().to_dict() == {"pathology": 8, "radiology": 193}
    pathology = frame[frame["domain"] == "pathology"]
    assert pathology.groupby("pathway").size().to_dict() == {
        "510(k)": 2,
        "De Novo": 3,
        "PMA": 3,
    }, "pathology's near-even pathway split is the figure's most-quoted finding"


def test_radiology_cancer_detection_begins_in_1998():
    """The claim the whole correction exists to fix.

    The first published version of this figure showed radiology beginning in
    2016, because the code-level rule could not see devices authorized before
    FDA created its cancer-specific product codes. The earliest is the M1000
    ImageChecker, PMA P970058, 26 June 1998. If this test fails, that error is
    back and the figure's central visual claim is wrong again.
    """
    frame = pd.read_csv(
        PROJECT_ROOT / "data" / "processed" / "authorizations.csv", comment="#"
    )
    detection = frame[frame["category"] == "radiology_cancer_detection"]
    assert int(detection["year"].min()) == 1998, (
        "radiology's earliest cancer-detection authorization is no longer 1998. "
        "See docs/DECISIONS.md, 2026-09-03."
    )
    assert "P970058" in set(frame["submission_number"])


def test_the_stroke_and_obstetric_devices_are_not_counted():
    """POK's contamination, guarded.

    POK is named "...For Lesions Suspicious For Cancer" and was counted
    wholesale; 14 of its 21 devices are stroke, cardiac or obstetric. If any of
    these reappears, a code-level verdict has overridden a device decision.
    """
    frame = pd.read_csv(
        PROJECT_ROOT / "data" / "processed" / "authorizations.csv", comment="#"
    )
    counted = set(frame["submission_number"])
    for submission, what in [
        ("K200760", "Rapid ASPECTS, acute ischemic stroke"),
        ("K233342", "CINA-ASPECTS, stroke"),
        ("K201555", "EchoGo Pro, stress echocardiography"),
        ("K242342", "Fetal EchoScan, fetal cardiac ultrasound"),
        ("K243614", "Sonio Suspect, fetal anomaly detection"),
    ]:
        assert submission not in counted, f"{submission} ({what}) is counted as oncology"


def test_the_qfm_mammography_devices_are_counted():
    """The mirror of the POK guard.

    QFM is excluded at code level and holds six mammography devices, not the one
    the config originally recorded. A device decision must outrank the code.
    """
    frame = pd.read_csv(
        PROJECT_ROOT / "data" / "processed" / "authorizations.csv", comment="#"
    )
    counted = set(frame["submission_number"])
    for submission, name in [
        ("K183285", "cmTriage"),
        ("K200905", "HealthMammo"),
        ("K203517", "Saige-Q"),
        ("K220080", "CogNet QmTRIAGE"),
        ("K233108", "VinDr-Mammo"),
    ]:
        assert submission in counted, (
            f"{submission} ({name}) is a mammography device under QFM and is not "
            "counted. The code-level exclusion has overridden its device decision."
        )
