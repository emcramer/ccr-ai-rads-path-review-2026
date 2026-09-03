"""Device-level adjudication.

This layer exists because the code-level rule failed in a specific, damaging
way: FDA created its cancer-specific product codes around 2018-2020, so a rule
keyed on those codes cannot see an oncology device authorized before they
existed. The published figure showed radiology beginning in 2016 when its first
cancer-directed authorization is the 1998 M1000 ImageChecker, under the generic
code MYN.

The tests below are written against the failure modes that produced that, and
against the ones this replacement could introduce. The loader is deliberately
strict, because every fault it might wave through turns into a wrong number in a
figure rather than into a crash.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from clinops.adjudication import (
    MIN_EVIDENCE_CHARS,
    AdjudicationError,
    AdjudicationSet,
    load_adjudication,
    provenance,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

EVIDENCE = "Known product: iCAD SecondLook, computer-aided detection for screening mammography, PMA P010034."


def write_fragment(config_dir: Path, name: str, body: str) -> Path:
    """Write one adjudication fragment into a config directory."""
    directory = config_dir / "adjudication"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def one_entry(
    submission: str = "P010034",
    decision: str = "oncology",
    category: str = "radiology_cancer_detection",
    evidence: str = EVIDENCE,
    extra: str = "",
) -> str:
    """A fragment carrying a single entry, for the failure-mode tests."""
    category_line = f"    category: {category}\n" if category else ""
    return f"""\
        version: 1
        codes: [MYN]
        adjudicated:
          - submission_number: {submission}
            device: "SECOND LOOK"
            product_code: MYN
            decision: {decision}
        {category_line.rstrip()}
            evidence: >-
              {evidence}
        {extra}
        """


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


def test_a_missing_directory_yields_an_empty_set(tmp_path):
    """The pipeline must still run on the code-level rule alone.

    An absent adjudication directory is a state to report, not to crash on.
    """
    result = load_adjudication(tmp_path)
    assert isinstance(result, AdjudicationSet)
    assert result.decisions == {}
    assert result.n_counted == 0


def test_an_oncology_entry_is_loaded_and_counted(tmp_path):
    write_fragment(tmp_path, "a.yaml", one_entry())
    result = load_adjudication(tmp_path)
    decision = result.get("P010034")
    assert decision is not None
    assert decision.counted
    assert decision.category == "radiology_cancer_detection"
    assert result.n_counted == 1


def test_submission_numbers_are_matched_case_and_space_insensitively(tmp_path):
    """The join key comes from a CSV written by hand over three decades."""
    write_fragment(tmp_path, "a.yaml", one_entry(submission="p010034"))
    result = load_adjudication(tmp_path)
    assert result.get("P010034") is not None
    assert result.get("  p010034  ") is not None


def test_fragments_merge_across_files(tmp_path):
    write_fragment(tmp_path, "a.yaml", one_entry(submission="P010034"))
    write_fragment(tmp_path, "b.yaml", one_entry(submission="P970058"))
    result = load_adjudication(tmp_path)
    assert set(result.decisions) == {"P010034", "P970058"}
    assert len(result.fragments) == 2


# --------------------------------------------------------------------------
# The checks that stop a wrong number reaching the figure
# --------------------------------------------------------------------------


def test_one_device_adjudicated_twice_is_an_error(tmp_path):
    """Fragments are split by product code so they cannot overlap.

    Last-one-wins would let two people disagree and leave no trace of it.
    """
    write_fragment(tmp_path, "a.yaml", one_entry(submission="P010034"))
    write_fragment(
        tmp_path, "b.yaml", one_entry(submission="P010034", decision="not_oncology", category="")
    )
    with pytest.raises(AdjudicationError, match="adjudicated twice"):
        load_adjudication(tmp_path)


def test_an_oncology_entry_without_a_category_is_an_error(tmp_path):
    """A counted device must say which series it joins."""
    write_fragment(tmp_path, "a.yaml", one_entry(category=""))
    with pytest.raises(AdjudicationError, match="must say which series"):
        load_adjudication(tmp_path)


def test_an_unknown_category_is_an_error(tmp_path):
    """A typo would silently drop the device from every series."""
    write_fragment(tmp_path, "a.yaml", one_entry(category="radiology_cancer_detecton"))
    with pytest.raises(AdjudicationError, match="is not one of"):
        load_adjudication(tmp_path)


def test_an_unknown_decision_is_an_error(tmp_path):
    write_fragment(tmp_path, "a.yaml", one_entry(decision="probably", category=""))
    with pytest.raises(AdjudicationError, match="is not one of"):
        load_adjudication(tmp_path)


def test_a_non_counted_entry_may_not_carry_a_category(tmp_path):
    """A category on an excluded row reads as counted to anyone scanning."""
    write_fragment(
        tmp_path,
        "a.yaml",
        one_entry(decision="not_oncology", category="radiology_cancer_detection"),
    )
    with pytest.raises(AdjudicationError, match="Only an 'oncology' decision"):
        load_adjudication(tmp_path)


def test_evidence_is_required_on_every_decision(tmp_path):
    """An unexplained decision looks authoritative in the output and is not.

    This applies to exclusions too: leaving a device out is as consequential as
    putting one in, and the QFM episode is the proof -- the exclusion was right
    and its recorded evidence was false.
    """
    write_fragment(tmp_path, "a.yaml", one_entry(evidence="cancer"))
    with pytest.raises(AdjudicationError, match="must record why"):
        load_adjudication(tmp_path)

    write_fragment(
        tmp_path, "a.yaml", one_entry(decision="not_oncology", category="", evidence="no")
    )
    with pytest.raises(AdjudicationError, match="must record why"):
        load_adjudication(tmp_path)


def test_a_declared_device_count_that_disagrees_is_an_error(tmp_path):
    """`n_devices` is there to catch a fragment truncated mid-write."""
    body = one_entry().replace(
        "        codes: [MYN]", "        codes: [MYN]\n        n_devices: 7"
    )
    write_fragment(tmp_path, "a.yaml", body)
    with pytest.raises(AdjudicationError, match="declares n_devices"):
        load_adjudication(tmp_path)


def test_every_problem_is_reported_in_one_pass(tmp_path):
    """These files are written in bulk; one error per run is unusable."""
    write_fragment(
        tmp_path,
        "a.yaml",
        """\
        version: 1
        codes: [MYN]
        adjudicated:
          - submission_number: P000001
            decision: oncology
            evidence: short
          - submission_number: P000002
            decision: nonsense
            evidence: also much too short to count as evidence at all
        """,
    )
    with pytest.raises(AdjudicationError) as caught:
        load_adjudication(tmp_path)
    message = str(caught.value)
    assert "3 problem(s)" in message, message
    assert "P000001" in message and "P000002" in message


def test_a_malformed_fragment_names_itself(tmp_path):
    write_fragment(tmp_path, "broken.yaml", "version: 1\nadjudicated: not-a-list\n")
    with pytest.raises(AdjudicationError, match="broken.yaml"):
        load_adjudication(tmp_path)


# --------------------------------------------------------------------------
# Tallies the report and the manifest depend on
# --------------------------------------------------------------------------


def test_counts_separate_the_three_decisions(tmp_path):
    write_fragment(
        tmp_path,
        "a.yaml",
        f"""\
        version: 1
        codes: [MYN]
        adjudicated:
          - submission_number: P970058
            decision: oncology
            category: radiology_cancer_detection
            evidence: >-
              {EVIDENCE}
          - submission_number: P980025
            decision: not_oncology
            evidence: >-
              Logicon Caries Detector is a dental caries detection device, not oncology.
          - submission_number: K111776
            decision: unresolved
            evidence: >-
              DeltaView is a temporal subtraction tool; the row does not state a target.
        """,
    )
    result = load_adjudication(tmp_path)
    assert result.counts() == {"oncology": 1, "not_oncology": 1, "unresolved": 1}
    assert result.n_counted == 1
    assert result.n_unresolved == 1
    assert result.counts_by_category() == {"radiology_cancer_detection": 1}


def test_provenance_carries_a_digest_per_fragment(tmp_path):
    """A run manifest must pin the exact adjudication a figure was built from."""
    write_fragment(tmp_path, "a.yaml", one_entry())
    block = provenance(load_adjudication(tmp_path))
    assert block["n_devices"] == 1
    assert set(block["fragments"]) == {"a.yaml"}
    assert len(block["fragments"]["a.yaml"]) == 64
    assert block["versions"] == {"a.yaml": 1}


# --------------------------------------------------------------------------
# The project's own fragments
# --------------------------------------------------------------------------


@pytest.mark.skipif(
    not (PROJECT_ROOT / "config" / "adjudication").is_dir(),
    reason="no adjudication fragments yet",
)
def test_the_projects_fragments_load():
    """The real files must satisfy every check above."""
    result = load_adjudication(PROJECT_ROOT / "config")
    assert result.decisions, "adjudication directory exists but holds no decisions"


@pytest.mark.skipif(
    not (PROJECT_ROOT / "config" / "adjudication").is_dir(),
    reason="no adjudication fragments yet",
)
def test_the_1998_imagechecker_is_adjudicated_and_counted():
    """The device whose absence proved the code-level rule was broken.

    M1000 ImageChecker, PMA P970058, 26 June 1998: R2 Technology's mammography
    CAD, the first FDA-approved CAD device. It sits under the generic code MYN,
    which a code-only rule excludes, and its absence is what made the figure
    claim radiology began in 2016. If this test fails, that claim is back.
    """
    result = load_adjudication(PROJECT_ROOT / "config")
    if "MYN" not in result.codes:
        pytest.skip("MYN has not been adjudicated yet")
    decision = result.get("P970058")
    assert decision is not None, (
        "P970058 (M1000 ImageChecker, 1998) has no adjudication entry. It is the "
        "earliest cancer-directed radiology authorization on FDA's list and the "
        "reason this whole layer exists."
    )
    assert decision.counted, (
        f"P970058 (M1000 ImageChecker) is adjudicated {decision.decision!r}. It is "
        "mammography computer-aided detection and must count, or the figure's "
        "timeline is wrong again."
    )
    assert decision.category == "radiology_cancer_detection"
