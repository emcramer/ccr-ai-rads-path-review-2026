"""PubMed E-utilities client and raw capture.

Retrieval works in date slices. PubMed refuses a ``retstart`` above 9,998, and
``usehistory=y`` does **not** lift that ceiling: the history server holds the
whole result set but will not page past the first 9,999 records. Any corpus
larger than that must be pulled as several smaller searches.

So this module slices the configured date range by publication date, asks
PubMed how many records each slice holds, and subdivides any slice that comes
back over the threshold -- years into months, months into days -- until every
slice is small enough to page through. The slices are derived from the counts
PubMed reports, never from a hard-coded list, because the recent years of this
corpus are the large ones and they keep growing.

Deduplication by PMID is then required, not optional. PubMed's publication date
filter matches both the electronic and the print date, so a paper posted online
in December and printed in January is returned by two slices. On the review
corpus the slices sum to 50,298 records for 44,617 distinct ones, a 12.7%
overlap. The deduplicated total is reconciled against the count for the whole
date range, and a run that fails to reconcile fails.

A slice never determines a record's year. That comes from the record itself,
under the rule in :mod:`trends.parse`: a paper can arrive in the 2024 slice and
parse to 2023.

Every response is written to disk exactly as returned, and ``manifest.json``
records each slice, its window, its count, its files, and the digest of each.

Nothing here parses records into rows. That is :mod:`trends.parse`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import random
import socket
import sys
import time
from calendar import monthrange
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence

import requests
from lxml import etree

from trends import __version__
from trends.config import CorpusConfig

log = logging.getLogger(__name__)

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Rate ceilings set by NCBI's E-utilities usage policy.
RATE_WITHOUT_KEY = 3
RATE_WITH_KEY = 10

# Retry policy. NCBI returns 429 under load and 5xx during maintenance windows;
# both are worth waiting out.
RETRY_STATUS = frozenset({429, 500, 502, 503, 504})

# NCBI also reports some server-side failures with a client-error status. A 400
# carrying one of these phrases is a timeout inside NCBI, not a fault in our
# request, and deserves the same backoff as a 503:
#
#     <ERROR> Error: External viewer error: Empty Response.
#             Bytes read: 0 Status: Timeout</ERROR>
#
# The test is on the body, never on the status alone. A 400 that says
# "'retstart' cannot be larger than 9998" is a real bug in the request and must
# fail at once: waiting out a mistake only hides it.
TRANSIENT_BODY_SIGNATURES = (
    "empty response",
    "status: timeout",
    "external viewer error",
    "bytes read: 0",
)

# Tries at the current batch size before halving it. Oversized efetch responses
# are the ones that time out, so shrinking beats repeating.
ATTEMPTS_BEFORE_SPLIT = 2

# Never halve below this. Beneath it the response is small enough that size is
# not the problem, so spend the remaining attempts at full strength instead.
MIN_SPLIT_SIZE = 50
DEFAULT_MAX_ATTEMPTS = 5
BACKOFF_BASE_SECONDS = 1.0
BACKOFF_CAP_SECONDS = 60.0

# efetch returns PubMed XML under one of two record elements. Books and book
# chapters (GeneReviews, StatPearls) use the second.
RECORD_TAGS = ("PubmedArticle", "PubmedBookArticle")

# PubMed refuses a retstart above this, whether or not the search used the
# history server. It is a property of the pubmed database, not of our request.
RETSTART_CEILING = 9998

# A slice holding more than this is subdivided. The margin below the ceiling
# leaves room for a result set that grows between the search and the fetch.
SLICE_THRESHOLD = 9000

# The ladder the subdivision walks down.
FINER_GRANULARITY = {"year": "month", "month": "day"}


class PubMedError(RuntimeError):
    """Raised when retrieval fails in a way that would truncate the corpus."""


class TransientRetrievalError(PubMedError):
    """A failure that looks temporary rather than wrong.

    Raised when attempts run out on something worth retrying: a 429, a 5xx, a
    dropped connection, or a 400 whose body carries an NCBI timeout signature.
    The caller may respond by asking for less at a time. A genuine client error
    raises plain :class:`PubMedError` instead and is never retried.
    """


def looks_transient(body: str) -> bool:
    """Say whether an error body reads as a temporary server-side failure.

    Matches on phrases NCBI uses for its own timeouts. The comparison is
    case-insensitive and looks anywhere in the body.
    """
    lowered = (body or "").lower()
    return any(phrase in lowered for phrase in TRANSIENT_BODY_SIGNATURES)


@dataclass(frozen=True)
class Batch:
    """One planned ``efetch`` call.

    Attributes:
        index: Zero-based position in the run, used to name the output file.
        retstart: Offset into the history-server result set.
        retmax: How many records this call asks for.
    """

    index: int
    retstart: int
    retmax: int


@dataclass(frozen=True)
class SearchResult:
    """What ``esearch`` reported, and the handle to fetch it with.

    Attributes:
        count: Records matching the query, as PubMed counts them.
        webenv: History-server session key.
        query_key: History-server result-set key within that session.
        query_translation: How PubMed expanded the query. Worth keeping: it is
            the difference between the terms we wrote and the search that ran.
        raw_xml: The esearch response, saved alongside the efetch files.
    """

    count: int
    webenv: str
    query_key: str
    query_translation: str
    raw_xml: bytes


def plan_batches(
    total: int, batch_size: int, max_records: int | None = None
) -> list[Batch]:
    """Divide a result set into ``efetch`` calls.

    Args:
        total: Records the search reported.
        batch_size: Records to request per call.
        max_records: Stop after this many, for smoke tests. ``None`` means all.

    Returns:
        Batches in fetch order. The last one is short when the total is not a
        multiple of the batch size. An empty result set plans no calls.

    Raises:
        ValueError: ``total`` is negative, or a size or cap is not positive.
    """
    if total < 0:
        raise ValueError(f"total must not be negative, got {total}")
    if batch_size <= 0:
        raise ValueError(f"batch_size must be positive, got {batch_size}")
    if max_records is not None and max_records <= 0:
        raise ValueError(f"max_records must be positive, got {max_records}")

    wanted = total if max_records is None else min(total, max_records)
    return [
        Batch(index=i, retstart=start, retmax=min(batch_size, wanted - start))
        for i, start in enumerate(range(0, wanted, batch_size))
    ]


@dataclass(frozen=True)
class DateSlice:
    """One publication-date window to search on its own.

    Attributes:
        start: Inclusive first day.
        end: Inclusive last day.
        granularity: The unit this window was cut to -- ``year``, ``month``, or
            ``day``. It says how the slice was reached and how it may be cut
            further; the window itself may be shorter than the unit where it
            meets the edge of the configured range.
    """

    start: date
    end: date
    granularity: str

    @property
    def mindate(self) -> str:
        """Start in the ``YYYY/MM/DD`` form E-utilities expects."""
        return self.start.strftime("%Y/%m/%d")

    @property
    def maxdate(self) -> str:
        """End in the ``YYYY/MM/DD`` form E-utilities expects."""
        return self.end.strftime("%Y/%m/%d")

    @property
    def label(self) -> str:
        """A filename-safe name for the window, used for its saved responses."""
        return f"{self.start:%Y%m%d}-{self.end:%Y%m%d}"


def year_slices(start: date, end: date) -> list[DateSlice]:
    """Cut a date range into calendar years.

    The first and last slices are clipped to the range, so a range ending on
    1 September yields a final slice that stops there.

    Raises:
        ValueError: ``start`` falls after ``end``.
    """
    if start > end:
        raise ValueError(f"start ({start}) is after end ({end})")
    return [
        DateSlice(max(start, date(year, 1, 1)), min(end, date(year, 12, 31)), "year")
        for year in range(start.year, end.year + 1)
    ]


def _split_into(window: DateSlice, unit: str) -> list[DateSlice]:
    """Cut one window into calendar months or into single days."""
    if unit == "month":
        parts: list[DateSlice] = []
        year, month = window.start.year, window.start.month
        while (year, month) <= (window.end.year, window.end.month):
            last = date(year, month, monthrange(year, month)[1])
            parts.append(
                DateSlice(
                    max(window.start, date(year, month, 1)),
                    min(window.end, last),
                    "month",
                )
            )
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        return parts
    if unit == "day":
        span = (window.end - window.start).days + 1
        return [
            DateSlice(window.start + timedelta(days=offset),
                      window.start + timedelta(days=offset), "day")
            for offset in range(span)
        ]
    raise ValueError(f"unknown unit {unit!r}")


def subdivide(window: DateSlice) -> list[DateSlice]:
    """Cut a slice that holds too many records into finer ones.

    A year becomes months and a month becomes days. When a window already fits
    inside one unit of the next size down -- a "year" slice clipped to a single
    month, say -- cutting it there would return the same window and loop, so the
    split goes one step finer instead.

    Raises:
        PubMedError: The slice is a single day. Nothing divides a day, so a day
            holding more records than PubMed will page through cannot be
            retrieved. The run must stop rather than lose the remainder.
    """
    finer = FINER_GRANULARITY.get(window.granularity)
    if finer is None:
        raise PubMedError(
            f"Slice {window.label} covers a single day and still holds more records "
            f"than PubMed will page through ({RETSTART_CEILING} maximum). It cannot "
            "be divided further. Narrow the query, or split the corpus on something "
            "other than date."
        )
    parts = _split_into(window, finer)
    if len(parts) == 1 and parts[0].start == window.start and parts[0].end == window.end:
        return subdivide(replace(window, granularity=finer))
    return parts


def plan_slices(
    start: date,
    end: date,
    search_for: Any,
    *,
    threshold: int = SLICE_THRESHOLD,
    on_leaf: Any | None = None,
) -> list[tuple[DateSlice, SearchResult]]:
    """Work out the slices to fetch, asking PubMed how big each one is.

    Starts from calendar years. Every slice is searched; one that comes back
    over ``threshold`` is subdivided and its parts searched in turn, until each
    remaining slice is small enough to page through. The plan is therefore
    derived from PubMed's own counts and needs no maintained list of years.

    Args:
        start: First day of the configured range.
        end: Last day of the configured range.
        search_for: Callable taking a :class:`DateSlice` and returning the
            :class:`SearchResult` for it. Injected so the plan can be built and
            tested without a network.
        threshold: Records above which a slice is subdivided.
        on_leaf: Called with each slice and its result the moment the slice is
            settled, before the next one is searched. A retrieval fetches there,
            so that a slice is fetched right after its search: history-server
            handles do not live forever, and a large pull can run for many
            minutes. Leave it unset to plan without fetching.

    Returns:
        The leaf slices in date order, each with the search result that will
        fetch it. Empty slices are kept, so the manifest shows the whole plan.

    Raises:
        PubMedError: A single-day slice is still over the retrieval ceiling.
    """
    planned: list[tuple[DateSlice, SearchResult]] = []

    def walk(window: DateSlice) -> None:
        result = search_for(window)
        if result.count > threshold:
            parts = subdivide(window)
            log.info(
                "Slice %s holds %d records, over the %d threshold. Subdividing into "
                "%d %s slices.",
                window.label, result.count, threshold, len(parts), parts[0].granularity,
            )
            for part in parts:
                walk(part)
        else:
            planned.append((window, result))
            if on_leaf is not None:
                on_leaf(window, result)

    for window in year_slices(start, end):
        walk(window)
    return planned


def extract_pmids(xml_bytes: bytes) -> list[str]:
    """Return the PMIDs in an efetch response, in document order.

    Used to deduplicate across overlapping slices during the run, so the count
    can be reconciled before anything downstream reads the files.
    """
    root = etree.fromstring(xml_bytes)
    pmids: list[str] = []
    for tag, path in (
        ("PubmedArticle", "MedlineCitation/PMID"),
        ("PubmedBookArticle", "BookDocument/PMID"),
    ):
        for record in root.iter(tag):
            node = record.find(path)
            if node is not None and node.text:
                pmids.append(node.text.strip())
    return pmids


def split_batch(batch: Batch) -> list[Batch]:
    """Halve one batch into two smaller ones over the same window.

    The pieces keep the parent's index and are told apart by ``retstart``, which
    is what names their files, so a split leaves no ambiguity in the capture.

    Raises:
        PubMedError: The batch is a single record and cannot be divided.
    """
    if batch.retmax < 2:
        raise PubMedError(
            f"Batch at retstart={batch.retstart} is a single record and still "
            "fails. PubMed cannot serve it."
        )
    first = batch.retmax // 2
    return [
        Batch(batch.index, batch.retstart, first),
        Batch(batch.index, batch.retstart + first, batch.retmax - first),
    ]


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 of a file, read in chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def count_records(xml_bytes: bytes) -> int:
    """Count PubMed records in an efetch response.

    Raises:
        PubMedError: The payload is not well-formed XML, or carries an NCBI
            ``<ERROR>`` element. Both arrive with HTTP 200 and must not pass
            for a valid batch.
    """
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:
        raise PubMedError(f"efetch returned XML that will not parse: {exc}") from exc
    error = root.find(".//ERROR")
    if error is not None:
        raise PubMedError(f"efetch returned an NCBI error: {(error.text or '').strip()}")
    return sum(len(root.findall(f".//{tag}")) for tag in RECORD_TAGS)


class RateLimiter:
    """Spaces requests so a client stays inside a per-second ceiling.

    NCBI counts requests per second across a whole client, so one limiter is
    shared by every call the client makes.
    """

    def __init__(self, requests_per_second: float) -> None:
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        self._interval = 1.0 / requests_per_second
        self._last_call = 0.0

    def wait(self) -> None:
        """Sleep long enough that the next request stays under the ceiling."""
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._interval:
            time.sleep(self._interval - elapsed)
        self._last_call = time.monotonic()


class EUtilsClient:
    """A throttled, retrying E-utilities client.

    Every request carries ``tool`` and ``email``, which NCBI requires so it can
    reach a heavy user before blocking one. An API key, if present, is sent as
    well and raises the rate ceiling from 3 requests per second to 10.

    Args:
        tool: Client name registered with NCBI on each request.
        email: Contact address sent on each request.
        api_key: NCBI API key. Defaults to the ``NCBI_API_KEY`` environment
            variable, and to none at all if that is unset.
        requests_per_second: Ceiling to use when no API key is available.
        max_attempts: Tries per request, the first included.
        timeout: Per-request socket timeout, in seconds.
        session: Injected for testing. Defaults to a fresh requests session.
    """

    def __init__(
        self,
        tool: str,
        email: str,
        *,
        api_key: str | None = None,
        requests_per_second: float = RATE_WITHOUT_KEY,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        timeout: float = 60.0,
        session: Any | None = None,
        base_url: str = BASE_URL,
    ) -> None:
        self.tool = tool
        self.email = email
        self.api_key = api_key if api_key is not None else os.environ.get("NCBI_API_KEY") or None
        self.base_url = base_url.rstrip("/")
        self.max_attempts = max_attempts
        self.timeout = timeout
        self.session = session if session is not None else requests.Session()
        self.rate = RATE_WITH_KEY if self.api_key else requests_per_second
        self.limiter = RateLimiter(self.rate)
        log.info(
            "E-utilities client: tool=%s email=%s api_key=%s rate=%s/s",
            self.tool, self.email, "yes" if self.api_key else "no", self.rate,
        )

    def _common_params(self) -> dict[str, str]:
        """Parameters NCBI wants on every request."""
        params = {"tool": self.tool, "email": self.email}
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def _sleep_for_retry(self, attempt: int, response: Any | None) -> None:
        """Wait before a retry, honoring ``Retry-After`` when NCBI sends one."""
        delay = min(BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)), BACKOFF_CAP_SECONDS)
        if response is not None:
            header = response.headers.get("Retry-After") if response.headers else None
            if header:
                try:
                    delay = max(delay, float(header))
                except ValueError:
                    pass
        delay += random.uniform(0, delay * 0.1)  # jitter, to desynchronize retries
        log.warning("Retrying in %.1fs (attempt %d of %d)", delay, attempt, self.max_attempts)
        time.sleep(delay)

    def request(
        self, endpoint: str, params: dict[str, Any], *, method: str = "GET",
        max_attempts: int | None = None,
    ) -> bytes:
        """Call one E-utilities endpoint and return the response body.

        Retries connection failures, 429, 5xx, and any status whose body carries
        an NCBI timeout signature, with exponential backoff and jitter. A status
        outside that set is a fault in our request and is raised at once, so a
        bug surfaces as an error rather than as a long wait.

        Args:
            endpoint: E-utilities endpoint name, without the ``.fcgi``.
            params: Request parameters, merged with tool, email, and API key.
            method: ``GET`` or ``POST``.
            max_attempts: Tries for this call. Defaults to the client's setting;
                a caller that plans to shrink the request passes fewer.

        Raises:
            TransientRetrievalError: Attempts ran out on a retryable failure.
            PubMedError: The server reported an error a retry cannot mend.
        """
        url = f"{self.base_url}/{endpoint}.fcgi"
        payload = {**self._common_params(), **params}
        attempts = self.max_attempts if max_attempts is None else max_attempts
        last_error = "unknown"

        for attempt in range(1, attempts + 1):
            self.limiter.wait()
            response = None
            try:
                if method == "POST":
                    response = self.session.post(url, data=payload, timeout=self.timeout)
                else:
                    response = self.session.get(url, params=payload, timeout=self.timeout)
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                log.warning("%s request failed: %s", endpoint, last_error)
            else:
                if response.status_code == 200:
                    return response.content

                body = response.text or ""
                last_error = f"HTTP {response.status_code}"
                if response.status_code in RETRY_STATUS:
                    log.warning("%s returned %s", endpoint, last_error)
                elif looks_transient(body):
                    # NCBI reporting its own timeout with a client-error status.
                    last_error = f"{last_error} (server timeout: {body.strip()[:200]})"
                    log.warning("%s returned %s; the body reads as a server-side "
                                "timeout, so it will be retried", endpoint, last_error)
                else:
                    raise PubMedError(
                        f"{endpoint} failed with {last_error} and will not be retried. "
                        f"Body: {body[:500]!r}"
                    )

            if attempt < attempts:
                self._sleep_for_retry(attempt, response)

        raise TransientRetrievalError(
            f"{endpoint} failed after {attempts} attempts. Last error: {last_error}"
        )

    def esearch(
        self,
        query: str,
        *,
        db: str = "pubmed",
        mindate: str | None = None,
        maxdate: str | None = None,
        datetype: str = "pdat",
    ) -> SearchResult:
        """Run the search and park the result set on the history server.

        The query goes by POST because a full search strategy runs to several
        kilobytes, past what a URL reliably carries.

        Args:
            query: The PubMed query string, already normalized.
            db: Entrez database. Only ``pubmed`` is used here.
            mindate: Inclusive lower date bound, ``YYYY/MM/DD``.
            maxdate: Inclusive upper date bound, ``YYYY/MM/DD``.
            datetype: Which date the bounds apply to. ``pdat`` is publication
                date, the one the trend line is drawn against.

        Raises:
            PubMedError: The response is unparseable or carries no history keys.
        """
        params: dict[str, Any] = {
            "db": db, "term": query, "usehistory": "y", "retmax": 0, "retmode": "xml",
        }
        if mindate and maxdate:
            params.update(mindate=mindate, maxdate=maxdate, datetype=datetype)

        raw = self.request("esearch", params, method="POST")
        try:
            root = etree.fromstring(raw)
        except etree.XMLSyntaxError as exc:
            raise PubMedError(f"esearch returned XML that will not parse: {exc}") from exc

        error = root.find(".//ERROR")
        if error is not None:
            raise PubMedError(f"esearch rejected the query: {(error.text or '').strip()}")

        def text_of(tag: str) -> str:
            node = root.find(tag)
            return (node.text or "").strip() if node is not None else ""

        count, webenv, query_key = text_of("Count"), text_of("WebEnv"), text_of("QueryKey")
        if not count.isdigit():
            raise PubMedError(f"esearch returned no usable Count. Body: {raw[:500]!r}")
        if int(count) and not (webenv and query_key):
            raise PubMedError(
                "esearch returned no WebEnv or QueryKey, so the history server "
                f"cannot be paged. Body: {raw[:500]!r}"
            )

        return SearchResult(
            count=int(count),
            webenv=webenv,
            query_key=query_key,
            query_translation=text_of("QueryTranslation"),
            raw_xml=raw,
        )

    def efetch_batch(
        self, webenv: str, query_key: str, batch: Batch, *, db: str = "pubmed",
        max_attempts: int | None = None,
    ) -> bytes:
        """Fetch one batch off the history server and check that it holds records.

        A response that is malformed, carries an NCBI error, or holds no records
        is retried; the HTTP layer cannot see these, because NCBI sends them with
        status 200.

        Raises:
            TransientRetrievalError: The batch is still unusable after every
                attempt. The caller may retry it in smaller pieces.
            PubMedError: The server reported an error a retry cannot mend.
        """
        params = {
            "db": db, "WebEnv": webenv, "query_key": query_key,
            "retstart": batch.retstart, "retmax": batch.retmax,
            "retmode": "xml", "rettype": "null",
        }
        attempts = self.max_attempts if max_attempts is None else max_attempts
        last_error = "unknown"
        for attempt in range(1, attempts + 1):
            raw = self.request("efetch", params, max_attempts=attempts)
            try:
                found = count_records(raw)
            except PubMedError as exc:
                last_error = str(exc)
                log.warning("Batch %d: %s", batch.index, last_error)
            else:
                if found:
                    if found < batch.retmax:
                        log.warning(
                            "Batch %d asked for %d records and got %d. PubMed "
                            "returns fewer when records were deleted since the search.",
                            batch.index, batch.retmax, found,
                        )
                    return raw
                last_error = "response held no records"
                log.warning("Batch %d: %s", batch.index, last_error)

            if attempt < attempts:
                self._sleep_for_retry(attempt, None)

        raise TransientRetrievalError(
            f"Batch {batch.index} (retstart={batch.retstart}, retmax={batch.retmax}) "
            f"failed after {attempts} attempts. Last error: {last_error}."
        )

    def efetch_window(
        self, webenv: str, query_key: str, batch: Batch, *, db: str = "pubmed",
    ) -> list[tuple[Batch, bytes]]:
        """Fetch one batch, asking for less at a time if it keeps timing out.

        Large efetch responses are the ones NCBI times out on, so a batch that
        fails transiently twice is halved and each half fetched in turn, rather
        than the same oversized request being repeated. Halving continues while
        the pieces stay above :data:`MIN_SPLIT_SIZE`; below that, size is not the
        problem and the full attempt budget is spent instead.

        Returns:
            One ``(batch, xml)`` pair per request that succeeded: a single pair
            when nothing was split, several when it was.

        Raises:
            TransientRetrievalError: A piece failed even at the smallest size.
            PubMedError: The server reported an error a retry cannot mend.
        """
        if batch.retmax > MIN_SPLIT_SIZE:
            try:
                raw = self.efetch_batch(
                    webenv, query_key, batch, db=db, max_attempts=ATTEMPTS_BEFORE_SPLIT,
                )
            except TransientRetrievalError as exc:
                halves = split_batch(batch)
                log.warning(
                    "Batch at retstart=%d failed %d times at size %d (%s). "
                    "Refetching the same window as %d batches of %s instead.",
                    batch.retstart, ATTEMPTS_BEFORE_SPLIT, batch.retmax, exc,
                    len(halves), " and ".join(str(h.retmax) for h in halves),
                )
                pieces: list[tuple[Batch, bytes]] = []
                for half in halves:
                    pieces.extend(self.efetch_window(webenv, query_key, half, db=db))
                return pieces
            return [(batch, raw)]

        return [(batch, self.efetch_batch(webenv, query_key, batch, db=db))]


def resolve_output_dir(base: Path, name: str) -> Path:
    """Choose a raw output directory that does not already hold a run.

    ``data/raw`` is append-only. When a directory of the wanted name already
    exists and holds a manifest, this returns ``<name>-002``, ``-003``, and so
    on, so an earlier pull is never written over.
    """
    candidate = base / name
    suffix = 1
    while candidate.exists() and any(candidate.iterdir()):
        suffix += 1
        candidate = base / f"{name}-{suffix:03d}"
    return candidate


def load_progress(out_dir: Path) -> dict[str, dict[str, Any]]:
    """Read a partial capture's progress log and return the slices worth keeping.

    ``progress.jsonl`` is appended as the run goes, one line per file written
    and one per slice finished, so a run that dies still leaves a record of what
    it had. A slice is kept only when every file it claims is present and its
    SHA-256 still matches what was recorded. Anything else is refetched: a
    half-written file is worth less than the minute it costs to fetch again.

    Returns:
        Verified slices, keyed by slice label. Empty when there is no log.
    """
    path = out_dir / "progress.jsonl"
    if not path.exists():
        return {}

    file_records: dict[str, dict[str, Any]] = {}
    slice_records: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            log.warning("Ignoring an unreadable line in %s", path)
            continue
        if record.get("kind") == "file":
            file_records[record["file"]] = record
        elif record.get("kind") == "slice":
            slice_records[record["label"]] = record

    verified: dict[str, dict[str, Any]] = {}
    for label, record in slice_records.items():
        files = []
        for name in record.get("files", []):
            claimed = file_records.get(name)
            on_disk = out_dir / name
            if claimed is None or not on_disk.exists():
                log.warning("Slice %s: %s is missing; the slice will be refetched",
                            label, name)
                break
            if sha256_file(on_disk) != claimed["sha256"]:
                log.warning("Slice %s: %s does not match its recorded digest; "
                            "the slice will be refetched", label, name)
                break
            files.append(claimed)
        else:
            verified[label] = {"slice": record, "files": files}
    return verified


def retrieve(
    config: CorpusConfig,
    out_dir: Path,
    *,
    client: EUtilsClient | None = None,
    max_records: int | None = None,
    allow_shortfall: bool = False,
    query_source: str = "config",
    slice_threshold: int = SLICE_THRESHOLD,
    resume: bool = False,
    cli_args: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Run one full retrieval and write the raw capture plus its manifest.

    The date range is searched once whole, to get the number every later count
    is reconciled against, then partitioned into slices small enough to page
    through. Each slice is searched and fetched on its own, and records are
    deduplicated by PMID across slices.

    Args:
        config: The validated corpus configuration.
        out_dir: Directory to write into. Created; must not already hold a run.
        client: An existing client. One is built from the config if omitted.
        max_records: Stop after this many records, for smoke tests. Reconciling
            against the whole-range count is skipped when it is set, because a
            capped run is expected to be short.
        allow_shortfall: Finish even when the numbers do not add up -- fewer
            records than the slices promised, or a deduplicated total that does
            not match the whole-range count. Off by default, because either one
            quietly bends the trend line. The choice is recorded in the manifest.
        query_source: ``"config"``, or ``"cli-override"`` when the query came
            from ``--query``. Recorded so a capture made while testing is never
            mistaken for the corpus.
        slice_threshold: Records above which a slice is subdivided.
        resume: Continue a partial capture in ``out_dir``, keeping the slices
            whose files still match their recorded digests and refetching the
            rest. Only an unfinished run can be resumed: a directory holding a
            ``manifest.json`` is a completed capture and is never written into.
        cli_args: The command line, recorded for provenance.

    Returns:
        The manifest, as written.

    Raises:
        PubMedError: A batch failed, records were lost, or the deduplicated
            total did not reconcile, with ``allow_shortfall`` off.
    """
    started = datetime.now(timezone.utc)
    out_dir.mkdir(parents=True, exist_ok=True)
    settings = config.retrieval

    if client is None:
        client = EUtilsClient(
            tool=settings.tool,
            email=settings.email,
            requests_per_second=settings.requests_per_second,
        )

    already_done: dict[str, dict[str, Any]] = {}
    if resume:
        if (out_dir / "manifest.json").exists():
            raise PubMedError(
                f"{out_dir} holds a finished run (it has a manifest.json). A "
                "completed capture is never written into. Resume the unfinished "
                "directory, or start a new run."
            )
        already_done = load_progress(out_dir)
        log.info("Resuming %s: %d slices already captured and verified",
                 out_dir, len(already_done))

    progress_path = out_dir / "progress.jsonl"

    def record_progress(entry: dict[str, Any]) -> None:
        """Append one line to the progress log and flush it.

        Written as the run goes, so a run that dies is resumable. The manifest
        is the finished account; this is the running one.
        """
        with progress_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")

    # The whole range in one search. Its Count is reliable even though its
    # records cannot all be paged; it is the number the run reconciles against.
    log.info("Searching the whole range (%s to %s, datetype=pdat)",
             config.mindate, config.maxdate)
    whole = client.esearch(
        config.query, db=settings.db,
        mindate=config.mindate, maxdate=config.maxdate,
    )
    (out_dir / "esearch_whole_range.xml").write_bytes(whole.raw_xml)
    log.info("Whole range matches %d records", whole.count)
    if whole.query_translation:
        log.info("PubMed translated the query to: %s", whole.query_translation)

    files: list[dict[str, Any]] = []
    slice_records: list[dict[str, Any]] = []
    pmids: set[str] = set()
    tally = {
        "fetched": 0, "requested": 0, "remaining": max_records,
        "stopped_early": False, "batches_split": 0,
    }

    def search_for(window: DateSlice) -> SearchResult:
        """Search one slice and save the response."""
        result = client.esearch(
            config.query, db=settings.db,
            mindate=window.mindate, maxdate=window.maxdate,
        )
        (out_dir / f"esearch_{window.label}.xml").write_bytes(result.raw_xml)
        log.info("Slice %s (%s): %d records", window.label, window.granularity, result.count)
        return result

    def fetch_slice(window: DateSlice, result: SearchResult) -> None:
        """Fetch one settled slice, straight after its search."""
        entry: dict[str, Any] = {
            "label": window.label,
            "start": window.mindate,
            "end": window.maxdate,
            "granularity": window.granularity,
            "esearch_count": result.count,
            "webenv": result.webenv,
            "query_key": result.query_key,
            "requested": 0,
            "fetched": 0,
            "files": [],
        }
        slice_records.append(entry)

        # A slice kept from a partial capture is read back, not refetched.
        kept = already_done.get(window.label)
        if kept is not None:
            entry["resumed"] = True
            entry["requested"] = kept["slice"].get("requested", 0)
            entry["fetched"] = kept["slice"].get("fetched", 0)
            tally["requested"] += entry["requested"]
            tally["fetched"] += entry["fetched"]
            for file_record in kept["files"]:
                entry["files"].append(file_record["file"])
                files.append({k: v for k, v in file_record.items() if k != "kind"})
                pmids.update(extract_pmids((out_dir / file_record["file"]).read_bytes()))
            log.info("Slice %s: kept %d records from the partial capture",
                     window.label, entry["fetched"])
            return

        remaining = tally["remaining"]
        if remaining is not None and remaining <= 0:
            entry["skipped"] = "record cap reached"
            tally["stopped_early"] = True
            return
        if result.count == 0:
            record_progress({"kind": "slice", **entry})
            return
        if result.count > RETSTART_CEILING:
            raise PubMedError(
                f"Slice {window.label} holds {result.count} records, past the "
                f"{RETSTART_CEILING} PubMed will page through. The subdivision "
                f"should have prevented this; the slice threshold is {slice_threshold}."
            )

        # Clear anything an earlier attempt left for this slice, so a refetch
        # cannot leave orphan files beside the ones the manifest describes.
        for stale in out_dir.glob(f"efetch_{window.label}_*.xml"):
            stale.unlink()

        batches = plan_batches(result.count, settings.batch_size, remaining)
        entry["requested"] = sum(batch.retmax for batch in batches)
        tally["requested"] += entry["requested"]

        for batch in batches:
            pieces = client.efetch_window(
                result.webenv, result.query_key, batch, db=settings.db
            )
            was_split = len(pieces) > 1
            if was_split:
                tally["batches_split"] += 1
            for piece, raw in pieces:
                name = (f"efetch_{window.label}_{piece.index:04d}_"
                        f"{piece.retstart:07d}.xml")
                path = out_dir / name
                path.write_bytes(raw)
                found = count_records(raw)
                pmids.update(extract_pmids(raw))
                tally["fetched"] += found
                entry["fetched"] += found
                entry["files"].append(name)
                file_record = {
                    "file": name,
                    "slice": window.label,
                    "retstart": piece.retstart,
                    "retmax": piece.retmax,
                    "records": found,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
                if was_split:
                    file_record["split_from_retmax"] = batch.retmax
                files.append(file_record)
                record_progress({"kind": "file", **file_record})
                log.info("Slice %s batch %d of %d%s: %d records -> %s",
                         window.label, batch.index + 1, len(batches),
                         " (split)" if was_split else "", found, name)

        if tally["remaining"] is not None:
            tally["remaining"] -= entry["requested"]
        record_progress({"kind": "slice", **entry})

    slices = plan_slices(
        config.start_date, config.end_date, search_for,
        threshold=slice_threshold, on_leaf=fetch_slice,
    )
    sum_of_slice_counts = sum(result.count for _, result in slices)
    fetched = tally["fetched"]
    requested = tally["requested"]
    stopped_early = tally["stopped_early"]
    log.info(
        "Fetched %d slices summing to %d records, against %d for the whole range. "
        "The difference is overlap: the publication date filter matches both the "
        "electronic and the print date, so records near a year boundary fall in "
        "two slices. They are deduplicated by PMID.",
        len(slices), sum_of_slice_counts, whole.count,
    )

    unique = len(pmids)
    duplicates = fetched - unique
    shortfall = requested - fetched
    capped = max_records is not None
    reconciles = None if capped else unique == whole.count

    finished = datetime.now(timezone.utc)
    manifest: dict[str, Any] = {
        "package": "trends",
        "package_version": __version__,
        "retrieval_timestamp_utc": started.isoformat(),
        "retrieval_finished_utc": finished.isoformat(),
        "retrieval_date": started.date().isoformat(),
        "elapsed_seconds": round((finished - started).total_seconds(), 1),
        "config": {
            "path": str(config.path),
            "version": config.version,
            "sha256": config.sha256,
        },
        "query": config.query,
        "query_source": query_source,
        "query_translation": whole.query_translation,
        "date_range": {
            "start": config.mindate, "end": config.maxdate, "datetype": "pdat",
        },
        "slicing": {
            "reason": (
                "PubMed refuses retstart above 9998 even with usehistory=y, so a "
                "corpus larger than that is pulled as date slices and deduplicated."
            ),
            "threshold": slice_threshold,
            "retstart_ceiling": RETSTART_CEILING,
            "n_slices": len(slices),
            "granularities": sorted({window.granularity for window, _ in slices}),
            "stopped_early": stopped_early,
        },
        "resilience": {
            "batches_split": tally["batches_split"],
            "min_split_size": MIN_SPLIT_SIZE,
            "attempts_before_split": ATTEMPTS_BEFORE_SPLIT,
            "resumed": resume,
            "slices_resumed": sum(
                1 for entry in slice_records if entry.get("resumed")
            ),
            "note": (
                "A batch that timed out twice was refetched in halves; files "
                "carrying split_from_retmax came from one that was. NCBI reports "
                "some server-side timeouts with status 400, so retryability is "
                "decided by the response body, not the status alone."
            ),
        },
        "eutils": {
            "base_url": client.base_url,
            "db": settings.db,
            "tool": client.tool,
            "email": client.email,
            "api_key_used": bool(client.api_key),
            "requests_per_second": client.rate,
            "batch_size": settings.batch_size,
            "retmode": "xml",
            "usehistory": "y",
        },
        "counts": {
            "whole_range_esearch": whole.count,
            "sum_of_slice_counts": sum_of_slice_counts,
            "requested": requested,
            "fetched_records": fetched,
            "unique_pmids": unique,
            "duplicate_pmids": duplicates,
            "shortfall": shortfall,
            "reconciles_with_whole_range": reconciles,
            "max_records": max_records,
            "allow_shortfall": allow_shortfall,
        },
        "slices": slice_records,
        "files": files,
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "hostname": socket.gethostname(),
        },
        "cli_args": list(cli_args) if cli_args else None,
    }

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    log.info("Wrote %s", manifest_path)
    log.info("Fetched %d records across %d slices: %d distinct, %d duplicates (%.1f%%)",
             fetched, len(slices), unique, duplicates,
             100 * duplicates / fetched if fetched else 0)
    if tally["batches_split"]:
        log.info("%d batches were refetched at a smaller size after timing out",
                 tally["batches_split"])

    # The capture must describe every file in it, or a later step could parse
    # something the manifest never accounted for.
    described = {record["file"] for record in files}
    on_disk = {path.name for path in out_dir.glob("efetch_*.xml")}
    if on_disk - described:
        log.warning("%d efetch files in %s are not described by the manifest: %s",
                    len(on_disk - described), out_dir,
                    ", ".join(sorted(on_disk - described)[:5]))

    problems = []
    if shortfall:
        problems.append(
            f"asked for {requested} records and got {fetched}: {shortfall} missing"
        )
    if reconciles is False:
        problems.append(
            f"{unique} distinct records after deduplication, but the whole-range "
            f"search reported {whole.count}: off by {unique - whole.count}"
        )
    if problems and not allow_shortfall:
        raise PubMedError(
            "Retrieval did not reconcile: "
            + "; ".join(problems)
            + f". The raw files and manifest are in {out_dir} for inspection. "
            "Re-run, or pass --allow-shortfall if the difference is understood."
        )
    if problems:
        log.warning("Accepted a run that does not reconcile (--allow-shortfall): %s",
                    "; ".join(problems))
    elif reconciles:
        log.info("Reconciled: %d distinct records, matching the whole-range count", unique)
    return manifest


def iter_raw_files(raw_dir: Path) -> Iterator[Path]:
    """Yield the efetch XML files of a raw capture directory, in fetch order."""
    yield from sorted(raw_dir.glob("efetch_*.xml"))
