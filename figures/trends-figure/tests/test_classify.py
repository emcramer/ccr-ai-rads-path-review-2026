"""Tests for :mod:`trends.classify`.

The suite runs against hand-written fixture dictionaries and a hand-written
record table, not against the real corpus, so a change to ``config/*.yaml``
cannot make a test pass or fail. One test loads the real dictionaries, but only
to prove they compile.

What the fixture proves: the matcher's contract — word boundaries, whitespace
tolerance, case sensitivity, exclusion, multi-label assignment, the ``other``
fallback, and the record filters. What it cannot prove: that the real terms
select the right literature. That is measured in ``docs/search-strategy.md`` and
by the validation sample, not here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from trends import aggregate, classify

FIXTURES = Path(__file__).parent / "fixtures"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
THEMES_FIXTURE = FIXTURES / "classify_themes.yaml"
MODALITIES_FIXTURE = FIXTURES / "classify_modalities.yaml"
RECORDS_FIXTURE = FIXTURES / "classify_records.csv"


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def themes() -> classify.TermDictionary:
    """The fixture theme dictionary, compiled."""
    return classify.load_term_dictionary(
        THEMES_FIXTURE, kind="themes", expected_keys=classify.THEME_KEYS
    )


@pytest.fixture(scope="module")
def modalities() -> classify.TermDictionary:
    """The fixture modality dictionary, compiled."""
    return classify.load_term_dictionary(
        MODALITIES_FIXTURE,
        kind="modalities",
        expected_keys=classify.MODALITY_KEYS,
        optional_include={classify.OTHER_MODALITY},
    )


@pytest.fixture(scope="module")
def records() -> pd.DataFrame:
    """The fixture record table."""
    return classify.read_records(RECORDS_FIXTURE)


@pytest.fixture(scope="module")
def result(records, themes, modalities) -> classify.ClassificationResult:
    """The fixture records classified by the fixture dictionaries."""
    return classify.classify_records(records, themes, modalities)


@pytest.fixture(scope="module")
def labels(result) -> pd.DataFrame:
    """The label table, indexed by PMID for readable assertions."""
    return result.labels.set_index("pmid")


def write_dictionary(path: Path, body: str, *, version: int = 1) -> Path:
    """Write a one-off dictionary file for a validation test."""
    path.write_text(f"version: {version}\ncategories:\n{body}", encoding="utf-8")
    return path


def matches(dictionary: classify.TermDictionary, text: str) -> set[str]:
    """Return the categories a text is assigned by a dictionary."""
    return {
        key for key, match in classify.match_text(dictionary, text).items() if match.matched
    }


# --------------------------------------------------------------------------
# Loading and validating a dictionary
# --------------------------------------------------------------------------


def test_fixture_dictionaries_load(themes, modalities):
    """Both fixture files compile and report what they hold."""
    assert themes.version == 7
    # Declared out of canonical order on purpose: order in the file is not the
    # figure's order, and the loader must not care.
    assert set(themes.keys) == set(classify.THEME_KEYS)
    assert modalities.version == 4
    assert set(modalities.keys) == set(classify.MODALITY_KEYS)
    assert len(themes.sha256) == 64
    assert themes.n_patterns == 12  # ten includes and two excludes
    assert len(modalities.categories["other"].include) == 2  # additive: it has patterns


def test_category_order_in_the_file_does_not_matter(modalities):
    """The fixture declares its categories out of figure order; that is allowed."""
    assert modalities.keys != classify.MODALITY_KEYS
    assert set(modalities.keys) == set(classify.MODALITY_KEYS)


def test_missing_file_names_the_path(tmp_path):
    """A missing dictionary raises rather than classifying nothing."""
    with pytest.raises(classify.TermDictionaryError, match="not found"):
        classify.load_term_dictionary(tmp_path / "absent.yaml", kind="themes")


def test_unknown_kind_is_rejected(tmp_path):
    """``kind`` may only be phrase or regex."""
    path = write_dictionary(
        tmp_path / "d.yaml",
        '  a:\n    label: "A"\n    include:\n      - pattern: "x"\n        kind: glob\n',
    )
    with pytest.raises(classify.TermDictionaryError, match="'kind' must be"):
        classify.load_term_dictionary(path, kind="themes")


def test_uncompilable_regex_is_rejected(tmp_path):
    """A regex that will not compile is caught at load, not at match time."""
    path = write_dictionary(
        tmp_path / "d.yaml",
        '  a:\n    label: "A"\n    include:\n      - pattern: "([unclosed"\n        kind: regex\n',
    )
    with pytest.raises(classify.TermDictionaryError, match="will not compile"):
        classify.load_term_dictionary(path, kind="themes")


def test_other_may_carry_include_patterns(tmp_path):
    """``other`` is additive: it takes patterns of its own as well as the fallback."""
    path = write_dictionary(
        tmp_path / "d.yaml",
        '  other:\n    label: "Other"\n    include:\n      - pattern: "x"\n        kind: phrase\n',
    )
    dictionary = classify.load_term_dictionary(
        path, kind="modalities", optional_include={"other"}
    )
    assert len(dictionary.categories["other"].include) == 1


def test_other_may_also_carry_no_patterns(tmp_path):
    """And it may have none, which leaves only the fallback route."""
    path = write_dictionary(tmp_path / "d.yaml", '  other:\n    label: "Other"\n    include: []\n')
    dictionary = classify.load_term_dictionary(
        path, kind="modalities", optional_include={"other"}
    )
    assert dictionary.categories["other"].include == ()


def test_category_with_no_include_patterns_is_rejected(tmp_path):
    """A patternless named category would silently empty a figure block."""
    path = write_dictionary(tmp_path / "d.yaml", '  a:\n    label: "A"\n    include: []\n')
    with pytest.raises(classify.TermDictionaryError, match="can never match"):
        classify.load_term_dictionary(path, kind="themes")


def test_renamed_category_is_caught(tmp_path):
    """The canonical keys are fixed; a renamed one is an error, not a blank block."""
    path = write_dictionary(
        tmp_path / "d.yaml",
        '  foundation_model:\n    label: "A"\n    include:\n'
        '      - pattern: "x"\n        kind: phrase\n',
    )
    with pytest.raises(classify.TermDictionaryError) as excinfo:
        classify.load_term_dictionary(path, kind="themes", expected_keys=classify.THEME_KEYS)
    assert "missing" in str(excinfo.value)
    assert "not canonical" in str(excinfo.value)


def test_case_sensitive_true_contradicting_inline_flag_is_rejected(tmp_path):
    """``case_sensitive: true`` and ``(?i)`` cannot both be meant."""
    path = write_dictionary(
        tmp_path / "d.yaml",
        '  a:\n    label: "A"\n    include:\n      - pattern: "(?i)abc"\n'
        "        kind: regex\n        case_sensitive: true\n",
    )
    with pytest.raises(classify.TermDictionaryError, match="contradicts"):
        classify.load_term_dictionary(path, kind="themes")


def test_every_problem_is_reported_at_once(tmp_path):
    """The message lists all problems, so the file is fixed in one pass."""
    path = write_dictionary(
        tmp_path / "d.yaml",
        '  a:\n    label: "A"\n    include:\n      - pattern: "([bad"\n        kind: regex\n'
        '      - pattern: "x"\n        kind: glob\n',
        version=0,
    )
    with pytest.raises(classify.TermDictionaryError) as excinfo:
        classify.load_term_dictionary(path, kind="themes")
    assert "3 problem(s)" in str(excinfo.value)


def test_real_dictionaries_compile():
    """The shipped ``config/*.yaml`` load and hold the canonical keys.

    A guard, not a measurement: it says the dictionaries are usable, not that
    they are right.
    """
    config = PROJECT_ROOT / "config"
    if not (config / "themes.yaml").exists():  # pragma: no cover - config is present
        pytest.skip("config/themes.yaml is not present")
    themes, modalities = classify.load_dictionaries(config)
    assert themes.version >= 1 and modalities.version >= 1
    assert themes.keys == classify.THEME_KEYS
    assert set(modalities.keys) == set(classify.MODALITY_KEYS)
    # `other` is additive; the shipped file gives it patterns of its own.
    assert len(modalities.categories["other"].include) >= 1
    classify.check_domain_coverage(modalities.keys)


# --------------------------------------------------------------------------
# Phrase semantics
# --------------------------------------------------------------------------


def test_phrase_is_word_bounded(themes):
    """A phrase matches a whole word only, plural included: it is a literal."""
    assert matches(themes, "A digital twin of the heart") == {"digital_twins"}
    assert "digital_twins" not in matches(themes, "Two digital twins of the heart")
    assert "digital_twins" not in matches(themes, "predigital twin")
    assert matches(themes, "DIGITAL TWIN.") == {"digital_twins"}


def test_phrase_tolerates_any_whitespace(modalities):
    """The gap between a phrase's words may be any run of whitespace."""
    for text in (
        "whole slide imaging",
        "whole  slide imaging",
        "whole\nslide\timaging",
    ):
        assert matches(modalities, text) == {"he_histology"}
    assert "he_histology" not in matches(modalities, "whole-slide imaging")


def test_phrase_bounded_by_a_non_word_character(themes):
    """``510(k)`` ends in a bracket, where ``\\b`` would assert the wrong thing."""
    assert matches(themes, "A 510(k)-cleared device") == {"clinical_fda"}
    assert matches(themes, "cleared under 510(k).") == {"clinical_fda"}


def test_phrase_is_case_insensitive_by_default(modalities):
    """``ultrasound`` is written with no flag, so case does not matter."""
    assert matches(modalities, "Ultrasound of the liver") == {"ultrasound"}
    assert matches(modalities, "ULTRASOUND of the liver") == {"ultrasound"}


def test_case_sensitive_phrase_matches_the_acronym_only(modalities):
    """``case_sensitive: true`` is how an acronym is written as a phrase."""
    assert matches(modalities, "We read 400 WSIs") == set()   # bounded: WSIs is not WSI
    assert matches(modalities, "We read the WSI") == {"he_histology"}
    assert matches(modalities, "We read the wsi") == set()
    assert matches(modalities, "CODEX panels") == {"spatial_proteomics"}
    assert matches(modalities, "an illuminated codex") == set()


def test_compile_phrase_rejects_an_empty_literal():
    """An empty phrase would match everywhere."""
    with pytest.raises(ValueError):
        classify.compile_phrase("   ", case_sensitive=False)


# --------------------------------------------------------------------------
# Regex semantics
# --------------------------------------------------------------------------


def test_regex_is_case_sensitive_unless_it_says_otherwise(modalities):
    """A regex compiles as written. This is what makes bare ``CT`` usable."""
    assert matches(modalities, "chest CT of the thorax") == {"ct"}
    assert matches(modalities, "a qPCR Ct value of 30") == set()
    assert matches(modalities, "computed tomography") == {"ct"}  # phrase, insensitive
    assert matches(modalities, "COMPUTED TOMOGRAPHY") == {"ct"}


def test_inline_flag_opts_a_regex_into_case_insensitivity(modalities):
    """``(?i)`` at position 0 is the documented way to ignore case in a regex."""
    assert matches(modalities, "the RADIOLOGY REPORT was parsed") == {"radiology_report"}
    assert matches(modalities, "the radiology reports were parsed") == {"radiology_report"}


def test_case_sensitive_false_makes_a_regex_insensitive(tmp_path):
    """The override adds ``re.IGNORECASE`` to a regex written without ``(?i)``."""
    path = write_dictionary(
        tmp_path / "d.yaml",
        '  a:\n    label: "A"\n    include:\n      - pattern: "\\\\bCT\\\\b"\n'
        "        kind: regex\n        case_sensitive: false\n",
    )
    dictionary = classify.load_term_dictionary(path, kind="themes")
    assert dictionary.categories["a"].include[0].case_sensitive is False
    assert matches(dictionary, "a qPCR Ct value") == {"a"}


def test_compiled_patterns_report_their_case_sensitivity(themes, modalities):
    """The flag lands on the Pattern, so the manifest and the hits table can say so."""
    assert modalities.categories["ct"].include[0].case_sensitive is True      # \bCTs?\b
    assert modalities.categories["ct"].include[1].case_sensitive is False     # phrase
    assert themes.categories["clinical_fda"].include[0].case_sensitive is False  # (?i)


def test_conjunctive_pattern_reads_title_and_abstract_as_one_string(modalities):
    """``^(?=...)`` anchors at the start of title-plus-abstract, not of a line."""
    text = classify.record_text(
        "Deep learning on pathology reports", "We apply natural language processing."
    )
    assert "pathology_report" in matches(modalities, text)
    assert "pathology_report" not in matches(
        modalities, classify.record_text("Deep learning on pathology reports", "No text here.")
    )
    assert "pathology_report" not in matches(
        modalities, classify.record_text("Natural language processing", "No report here.")
    )


# --------------------------------------------------------------------------
# Classifying a record table
# --------------------------------------------------------------------------


def test_record_filters_are_counted(result):
    """Book records, blank PMIDs, and yearless records are dropped and reported."""
    assert result.n_records_in == 23
    assert result.exclusions == {
        "book_records": 1, "missing_pmid": 1, "missing_year": 1, "outside_date_range": 0,
    }
    assert result.n_records_out == 20
    assert "1013" not in set(result.labels["pmid"])  # the book record


def test_pmid_stays_a_string(labels):
    """A numeric-looking PMID must not become 1001.0 on the way through pandas."""
    assert "1001" in labels.index
    assert isinstance(labels.index[0], str)
    assert not any(pmid.endswith(".0") for pmid in labels.index)


def test_a_multi_label_record_carries_every_label_it_earns(labels):
    """One record, one theme, two modalities, and the domain that follows."""
    row = labels.loc["1001"]
    assert row["theme_foundation_models"] == 1
    assert row["mod_he_histology"] == 1 and row["mod_ct"] == 1
    assert row["mod_other"] == 0
    assert row["domain"] == "both"


def test_a_record_matching_no_modality_lands_in_other(labels):
    """``other`` is the classifier's fallback, and it is exclusive of the rest."""
    row = labels.loc["1002"]
    assert row["mod_other"] == 1
    assert sum(row[f"mod_{key}"] for key in classify.MODALITY_KEYS) == 1
    assert row["domain"] == "none"


def test_a_record_matching_no_theme_stays_in_the_corpus(labels):
    """No theme is not an exclusion. The record still counts in the denominator."""
    row = labels.loc["1002"]
    assert sum(row[f"theme_{key}"] for key in classify.THEME_KEYS) == 0
    assert "1002" in labels.index


def test_acronym_traps(labels):
    """The four collisions the dictionary authors measured, held here."""
    trap = labels.loc["1004"]                      # "qPCR Ct", "pet ownership", "US"
    assert trap["mod_ct"] == 0 and trap["mod_pet"] == 0 and trap["mod_ultrasound"] == 0
    assert trap["mod_other"] == 1
    lower = labels.loc["1008"]                     # "codex", "wsi"
    assert lower["mod_he_histology"] == 0 and lower["mod_spatial_proteomics"] == 0


def test_ct_fires_inside_pet_ct(labels):
    """A slash is a word boundary, so PET/CT carries both labels. Intended."""
    row = labels.loc["1005"]
    assert row["mod_pet"] == 1 and row["mod_ct"] == 1 and row["mod_mri"] == 1
    assert row["domain"] == "radiology"


def test_exclude_suppresses_one_label_and_leaves_the_record(labels, result):
    """The IHC / intrahepatic cholangiocarcinoma collision, as the dictionary handles it."""
    row = labels.loc["1006"]
    assert row["mod_ihc"] == 0            # suppressed
    assert row["mod_ultrasound"] == 1     # the record survives, with its other labels
    suppressed = result.hits.loc[
        (result.hits["pmid"] == "1006") & (result.hits["category"] == "ihc")
    ]
    assert set(suppressed["role"]) == {"include", "exclude"}
    assert set(suppressed["category_matched"]) == {0}


def test_theme_exclude_suppresses_a_theme(labels):
    """"Multimodal therapy" is not multimodal integration."""
    assert labels.loc["1011"]["theme_multimodal_integration"] == 0
    assert labels.loc["1012"]["theme_multimodal_integration"] == 1


@pytest.mark.parametrize(
    ("pmid", "domain"),
    [("1001", "both"), ("1003", "radiology"), ("1007", "pathology"), ("1008", "none")],
)
def test_domain_is_derived_from_the_modality_labels(labels, pmid, domain):
    """The rule in docs/figure-spec.md, applied to real fixture rows."""
    assert labels.loc[pmid]["domain"] == domain


@pytest.mark.parametrize(
    ("modalities_present", "expected"),
    [
        (["mri"], "radiology"),
        (["ihc"], "pathology"),
        (["ct", "he_histology"], "both"),
        (["other"], "none"),
        ([], "none"),
    ],
)
def test_derive_domain(modalities_present, expected):
    """The domain rule on its own."""
    assert classify.derive_domain(modalities_present) == expected


def test_provenance_names_the_pattern_that_fired(result):
    """A disputed label can be checked without reopening the abstract."""
    hits = result.hits
    row = hits.loc[
        (hits["pmid"] == "1009") & (hits["category"] == "clinical_fda")
    ].iloc[0]
    assert row["pattern_id"] == "clinical_fda:include[1]"
    assert row["pattern"] == "510(k)"
    assert row["kind"] == "phrase"
    assert row["n_hits"] == 1
    assert "510(k)" in row["excerpt"]
    assert set(hits.columns) == set(aggregate.PATTERN_HIT_COLUMNS)


def test_hit_counts_count_every_occurrence(modalities):
    """``n_hits`` is occurrences, not records; the report counts records."""
    match = classify.match_text(modalities, "CT and CT and CT again")["ct"]
    assert match.include_hits[0].count == 3


def test_classification_is_deterministic(records, themes, modalities):
    """Same records, same dictionaries, same labels. Every time."""
    first = classify.classify_records(records, themes, modalities)
    second = classify.classify_records(records, themes, modalities)
    pd.testing.assert_frame_equal(first.labels, second.labels)
    pd.testing.assert_frame_equal(first.hits, second.hits)


def test_missing_record_column_is_named(tmp_path):
    """A record table that is not the one parse.py writes fails loudly."""
    path = tmp_path / "records.csv"
    path.write_text("pmid,title\n1,A\n", encoding="utf-8")
    with pytest.raises(classify.RecordTableError, match="abstract"):
        classify.read_records(path)


def test_record_text_joins_title_and_abstract():
    """A missing abstract still leaves the title matchable."""
    assert classify.record_text("T", "A") == "T \n A"
    assert classify.record_text("T", None) == "T \n "
    assert classify.record_text(None, "A") == " \n A"


def test_canonical_keys_agree_everywhere():
    """The category keys are written down in four places. They must agree.

    ``config/*.yaml`` declares them, ``trends.aggregate`` names them, and
    ``trends.plotting.style`` repeats them for the drawing code, which may not
    import the pipeline. The domain lists are a fourth copy. Adding a modality
    to the dictionary alone used to surface as a wall of unrelated errors in
    another agent's test run; it surfaces here instead, as one readable failure
    naming the key that is out of step.
    """
    import yaml
    from trends.plotting import style

    assert aggregate.THEME_KEYS == style.THEME_ORDER
    assert aggregate.MODALITY_KEYS == style.MODALITY_ORDER
    assert classify.RADIOLOGY_MODALITIES == style.RADIOLOGY_MODALITIES
    assert classify.PATHOLOGY_MODALITIES == style.PATHOLOGY_MODALITIES

    config = PROJECT_ROOT / "config"
    if not (config / "modalities.yaml").exists():  # pragma: no cover - config is present
        pytest.skip("config/ is not present")
    drift: list[str] = []
    for filename, keys in (
        ("themes.yaml", aggregate.THEME_KEYS),
        ("modalities.yaml", aggregate.MODALITY_KEYS),
    ):
        declared = set(yaml.safe_load((config / filename).read_text())["categories"])
        if missing := sorted(set(keys) - declared):
            drift.append(f"config/{filename} has not caught up: missing {missing}")
        if extra := sorted(declared - set(keys)):
            drift.append(f"config/{filename} declares uncanonical {extra}")
    assert not drift, (
        "; ".join(drift)
        + ". See the message in trends.classify.load_term_dictionary for the four "
        "places that must change together."
    )

    # And every modality takes a side, or is deliberately placed outside the rule.
    classify.check_domain_coverage(aggregate.MODALITY_KEYS)


def test_the_fixture_dictionaries_cover_every_canonical_category(themes, modalities, result):
    """The fixture must keep pace with the dictionary, and be exercised.

    Two claims. Every canonical key is declared, so a table built from the
    fixture has the columns the plotting reader demands. And every named
    category is assigned to at least one fixture record, so a new modality
    cannot arrive as a row that no test ever touches.
    """
    assert set(modalities.keys) == set(aggregate.MODALITY_KEYS)
    assert set(themes.keys) == set(aggregate.THEME_KEYS)

    assigned = set(result.hits.loc[result.hits["category_matched"] == 1, "category"])
    named = {key for key in modalities.keys if key != classify.OTHER_MODALITY}
    assert named - assigned == set(), (
        "no fixture record carries these modalities; add one to "
        "tests/fixtures/classify_records.csv"
    )
    assert set(themes.keys) - assigned == set()


def test_an_unassigned_modality_is_rejected():
    """A modality in neither domain list would quietly make Panel B wrong."""
    with pytest.raises(classify.TermDictionaryError, match="none of the three lists"):
        classify.check_domain_coverage(["mri", "spectroscopy"])


def test_label_columns_follow_the_loaded_dictionary(records, themes, tmp_path):
    """The column set comes from the dictionary, not from a constant.

    A dictionary with one modality fewer produces one column fewer, with no edit
    to ``trends.aggregate``. The same mechanism gives a newly added modality its
    column.
    """
    text = MODALITIES_FIXTURE.read_text()
    start = text.index("  mammography:")
    trimmed = tmp_path / "modalities.yaml"
    trimmed.write_text(text[:start] + text[text.index("  xray:"):], encoding="utf-8")
    smaller = classify.load_term_dictionary(
        trimmed, kind="modalities", optional_include={classify.OTHER_MODALITY}
    )
    assert "mammography" not in smaller.keys

    result = classify.classify_records(records, themes, smaller)
    assert "mod_mammography" not in result.labels.columns
    assert "mod_xray" in result.labels.columns
    assert list(result.labels.columns) == list(
        aggregate.paper_label_columns(
            aggregate.THEME_KEYS,
            [key for key in aggregate.MODALITY_KEYS if key != "mammography"],
        )
    )


# --------------------------------------------------------------------------
# Report and command line
# --------------------------------------------------------------------------


def test_report_names_the_counts_a_reader_needs(result, themes, modalities):
    """The diagnostic report is how a runaway term is spotted before the figure."""
    text = classify.format_report(
        result, themes, modalities, aggregate.build_combination_counts(result.labels)
    )
    assert "records analysed :      20" in text
    assert "book_records" in text
    assert "MOST FREQUENTLY FIRING PATTERNS" in text
    assert "PATTERNS THAT NEVER FIRED" in text
    assert "digital_twins" in text
    # The figure draws a remainder column, so the diagnostic must not describe a
    # hidden tail. Wording that says otherwise misreports the figure.
    assert "remainder column" in text
    assert "Nothing is hidden" in text
    assert "tail:" not in text


def test_the_report_follows_the_figures_cap(result, themes, modalities):
    """The number of combinations listed is the figure's, not a second constant.

    The diagnostic and Panel A described different figures once, when the panel
    moved from eight columns to twelve and a remainder. Reading the cap from the
    plotting package is what stops that recurring.
    """
    from trends.plotting import panel_a

    assert classify.figure_column_cap() == panel_a.DEFAULT_TOP_N
    assert classify._FALLBACK_COLUMN_CAP == panel_a.DEFAULT_TOP_N

    text = classify.format_report(
        result, themes, modalities, aggregate.build_combination_counts(result.labels)
    )
    assert f"the top {panel_a.DEFAULT_TOP_N} per theme" in text

    # And an explicit cap still overrides it, for a one-off look at a wider list.
    narrow = classify.format_report(
        result, themes, modalities,
        aggregate.build_combination_counts(result.labels), top_combinations=3,
    )
    assert "the top 3 per theme" in narrow


def test_cli_writes_every_output(tmp_path, capsys):
    """End to end, and the tables it writes load in trends.plotting.io."""
    from trends.plotting import io

    config = tmp_path / "config"
    config.mkdir()
    (config / "themes.yaml").write_text(THEMES_FIXTURE.read_text(), encoding="utf-8")
    (config / "modalities.yaml").write_text(MODALITIES_FIXTURE.read_text(), encoding="utf-8")
    output = tmp_path / "processed"

    code = classify.main(
        ["--records", str(RECORDS_FIXTURE), "--config-dir", str(config),
         "--output", str(output), "--report"]
    )
    assert code == 0
    assert "CLASSIFICATION DIAGNOSTIC REPORT" in capsys.readouterr().out

    for name in ("paper_labels.csv", "combination_counts.csv", "theme_year_counts.csv",
                 "pattern_hits.csv", "run_manifest.json", "classification_report.txt"):
        assert (output / name).exists(), name

    data = io.load_figure_data(output)
    assert data.n_papers_total == 20

    manifest = json.loads((output / "run_manifest.json").read_text())
    assert manifest["counts"]["records_in"] == 23
    assert manifest["counts"]["exclusions"]["book_records"] == 1
    assert manifest["config"]["themes"]["version"] == 7
    assert len(manifest["config"]["themes"]["sha256"]) == 64
    # No corpus.yaml in this directory, so the partial year falls back and says so.
    assert manifest["partial_year"] == {"year": 2026, "source": "newest year in corpus"}


def test_cli_takes_the_partial_year_from_the_corpus_config(tmp_path):
    """``corpus.yaml`` fixes the retrieval year; the manifest records the route."""
    config = tmp_path / "config"
    config.mkdir()
    (config / "themes.yaml").write_text(THEMES_FIXTURE.read_text(), encoding="utf-8")
    (config / "modalities.yaml").write_text(MODALITIES_FIXTURE.read_text(), encoding="utf-8")
    (config / "corpus.yaml").write_text(
        'version: 2\ndate_range:\n  start: "2015/01/01"\n  end: "2025/06/30"\n',
        encoding="utf-8",
    )
    output = tmp_path / "processed"
    classify.main(
        ["--records", str(RECORDS_FIXTURE), "--config-dir", str(config),
         "--output", str(output), "--no-hits"]
    )
    manifest = json.loads((output / "run_manifest.json").read_text())
    assert manifest["partial_year"]["year"] == 2025
    assert manifest["partial_year"]["source"].endswith("corpus.yaml:date_range.end")
    assert not (output / "pattern_hits.csv").exists()
    # The same date range bounds the corpus: 2014 below, 2026 above.
    assert manifest["year_range_applied"] == {"first": 2015, "last": 2025}
    assert manifest["counts"]["exclusions"]["outside_date_range"] == 6

    flagged = pd.read_csv(output / "theme_year_counts.csv", comment="#")
    assert set(flagged.loc[flagged["partial_year"] == 1, "year"]) == {2025}


def test_cli_reports_a_broken_dictionary_and_exits_nonzero(tmp_path, capsys):
    """A malformed dictionary stops the run; it does not classify nothing."""
    config = tmp_path / "config"
    config.mkdir()
    (config / "themes.yaml").write_text("version: 1\ncategories: {}\n", encoding="utf-8")
    (config / "modalities.yaml").write_text(MODALITIES_FIXTURE.read_text(), encoding="utf-8")
    code = classify.main(
        ["--records", str(RECORDS_FIXTURE), "--config-dir", str(config),
         "--output", str(tmp_path / "out")]
    )
    assert code == 2
    assert "not usable" in capsys.readouterr().err


# --------------------------------------------------------------------------
# Mammography and radiography, added 2026-09-01 with the modality list
# --------------------------------------------------------------------------


def test_mammography_prefix_covers_the_word_family(modalities) -> None:
    """One prefix must cover mammogram, mammography and mammographic."""
    for text in ("a screening mammogram", "screening mammography", "mammographic density"):
        assert matches(modalities, text) == {"mammography"}


def test_xray_does_not_claim_computed_tomography(modalities) -> None:
    """CT is formally "X-ray computed tomography"; that paper belongs to `ct`."""
    assert "xray" not in matches(modalities, "X-ray computed tomography of the thorax")


def test_xray_does_not_claim_crystallography(modalities) -> None:
    """X-ray names a physical process as often as it names a chest film."""
    assert matches(modalities, "X-ray diffraction of a kinase domain") == set()


# --------------------------------------------------------------------------
# `other` is additive; genomics and clinical data take no domain; the window
# --------------------------------------------------------------------------


def test_other_sits_alongside_a_named_modality(labels, result):
    """The change that stopped the multimodal theme reading as unimodal.

    ``other`` fires on its own patterns now, so a paper using CT and endoscopy
    carries both. Before, ``other`` was reachable only when nothing named
    matched, and that paper read as CT alone.
    """
    row = labels.loc["1020"]
    assert row["mod_ct"] == 1 and row["mod_other"] == 1
    assert row["domain"] == "radiology"
    hits = result.hits
    assigned = hits.loc[
        (hits["pmid"] == "1020") & (hits["category"] == "other") & (hits["role"] == "include")
    ]
    assert len(assigned) == 1
    assert "endoscop" in assigned.iloc[0]["pattern"]


def test_the_two_routes_to_other_are_distinguishable(result):
    """A pattern match and the fallback mean different things and are recorded apart."""
    hits = result.hits
    fallback = hits.loc[hits["role"] == "fallback"]
    assert set(fallback["category"]) == {"other"}
    assert set(fallback["pattern_id"]) == {"other:fallback"}
    # 1002 matched nothing at all; 1020 matched an `other` pattern.
    assert "1002" in set(fallback["pmid"])
    assert "1020" not in set(fallback["pmid"])

    routes = classify.other_route_counts(result)
    assert routes["by_pattern"] + routes["by_fallback"] == routes["total"]
    assert routes["by_pattern"] >= 1 and routes["by_fallback"] >= 1


def test_every_paper_still_carries_at_least_one_modality(labels):
    """The fallback survives the change, so Panel A loses no paper."""
    columns = [f"mod_{key}" for key in aggregate.MODALITY_KEYS]
    assert int(labels[columns].sum(axis=1).min()) >= 1


def test_genomics_and_clinical_data_take_no_domain(labels):
    """A paper using MRI and genomics is radiology, not both."""
    row = labels.loc["1019"]
    assert row["mod_mri"] == 1
    assert row["mod_genomics"] == 1 and row["mod_clinical_data"] == 1
    assert row["domain"] == "radiology"


def test_domain_coverage_accepts_a_deliberate_non_domain_modality():
    """Membership of NO_DOMAIN_MODALITIES is a decision, and the guard reads it."""
    classify.check_domain_coverage(["mri", "genomics", "clinical_data", "other"])
    assert "genomics" in classify.NO_DOMAIN_MODALITIES
    assert not (classify.NO_DOMAIN_MODALITIES & classify.RADIOLOGY_MODALITIES)
    assert not (classify.NO_DOMAIN_MODALITIES & classify.PATHOLOGY_MODALITIES)


def test_a_modality_in_two_lists_is_rejected(monkeypatch):
    """Belonging to two lists is as wrong as belonging to none."""
    monkeypatch.setattr(
        classify, "NO_DOMAIN_MODALITIES", frozenset({"other", "mri"})
    )
    with pytest.raises(classify.TermDictionaryError, match="more than one list"):
        classify.check_domain_coverage(["mri", "other"])


def test_records_outside_the_date_window_are_dropped(records, themes, modalities):
    """An early-online record makes the corpus's first year biased, so it goes."""
    windowed = classify.classify_records(
        records, themes, modalities, year_range=(2015, 2026)
    )
    assert windowed.exclusions["outside_date_range"] == 1
    assert 2014 not in set(windowed.labels["year"])
    assert windowed.n_records_out == 19


def test_no_window_keeps_every_year(result):
    """With no date range configured, nothing is dropped on that rule."""
    assert result.exclusions["outside_date_range"] == 0
    assert 2014 in set(result.labels["year"])


def test_the_window_is_read_from_the_corpus_config(tmp_path):
    """The window comes from the config, not from a number in the code."""
    path = tmp_path / "corpus.yaml"
    path.write_text(
        'version: 3\ndate_range:\n  start: "2015/01/01"\n  end: "2026/09/01"\n',
        encoding="utf-8",
    )
    window = classify.read_corpus_window(path)
    assert window.years == (2015, 2026)
    assert window.partial_year == 2026
    assert window.meta["date_range_start"] == "2015/01/01"

    missing = classify.read_corpus_window(tmp_path / "absent.yaml")
    assert missing.years is None and missing.partial_year is None


def test_an_agent_that_is_a_drug_is_excluded_not_matched(labels, result):
    """"Agent" is a drug as often as it is software.

    In this corpus bare "agent" matches contrast agents and therapeutic agents
    far more often than it matches an AI one, so the agentic theme lives or dies
    by its exclude list. The fixture reproduces the collision: one record is a
    planning, tool-calling system, the other is gadolinium.
    """
    assert labels.loc["1022"]["theme_agentic_ai"] == 1
    assert labels.loc["1023"]["theme_agentic_ai"] == 0
    assert labels.loc["1023"]["mod_mri"] == 1        # the record itself survives

    hits = result.hits
    suppressed = hits.loc[(hits["pmid"] == "1023") & (hits["category"] == "agentic_ai")]
    assert set(suppressed["role"]) == {"include", "exclude"}
    assert set(suppressed["category_matched"]) == {0}
    assert "contrast agent" in " ".join(suppressed["excerpt"]).lower()


# --------------------------------------------------------------------------
# The config version ledger
#
# A config file's `version` is what a run manifest records, and it is the only
# thing that lets a reader tie a published count back to the terms that produced
# it. That guarantee breaks silently when a file is edited without the version
# moving: the manifest still names a version, but the version no longer means
# what it meant. It happened three times in one day, twice under themes.yaml and
# once under modalities.yaml, and was caught each time by hand.
#
# `config/VERSIONS.json` freezes each version to a hash, and these tests make it
# bite. The ledger is append-only: a version, once written, is never re-pointed
# at different content.
# --------------------------------------------------------------------------

#: Config files the ledger governs.
LEDGERED_CONFIGS: tuple[str, ...] = ("themes.yaml", "modalities.yaml", "corpus.yaml")

#: The ledger itself, inside the config directory.
LEDGER_NAME = "VERSIONS.json"

#: Shortest hash prefix the ledger may record and still be checkable.
_MIN_HASH_PREFIX = 8


def _keep_duplicate_pairs(pairs: list[tuple[str, object]]) -> list[tuple[str, object]]:
    """``object_pairs_hook`` that preserves repeated keys instead of collapsing them.

    ``json.load`` keeps the last of a repeated key, which would hide exactly the
    mistake this checks for.
    """
    return pairs


def _entry_hash(value: object) -> str | None:
    """Pull the hash out of a ledger entry.

    Accepts a bare string, or a mapping carrying the hash under ``sha256``,
    ``hash``, or ``digest`` — the shape a reconstructed entry takes when it is
    marked as such. Returns ``None`` when no hash can be read, which the caller
    treats as "not recorded" rather than as a violation.
    """
    if isinstance(value, list):  # a nested object, from the pairs hook
        value = dict(value)
    if isinstance(value, str):
        text = value.strip()
    elif isinstance(value, dict):
        for key in ("sha256", "hash", "digest"):
            found = value.get(key)
            if isinstance(found, str):
                text = found.strip()
                break
        else:
            return None
    else:
        return None
    text = text.rstrip("….").strip()
    if len(text) < _MIN_HASH_PREFIX or any(c not in "0123456789abcdefABCDEF" for c in text):
        return None
    return text.lower()


def _file_sections(raw: list) -> list[tuple[str, list]]:
    """Return the ``(filename, versions)`` sections of a parsed ledger.

    Two shapes are accepted: entries at the top level, and entries nested under
    a ``files`` key beside metadata. Keys beginning with ``_`` are commentary —
    the ledger carries its own README and a record of past breaches — and are
    skipped, as is anything that is not a mapping of versions.
    """
    pairs = [item for item in raw if isinstance(item, (list, tuple)) and len(item) == 2]
    for key, value in pairs:
        if key == "files" and isinstance(value, list):
            pairs = [item for item in value if isinstance(item, (list, tuple)) and len(item) == 2]
            break
    return [
        (str(key), value)
        for key, value in pairs
        if not str(key).startswith("_") and isinstance(value, list)
    ]


def _parse_ledger(path: Path) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Read ``VERSIONS.json``.

    Returns the recorded hashes as ``{filename: {version: hash}}``, and a list of
    reuse problems: a version written twice with different hashes.
    """
    raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_keep_duplicate_pairs)
    entries: dict[str, dict[str, str]] = {}
    problems: list[str] = []
    for filename, versions in _file_sections(raw):
        recorded: dict[str, str] = {}
        for item in versions:
            if not (isinstance(item, (list, tuple)) and len(item) == 2):
                continue
            version, value = item
            digest = _entry_hash(value)
            if digest is None:
                continue
            version = str(version)
            if version in recorded and recorded[version] != digest:
                problems.append(
                    f"{path} records {filename} version {version} twice, with different "
                    f"hashes ({recorded[version][:12]}… and {digest[:12]}…). A version is "
                    "frozen once. Give the later content a new version number and append "
                    "it as a new entry; never re-point an existing one."
                )
            recorded[version] = digest
        entries[filename] = recorded
    return entries, problems


def _hash_mismatches(config_dir: Path, entries: dict[str, dict[str, str]]) -> list[str]:
    """Compare each config file on disk with the hash its own version froze.

    Files absent from disk, files the ledger does not carry, and versions the
    ledger does not carry are skipped: an unrecorded version is not evidence of
    a violation.
    """
    import yaml

    problems: list[str] = []
    for filename in LEDGERED_CONFIGS:
        path = config_dir / filename
        recorded = entries.get(filename)
        if not path.exists() or not recorded:
            continue
        version = str(yaml.safe_load(path.read_text(encoding="utf-8")).get("version"))
        expected = recorded.get(version)
        if expected is None:
            continue
        actual = classify.file_digest(path)
        if not actual.startswith(expected):
            problems.append(
                f"config/{filename} says version {version}, and {LEDGER_NAME} froze "
                f"version {version} at {expected[:12]}…, but the file now hashes to "
                f"{actual[:12]}…. The file was edited without the version moving, so "
                f"every manifest naming {filename} v{version} is now ambiguous. Fix it by "
                f"bumping `version` in config/{filename} and appending the new version "
                f"and its hash to config/{LEDGER_NAME} — not by editing the hash recorded "
                "for the existing version."
            )
    return problems


def test_config_files_match_the_version_ledger():
    """A config file may not change without its version moving.

    This is the guard that replaces catching it by hand.
    """
    config = PROJECT_ROOT / "config"
    ledger = config / LEDGER_NAME
    if not ledger.exists():
        pytest.skip(f"config/{LEDGER_NAME} does not exist yet")
    entries, _ = _parse_ledger(ledger)
    problems = _hash_mismatches(config, entries)
    assert not problems, "\n\n".join(problems)


def test_the_version_ledger_never_reuses_a_version():
    """The ledger is append-only: one version, one hash, forever."""
    config = PROJECT_ROOT / "config"
    ledger = config / LEDGER_NAME
    if not ledger.exists():
        pytest.skip(f"config/{LEDGER_NAME} does not exist yet")
    _, problems = _parse_ledger(ledger)
    assert not problems, "\n\n".join(problems)


# -- and the guard's own tests, so it is not itself taken on trust ------------


def _write_ledger(tmp_path: Path, body: str) -> Path:
    """Write a config directory holding one dictionary and a ledger."""
    config = tmp_path / "config"
    config.mkdir(exist_ok=True)
    (config / LEDGER_NAME).write_text(body, encoding="utf-8")
    return config


def test_the_ledger_guard_passes_a_change_followed_by_a_bump(tmp_path):
    """The legitimate case: edit the file, bump the version, append an entry."""
    config = _write_ledger(tmp_path, "{}")
    path = config / "themes.yaml"
    path.write_text("version: 4\ncategories: {}\n", encoding="utf-8")
    first = classify.file_digest(path)

    path.write_text("version: 5\ncategories: {}\n", encoding="utf-8")
    second = classify.file_digest(path)
    (config / LEDGER_NAME).write_text(
        json.dumps({"themes.yaml": {"4": first, "5": second}}), encoding="utf-8"
    )
    entries, reuse = _parse_ledger(config / LEDGER_NAME)
    assert _hash_mismatches(config, entries) == []
    assert reuse == []


def test_the_ledger_guard_catches_an_edit_without_a_bump(tmp_path):
    """Failure mode one, and the message must say what to do about it."""
    config = _write_ledger(tmp_path, "{}")
    path = config / "themes.yaml"
    path.write_text("version: 9\ncategories: {}\n", encoding="utf-8")
    frozen = classify.file_digest(path)
    (config / LEDGER_NAME).write_text(
        json.dumps({"themes.yaml": {"9": frozen}}), encoding="utf-8"
    )
    path.write_text("version: 9\ncategories: {}\n# a measurement note\n", encoding="utf-8")

    entries, _ = _parse_ledger(config / LEDGER_NAME)
    problems = _hash_mismatches(config, entries)
    assert len(problems) == 1
    assert "says version 9" in problems[0]
    assert "edited without the version moving" in problems[0]
    assert "bumping `version`" in problems[0]


def test_the_ledger_guard_catches_a_reused_version(tmp_path):
    """Failure mode two: the same version written twice with different hashes."""
    config = _write_ledger(
        tmp_path,
        '{"themes.yaml": {"9": "' + "a" * 64 + '", "9": "' + "b" * 64 + '"}}',
    )
    _, problems = _parse_ledger(config / LEDGER_NAME)
    assert len(problems) == 1
    assert "version 9 twice" in problems[0]
    assert "frozen once" in problems[0]


def test_the_ledger_guard_is_silent_about_what_it_does_not_carry(tmp_path):
    """Absence is not a violation: an unrecorded file or version is skipped.

    The ledger is being reconstructed and will not carry every past version.
    """
    config = _write_ledger(tmp_path, "{}")
    (config / "themes.yaml").write_text("version: 9\ncategories: {}\n", encoding="utf-8")
    (config / "modalities.yaml").write_text("version: 2\ncategories: {}\n", encoding="utf-8")
    (config / LEDGER_NAME).write_text(
        json.dumps({"themes.yaml": {"7": "c" * 64}}), encoding="utf-8"  # v9 not recorded
    )
    entries, reuse = _parse_ledger(config / LEDGER_NAME)
    assert _hash_mismatches(config, entries) == []      # v9 unrecorded, so nothing to check
    assert reuse == []


def test_the_ledger_guard_accepts_a_marked_reconstructed_entry(tmp_path):
    """A reconstructed entry carries its hash in a mapping and is still checked."""
    config = _write_ledger(tmp_path, "{}")
    path = config / "modalities.yaml"
    path.write_text("version: 2\ncategories: {}\n", encoding="utf-8")
    (config / LEDGER_NAME).write_text(
        json.dumps({
            "modalities.yaml": {
                "2": {"sha256": classify.file_digest(path), "reconstructed": True}
            }
        }),
        encoding="utf-8",
    )
    entries, _ = _parse_ledger(config / LEDGER_NAME)
    assert _hash_mismatches(config, entries) == []
