"""Tests for the command line entry point.

These check the wiring and the exit statuses, not the retrieval itself: a bad
config must stop the run before a single request goes out, and a failed pull
must return non-zero so a caller in a shell script notices.
"""

from __future__ import annotations

import json

import pytest

from trends import fetch
from trends.pubmed import PubMedError
from tests.test_pubmed import (
    Response,
    StubSession,
    efetch_xml,
    esearch_xml,
)


@pytest.fixture(autouse=True)
def quiet_sleep(monkeypatch):
    """Keep the retry backoff from slowing the suite."""
    monkeypatch.setattr("trends.pubmed.time.sleep", lambda seconds: None)


@pytest.fixture
def stub_client(monkeypatch):
    """Replace the client the CLI builds with one wired to a stub session."""

    def install(responses):
        from trends.pubmed import EUtilsClient

        client = EUtilsClient(
            "ccr-trends-figure", "ericscrum@gmail.com",
            api_key=None, session=StubSession(responses),
        )
        monkeypatch.setattr(fetch, "EUtilsClient", lambda *a, **k: client)
        return client

    return install


@pytest.fixture
def one_year_config_text(valid_config_text):
    """A config over a single year, so a run plans exactly one date slice."""
    return valid_config_text.replace(
        '  start: "2015/01/01"', '  start: "2024/01/01"'
    ).replace('  end: "2026/09/01"', '  end: "2024/12/31"')


def write_config(tmp_path, text: str):
    path = tmp_path / "corpus.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_a_bad_config_exits_two_and_fetches_nothing(tmp_path, caplog):
    path = write_config(tmp_path, "version: 1\nquery: |\n  ai[tiab]\n")
    status = fetch.main(["--config", str(path), "--log-dir", str(tmp_path / "logs")])
    assert status == 2
    assert "unusable" in caplog.text


def test_dry_run_searches_and_stops(tmp_path, one_year_config_text, stub_client):
    client = stub_client([Response(200, esearch_xml(412))] * 2)
    status = fetch.main([
        "--config", str(write_config(tmp_path, one_year_config_text)),
        "--log-dir", str(tmp_path / "logs"), "--dry-run",
    ])
    assert status == 0
    # The whole range and the one slice, both esearch. No efetch.
    assert len(client.session.calls) == 2
    assert all(url.endswith("esearch.fcgi") for _, url, _ in client.session.calls)
    assert not (tmp_path / "raw").exists()


def test_dry_run_reports_the_slice_plan(tmp_path, valid_config_text, stub_client, caplog):
    """Twelve years, one of them over the threshold and split into months."""
    responses = [Response(200, esearch_xml(20_000))]          # whole range
    for year in range(2015, 2027):
        if year == 2026:
            responses.append(Response(200, esearch_xml(9_500)))   # over threshold
            responses.extend([Response(200, esearch_xml(300))] * 9)
        else:
            responses.append(Response(200, esearch_xml(800)))
    stub_client(responses)

    status = fetch.main([
        "--config", str(write_config(tmp_path, valid_config_text)),
        "--log-dir", str(tmp_path / "logs"), "--dry-run",
        "--slice-threshold", "9000",
    ])
    assert status == 0
    assert "Subdividing into 9 month slices" in caplog.text
    assert "20 slices" in caplog.text        # 11 whole years plus 9 months of 2026


def test_a_full_run_writes_raw_and_interim(tmp_path, one_year_config_text, stub_client):
    stub_client([
        Response(200, esearch_xml(412)),
        Response(200, esearch_xml(412)),
        Response(200, efetch_xml(200, start=0)),
        Response(200, efetch_xml(200, start=200)),
        Response(200, efetch_xml(12, start=400)),
    ])
    out = tmp_path / "raw" / "2026-09-01"
    interim = tmp_path / "interim"
    status = fetch.main([
        "--config", str(write_config(tmp_path, one_year_config_text)),
        "--out", str(out), "--interim-dir", str(interim),
        "--log-dir", str(tmp_path / "logs"),
    ])
    assert status == 0
    counts = json.loads((out / "manifest.json").read_text())["counts"]
    assert counts["fetched_records"] == 412
    assert counts["unique_pmids"] == 412
    assert counts["reconciles_with_whole_range"] is True
    assert (interim / "records.parquet").exists()
    assert (interim / "records.csv").exists()
    assert json.loads((interim / "parse_summary.json").read_text())["records"] == 412
    assert list((tmp_path / "logs").glob("fetch_*.log"))


