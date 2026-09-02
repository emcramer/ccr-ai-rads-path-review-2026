"""Turn captured PubMed XML into one row per record.

Reads the ``efetch_*.xml`` files of a raw capture directory and writes
``records.parquet`` with a CSV twin for reading, plus ``parse_summary.json``
holding the counts a reader would otherwise have to recompute: records with no
abstract, records with a structured abstract, and where each row's year came
from.

The year rule, which the trend line rests on, is in :func:`choose_year`.

Run it alone with::

    python -m trends.parse --raw-dir data/raw/2026-09-01 --out data/interim
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import pandas as pd
from lxml import etree

log = logging.getLogger(__name__)

# Year columns are held as pandas nullable integers, so a record with no year
# stays missing instead of turning the whole column into floats.
INT_COLUMNS = ("year", "article_date_year", "pub_date_year")

# Columns held as lists of strings. The CSV twin joins them on "; ".
LIST_COLUMNS = ("publication_types", "mesh_descriptors", "mesh_major_descriptors", "languages")

# A year in a free-text date string. PubMed's MedlineDate holds things like
# "2015 Nov-Dec", "2015-2016", and "2019 Winter".
_YEAR_IN_TEXT = re.compile(r"\b(1[5-9]\d{2}|20\d{2}|21\d{2})\b")


@dataclass(frozen=True)
class ParseSummary:
    """Counts describing one parse, written beside the records."""

    files: int
    records: int
    articles: int
    book_articles: int
    duplicate_pmids: int
    without_abstract: int
    with_structured_abstract: int
    without_year: int
    year_sources: dict[str, int]
    languages: dict[str, int]
    year_histogram: dict[str, int]

    def as_dict(self) -> dict[str, Any]:
        """Return the summary as a JSON-ready mapping."""
        return {
            "files": self.files,
            "records": self.records,
            "records_by_type": {
                "PubmedArticle": self.articles,
                "PubmedBookArticle": self.book_articles,
            },
            "duplicate_pmids_dropped": self.duplicate_pmids,
            "abstracts": {
                "without_abstract": self.without_abstract,
                "with_structured_abstract": self.with_structured_abstract,
                "with_unstructured_abstract": self.records
                - self.without_abstract
                - self.with_structured_abstract,
            },
            "year": {
                "without_year": self.without_year,
                "sources": self.year_sources,
                "histogram": self.year_histogram,
            },
            "languages": self.languages,
        }


def _text(node: etree._Element | None) -> str:
    """Flatten an element's text, markup and all, to one whitespace-normal line.

    PubMed titles and abstracts carry inline ``<i>``, ``<sup>``, and ``<b>``
    tags. Taking ``.text`` alone would truncate at the first of them.
    """
    if node is None:
        return ""
    return re.sub(r"\s+", " ", "".join(node.itertext())).strip()


def _first_year(text: str) -> int | None:
    """Return the first four-digit year in a string, or None."""
    match = _YEAR_IN_TEXT.search(text or "")
    return int(match.group(1)) if match else None


def choose_year(
    article_date_year: int | None,
    pub_date_year: int | None,
    history_year: int | None = None,
) -> tuple[int | None, str]:
    """Pick the publication year for one record, and say where it came from.

    The rule, in order:

    1. If the article (electronic) date and the journal issue date are both
       present and the article date is *earlier*, use the article date. A paper
       published online in one year and assigned to an issue in the next belongs
       to the year it entered the literature, not the year the issue was bound.
    2. Otherwise use the journal issue date when there is one. An article date
       that falls after the issue date is a record-keeping artifact, not a later
       appearance, so the issue date stands. A year read out of a free-text
       ``MedlineDate`` is labeled ``PubDate[MedlineDate]`` by the caller.
    3. Failing that, use the article date alone.
    4. Failing that, use the PubMed history date, the day the record entered
       PubMed. This is a floor, not a publication date, and rows carrying it are
       labeled so they can be excluded.
    5. Otherwise the year is unknown.

    Returns:
        The year and the name of the field it came from. The field name goes
        into the ``year_source`` column, so any point on the trend line can be
        traced to the element that produced it.
    """
    if article_date_year is not None and pub_date_year is not None:
        if article_date_year < pub_date_year:
            return article_date_year, "ArticleDate"
        return pub_date_year, "PubDate"
    if pub_date_year is not None:
        return pub_date_year, "PubDate"
    if article_date_year is not None:
        return article_date_year, "ArticleDate"
    if history_year is not None:
        return history_year, "PubMedPubDate[pubmed]"
    return None, "none"


def _abstract_from(node: etree._Element | None) -> tuple[str, bool, int]:
    """Assemble an abstract from its parts.

    A structured abstract arrives as several ``AbstractText`` elements, each
    labeled (BACKGROUND, METHODS, and so on). The parts are joined into one
    string with their labels kept, because the labels carry meaning a term
    matcher can use. Copyright notices are left out.

    Returns:
        The abstract text, whether it was structured, and how many parts it had.
    """
    if node is None:
        return "", False, 0
    parts: list[str] = []
    labeled = False
    for element in node.findall("AbstractText"):
        text = _text(element)
        label = (element.get("Label") or "").strip()
        if label:
            labeled = True
            if text:
                parts.append(f"{label}: {text}")
        elif text:
            parts.append(text)
    return "\n\n".join(parts), labeled and len(parts) > 0, len(parts)


def _doi_from(article: etree._Element | None, ids_parent: etree._Element | None) -> str:
    """Return the record's DOI, preferring the canonical ArticleIdList entry."""
    for parent in (ids_parent, article):
        if parent is None:
            continue
        for node in parent.iter("ArticleId"):
            if (node.get("IdType") or "").lower() == "doi":
                value = _text(node)
                if value:
                    return value
    if article is not None:
        for node in article.findall("ELocationID"):
            if (node.get("EIdType") or "").lower() == "doi":
                value = _text(node)
                if value:
                    return value
    return ""


