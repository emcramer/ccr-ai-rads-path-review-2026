"""Tests for :mod:`trends.aggregate`.

The arithmetic these hold to is the arithmetic Panel A rests on: within a theme,
the combination counts sum to that theme's paper count, because every paper
carries at least one modality and appears in exactly one column. Panel B's
clinical split is deliberately not additive, and that is tested too, so nobody
later "fixes" it.

The output is checked by loading it back through ``trends.plotting.io``. A table
that will not load there is not done.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from trends import aggregate, classify
from trends.plotting import io

FIXTURES = Path(__file__).parent / "fixtures"


def make_labels(rows: list[dict]) -> pd.DataFrame:
    """Build a labels table from terse row specifications.

    Each row gives ``pmid``, ``year``, a ``themes`` list, and a ``modalities``
    list. The theme and modality flag columns, and the derived ``domain``, are
    filled in, so a test reads as the case it is testing.
    """
    built = []
    for row in rows:
        modalities = list(row.get("modalities") or [aggregate.OTHER_MODALITY])
        record = {
            "pmid": str(row["pmid"]),
            "year": int(row["year"]),
            "year_source": row.get("year_source", "PubDate"),
        }
        for key in aggregate.THEME_KEYS:
            record[f"theme_{key}"] = int(key in row.get("themes", ()))
        for key in aggregate.MODALITY_KEYS:
            record[f"mod_{key}"] = int(key in modalities)
        record["domain"] = classify.derive_domain(modalities)
        built.append(record)
    return pd.DataFrame(built, columns=list(aggregate.PAPER_LABEL_COLUMNS))


@pytest.fixture(scope="module")
def labels() -> pd.DataFrame:
    """The fixture records, classified by the fixture dictionaries."""
    themes = classify.load_term_dictionary(
        FIXTURES / "classify_themes.yaml", kind="themes", expected_keys=classify.THEME_KEYS
    )
    modalities = classify.load_term_dictionary(
        FIXTURES / "classify_modalities.yaml",
        kind="modalities",
        expected_keys=classify.MODALITY_KEYS,
        optional_include={classify.OTHER_MODALITY},
    )
    records = classify.read_records(FIXTURES / "classify_records.csv")
    # The window is the corpus's, so the fixture's deliberately-early record is
    # excluded here exactly as it is in a real run.
    return classify.classify_records(
        records, themes, modalities, year_range=(2015, 2026)
    ).labels


# --------------------------------------------------------------------------
# combination_counts.csv
# --------------------------------------------------------------------------


def test_combination_counts_sum_to_each_theme_total(labels):
    """The property Panel A rests on. No paper is lost and none is counted twice."""
    counts = aggregate.build_combination_counts(labels)
    for theme in aggregate.THEME_KEYS:
        expected = int(labels[f"theme_{theme}"].sum())
        found = int(counts.loc[counts["theme"] == theme, "n_papers"].sum())
        assert found == expected, theme


def test_combination_counts_sum_holds_on_a_larger_hand_built_case():
    """The same property where papers share combinations and carry two themes."""
    rows = [
        {"pmid": i, "year": 2024, "themes": ("foundation_models",), "modalities": ["ct"]}
        for i in range(10)
    ]
    rows += [
        {"pmid": 100 + i, "year": 2024,
         "themes": ("foundation_models", "digital_twins"),
         "modalities": ["ct", "mri"]}
        for i in range(4)
    ]
    rows += [{"pmid": 200, "year": 2024, "themes": ("digital_twins",), "modalities": []}]
    counts = aggregate.build_combination_counts(make_labels(rows))
    foundation = counts.loc[counts["theme"] == "foundation_models"]
    assert int(foundation["n_papers"].sum()) == 14
    assert list(foundation["modality_set"]) == ["ct", "ct+mri"]
    assert list(foundation["n_papers"]) == [10, 4]
    twins = counts.loc[counts["theme"] == "digital_twins"]
    assert int(twins["n_papers"].sum()) == 5
    assert set(twins["modality_set"]) == {"ct+mri", "other"}


def test_modality_set_is_alphabetical_and_plus_joined():
    """The spec asks for sorted keys joined by ``+``; the plot reader parses on ``+``."""
    labels = make_labels(
        [{"pmid": 1, "year": 2024, "themes": ("digital_twins",),
          "modalities": ["pet", "he_histology", "ct"]}]
    )
    counts = aggregate.build_combination_counts(labels)
    assert counts.loc[0, "modality_set"] == "ct+he_histology+pet"
    assert counts.loc[0, "n_modalities"] == 3


def test_other_alone_is_a_legitimate_combination():
    """A paper matching no named modality still occupies a column."""
    labels = make_labels([{"pmid": 1, "year": 2024, "themes": ("digital_twins",)}])
    counts = aggregate.build_combination_counts(labels)
    assert list(counts["modality_set"]) == ["other"]
    assert list(counts["n_modalities"]) == [1]


def test_rank_is_dense_from_one_and_ordered_by_count():
    """Panel A draws columns in rank order, so the rank must be exact."""
    rows = [{"pmid": i, "year": 2024, "themes": ("clinical_fda",), "modalities": ["ct"]}
            for i in range(5)]
    rows += [{"pmid": 10 + i, "year": 2024, "themes": ("clinical_fda",), "modalities": ["mri"]}
             for i in range(3)]
    rows += [{"pmid": 20, "year": 2024, "themes": ("clinical_fda",), "modalities": ["pet"]}]
    counts = aggregate.build_combination_counts(make_labels(rows))
    assert list(counts["rank_in_theme"]) == [1, 2, 3]
    assert list(counts["modality_set"]) == ["ct", "mri", "pet"]


def test_ties_break_deterministically():
    """Equal counts break on set size, then alphabetically. Reproducible, not arbitrary."""
    rows = [
        {"pmid": 1, "year": 2024, "themes": ("clinical_fda",), "modalities": ["mri", "ct"]},
        {"pmid": 2, "year": 2024, "themes": ("clinical_fda",), "modalities": ["pet"]},
        {"pmid": 3, "year": 2024, "themes": ("clinical_fda",), "modalities": ["ct"]},
    ]
    counts = aggregate.build_combination_counts(make_labels(rows))
    assert list(counts["modality_set"]) == ["ct", "pet", "ct+mri"]
    again = aggregate.build_combination_counts(make_labels(rows))
    pd.testing.assert_frame_equal(counts, again)


def test_a_theme_with_no_papers_contributes_no_rows(labels):
    """An empty theme block is empty, not a row of zeroes."""
    empty = make_labels([{"pmid": 1, "year": 2024, "themes": ("digital_twins",)}])
    counts = aggregate.build_combination_counts(empty)
    assert set(counts["theme"]) == {"digital_twins"}


# --------------------------------------------------------------------------
# theme_year_counts.csv
# --------------------------------------------------------------------------


def test_year_axis_is_dense(labels):
    """A year with no papers draws as a zero, not as a gap in the line."""
    counts = aggregate.build_theme_year_counts(labels, partial_year=2026)
    years = sorted(set(counts["year"]))
    assert years == [2021, 2022, 2023, 2024, 2025, 2026]
    empty_year = counts.loc[counts["year"] == 2022, "n_papers"]
    assert set(empty_year) == {0}


def test_every_theme_gets_the_whole_domain_breakdown(labels):
    """The figure chooses which rows to draw, so the table carries all of them."""
    counts = aggregate.build_theme_year_counts(labels, partial_year=2026)
    series = set(map(tuple, counts[["theme", "domain"]].drop_duplicates().to_numpy()))
    assert series == {
        (theme, domain)
        for theme in aggregate.THEME_KEYS
        for domain in aggregate.DOMAIN_SERIES
    }
    assert len(counts) == len(aggregate.THEME_KEYS) * len(aggregate.DOMAIN_SERIES) * 6
    assert not counts.duplicated(subset=["theme", "domain", "year"]).any()


def test_the_four_domain_rows_partition_each_theme(labels):
    """radiology + pathology + both + none == all, for every theme and every year.

    Each paper carries exactly one ``domain`` value, so the four rows are a
    partition. This is the identity Panel B's legend rests on, and the one that
    would break silently if ``domain`` and this reduction ever disagreed.
    """
    counts = aggregate.build_theme_year_counts(labels, partial_year=2026)
    wide = counts.pivot_table(
        index=["theme", "year"], columns="domain", values="n_papers", aggfunc="sum"
    )
    parts = wide[["radiology", "pathology", "both", "none"]].sum(axis=1)
    assert (parts == wide["all"]).all()
    assert int(wide["all"].sum()) > 0  # not vacuously true


def test_radiology_and_pathology_alone_do_not_sum_to_the_theme():
    """The other half of the same fact, and the reason the legend must say so.

    A cross-specialty paper sits in ``both``, not in each side, so the two
    single-specialty lines under-count the theme by the cross-specialty and
    no-domain papers.
    """
    labels = make_labels([
        {"pmid": 1, "year": 2024, "themes": ("clinical_fda",),
         "modalities": ["ct", "he_histology"]},          # both
        {"pmid": 2, "year": 2024, "themes": ("clinical_fda",), "modalities": ["ct"]},
        {"pmid": 3, "year": 2024, "themes": ("clinical_fda",), "modalities": ["genomics"]},
    ])
    counts = aggregate.build_theme_year_counts(labels)
    by_domain = counts[counts.theme == "clinical_fda"].set_index("domain")["n_papers"]
    assert by_domain["all"] == 3
    assert by_domain["radiology"] == 1 and by_domain["pathology"] == 0
    assert by_domain["both"] == 1 and by_domain["none"] == 1
    assert by_domain["radiology"] + by_domain["pathology"] < by_domain["all"]


def test_a_paper_with_no_imaging_modality_lands_on_the_none_line():
    """It is not lost: it counts in ``all`` and in ``none``, and nowhere else."""
    labels = make_labels([{"pmid": 1, "year": 2024, "themes": ("clinical_fda",)}])
    counts = aggregate.build_theme_year_counts(labels)
    by_domain = counts[counts.theme == "clinical_fda"].set_index("domain")["n_papers"]
    assert by_domain["all"] == 1 and by_domain["none"] == 1
    assert by_domain["radiology"] == 0 and by_domain["pathology"] == 0
    assert by_domain["both"] == 0


def test_only_the_retrieval_year_is_flagged_partial(labels):
    """The reader rejects a table flagging more than one year."""
    counts = aggregate.build_theme_year_counts(labels, partial_year=2026)
    assert set(counts.loc[counts["partial_year"] == 1, "year"]) == {2026}
    assert set(counts.loc[counts["partial_year"] == 0, "year"]) == {2021, 2022, 2023, 2024, 2025}


def test_no_year_is_flagged_when_none_is_given(labels):
    """Without a retrieval year nothing is claimed to be partial."""
    counts = aggregate.build_theme_year_counts(labels, partial_year=None)
    assert set(counts["partial_year"]) == {0}


def test_the_year_axis_can_be_overridden(labels):
    """A caller may widen the axis to the corpus date range."""
    counts = aggregate.build_theme_year_counts(labels, years=range(2015, 2027))
    assert sorted(set(counts["year"])) == list(range(2015, 2027))


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------


def test_written_tables_load_in_the_plotting_reader(labels, tmp_path):
    """The contract with the figure: these files must load there, or they are wrong."""
    paths = aggregate.write_tables(
        labels, tmp_path, partial_year=2026, provenance=["records: fixture"]
    )
    assert set(paths) == {"paper_labels", "combination_counts", "theme_year_counts"}
    data = io.load_figure_data(tmp_path)
    assert data.n_papers_total == len(labels)
    # The reader's vocabulary and this module's must agree, or a table that is
    # correct here is rejected there.
    from trends.plotting import style

    assert set(data.theme_years["domain"]) == set(aggregate.DOMAIN_SERIES)
    assert set(aggregate.DOMAIN_SERIES) <= set(style.DOMAIN_VALUES)


def test_the_provenance_header_does_not_break_the_reader(labels, tmp_path):
    """Every table carries a ``#`` header naming what produced it."""
    aggregate.write_tables(labels, tmp_path, provenance=["themes.yaml v7 sha256:abc"])
    text = (tmp_path / aggregate.COMBINATION_COUNTS).read_text()
    assert text.startswith("# file: combination_counts.csv")
    assert "themes.yaml v7" in text
    assert len(io.load_combination_counts(tmp_path / aggregate.COMBINATION_COUNTS)) > 0


