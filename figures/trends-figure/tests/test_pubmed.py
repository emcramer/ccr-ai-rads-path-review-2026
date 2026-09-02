"""Tests for the E-utilities client, offline.

Every request is served by a stub session, so the suite runs with no network and
no load on NCBI. Sleeps are stubbed out too, so the retry tests are instant.

The batching arithmetic gets the most attention here. A slip in it is the one
bug that would silently shorten the corpus rather than raise.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
import requests

from trends.config import CorpusConfig, RetrievalSettings
from trends.pubmed import (
    ATTEMPTS_BEFORE_SPLIT,
    MIN_SPLIT_SIZE,
    RETSTART_CEILING,
    SLICE_THRESHOLD,
    Batch,
    DateSlice,
    EUtilsClient,
    PubMedError,
    RateLimiter,
    SearchResult,
    TransientRetrievalError,
    count_records,
    extract_pmids,
    load_progress,
    sha256_file,
    looks_transient,
    plan_batches,
    plan_slices,
    resolve_output_dir,
    retrieve,
    split_batch,
    subdivide,
    year_slices,
)

def esearch_xml(count: int = 412, query_key: str = "1") -> bytes:
    """Build an esearch response reporting ``count`` records."""
    return (
        b"<eSearchResult><Count>%d</Count><RetMax>0</RetMax><RetStart>0</RetStart>"
        b"<QueryKey>%s</QueryKey><WebEnv>MCID_test</WebEnv><TranslationSet/>"
        b"<QueryTranslation>ai[tiab]</QueryTranslation></eSearchResult>"
        % (count, query_key.encode())
    )


ESEARCH_XML = esearch_xml()

# A server-side timeout, reported with a client-error status. Transient.
TIMEOUT_400 = (
    b"<eFetchResult><ERROR> Error: External viewer error: Empty Response. "
    b"Bytes read: 0 Status: Timeout</ERROR></eFetchResult>"
)

# A real fault in the request. Retrying it would only hide the bug.
RETSTART_400 = (
    b"<eFetchResult><ERROR>Search backend cannot retrieve history data. Reason: "
    b"Exception: 'retstart' cannot be larger than 9998. For PubMed, ESearch can "
    b"only retrieve the first 9,999 records matching the query.</ERROR></eFetchResult>"
)


def efetch_xml(n: int, start: int = 0) -> bytes:
    """Build an efetch response holding ``n`` minimally valid records.

    ``start`` offsets the PMIDs, so batches of one run can be given distinct
    records the way a real pull would.
    """
    records = b"".join(
        b'<PubmedArticle><MedlineCitation><PMID Version="1">%d</PMID>'
        b"<Article><ArticleTitle>Record %d</ArticleTitle>"
        b"<Journal><JournalIssue><PubDate><Year>2024</Year></PubDate>"
        b"</JournalIssue></Journal><Language>eng</Language></Article>"
        b"</MedlineCitation></PubmedArticle>" % (i, i)
        for i in range(start, start + n)
    )
    return b"<PubmedArticleSet>" + records + b"</PubmedArticleSet>"


class Response:
    """The parts of a requests response the client looks at."""

    def __init__(self, status_code: int, content: bytes = b"", headers: dict | None = None):
        self.status_code = status_code
        self.content = content
        self.text = content.decode("utf-8", "replace")
        self.headers = headers or {}


class StubSession:
    """A requests session that replays a scripted list of responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[tuple[str, str, dict]] = []

    def _next(self, method, url, params):
        self.calls.append((method, url, params))
        if not self.responses:
            raise AssertionError(f"stub ran out of responses at call {len(self.calls)}")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def get(self, url, params=None, timeout=None):
        return self._next("GET", url, params or {})

    def post(self, url, data=None, timeout=None):
        return self._next("POST", url, data or {})


@pytest.fixture(autouse=True)
def no_sleeping(monkeypatch):
    """Make backoff and throttling instant, so the suite stays fast."""
    monkeypatch.setattr("trends.pubmed.time.sleep", lambda seconds: None)


def make_client(responses, **kwargs) -> EUtilsClient:
    """Build a client wired to a stub session and no API key."""
    kwargs.setdefault("api_key", None)
    return EUtilsClient(
        tool="ccr-trends-figure", email="ericscrum@gmail.com",
        session=StubSession(responses), **kwargs,
    )


# -- batching arithmetic ---------------------------------------------------

@pytest.mark.parametrize(
    "total, size, cap, expected",
    [
        (0, 200, None, []),
        (1, 200, None, [(0, 1)]),
        (200, 200, None, [(0, 200)]),
        (201, 200, None, [(0, 200), (200, 1)]),
        (412, 200, None, [(0, 200), (200, 200), (400, 12)]),
        (412, 500, None, [(0, 412)]),
        (412, 200, 250, [(0, 200), (200, 50)]),
        (412, 200, 200, [(0, 200)]),
        (412, 200, 5000, [(0, 200), (200, 200), (400, 12)]),  # cap above the total
        (5, 1, None, [(0, 1), (1, 1), (2, 1), (3, 1), (4, 1)]),
    ],
)
def test_plan_batches(total, size, cap, expected):
    batches = plan_batches(total, size, cap)
    assert [(b.retstart, b.retmax) for b in batches] == expected
    assert [b.index for b in batches] == list(range(len(batches)))