def parse_article(record: etree._Element, source_file: str) -> dict[str, Any]:
    """Parse one ``PubmedArticle`` element into a row."""
    citation = record.find("MedlineCitation")
    article = citation.find("Article") if citation is not None else None
    pubmed_data = record.find("PubmedData")

    journal = article.find("Journal") if article is not None else None
    pub_date = journal.find("JournalIssue/PubDate") if journal is not None else None

    pub_date_year = None
    pub_date_is_medline = False
    if pub_date is not None:
        year_node = pub_date.find("Year")
        if year_node is not None:
            pub_date_year = _first_year(_text(year_node))
        else:
            # Journals without a numbered month use free text: "2019 Winter",
            # "2015 Nov-Dec", "2015-2016". Take the first year in the string.
            pub_date_year = _first_year(_text(pub_date.find("MedlineDate")))
            pub_date_is_medline = pub_date_year is not None

    article_years = [
        year
        for node in (article.findall("ArticleDate") if article is not None else [])
        if (year := _first_year(_text(node.find("Year")))) is not None
    ]
    article_date_year = min(article_years) if article_years else None

    history_year = None
    if pubmed_data is not None:
        for node in pubmed_data.findall("History/PubMedPubDate"):
            if node.get("PubStatus") == "pubmed":
                history_year = _first_year(_text(node.find("Year")))
                break

    year, year_source = choose_year(article_date_year, pub_date_year, history_year)
    if year_source == "PubDate" and pub_date_is_medline:
        year_source = "PubDate[MedlineDate]"
    abstract, structured, sections = _abstract_from(
        article.find("Abstract") if article is not None else None
    )

    mesh = [
        _text(heading.find("DescriptorName"))
        for heading in (citation.findall("MeshHeadingList/MeshHeading") if citation is not None else [])
    ]
    major = [
        _text(heading.find("DescriptorName"))
        for heading in (citation.findall("MeshHeadingList/MeshHeading") if citation is not None else [])
        if (heading.find("DescriptorName") is not None
            and heading.find("DescriptorName").get("MajorTopicYN") == "Y")
    ]
    languages = [
        _text(node) for node in (article.findall("Language") if article is not None else [])
    ]

    return {
        "pmid": _text(citation.find("PMID")) if citation is not None else "",
        "doi": _doi_from(article, pubmed_data),
        "title": _text(article.find("ArticleTitle")) if article is not None else "",
        "abstract": abstract,
        "has_abstract": bool(abstract),
        "abstract_structured": structured,
        "abstract_sections": sections,
        "journal": _text(journal.find("Title")) if journal is not None else "",
        "journal_iso": _text(journal.find("ISOAbbreviation")) if journal is not None else "",
        "year": year,
        "year_source": year_source,
        "article_date_year": article_date_year,
        "pub_date_year": pub_date_year,
        "publication_types": [
            _text(node)
            for node in (article.findall("PublicationTypeList/PublicationType")
                         if article is not None else [])
        ],
        "mesh_descriptors": [term for term in mesh if term],
        "mesh_major_descriptors": [term for term in major if term],
        "language": languages[0] if languages else "",
        "languages": languages,
        "record_type": "PubmedArticle",
        "source_file": source_file,
    }


def parse_book_article(record: etree._Element, source_file: str) -> dict[str, Any]:
    """Parse one ``PubmedBookArticle`` element into a row.

    Book chapters (StatPearls, GeneReviews) reach a PubMed search now and then.
    They carry no ``ArticleDate`` and no MeSH, so the year comes from the book's
    publication date and those columns stay empty. The ``record_type`` column
    marks them, so they can be excluded from the corpus if the team decides they
    do not belong in it.
    """
    document = record.find("BookDocument")
    if document is None:
        return {}
    book = document.find("Book")
    pub_date = book.find("PubDate") if book is not None else None
    year = _first_year(_text(pub_date.find("Year"))) if pub_date is not None else None
    abstract, structured, sections = _abstract_from(document.find("Abstract"))
    title = _text(document.find("ArticleTitle")) or (
        _text(book.find("BookTitle")) if book is not None else ""
    )
    languages = [_text(node) for node in document.findall("Language")]

    return {
        "pmid": _text(document.find("PMID")),
        "doi": _doi_from(None, document.find("ArticleIdList")),
        "title": title,
        "abstract": abstract,
        "has_abstract": bool(abstract),
        "abstract_structured": structured,
        "abstract_sections": sections,
        "journal": _text(book.find("BookTitle")) if book is not None else "",
        "journal_iso": "",
        "year": year,
        "year_source": "Book/PubDate" if year is not None else "none",
        "article_date_year": None,
        "pub_date_year": year,
        "publication_types": [_text(node) for node in document.findall("PublicationType")],
        "mesh_descriptors": [],
        "mesh_major_descriptors": [],
        "language": languages[0] if languages else "",
        "languages": languages,
        "record_type": "PubmedBookArticle",
        "source_file": source_file,
    }


