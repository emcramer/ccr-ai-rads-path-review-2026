"""Tests for turning PubMed XML into rows.

The fixture ``tests/fixtures/pubmed_sample.xml`` is a real efetch response,
recorded on 2026-09-01, holding six records chosen for their edge cases:

===========  =====================================================
PMID         Why it is in the fixture
===========  =====================================================
42676058     Structured abstract, four labeled sections.
40389997     No abstract at all (a published erratum).
41509996     Online in 2025, issue dated 2026: the article date wins.
29854105     Issue dated 2017, article date 2018: the issue date wins.
             Also carries no DOI.
41046013     Free-text ``MedlineDate`` of "2025 Winter".
42625643     An ordinary record: DOI, 15 MeSH terms, several
             publication types.
===========  =====================================================

No test here reaches the network.
"""

from __future__ import annotations

import json

import pytest

from trends.parse import (
    ParseSummary,
    _abstract_from,
    _first_year,
    choose_year,
    iter_records,
    parse_directory,
    write_outputs,
)


# -- the year rule ---------------------------------------------------------

@pytest.mark.parametrize(
    "article, journal, history, expected",
    [
        (2019, 2020, None, (2019, "ArticleDate")),   # online first, next year's issue
        (2020, 2020, None, (2020, "PubDate")),       # same year, no ambiguity
        (2021, 2020, None, (2020, "PubDate")),       # article date follows the issue
        (None, 2020, None, (2020, "PubDate")),       # print only
        (2019, None, None, (2019, "ArticleDate")),   # electronic only
        (None, None, 2018, (2018, "PubMedPubDate[pubmed]")),  # last resort
        (None, None, None, (None, "none")),          # nothing to go on
    ],
)
def test_choose_year(article, journal, history, expected):
    assert choose_year(article, journal, history) == expected


def test_year_rule_prefers_the_earlier_electronic_date(sample_records):
    row = sample_records["41509996"]
    assert (row["article_date_year"], row["pub_date_year"]) == (2025, 2026)
    assert row["year"] == 2025
    assert row["year_source"] == "ArticleDate"


def test_year_rule_keeps_the_issue_date_when_it_comes_first(sample_records):
    row = sample_records["29854105"]
    assert (row["article_date_year"], row["pub_date_year"]) == (2018, 2017)
    assert row["year"] == 2017
    assert row["year_source"] == "PubDate"


def test_year_is_read_out_of_a_free_text_medline_date(sample_records):
    row = sample_records["41046013"]
    assert row["year"] == 2025
    assert row["year_source"] == "PubDate[MedlineDate]"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2019 Winter", 2019), ("2015 Nov-Dec", 2015), ("2015-2016", 2015),
        ("2026", 2026), ("Spring", None), ("", None),
    ],
)
def test_first_year(text, expected):
    assert _first_year(text) == expected


def test_every_row_records_where_its_year_came_from(sample_records):
    assert all(row["year_source"] != "" for row in sample_records.values())


# -- abstracts -------------------------------------------------------------

def test_structured_abstract_keeps_its_labels(sample_records):
    row = sample_records["42676058"]
    assert row["abstract_structured"] is True
    assert row["abstract_sections"] == 4
    assert row["abstract"].startswith("BACKGROUND:")
    assert "METHODS:" in row["abstract"]
    assert row["has_abstract"] is True


def test_missing_abstract_is_empty_not_absent(sample_records):
    row = sample_records["40389997"]
    assert row["abstract"] == ""
    assert row["has_abstract"] is False
    assert row["abstract_structured"] is False
    assert row["abstract_sections"] == 0
    assert row["title"]  # the rest of the record still parses


def test_unstructured_abstract_is_one_unlabeled_section(sample_records):
    row = sample_records["41509996"]
    assert row["has_abstract"] is True
    assert row["abstract_structured"] is False
    assert row["abstract_sections"] == 1


def test_abstract_from_handles_a_missing_element():
    assert _abstract_from(None) == ("", False, 0)