def test_paper_labels_columns_are_the_spec_columns_in_order(labels, tmp_path):
    """docs/figure-spec.md fixes the schema; nothing extra travels with it."""
    aggregate.write_tables(labels, tmp_path)
    written = pd.read_csv(tmp_path / aggregate.PAPER_LABELS, comment="#")
    assert list(written.columns) == list(aggregate.PAPER_LABEL_COLUMNS)


def test_order_labels_names_a_missing_column(labels):
    """A labels table missing a column fails here, not in the plotting code."""
    with pytest.raises(KeyError, match="domain"):
        aggregate.order_labels(labels.drop(columns=["domain"]))


def test_empty_labels_produce_empty_tables():
    """No records is a legitimate, if useless, input. It must not raise."""
    empty = make_labels([]).astype({"year": "int64"})
    assert aggregate.build_combination_counts(empty).empty
    assert aggregate.build_theme_year_counts(empty).empty


def test_the_reductions_follow_the_table_they_are_given():
    """Column sets are read from the data, not from a constant in this module.

    A term dictionary that gains a category produces a labels table with an
    extra ``mod_`` column. Every reduction here must carry it through, so that
    adding a modality is an edit to ``config/`` and the key lists, not to the
    aggregation code. The canonical order still leads; a key the list does not
    know goes last.
    """
    labels = make_labels(
        [{"pmid": 1, "year": 2024, "themes": ("digital_twins",), "modalities": ["ct"]}]
    )
    labels["mod_spectroscopy"] = 1
    labels["theme_agents"] = 1

    assert aggregate.modality_keys_of(labels)[-1] == "spectroscopy"
    assert aggregate.modality_keys_of(labels)[:2] == ("he_histology", "ihc")
    assert aggregate.theme_keys_of(labels)[-1] == "agents"

    assert aggregate.add_modality_set(labels).iloc[0] == "ct+spectroscopy"
    assert list(aggregate.order_labels(labels).columns)[-1] == "domain"
    assert "mod_spectroscopy" in aggregate.order_labels(labels).columns

    counts = aggregate.build_combination_counts(labels)
    assert set(counts["theme"]) == {"digital_twins", "agents"}
    assert set(counts["modality_set"]) == {"ct+spectroscopy"}
    # Panel B draws a line per theme, zero-paper themes included, so the year
    # table carries every theme the labels declare.
    years = aggregate.build_theme_year_counts(labels)
    assert set(years["theme"]) == set(aggregate.theme_keys_of(labels))
    totals = years[(years["theme"] == "agents") & (years["domain"] == "all")]
    assert int(totals["n_papers"].sum()) == 1