@pytest.mark.parametrize("total, size", [(10_000, 200), (49_999, 500), (100_000, 1000)])
def test_batches_cover_the_whole_set_without_gap_or_overlap(total, size):
    """Past 10,000 records is where a retstart-paged pull would quietly stop."""
    batches = plan_batches(total, size)
    assert sum(b.retmax for b in batches) == total
    assert batches[0].retstart == 0
    for earlier, later in zip(batches, batches[1:]):
        assert earlier.retstart + earlier.retmax == later.retstart
    assert batches[-1].retstart + batches[-1].retmax == total


@pytest.mark.parametrize(
    "args", [(-1, 200, None), (100, 0, None), (100, -5, None), (100, 200, 0), (100, 200, -1)]
)
def test_plan_batches_rejects_nonsense(args):
    with pytest.raises(ValueError):
        plan_batches(*args)


# -- response checking -----------------------------------------------------

def test_count_records_counts_both_tags():
    assert count_records(efetch_xml(7)) == 7
    assert count_records(b"<PubmedArticleSet></PubmedArticleSet>") == 0


def test_count_records_rejects_broken_xml():
    with pytest.raises(PubMedError, match="will not parse"):
        count_records(b"<PubmedArticleSet><PubmedArticle>")


def test_count_records_rejects_an_ncbi_error_body():
    with pytest.raises(PubMedError, match="NCBI error"):
        count_records(b"<eFetchResult><ERROR>Empty id list</ERROR></eFetchResult>")


# -- throttling and retries ------------------------------------------------

def test_rate_defaults_to_three_without_a_key():
    assert make_client([]).rate == 3


def test_an_api_key_raises_the_rate_to_ten(monkeypatch):
    monkeypatch.setenv("NCBI_API_KEY", "deadbeef")
    client = EUtilsClient("t", "e@x.org", session=StubSession([]))
    assert client.api_key == "deadbeef"
    assert client.rate == 10
    assert client._common_params()["api_key"] == "deadbeef"


def test_tool_and_email_ride_on_every_request():
    client = make_client([Response(200, ESEARCH_XML)])
    client.esearch("ai[tiab]")
    _, _, params = client.session.calls[0]
    assert params["tool"] == "ccr-trends-figure"
    assert params["email"] == "ericscrum@gmail.com"
    assert "api_key" not in params


