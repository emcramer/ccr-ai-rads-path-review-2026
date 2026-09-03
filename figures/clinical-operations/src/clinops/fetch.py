"""Download the two sources and write one dated, append-only snapshot.

Usage::

    python -m clinops.fetch --config config/source.yaml

Why a snapshot and not a stream
-------------------------------
FDA republishes the AI-enabled device list *in place*, at a media URL that never
changes: the same URL returned 1,430 rows through 2025-12-30 and 1,524 rows
through 2026-03-30. The URL is therefore not a version, and a figure built from
the live URL is not reproducible. Every run writes the bytes it received into
``data/raw/<YYYY-MM-DD>/`` and everything downstream reads that directory.

The snapshot date is the **maximum ``Date of Final Decision`` in the file**, not
the day the run happened. That date identifies the list's content: two people
downloading the same list a week apart get the same directory name, and a run
that fetches a genuinely newer list gets a new one.

Raw directories are append-only. A non-empty directory of the wanted name is
never written into; a numbered sibling is used instead, so an earlier pull can
always be diffed against a later one.

Unlike the trends figure's gigabyte of PubMed XML, this snapshot is small --
about 130 KB of CSV and under a megabyte of JSON -- so ``data/raw/`` here is
tracked in git rather than gitignored. The figure is then rebuildable from a
clone with no network at all.

What is written
---------------
``devices.csv``
    The FDA response body, byte for byte.
``classification_<nnn>.json``
    Each openFDA batch response, byte for byte. Kept whole rather than reduced
    to ``classification_lookup.fields``, because the snapshot is the evidence
    and the projection is a downstream choice.
``manifest.json``
    Retrieval timestamp, source URLs, per-file SHA-256 and byte count, the
    device row count, the snapshot date, openFDA's ``last_updated``, and every
    product code that returned no classification record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import platform
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Final, Sequence
from urllib.parse import quote

import pandas as pd
import requests

from clinops import __version__
from clinops.config import ConfigError, SourceConfig, load_source_config

log = logging.getLogger("clinops.fetch")

#: File names inside a snapshot directory. Downstream modules read these by
#: name, so they are declared here and nowhere else.
DEVICE_LIST_FILE: Final[str] = "devices.csv"
CLASSIFICATION_PREFIX: Final[str] = "classification_"
MANIFEST_FILE: Final[str] = "manifest.json"

#: Default roots, relative to the project directory the CLI is run from.
DEFAULT_RAW_ROOT: Final[Path] = Path("data/raw")
DEFAULT_LOG_DIR: Final[Path] = Path("logs")

#: openFDA caps a single response at 1,000 records. A batch of `batch_size`
#: product codes returns at most `batch_size` records, so this is headroom, but
#: it is sent explicitly: the endpoint's default limit is 1.
RESPONSE_LIMIT: Final[int] = 1000

#: Statuses worth waiting out. openFDA returns 429 when the anonymous rate is
#: exceeded and 5xx during maintenance. A 404 means "no record matched" and is
#: handled as data, not as an error -- see :func:`fetch_classifications`.
RETRY_STATUS: Final[frozenset[int]] = frozenset({429, 500, 502, 503, 504})


class FetchError(RuntimeError):
    """A source could not be retrieved, or what came back was not usable."""


class SchemaError(FetchError):
    """The FDA list's columns are not the ones ``source.yaml`` requires.

    Raised before anything is written. A renamed column must stop the run: the
    parser would otherwise read a different column under a familiar name and
    produce a figure that is wrong in a way nobody notices.
    """


@dataclass(frozen=True)
class Download:
    """One retrieved response and what is known about it.

    Attributes:
        url: The URL requested.
        content: The response body, unmodified.
        sha256: Digest of those bytes.
        last_modified: The origin's ``Last-Modified`` header, where sent.
        elapsed_seconds: Wall time of the request.
    """

    url: str
    content: bytes
    sha256: str
    last_modified: str | None
    elapsed_seconds: float


def setup_logging(log_dir: Path, *, verbose: bool = False) -> Path:
    """Send logs to the console and to a new timestamped file in ``log_dir``.

    Returns the path of the log file. Timestamps are UTC, so runs on different
    machines sort together.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = log_dir / f"fetch_{stamp}.log"

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S%z"
    )
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    # Clear only our own handlers, so a second call in one process does not log
    # twice and so a caller's handlers (pytest's, for one) survive.
    for handler in list(root.handlers):
        if getattr(handler, "_clinops_handler", False):
            root.removeHandler(handler)
            handler.close()
    for handler in (logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()):
        handler.setFormatter(formatter)
        handler._clinops_handler = True  # type: ignore[attr-defined]
        root.addHandler(handler)
    return log_path