# -- the other fields ------------------------------------------------------

def test_ordinary_record_carries_every_field(sample_records):
    row = sample_records["42625643"]
    assert row["pmid"] == "42625643"
    assert row["doi"] == "10.3389/fimmu.2026.1915946"
    assert row["journal_iso"] == "Front Immunol"
    assert row["journal"]
    assert row["language"] == "eng"
    assert row["languages"] == ["eng"]
    assert "Journal Article" in row["publication_types"]
    assert len(row["mesh_descriptors"]) == 15
    assert row["record_type"] == "PubmedArticle"
    assert row["source_file"] == "pubmed_sample.xml"


def test_a_record_without_a_doi_gives_an_empty_string(sample_records):
    assert sample_records["29854105"]["doi"] == ""


def test_mesh_major_topics_are_a_subset(sample_records):
    row = sample_records["41046013"]
    assert set(row["mesh_major_descriptors"]) <= set(row["mesh_descriptors"])


def test_fixture_holds_the_six_expected_records(sample_records):
    assert set(sample_records) == {
        "42676058", "40389997", "41509996", "29854105", "41046013", "42625643"
    }


# -- the directory-level parse --------------------------------------------

def test_parse_directory_counts_and_writes(tmp_path, sample_xml):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "efetch_0000_0000000.xml").write_bytes(sample_xml)

    frame, summary = parse_directory(raw)

    assert len(frame) == 6
    assert isinstance(summary, ParseSummary)
    assert summary.without_abstract == 1
    assert summary.with_structured_abstract == 3
    assert summary.without_year == 0
    assert summary.year_sources["ArticleDate"] == 1
    assert summary.duplicate_pmids == 0
    assert str(frame["year"].dtype) == "Int64"

    out = tmp_path / "interim"
    paths = write_outputs(frame, summary, out)
    assert paths["parquet"].exists() and paths["csv"].exists()

    written = json.loads(paths["summary"].read_text())
    assert written["abstracts"]["without_abstract"] == 1
    assert written["records"] == 6

    import pandas as pd
    assert len(pd.read_parquet(paths["parquet"])) == 6
    # The CSV twin flattens list columns so a reader can scan it.
    assert ";" in pd.read_csv(paths["csv"])["mesh_descriptors"].dropna().iloc[0]


def test_duplicate_pmids_across_batches_are_dropped_and_counted(tmp_path, sample_xml):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "efetch_0000_0000000.xml").write_bytes(sample_xml)
    (raw / "efetch_0001_0000200.xml").write_bytes(sample_xml)

    frame, summary = parse_directory(raw)

    assert len(frame) == 6
    assert summary.duplicate_pmids == 6
    assert summary.records == 6


def test_an_empty_directory_fails_loudly(tmp_path):
    with pytest.raises(FileNotFoundError, match="No efetch"):
        parse_directory(tmp_path)


def test_iter_records_reads_both_record_tags():
    book = (
        b'<PubmedArticleSet><PubmedBookArticle><BookDocument>'
        b'<PMID Version="1">31643176</PMID>'
        b'<Book><PubDate><Year>2019</Year></PubDate>'
        b"<BookTitle>StatPearls</BookTitle></Book>"
        b"<ArticleTitle>Radiology Artifacts</ArticleTitle>"
        b"<Abstract><AbstractText>A chapter abstract.</AbstractText></Abstract>"
        b"<Language>eng</Language>"
        b"<PublicationType>Study Guide</PublicationType>"
        b"</BookDocument></PubmedBookArticle></PubmedArticleSet>"
    )
    rows = list(iter_records(book, "book.xml"))
    assert len(rows) == 1
    assert rows[0]["record_type"] == "PubmedBookArticle"
    assert rows[0]["year"] == 2019
    assert rows[0]["year_source"] == "Book/PubDate"
    assert rows[0]["title"] == "Radiology Artifacts"
    assert rows[0]["has_abstract"] is True