def iter_records(xml_bytes: bytes, source_file: str) -> Iterator[dict[str, Any]]:
    """Yield one row per record in an efetch response.

    Raises:
        etree.XMLSyntaxError: The payload will not parse.
    """
    root = etree.fromstring(xml_bytes)
    for record in root.iter("PubmedArticle"):
        yield parse_article(record, source_file)
    for record in root.iter("PubmedBookArticle"):
        row = parse_book_article(record, source_file)
        if row:
            yield row


def parse_directory(raw_dir: Path) -> tuple[pd.DataFrame, ParseSummary]:
    """Parse every efetch file in a raw capture directory.

    Duplicate PMIDs are dropped, keeping the first occurrence, and counted. A
    record set paged off the history server should hold none; a count above zero
    means the batches overlapped and the retrieval needs looking at.

    Raises:
        FileNotFoundError: The directory holds no ``efetch_*.xml`` files.
    """
    files = sorted(raw_dir.glob("efetch_*.xml"))
    if not files:
        raise FileNotFoundError(f"No efetch_*.xml files in {raw_dir}")

    rows: list[dict[str, Any]] = []
    for path in files:
        found = 0
        for row in iter_records(path.read_bytes(), path.name):
            rows.append(row)
            found += 1
        log.info("Parsed %d records from %s", found, path.name)

    frame = pd.DataFrame(rows)
    for column in INT_COLUMNS:
        if column in frame:
            frame[column] = frame[column].astype("Int64")
    total = len(frame)
    duplicates = int(frame["pmid"].duplicated().sum()) if total else 0
    if duplicates:
        log.warning("Dropping %d duplicate PMIDs", duplicates)
        frame = frame.drop_duplicates(subset="pmid", keep="first").reset_index(drop=True)

    summary = ParseSummary(
        files=len(files),
        records=len(frame),
        articles=int((frame["record_type"] == "PubmedArticle").sum()) if total else 0,
        book_articles=int((frame["record_type"] == "PubmedBookArticle").sum()) if total else 0,
        duplicate_pmids=duplicates,
        without_abstract=int((~frame["has_abstract"]).sum()) if total else 0,
        with_structured_abstract=int(frame["abstract_structured"].sum()) if total else 0,
        without_year=int(frame["year"].isna().sum()) if total else 0,
        year_sources=dict(Counter(frame["year_source"])) if total else {},
        languages=dict(Counter(frame["language"])) if total else {},
        year_histogram=(
            {str(int(year)): int(n)
             for year, n in sorted(Counter(frame["year"].dropna()).items())}
            if total else {}
        ),
    )
    return frame, summary


def write_outputs(frame: pd.DataFrame, summary: ParseSummary, out_dir: Path) -> dict[str, Path]:
    """Write ``records.parquet``, ``records.csv``, and ``parse_summary.json``.

    Parquet is the file later steps read: it keeps the list columns as lists and
    the year as a number. The CSV is for reading and for spot checks; its list
    columns are joined on ``"; "`` and cannot be split back apart reliably.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = out_dir / "records.parquet"
    csv_path = out_dir / "records.csv"
    summary_path = out_dir / "parse_summary.json"

    frame.to_parquet(parquet_path, index=False)

    flat = frame.copy()
    for column in LIST_COLUMNS:
        flat[column] = flat[column].apply(
            lambda values: "; ".join(values) if isinstance(values, (list, tuple)) else ""
        )
    flat.to_csv(csv_path, index=False)
    summary_path.write_text(json.dumps(summary.as_dict(), indent=2) + "\n", encoding="utf-8")

    return {"parquet": parquet_path, "csv": csv_path, "summary": summary_path}


def main(argv: list[str] | None = None) -> int:
    """Parse a raw capture directory from the command line."""
    parser = argparse.ArgumentParser(
        prog="python -m trends.parse",
        description="Parse captured PubMed XML into a record table.",
    )
    parser.add_argument("--raw-dir", required=True, type=Path,
                        help="Directory of efetch_*.xml files to parse.")
    parser.add_argument("--out", type=Path, default=Path("data/interim"),
                        help="Where to write records.parquet and its twins.")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    frame, summary = parse_directory(args.raw_dir)
    paths = write_outputs(frame, summary, args.out)
    log.info("Wrote %d records to %s", len(frame), paths["parquet"])
    print(json.dumps(summary.as_dict(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