def resolve_output_dir(base: Path, name: str) -> Path:
    """Choose a raw output directory that does not already hold a snapshot.

    ``data/raw`` is append-only. When a directory of the wanted name exists and
    holds anything, this returns ``<name>-002``, ``-003``, and so on, so an
    earlier pull is never written over. Two pulls of the same list therefore sit
    side by side and can be diffed.
    """
    candidate = base / name
    suffix = 1
    while candidate.exists() and any(candidate.iterdir()):
        suffix += 1
        candidate = base / f"{name}-{suffix:03d}"
    return candidate


def digest(content: bytes) -> str:
    """Return the SHA-256 of some bytes."""
    return hashlib.sha256(content).hexdigest()


def file_digest(path: str | Path) -> str:
    """Return the SHA-256 of a file, or ``""`` if it cannot be read."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:  # pragma: no cover - only reachable on a vanished file
        return ""


def download(
    session: requests.Session,
    url: str,
    *,
    timeout: float = 120.0,
    retries: int = 4,
    backoff: float = 2.0,
) -> Download:
    """Fetch one URL, retrying the statuses that are worth waiting out.

    Args:
        session: A session, so connections are reused across the batch queries.
        url: What to fetch.
        timeout: Per-attempt timeout in seconds.
        retries: Attempts after the first.
        backoff: Base of the exponential wait between attempts.

    Returns:
        The response body and its digest.

    Raises:
        FetchError: Every attempt failed, or the final status was an error.
    """
    last: str = ""
    for attempt in range(retries + 1):
        try:
            started = time.monotonic()
            response = session.get(url, timeout=timeout)
            elapsed = time.monotonic() - started
        except requests.RequestException as exc:
            last = f"{type(exc).__name__}: {exc}"
        else:
            if response.status_code == 200:
                return Download(
                    url=url,
                    content=response.content,
                    sha256=digest(response.content),
                    last_modified=response.headers.get("Last-Modified"),
                    elapsed_seconds=elapsed,
                )
            last = f"HTTP {response.status_code}"
            if response.status_code not in RETRY_STATUS:
                raise FetchError(f"{url} returned {last}. {response.text[:300]}")
        if attempt < retries:
            wait = backoff**attempt
            log.warning("%s (%s); retrying in %.0fs", url, last, wait)
            time.sleep(wait)
    raise FetchError(
        f"{url} failed after {retries + 1} attempts. Last: {last}. "
        "Both sources are public and unauthenticated, so this is a network or an "
        "outage, not a credential problem."
    )


def read_device_frame(content: bytes) -> pd.DataFrame:
    """Parse the FDA CSV body into a frame, with every column left as text.

    Dates and submission numbers are parsed by :mod:`clinops.enrich`, not here.
    Reading everything as text keeps a leading-zero submission number intact and
    keeps this function's only job the one it can fail at: producing a frame.
    """
    from io import BytesIO

    try:
        return pd.read_csv(BytesIO(content), dtype=str, encoding="utf-8-sig")
    except Exception as exc:  # pandas raises several unrelated types here
        raise FetchError(
            f"The FDA response is not readable as CSV ({type(exc).__name__}: {exc}). "
            "Check the URL in source.yaml: FDA has served an HTML error page from a "
            "media URL before."
        ) from exc


def normalise_columns(frame: pd.DataFrame, source: SourceConfig) -> pd.DataFrame:
    """Drop the tolerated columns, then assert exactly the required set.

    FDA has already changed this schema once: the 2025-12-30 snapshot carries a
    duplicate ``submission`` column that the live file does not. That column is
    dropped when present and never required. Everything else must match
    ``device_list.required_columns`` exactly -- no missing column, and no extra
    one either, because an extra column is how a rename presents itself.

    Raises:
        SchemaError: The columns are not the required set. The message names
            what is missing, what is unexpected, and what to do about it.
    """
    device_list = source.device_list
    tolerated = [c for c in frame.columns if c in device_list.tolerated_columns]
    if tolerated:
        log.info("Dropping tolerated column(s): %s", ", ".join(tolerated))
        frame = frame.drop(columns=tolerated)

    found = tuple(frame.columns)
    required = device_list.required_columns
    missing = [c for c in required if c not in found]
    unexpected = [c for c in found if c not in required]
    if missing or unexpected:
        raise SchemaError(
            "The FDA device list does not have the expected columns.\n"
            f"  required   : {', '.join(required)}\n"
            f"  found      : {', '.join(found)}\n"
            + (f"  missing    : {', '.join(missing)}\n" if missing else "")
            + (f"  unexpected : {', '.join(unexpected)}\n" if unexpected else "")
            + "Nothing was written. FDA has renamed a column, or added one. Decide what "
            "the new column means, then update device_list.required_columns (for a real "
            "rename) or device_list.tolerated_columns (for one to ignore) in "
            f"{source.path}, bump its `version`, and append the new hash to "
            "config/VERSIONS.json. Do not delete the column from the CSV."
        )
    return frame


def snapshot_date_of(frame: pd.DataFrame) -> date:
    """Return the maximum ``Date of Final Decision`` in a device frame.

    This names the snapshot directory. It is a property of the list's content,
    so it identifies which list was fetched; the day the run happened does not.

    Raises:
        FetchError: No row carries a parsable decision date.
    """
    parsed = pd.to_datetime(frame["Date of Final Decision"], format="%m/%d/%Y", errors="coerce")
    unparsed = int(parsed.isna().sum())
    if unparsed:
        log.warning(
            "%d of %d rows have an unparsable Date of Final Decision", unparsed, len(frame)
        )
    if parsed.notna().sum() == 0:
        raise FetchError(
            "No row in the FDA list carries a parsable Date of Final Decision "
            "(expected MM/DD/YYYY). The snapshot cannot be dated, so nothing was "
            "written."
        )
    return parsed.max().date()


def plan_batches(codes: Sequence[str], batch_size: int) -> list[list[str]]:
    """Split product codes into query batches, sorted so a run is reproducible."""
    ordered = sorted(set(codes))
    return [ordered[i : i + batch_size] for i in range(0, len(ordered), batch_size)]


def classification_url(endpoint: str, batch: Sequence[str]) -> str:
    """Build one openFDA query for a batch of product codes.

    ``search=product_code:("A" "B" ...)`` is openFDA's OR form. Quoting each
    code matters: unquoted, a three-letter code is tokenised and matches
    substrings of unrelated codes.
    """
    terms = " ".join(f'"{code}"' for code in batch)
    return f"{endpoint}?search={quote(f'product_code:({terms})')}&limit={RESPONSE_LIMIT}"


def fetch_classifications(
    session: requests.Session,
    codes: Sequence[str],
    source: SourceConfig,
    *,
    timeout: float = 120.0,
) -> tuple[list[Download], dict[str, Any]]:
    """Query openFDA for every distinct product code, in batches.

    A code that matches nothing is not an error: openFDA answers a search with
    no hits with 404 and a ``NOT_FOUND`` body, and FDA does retire codes. Such
    codes are collected and reported rather than dropped, because a missing
    classification silently removes a device from every downstream decision.

    Returns:
        The batch downloads, and a summary block for the manifest.
    """
    lookup = source.classification_lookup
    batches = plan_batches(codes, lookup.batch_size)
    interval = 1.0 / lookup.requests_per_second
    log.info(
        "Querying %s for %d distinct product codes in %d batch(es) of up to %d, "
        "at %d request(s)/second",
        lookup.endpoint, len(set(codes)), len(batches), lookup.batch_size,
        lookup.requests_per_second,
    )

    downloads: list[Download] = []
    found: set[str] = set()
    last_updated: str | None = None
    for index, batch in enumerate(batches, start=1):
        if index > 1:
            time.sleep(interval)
        url = classification_url(lookup.endpoint, batch)
        try:
            result = download(session, url, timeout=timeout)
        except FetchError as exc:
            # A batch in which no code matches anything answers 404. Recording
            # it as an empty batch keeps the run going and leaves the codes in
            # the "no record" list, where they are reported.
            if "HTTP 404" not in str(exc):
                raise
            log.warning("Batch %d matched no classification record at all", index)
            continue
        downloads.append(result)
        payload = json.loads(result.content)
        meta = payload.get("meta") or {}
        last_updated = meta.get("last_updated", last_updated)
        results = payload.get("results") or []
        for record in results:
            code = record.get("product_code")
            if code:
                found.add(str(code))
        log.info("Batch %d/%d: %d code(s) queried, %d record(s) returned",
                 index, len(batches), len(batch), len(results))

    missing = sorted(set(codes) - found)
    if missing:
        log.warning(
            "%d product code(s) returned no openFDA classification record: %s. "
            "Devices carrying them cannot be classified from the lookup; they are "
            "listed in the manifest and in the classification report.",
            len(missing), ", ".join(missing),
        )
    summary = {
        "endpoint": lookup.endpoint,
        "last_updated": last_updated,
        "batch_size": lookup.batch_size,
        "requests_per_second": lookup.requests_per_second,
        "fields_kept_downstream": list(lookup.fields),
        "n_batches": len(batches),
        "n_codes_queried": len(set(codes)),
        "n_codes_with_record": len(found),
        "codes_without_record": missing,
    }
    return downloads, summary


def write_snapshot(
    out_dir: Path,
    devices: Download,
    classifications: Sequence[Download],
    *,
    source: SourceConfig,
    snapshot_date: date,
    n_devices: int,
    lookup_summary: dict[str, Any],
    cli_args: Sequence[str],
) -> dict[str, Any]:
    """Write the raw bodies and the manifest, and return the manifest.

    Every file is written exactly as received. The manifest is written last, so
    a directory holding one is a finished snapshot.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, dict[str, Any]] = {}

    device_path = out_dir / DEVICE_LIST_FILE
    device_path.write_bytes(devices.content)
    files[DEVICE_LIST_FILE] = {
        "source_url": devices.url,
        "sha256": devices.sha256,
        "bytes": len(devices.content),
        "http_last_modified": devices.last_modified,
        "n_rows": n_devices,
    }

    for index, result in enumerate(classifications, start=1):
        name = f"{CLASSIFICATION_PREFIX}{index:03d}.json"
        (out_dir / name).write_bytes(result.content)
        files[name] = {
            "source_url": result.url,
            "sha256": result.sha256,
            "bytes": len(result.content),
        }

    manifest = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool": "clinops.fetch",
        "clinops": __version__,
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "snapshot_date": snapshot_date.isoformat(),
        "snapshot_date_source": "max(Date of Final Decision) in the downloaded list",
        "config": {
            "path": str(source.path),
            "version": source.version,
            "sha256": source.sha256,
        },
        "device_list": {
            "name": source.device_list.name,
            "csv_url": source.device_list.csv_url,
            "landing_page": source.device_list.landing_page,
            "alternate_urls": dict(source.device_list.alternate_urls),
            "n_rows": n_devices,
            "required_columns": list(source.device_list.required_columns),
        },
        "classification_lookup": lookup_summary,
        "files": files,
        "cli_args": list(cli_args),
    }
    (out_dir / MANIFEST_FILE).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    log.info("Wrote %s", out_dir / MANIFEST_FILE)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    """Define the command line."""
    parser = argparse.ArgumentParser(
        prog="python -m clinops.fetch",
        description=(
            "Download the FDA AI-enabled device list and the openFDA product-code "
            "classifications, and write one dated, append-only snapshot."
        ),
        epilog=(
            "The snapshot directory is named for the maximum Date of Final Decision "
            "in the downloaded list, not for the day of the run, so the name "
            "identifies the list's content. An existing non-empty directory is never "
            "written into; a numbered sibling is used instead. The snapshot is small "
            "enough to be tracked in git, which is what makes the figure rebuildable "
            "with no network."
        ),
    )
    parser.add_argument("--config", type=Path, default=Path("config/source.yaml"),
                        help="Path to source.yaml. Default: config/source.yaml.")
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT,
                        help=f"Where snapshot directories live. "
                             f"Default: {DEFAULT_RAW_ROOT}.")
    parser.add_argument("--out", type=Path, default=None,
                        help="Write to this exact directory instead of "
                             "<raw-root>/<snapshot-date>. Still never overwrites a "
                             "non-empty directory.")
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR,
                        help=f"Where the run log goes. Default: {DEFAULT_LOG_DIR}.")
    parser.add_argument("--timeout", type=float, default=120.0,
                        help="Per-request timeout in seconds. Default: 120.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Download the device list, report its row count and "
                             "snapshot date, then stop. No openFDA queries and no "
                             "files written except the log.")
    parser.add_argument("--verbose", action="store_true", help="Debug-level logging.")
    parser.add_argument("--version", action="version", version=f"clinops {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one retrieval. Returns a process exit status."""
    argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(argv)

    log_path = setup_logging(args.log_dir, verbose=args.verbose)
    log.info("clinops %s starting", __version__)
    log.info("Logging to %s", log_path)

    try:
        source = load_source_config(args.config)
    except ConfigError as exc:
        log.error("Configuration is unusable:\n%s", exc)
        return 2
    log.info("Config %s version %d (sha256 %s)",
             source.path, source.version, source.sha256[:12])

    session = requests.Session()
    session.headers["User-Agent"] = f"clinops/{__version__} (CCR review figure pipeline)"

    try:
        log.info("Fetching %s", source.device_list.csv_url)
        devices = download(session, source.device_list.csv_url, timeout=args.timeout)
        log.info("Received %d bytes (sha256 %s)", len(devices.content), devices.sha256[:12])

        frame = normalise_columns(read_device_frame(devices.content), source)
        snapshot_date = snapshot_date_of(frame)
        log.info("%d device rows; snapshot date %s (max Date of Final Decision)",
                 len(frame), snapshot_date)

        expected_rows = source.expected.get("total_devices")
        if isinstance(expected_rows, int) and expected_rows != len(frame):
            # Not an error. The list grows; source.yaml records what was last
            # measured so the growth is visible rather than silent.
            log.warning(
                "The list holds %d rows; source.yaml last measured %d. The figure's "
                "numbers will differ from the ones recorded in docs/. This is drift, "
                "not a failure.", len(frame), expected_rows,
            )

        codes = sorted(frame["Primary Product Code"].dropna().str.strip().unique())
        if args.dry_run:
            log.info("Dry run: %d rows, %d distinct product codes, snapshot date %s. "
                     "Nothing written.", len(frame), len(codes), snapshot_date)
            return 0

        classifications, lookup_summary = fetch_classifications(
            session, codes, source, timeout=args.timeout
        )

        base_dir = args.out.parent if args.out else args.raw_root
        base_name = args.out.name if args.out else snapshot_date.isoformat()
        out_dir = resolve_output_dir(base_dir, base_name)
        if out_dir.name != base_name:
            log.warning(
                "%s already holds a snapshot; writing to %s instead. data/raw is "
                "append-only, so the earlier pull is kept and the two can be diffed.",
                base_dir / base_name, out_dir,
            )
        log.info("Snapshot directory: %s", out_dir)

        manifest = write_snapshot(
            out_dir, devices, classifications,
            source=source,
            snapshot_date=snapshot_date,
            n_devices=len(frame),
            lookup_summary=lookup_summary,
            cli_args=argv,
        )
    except SchemaError as exc:
        log.error("%s", exc)
        return 1
    except FetchError as exc:
        log.error("Retrieval failed: %s", exc)
        return 1

    total_bytes = sum(entry["bytes"] for entry in manifest["files"].values())
    log.info(
        "Snapshot %s written: %d device rows, %d classification batch file(s), "
        "%.0f KB total. openFDA last_updated %s.",
        out_dir, manifest["device_list"]["n_rows"],
        manifest["classification_lookup"]["n_batches"], total_bytes / 1024,
        manifest["classification_lookup"]["last_updated"],
    )
    missing = manifest["classification_lookup"]["codes_without_record"]
    if missing:
        log.warning("%d code(s) without a classification record: %s",
                    len(missing), ", ".join(missing))
    log.info("Next: python -m clinops.classify --config-dir %s --report",
             args.config.parent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