def test_rate_limiter_spaces_calls(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr("trends.pubmed.time.sleep", slept.append)
    clock = iter([0.0, 0.0, 0.0, 0.0])
    monkeypatch.setattr("trends.pubmed.time.monotonic", lambda: next(clock))
    limiter = RateLimiter(3)
    limiter.wait()
    limiter.wait()
    assert slept and slept[0] == pytest.approx(1 / 3)


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_retryable_statuses_are_retried(status):
    client = make_client([Response(status), Response(200, ESEARCH_XML)])
    assert client.esearch("ai[tiab]").count == 412
    assert len(client.session.calls) == 2


def test_connection_errors_are_retried():
    client = make_client(
        [requests.ConnectionError("reset by peer"), Response(200, ESEARCH_XML)]
    )
    assert client.esearch("ai[tiab]").count == 412


def test_a_client_error_is_not_retried():
    client = make_client([Response(400, b"bad request"), Response(200, ESEARCH_XML)])
    with pytest.raises(PubMedError, match="HTTP 400"):
        client.esearch("ai[tiab]")
    assert len(client.session.calls) == 1


def test_giving_up_raises_after_the_attempt_limit():
    client = make_client([Response(503)] * 3, max_attempts=3)
    with pytest.raises(PubMedError, match="after 3 attempts"):
        client.esearch("ai[tiab]")
    assert len(client.session.calls) == 3


def test_retry_after_header_is_honored(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr("trends.pubmed.time.sleep", slept.append)
    client = make_client(
        [Response(429, headers={"Retry-After": "30"}), Response(200, ESEARCH_XML)]
    )
    client.esearch("ai[tiab]")
    assert max(slept) >= 30


# -- esearch ---------------------------------------------------------------

def test_esearch_posts_and_returns_the_history_handle():
    client = make_client([Response(200, ESEARCH_XML)])
    result = client.esearch("ai[tiab]", mindate="2015/01/01", maxdate="2026/09/01")
    method, url, params = client.session.calls[0]
    assert method == "POST"           # the corpus query is too long for a URL
    assert url.endswith("esearch.fcgi")
    assert params["usehistory"] == "y"
    assert params["datetype"] == "pdat"
    assert (result.count, result.webenv, result.query_key) == (412, "MCID_test", "1")
    assert result.query_translation == "ai[tiab]"


def test_esearch_reports_a_rejected_query():
    body = b"<eSearchResult><ERROR>Field not found</ERROR></eSearchResult>"
    with pytest.raises(PubMedError, match="rejected the query"):
        make_client([Response(200, body)]).esearch("bogus[nosuchfield]")


def test_esearch_without_history_keys_fails():
    body = b"<eSearchResult><Count>10</Count></eSearchResult>"
    with pytest.raises(PubMedError, match="no WebEnv"):
        make_client([Response(200, body)]).esearch("ai[tiab]")


# -- efetch ----------------------------------------------------------------

def test_efetch_batch_passes_the_history_handle():
    client = make_client([Response(200, efetch_xml(200))])
    client.efetch_batch("MCID_test", "1", Batch(0, 0, 200))
    _, url, params = client.session.calls[0]
    assert url.endswith("efetch.fcgi")
    assert (params["WebEnv"], params["query_key"]) == ("MCID_test", "1")
    assert (params["retstart"], params["retmax"]) == (0, 200)


def test_an_empty_batch_is_retried_then_fails():
    client = make_client([Response(200, efetch_xml(0))] * 3, max_attempts=3)
    with pytest.raises(PubMedError, match="failed after 3 attempts"):
        client.efetch_batch("MCID_test", "1", Batch(2, 400, 200))
    assert len(client.session.calls) == 3


def test_a_batch_that_recovers_on_retry_is_kept():
    client = make_client([Response(200, b"<broken"), Response(200, efetch_xml(200))])
    assert count_records(client.efetch_batch("MCID_test", "1", Batch(0, 0, 200))) == 200


# -- append-only output directories ---------------------------------------

def test_resolve_output_dir_never_reuses_a_directory_holding_a_run(tmp_path):
    assert resolve_output_dir(tmp_path, "2026-09-01") == tmp_path / "2026-09-01"

    first = tmp_path / "2026-09-01"
    first.mkdir()
    (first / "manifest.json").write_text("{}")
    assert resolve_output_dir(tmp_path, "2026-09-01") == tmp_path / "2026-09-01-002"

    second = tmp_path / "2026-09-01-002"
    second.mkdir()
    (second / "manifest.json").write_text("{}")
    assert resolve_output_dir(tmp_path, "2026-09-01") == tmp_path / "2026-09-01-003"


def test_an_empty_directory_is_reused(tmp_path):
    (tmp_path / "smoke").mkdir()
    assert resolve_output_dir(tmp_path, "smoke") == tmp_path / "smoke"


# -- date slicing ---------------------------------------------------------

def search_stub(counts: dict[str, int], default: int = 0):
    """A ``search_for`` that reports scripted counts and records its calls.

    Keys are slice labels. Anything not named gets ``default``.
    """
    calls: list[str] = []

    def search_for(window: DateSlice) -> SearchResult:
        calls.append(window.label)
        return SearchResult(
            count=counts.get(window.label, default),
            webenv="MCID_test", query_key="1",
            query_translation="ai[tiab]", raw_xml=b"<eSearchResult/>",
        )

    search_for.calls = calls
    return search_for


def test_year_slices_clip_to_the_configured_range():
    windows = year_slices(date(2015, 6, 15), date(2026, 9, 1))
    assert len(windows) == 12
    assert (windows[0].mindate, windows[0].maxdate) == ("2015/06/15", "2015/12/31")
    assert (windows[-1].mindate, windows[-1].maxdate) == ("2026/01/01", "2026/09/01")
    assert {w.granularity for w in windows} == {"year"}
    # Back to back, no gap and no overlap.
    for earlier, later in zip(windows, windows[1:]):
        assert earlier.end + timedelta(days=1) == later.start


def test_year_slices_reject_a_backwards_range():
    with pytest.raises(ValueError, match="is after end"):
        year_slices(date(2026, 1, 1), date(2015, 1, 1))


def test_a_year_subdivides_into_its_months():
    months = subdivide(DateSlice(date(2024, 1, 1), date(2024, 12, 31), "year"))
    assert len(months) == 12
    assert months[0].label == "20240101-20240131"
    assert months[1].maxdate == "2024/02/29"      # 2024 is a leap year
    assert months[-1].label == "20241201-20241231"
    assert {m.granularity for m in months} == {"month"}


def test_a_clipped_year_subdivides_only_over_its_own_span():
    months = subdivide(DateSlice(date(2026, 1, 1), date(2026, 9, 1), "year"))
    assert len(months) == 9
    assert months[-1].label == "20260901-20260901"


def test_a_month_subdivides_into_its_days():
    days = subdivide(DateSlice(date(2024, 2, 1), date(2024, 2, 29), "month"))
    assert len(days) == 29
    assert all(d.start == d.end for d in days)
    assert days[0].label == "20240201-20240201"
    assert days[-1].label == "20240229-20240229"


def test_a_window_already_inside_one_month_goes_straight_to_days():
    """Splitting it by month would return the same window and loop forever."""
    days = subdivide(DateSlice(date(2026, 3, 4), date(2026, 3, 9), "year"))
    assert len(days) == 6
    assert {d.granularity for d in days} == {"day"}


def test_a_single_day_cannot_be_divided_further():
    with pytest.raises(PubMedError, match="single day"):
        subdivide(DateSlice(date(2026, 3, 4), date(2026, 3, 4), "day"))


def test_a_slice_under_the_threshold_is_not_split():
    search_for = search_stub({}, default=500)
    planned = plan_slices(date(2015, 1, 1), date(2016, 12, 31), search_for, threshold=9000)
    assert [w.label for w, _ in planned] == ["20150101-20151231", "20160101-20161231"]
    assert {w.granularity for w, _ in planned} == {"year"}
    assert len(search_for.calls) == 2          # no wasted searches


def test_a_slice_over_the_threshold_is_split_into_months():
    search_for = search_stub({"20160101-20161231": 12_000}, default=500)
    planned = plan_slices(date(2015, 1, 1), date(2016, 12, 31), search_for, threshold=9000)
    labels = [w.label for w, _ in planned]
    assert labels[0] == "20150101-20151231"    # the small year is untouched
    assert len(labels) == 1 + 12               # the big year became twelve months
    assert labels[1] == "20160101-20160131"
    assert [w.granularity for w, _ in planned][1:] == ["month"] * 12


def test_subdivision_recurses_to_days_when_a_month_is_still_too_big():
    search_for = search_stub(
        {"20240101-20241231": 40_000, "20240301-20240331": 10_000}, default=500
    )
    planned = plan_slices(date(2024, 1, 1), date(2024, 12, 31), search_for, threshold=9000)
    granularities = [w.granularity for w, _ in planned]
    assert granularities.count("month") == 11  # every month but March
    assert granularities.count("day") == 31    # March, one day at a time
    assert not any(w.label == "20240301-20240331" for w, _ in planned)


def test_the_plan_follows_the_counts_not_a_list_of_years():
    """Only the years PubMed says are large get split, whichever they are."""
    search_for = search_stub({"20260101-20260901": 30_000}, default=200)
    planned = plan_slices(date(2015, 1, 1), date(2026, 9, 1), search_for, threshold=9000)
    split = [w for w, _ in planned if w.granularity == "month"]
    whole_years = [w for w, _ in planned if w.granularity == "year"]
    assert len(whole_years) == 11              # 2015 to 2025 stay whole
    assert len(split) == 9                     # 2026 splits, January to September


def test_every_planned_slice_is_under_the_ceiling():
    search_for = search_stub({"20240101-20241231": 40_000}, default=500)
    planned = plan_slices(date(2024, 1, 1), date(2024, 12, 31), search_for, threshold=9000)
    assert all(result.count <= RETSTART_CEILING for _, result in planned)


def test_slices_cover_the_range_without_a_gap():
    search_for = search_stub({"20240101-20241231": 40_000}, default=500)
    planned = plan_slices(date(2024, 1, 1), date(2025, 12, 31), search_for, threshold=9000)
    windows = [w for w, _ in planned]
    assert windows[0].start == date(2024, 1, 1)
    assert windows[-1].end == date(2025, 12, 31)
    for earlier, later in zip(windows, windows[1:]):
        assert earlier.end + timedelta(days=1) == later.start


def test_the_default_threshold_sits_below_the_pubmed_ceiling():
    assert SLICE_THRESHOLD < RETSTART_CEILING


# -- PMID extraction -------------------------------------------------------

def test_extract_pmids_reads_both_record_tags():
    assert extract_pmids(efetch_xml(3)) == ["0", "1", "2"]
    assert extract_pmids(efetch_xml(2, start=7)) == ["7", "8"]
    book = (
        b'<PubmedArticleSet><PubmedBookArticle><BookDocument>'
        b'<PMID Version="1">31643176</PMID></BookDocument></PubmedBookArticle>'
        b"</PubmedArticleSet>"
    )
    assert extract_pmids(book) == ["31643176"]


# -- the whole retrieval ---------------------------------------------------


def make_config(tmp_path, batch_size=200, start=None, end=None) -> CorpusConfig:
    """A config object for the retrieval tests, over one year by default."""
    return CorpusConfig(
        version=1,
        start_date=start or date(2024, 1, 1),
        end_date=end or date(2024, 12, 31),
        query="ai[tiab]",
        retrieval=RetrievalSettings(
            db="pubmed", tool="ccr-trends-figure", email="ericscrum@gmail.com",
            batch_size=batch_size, requests_per_second=3,
        ),
        path=tmp_path / "corpus.yaml",
        sha256="0" * 64,
    )


def test_retrieve_writes_every_file_and_a_full_manifest(tmp_path):
    client = make_client([
        Response(200, esearch_xml(412)),            # the whole range
        Response(200, esearch_xml(412)),            # the one year slice
        Response(200, efetch_xml(200, start=0)),
        Response(200, efetch_xml(200, start=200)),
        Response(200, efetch_xml(12, start=400)),
    ])
    out = tmp_path / "raw" / "2026-09-01"
    manifest = retrieve(make_config(tmp_path), out, client=client)

    assert (out / "esearch_whole_range.xml").exists()
    assert (out / "esearch_20240101-20241231.xml").exists()
    assert sorted(path.name for path in out.glob("efetch_*.xml")) == [
        "efetch_20240101-20241231_0000_0000000.xml",
        "efetch_20240101-20241231_0001_0000200.xml",
        "efetch_20240101-20241231_0002_0000400.xml",
    ]
    assert manifest["counts"] == {
        "whole_range_esearch": 412, "sum_of_slice_counts": 412,
        "requested": 412, "fetched_records": 412,
        "unique_pmids": 412, "duplicate_pmids": 0, "shortfall": 0,
        "reconciles_with_whole_range": True,
        "max_records": None, "allow_shortfall": False,
    }
    assert manifest["query"] == "ai[tiab]"
    assert manifest["query_source"] == "config"
    assert manifest["slicing"]["threshold"] == SLICE_THRESHOLD
    assert manifest["slicing"]["n_slices"] == 1
    assert manifest["date_range"] == {
        "start": "2024/01/01", "end": "2024/12/31", "datetype": "pdat",
    }
    assert manifest["config"]["version"] == 1
    assert manifest["package_version"]
    assert len(manifest["files"]) == 3
    assert all(len(f["sha256"]) == 64 and f["bytes"] > 0 for f in manifest["files"])
    assert all(f["slice"] == "20240101-20241231" for f in manifest["files"])

    assert json.loads((out / "manifest.json").read_text()) == manifest


def test_the_manifest_records_every_slice(tmp_path):
    client = make_client([
        Response(200, esearch_xml(300)),
        Response(200, esearch_xml(200)), Response(200, efetch_xml(200, start=0)),
        Response(200, esearch_xml(100)), Response(200, efetch_xml(100, start=200)),
    ])
    manifest = retrieve(
        make_config(tmp_path, end=date(2025, 12, 31)), tmp_path / "raw", client=client
    )
    slices = manifest["slices"]
    assert [s["label"] for s in slices] == ["20240101-20241231", "20250101-20251231"]
    assert [s["esearch_count"] for s in slices] == [200, 100]
    assert [s["start"] for s in slices] == ["2024/01/01", "2025/01/01"]
    assert [s["end"] for s in slices] == ["2024/12/31", "2025/12/31"]
    assert [s["granularity"] for s in slices] == ["year", "year"]
    assert [s["fetched"] for s in slices] == [200, 100]
    assert all(s["files"] for s in slices)


def test_records_are_deduplicated_by_pmid_across_slices(tmp_path):
    """The real corpus overlaps 12.7% between year slices. Model that here.

    The publication date filter matches both the electronic and the print date,
    so a paper online in December and printed in January is returned twice.
    """
    client = make_client([
        Response(200, esearch_xml(150)),                        # whole range
        Response(200, esearch_xml(100)),                        # 2024
        Response(200, efetch_xml(100, start=0)),                # PMIDs 0-99
        Response(200, esearch_xml(100)),                        # 2025
        Response(200, efetch_xml(100, start=50)),               # PMIDs 50-149
    ])
    manifest = retrieve(
        make_config(tmp_path, end=date(2025, 12, 31)), tmp_path / "raw", client=client
    )
    counts = manifest["counts"]
    assert counts["sum_of_slice_counts"] == 200
    assert counts["fetched_records"] == 200
    assert counts["unique_pmids"] == 150
    assert counts["duplicate_pmids"] == 50
    assert counts["whole_range_esearch"] == 150
    assert counts["reconciles_with_whole_range"] is True


def test_a_deduplicated_total_that_misses_the_whole_range_count_fails(tmp_path):
    """The check that would have caught a silently short corpus."""
    client = make_client([
        Response(200, esearch_xml(160)),          # the range really holds 160
        Response(200, esearch_xml(100)),
        Response(200, efetch_xml(100, start=0)),
        Response(200, esearch_xml(100)),
        Response(200, efetch_xml(100, start=50)),  # only 150 distinct
    ])
    out = tmp_path / "raw"
    with pytest.raises(PubMedError, match="off by -10"):
        retrieve(make_config(tmp_path, end=date(2025, 12, 31)), out, client=client)
    # The evidence survives the failure.
    counts = json.loads((out / "manifest.json").read_text())["counts"]
    assert counts["unique_pmids"] == 150
    assert counts["reconciles_with_whole_range"] is False


def test_allow_shortfall_accepts_a_run_that_does_not_reconcile(tmp_path):
    client = make_client([
        Response(200, esearch_xml(160)),
        Response(200, esearch_xml(100)), Response(200, efetch_xml(100, start=0)),
        Response(200, esearch_xml(100)), Response(200, efetch_xml(100, start=50)),
    ])
    manifest = retrieve(
        make_config(tmp_path, end=date(2025, 12, 31)), tmp_path / "raw",
        client=client, allow_shortfall=True,
    )
    assert manifest["counts"]["reconciles_with_whole_range"] is False
    assert manifest["counts"]["allow_shortfall"] is True


def test_a_big_slice_is_subdivided_during_a_real_retrieval(tmp_path):
    """A year over the threshold becomes months, and every month is fetched."""
    responses = [Response(200, esearch_xml(2400)), Response(200, esearch_xml(2400))]
    for month in range(12):
        responses.append(Response(200, esearch_xml(200)))
        responses.append(Response(200, efetch_xml(200, start=month * 200)))
    client = make_client(responses)

    manifest = retrieve(
        make_config(tmp_path), tmp_path / "raw", client=client, slice_threshold=1000
    )
    assert manifest["slicing"]["n_slices"] == 12
    assert manifest["slicing"]["granularities"] == ["month"]
    assert manifest["counts"]["unique_pmids"] == 2400
    assert manifest["counts"]["reconciles_with_whole_range"] is True
    assert len(list((tmp_path / "raw").glob("efetch_*.xml"))) == 12


def test_a_slice_past_the_ceiling_stops_the_run(tmp_path):
    """Belt and braces: the subdivision should already have prevented this."""
    client = make_client([
        Response(200, esearch_xml(20_000)), Response(200, esearch_xml(20_000)),
    ])
    with pytest.raises(PubMedError, match="past the 9998"):
        retrieve(make_config(tmp_path), tmp_path / "raw",
                 client=client, slice_threshold=50_000)


def test_max_records_caps_the_pull_across_slices(tmp_path):
    client = make_client([
        Response(200, esearch_xml(300)),
        Response(200, esearch_xml(200)), Response(200, efetch_xml(50, start=0)),
        Response(200, esearch_xml(100)),   # searched, then skipped: the cap is spent
    ])
    manifest = retrieve(
        make_config(tmp_path, end=date(2025, 12, 31)), tmp_path / "smoke",
        client=client, max_records=50,
    )
    assert manifest["slices"][1]["skipped"] == "record cap reached"
    assert manifest["counts"]["requested"] == 50
    assert manifest["counts"]["fetched_records"] == 50
    assert manifest["counts"]["max_records"] == 50
    # A capped run is expected to be short, so it is not reconciled.
    assert manifest["counts"]["reconciles_with_whole_range"] is None
    assert manifest["slicing"]["stopped_early"] is True
    assert len(manifest["files"]) == 1


def test_a_failed_batch_stops_the_run(tmp_path):
    """Splitting buys more tries, but a batch that never comes back still fails."""
    client = make_client(
        [Response(200, esearch_xml(412)), Response(200, esearch_xml(412)),
         Response(200, efetch_xml(200))] + [Response(503)] * 200,
        max_attempts=3,
    )
    with pytest.raises(PubMedError):
        retrieve(make_config(tmp_path), tmp_path / "raw", client=client)


def test_a_shortfall_fails_the_run_but_keeps_the_evidence(tmp_path):
    """Fewer records than promised must never pass as a finished corpus."""
    client = make_client([
        Response(200, esearch_xml(412)), Response(200, esearch_xml(412)),
        Response(200, efetch_xml(200, start=0)),
        Response(200, efetch_xml(198, start=200)),   # two records short
        Response(200, efetch_xml(12, start=400)),
    ])
    out = tmp_path / "raw"
    with pytest.raises(PubMedError, match="2 missing"):
        retrieve(make_config(tmp_path), out, client=client)
    assert json.loads((out / "manifest.json").read_text())["counts"]["shortfall"] == 2


def test_an_empty_result_set_fetches_nothing(tmp_path):
    client = make_client([Response(200, esearch_xml(0)), Response(200, esearch_xml(0))])
    manifest = retrieve(make_config(tmp_path), tmp_path / "raw", client=client)
    assert manifest["counts"]["fetched_records"] == 0
    assert manifest["counts"]["unique_pmids"] == 0
    assert manifest["files"] == []
    assert manifest["counts"]["reconciles_with_whole_range"] is True


def test_an_empty_slice_is_recorded_but_not_fetched(tmp_path):
    client = make_client([
        Response(200, esearch_xml(100)),
        Response(200, esearch_xml(0)),                          # 2024 empty
        Response(200, esearch_xml(100)), Response(200, efetch_xml(100)),
    ])
    manifest = retrieve(
        make_config(tmp_path, end=date(2025, 12, 31)), tmp_path / "raw", client=client
    )
    assert [s["esearch_count"] for s in manifest["slices"]] == [0, 100]
    assert manifest["slices"][0]["files"] == []
    assert len(manifest["files"]) == 1


# -- retryability is decided by the body, not the status --------------------

@pytest.mark.parametrize(
    "body, transient",
    [
        (TIMEOUT_400.decode(), True),
        ("Error: External viewer error: Empty Response.", True),
        ("Bytes read: 0 Status: Timeout", True),
        ("STATUS: TIMEOUT", True),                    # matching ignores case
        (RETSTART_400.decode(), False),
        ("Empty id list", False),
        ("Field not found", False),
        ("", False),
    ],
)
def test_looks_transient(body, transient):
    assert looks_transient(body) is transient


def test_a_timeout_reported_as_400_is_retried_and_then_succeeds():
    """The failure that killed the second full pull."""
    client = make_client([
        Response(400, TIMEOUT_400),
        Response(200, efetch_xml(200)),
    ])
    raw = client.efetch_batch("MCID_test", "1", Batch(0, 0, 200))
    assert count_records(raw) == 200
    assert len(client.session.calls) == 2


def test_a_retstart_400_fails_at_once_without_retrying():
    """The bug that started all this must stay loud."""
    client = make_client([Response(400, RETSTART_400), Response(200, efetch_xml(200))])
    with pytest.raises(PubMedError, match="will not be retried") as caught:
        client.efetch_batch("MCID_test", "1", Batch(19, 9500, 500))
    assert "retstart" in str(caught.value)
    assert not isinstance(caught.value, TransientRetrievalError)
    assert len(client.session.calls) == 1        # tried once, then stopped


def test_a_transient_400_that_never_recovers_still_fails():
    client = make_client([Response(400, TIMEOUT_400)] * 4, max_attempts=4)
    with pytest.raises(TransientRetrievalError, match="after 4 attempts"):
        client.efetch_batch("MCID_test", "1", Batch(0, 0, 30))
    assert len(client.session.calls) == 4


def test_a_transient_400_raises_the_transient_type():
    client = make_client([Response(400, TIMEOUT_400)] * 2, max_attempts=2)
    with pytest.raises(TransientRetrievalError):
        client.request("efetch", {"db": "pubmed"})


# -- shrinking a batch that keeps timing out -------------------------------

@pytest.mark.parametrize(
    "batch, expected",
    [
        (Batch(1, 500, 500), [(500, 250), (750, 250)]),
        (Batch(0, 0, 200), [(0, 100), (100, 100)]),
        (Batch(3, 90, 7), [(90, 3), (93, 4)]),        # odd sizes stay covered
        (Batch(0, 0, 2), [(0, 1), (1, 1)]),
    ],
)
def test_split_batch_halves_and_covers_the_same_window(batch, expected):
    halves = split_batch(batch)
    assert [(h.retstart, h.retmax) for h in halves] == expected
    assert sum(h.retmax for h in halves) == batch.retmax
    assert halves[0].retstart == batch.retstart
    assert halves[-1].retstart + halves[-1].retmax == batch.retstart + batch.retmax


def test_a_single_record_batch_cannot_be_split():
    with pytest.raises(PubMedError, match="single record"):
        split_batch(Batch(0, 0, 1))


def test_a_batch_that_times_out_twice_is_refetched_in_halves():
    client = make_client([
        Response(400, TIMEOUT_400),                   # attempt 1 at size 200
        Response(400, TIMEOUT_400),                   # attempt 2 at size 200
        Response(200, efetch_xml(100, start=0)),      # first half
        Response(200, efetch_xml(100, start=100)),    # second half
    ])
    pieces = client.efetch_window("MCID_test", "1", Batch(0, 0, 200))

    assert [(b.retstart, b.retmax) for b, _ in pieces] == [(0, 100), (100, 100)]
    assert sum(count_records(raw) for _, raw in pieces) == 200
    # Two wasted tries at the big size, then one per half. No more.
    assert len(client.session.calls) == 4
    sizes = [int(params["retmax"]) for _, _, params in client.session.calls]
    assert sizes == [200, 200, 100, 100]


def test_splitting_stops_at_the_minimum_size():
    """Below the floor, size is not the problem; spend the attempts instead."""
    client = make_client([Response(400, TIMEOUT_400)] * 3, max_attempts=3)
    with pytest.raises(TransientRetrievalError):
        client.efetch_window("MCID_test", "1", Batch(0, 0, MIN_SPLIT_SIZE))
    sizes = [int(params["retmax"]) for _, _, params in client.session.calls]
    assert sizes == [MIN_SPLIT_SIZE] * 3          # never halved


def test_a_batch_that_succeeds_first_time_is_not_split():
    client = make_client([Response(200, efetch_xml(200))])
    pieces = client.efetch_window("MCID_test", "1", Batch(0, 0, 200))
    assert len(pieces) == 1
    assert len(client.session.calls) == 1


def test_the_manifest_records_which_batches_were_split(tmp_path):
    client = make_client([
        Response(200, esearch_xml(200)), Response(200, esearch_xml(200)),
        Response(400, TIMEOUT_400), Response(400, TIMEOUT_400),
        Response(200, efetch_xml(100, start=0)),
        Response(200, efetch_xml(100, start=100)),
    ])
    manifest = retrieve(make_config(tmp_path), tmp_path / "raw", client=client)

    assert manifest["resilience"]["batches_split"] == 1
    split_files = [f for f in manifest["files"] if "split_from_retmax" in f]
    assert len(split_files) == 2
    assert all(f["split_from_retmax"] == 200 for f in split_files)
    assert [f["retmax"] for f in split_files] == [100, 100]
    assert manifest["counts"]["fetched_records"] == 200
    assert manifest["counts"]["unique_pmids"] == 200
    # Every file on disk is described by the manifest.
    assert {f["file"] for f in manifest["files"]} == {
        p.name for p in (tmp_path / "raw").glob("efetch_*.xml")
    }


# -- resuming a partial capture --------------------------------------------

def fail_after_first_slice(tmp_path):
    """Run a two-slice retrieval whose second slice never comes back."""
    client = make_client(
        [Response(200, esearch_xml(200)),                     # whole range
         Response(200, esearch_xml(100)),                     # 2024
         Response(200, efetch_xml(100, start=0)),
         Response(200, esearch_xml(100))]                     # 2025
        + [Response(503)] * 200,
        max_attempts=2,
    )
    out = tmp_path / "raw"
    with pytest.raises(PubMedError):
        retrieve(make_config(tmp_path, end=date(2025, 12, 31)), out, client=client)
    return out


def test_a_dead_run_leaves_a_progress_log(tmp_path):
    out = fail_after_first_slice(tmp_path)
    assert not (out / "manifest.json").exists()   # it never finished
    verified = load_progress(out)
    assert list(verified) == ["20240101-20241231"]
    assert verified["20240101-20241231"]["slice"]["fetched"] == 100


def test_resume_keeps_verified_slices_and_refetches_the_rest(tmp_path):
    out = fail_after_first_slice(tmp_path)
    kept_file = out / "efetch_20240101-20241231_0000_0000000.xml"
    kept_bytes = kept_file.read_bytes()

    client = make_client([
        Response(200, esearch_xml(200)),                   # whole range
        Response(200, esearch_xml(100)),                   # 2024, searched again
        Response(200, esearch_xml(100)),                   # 2025
        Response(200, efetch_xml(100, start=100)),         # only this is fetched
    ])
    manifest = retrieve(
        make_config(tmp_path, end=date(2025, 12, 31)), out, client=client, resume=True
    )

    efetches = [c for c in client.session.calls if c[1].endswith("efetch.fcgi")]
    assert len(efetches) == 1                              # 2024 was not refetched
    assert kept_file.read_bytes() == kept_bytes            # and was not rewritten
    assert manifest["resilience"]["slices_resumed"] == 1
    assert manifest["resilience"]["resumed"] is True
    assert manifest["slices"][0]["resumed"] is True
    assert manifest["counts"]["fetched_records"] == 200
    assert manifest["counts"]["unique_pmids"] == 200
    assert manifest["counts"]["reconciles_with_whole_range"] is True
    assert len(manifest["files"]) == 2


def test_resume_refetches_a_file_that_does_not_match_its_digest(tmp_path):
    """A half-written file is worth less than the minute it costs to refetch."""
    out = fail_after_first_slice(tmp_path)
    (out / "efetch_20240101-20241231_0000_0000000.xml").write_bytes(
        b"<PubmedArticleSet><!-- truncated by a crash --></PubmedArticleSet>"
    )

    client = make_client([
        Response(200, esearch_xml(200)),
        Response(200, esearch_xml(100)), Response(200, efetch_xml(100, start=0)),
        Response(200, esearch_xml(100)), Response(200, efetch_xml(100, start=100)),
    ])
    manifest = retrieve(
        make_config(tmp_path, end=date(2025, 12, 31)), out, client=client, resume=True
    )
    efetches = [c for c in client.session.calls if c[1].endswith("efetch.fcgi")]
    assert len(efetches) == 2                    # the tampered slice came back too
    assert manifest["resilience"]["slices_resumed"] == 0
    assert manifest["counts"]["unique_pmids"] == 200


def test_resume_refetches_when_a_file_has_gone_missing(tmp_path):
    out = fail_after_first_slice(tmp_path)
    (out / "efetch_20240101-20241231_0000_0000000.xml").unlink()

    client = make_client([
        Response(200, esearch_xml(200)),
        Response(200, esearch_xml(100)), Response(200, efetch_xml(100, start=0)),
        Response(200, esearch_xml(100)), Response(200, efetch_xml(100, start=100)),
    ])
    manifest = retrieve(
        make_config(tmp_path, end=date(2025, 12, 31)), out, client=client, resume=True
    )
    assert manifest["resilience"]["slices_resumed"] == 0
    assert manifest["counts"]["unique_pmids"] == 200


def test_a_finished_capture_is_never_resumed_into(tmp_path):
    client = make_client([
        Response(200, esearch_xml(200)), Response(200, esearch_xml(200)),
        Response(200, efetch_xml(200)),
    ])
    out = tmp_path / "raw"
    retrieve(make_config(tmp_path), out, client=client)
    assert (out / "manifest.json").exists()

    with pytest.raises(PubMedError, match="finished run"):
        retrieve(make_config(tmp_path), out,
                 client=make_client([Response(200, esearch_xml(200))]), resume=True)


def test_load_progress_on_a_directory_with_no_log(tmp_path):
    tmp_path.joinpath("empty").mkdir()
    assert load_progress(tmp_path / "empty") == {}


def test_load_progress_ignores_a_torn_final_line(tmp_path):
    """A crash mid-write leaves half a line. It must not sink the whole log."""
    out = tmp_path / "raw"
    out.mkdir()
    payload = efetch_xml(10)
    name = "efetch_20240101-20241231_0000_0000000.xml"
    (out / name).write_bytes(payload)
    digest = sha256_file(out / name)
    (out / "progress.jsonl").write_text(
        json.dumps({"kind": "file", "file": name, "sha256": digest}) + "\n"
        + json.dumps({"kind": "slice", "label": "20240101-20241231",
                      "files": [name], "fetched": 10, "requested": 10}) + "\n"
        + '{"kind": "file", "file": "efetch_2025',      # torn by the crash
        encoding="utf-8",
    )
    verified = load_progress(out)
    assert list(verified) == ["20240101-20241231"]


def test_a_refetched_slice_leaves_no_orphan_files(tmp_path):
    """Refetching must not leave a stale file beside the ones it replaces."""
    out = fail_after_first_slice(tmp_path)
    orphan = out / "efetch_20250101-20251231_0000_0000000.xml"
    orphan.write_bytes(efetch_xml(3, start=900))     # junk from the dead attempt

    client = make_client([
        Response(200, esearch_xml(200)),
        Response(200, esearch_xml(100)),
        Response(200, esearch_xml(100)), Response(200, efetch_xml(100, start=100)),
    ])
    manifest = retrieve(
        make_config(tmp_path, end=date(2025, 12, 31)), out, client=client, resume=True
    )
    assert manifest["counts"]["unique_pmids"] == 200      # not 203
    assert {f["file"] for f in manifest["files"]} == {
        p.name for p in out.glob("efetch_*.xml")
    }
