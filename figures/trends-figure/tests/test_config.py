"""Tests for loading and validating ``corpus.yaml``.

A bad config must fail at load, naming the field, rather than producing a
half-right corpus that nobody notices until the figure looks wrong.
"""

from __future__ import annotations

import pytest

from trends.config import ConfigError, load_corpus_config, normalize_query


def write(tmp_path, text: str):
    """Write a config file into a temporary directory and return its path."""
    path = tmp_path / "corpus.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_valid_config_loads(tmp_path, valid_config_text):
    config = load_corpus_config(write(tmp_path, valid_config_text))
    assert config.version == 3
    assert config.mindate == "2015/01/01"
    assert config.maxdate == "2026/09/01"
    assert config.retrieval.batch_size == 200
    assert config.retrieval.email == "ericscrum@gmail.com"
    assert config.sha256


def test_comments_are_stripped_and_query_flattened(tmp_path, valid_config_text):
    config = load_corpus_config(write(tmp_path, valid_config_text))
    assert config.query == (
        "artificial intelligence[Title/Abstract] AND pathology[Title/Abstract]"
    )
    assert "#" not in config.query


def test_normalize_query_counts_comments():
    query, comments = normalize_query("# one\n# two\ncancer[tiab]\n  AND ai[tiab]\n")
    assert query == "cancer[tiab] AND ai[tiab]"
    assert comments == 2


def test_missing_file_names_the_path(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_corpus_config(tmp_path / "absent.yaml")


def test_invalid_yaml_is_rejected(tmp_path):
    with pytest.raises(ConfigError, match="not valid YAML"):
        load_corpus_config(write(tmp_path, "version: 1\n  bad: [indent\n"))


def test_empty_file_is_rejected(tmp_path):
    with pytest.raises(ConfigError, match="empty"):
        load_corpus_config(write(tmp_path, "\n"))


def test_non_mapping_top_level_is_rejected(tmp_path):
    with pytest.raises(ConfigError, match="must be a mapping"):
        load_corpus_config(write(tmp_path, "- one\n- two\n"))


def test_stub_query_is_rejected(tmp_path, valid_config_text):
    """A query block holding only comments is not a search strategy."""
    text = valid_config_text.replace(
        "  # a comment line, dropped\n"
        "  artificial intelligence[Title/Abstract]\n"
        "  AND pathology[Title/Abstract]\n",
        "  # PubMed query string goes here.\n",
    )
    with pytest.raises(ConfigError, match="query: empty"):
        load_corpus_config(write(tmp_path, text))


def test_stub_query_passes_when_the_caller_brings_its_own(tmp_path, valid_config_text):
    text = valid_config_text.replace(
        "  # a comment line, dropped\n"
        "  artificial intelligence[Title/Abstract]\n"
        "  AND pathology[Title/Abstract]\n",
        "  # PubMed query string goes here.\n",
    )
    config = load_corpus_config(write(tmp_path, text), require_query=False)
    assert config.query == ""


@pytest.mark.parametrize(
    "old, new, expected",
    [
        ('  start: "2015/01/01"', '  start: "2015-01-01"', "date_range.start"),
        ('  start: "2015/01/01"', '  start: "2015/13/01"', "not a real date"),
        ('  end: "2026/09/01"', '  end: "2014/01/01"', "is after end"),
        ("  db: pubmed", "  db: pmc", "only 'pubmed' is supported"),
        ('  email: "ericscrum@gmail.com"', "  email: nobody", "not an address"),
        ("  batch_size: 200", "  batch_size: 0", "outside 1-10000"),
        ("  requests_per_second: 3", "  requests_per_second: 25", "outside 1-10"),
        ("  requests_per_second: 3", '  requests_per_second: "three"', "expected an integer"),
        ("version: 3\n", "", "version: missing"),
        ("  batch_size: 200\n", "", "retrieval.batch_size: missing"),
    ],
)
def test_malformed_fields_are_named(tmp_path, valid_config_text, old, new, expected):
    text = valid_config_text.replace(old, new)
    with pytest.raises(ConfigError, match=expected):
        load_corpus_config(write(tmp_path, text))


def test_every_problem_is_reported_at_once(tmp_path, valid_config_text):
    text = (
        valid_config_text.replace("  db: pubmed", "  db: pmc")
        .replace("  batch_size: 200", "  batch_size: -1")
        .replace('  email: "ericscrum@gmail.com"', "  email: nobody")
    )
    with pytest.raises(ConfigError) as caught:
        load_corpus_config(write(tmp_path, text))
    message = str(caught.value)
    assert "3 problem(s)" in message
    assert "retrieval.db" in message and "batch_size" in message and "email" in message


def test_missing_date_range_is_reported(tmp_path, valid_config_text):
    text = valid_config_text.replace(
        'date_range:\n  start: "2015/01/01"\n  end: "2026/09/01"\n', ""
    )
    with pytest.raises(ConfigError, match="date_range: missing"):
        load_corpus_config(write(tmp_path, text))