def test_a_failed_retrieval_exits_one(tmp_path, one_year_config_text, stub_client):
    stub_client([Response(200, esearch_xml(412))] * 2 + [Response(503)] * 10)
    status = fetch.main([
        "--config", str(write_config(tmp_path, one_year_config_text)),
        "--out", str(tmp_path / "raw"), "--log-dir", str(tmp_path / "logs"),
    ])
    assert status == 1


def test_a_query_override_is_marked_in_the_manifest(tmp_path, one_year_config_text, stub_client):
    stub_client([Response(200, esearch_xml(30))] * 2 + [Response(200, efetch_xml(30))])
    out = tmp_path / "raw" / "smoke"
    fetch.main([
        "--config", str(write_config(tmp_path, one_year_config_text)),
        "--query", "throwaway[tiab]", "--max-records", "30",
        "--out", str(out), "--interim-dir", str(tmp_path / "interim"),
        "--log-dir", str(tmp_path / "logs"),
    ])
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["query"] == "throwaway[tiab]"
    assert manifest["query_source"] == "cli-override"


def test_an_existing_raw_directory_is_not_overwritten(tmp_path, one_year_config_text, stub_client):
    stub_client([Response(200, esearch_xml(30))] * 2 + [Response(200, efetch_xml(30))])
    out = tmp_path / "raw" / "2026-09-01"
    out.mkdir(parents=True)
    (out / "manifest.json").write_text('{"counts": {"fetched_records": 999}}')

    fetch.main([
        "--config", str(write_config(tmp_path, one_year_config_text)),
        "--max-records", "30", "--out", str(out),
        "--interim-dir", str(tmp_path / "interim"), "--log-dir", str(tmp_path / "logs"),
    ])
    # The earlier run is untouched; the new one went to a numbered sibling.
    assert json.loads((out / "manifest.json").read_text())["counts"]["fetched_records"] == 999
    assert (out.parent / "2026-09-01-002" / "manifest.json").exists()


def test_no_parse_leaves_the_interim_directory_alone(tmp_path, one_year_config_text, stub_client):
    stub_client([Response(200, esearch_xml(30))] * 2 + [Response(200, efetch_xml(30))])
    interim = tmp_path / "interim"
    status = fetch.main([
        "--config", str(write_config(tmp_path, one_year_config_text)),
        "--max-records", "30", "--no-parse",
        "--out", str(tmp_path / "raw" / "smoke"), "--interim-dir", str(interim),
        "--log-dir", str(tmp_path / "logs"),
    ])
    assert status == 0
    assert not interim.exists()


def test_resume_needs_an_out_directory(tmp_path, one_year_config_text):
    status = fetch.main([
        "--config", str(write_config(tmp_path, one_year_config_text)),
        "--resume", "--log-dir", str(tmp_path / "logs"),
    ])
    assert status == 2


def test_resume_on_a_missing_directory_exits_two(tmp_path, one_year_config_text):
    status = fetch.main([
        "--config", str(write_config(tmp_path, one_year_config_text)),
        "--resume", "--out", str(tmp_path / "absent"),
        "--log-dir", str(tmp_path / "logs"),
    ])
    assert status == 2


def test_without_resume_a_used_directory_is_stepped_around(
    tmp_path, one_year_config_text, stub_client, caplog
):
    stub_client([Response(200, esearch_xml(30))] * 2 + [Response(200, efetch_xml(30))])
    out = tmp_path / "raw" / "2026-09-02"
    out.mkdir(parents=True)
    (out / "progress.jsonl").write_text("")
    fetch.main([
        "--config", str(write_config(tmp_path, one_year_config_text)),
        "--out", str(out), "--interim-dir", str(tmp_path / "interim"),
        "--log-dir", str(tmp_path / "logs"),
    ])
    assert (out.parent / "2026-09-02-002" / "manifest.json").exists()
    assert "Pass --resume to continue it" in caplog.text
