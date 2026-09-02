"""Command line entry point: config in, raw capture and record table out.

Usage::

    PYTHONPATH=src python -m trends.fetch --config config/corpus.yaml
    PYTHONPATH=src python -m trends.fetch --config config/corpus.yaml --max-records 200 \
        --out data/raw/smoke --interim-dir data/interim/smoke

The run loads and validates the config, searches PubMed, writes every response
to the raw directory with a manifest, then parses the capture into
``records.parquet``. It logs to the console and to a timestamped file in
``logs/``. Any failure stops the run with a non-zero exit status; a truncated
corpus is never written quietly.
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from trends import __version__
from trends.config import ConfigError, load_corpus_config
from trends.parse import parse_directory, write_outputs
from trends.pubmed import (
    SLICE_THRESHOLD,
    EUtilsClient,
    PubMedError,
    plan_batches,
    plan_slices,
    resolve_output_dir,
    retrieve,
)

log = logging.getLogger("trends.fetch")


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
        if getattr(handler, "_trends_handler", False):
            root.removeHandler(handler)
            handler.close()
    for handler in (logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()):
        handler.setFormatter(formatter)
        handler._trends_handler = True
        root.addHandler(handler)
    return log_path


def build_parser() -> argparse.ArgumentParser:
    """Define the command line."""
    parser = argparse.ArgumentParser(
        prog="python -m trends.fetch",
        description="Retrieve a PubMed corpus and parse it into a record table.",
    )
    parser.add_argument("--config", required=True, type=Path,
                        help="Path to corpus.yaml.")
    parser.add_argument("--max-records", type=int, default=None,
                        help="Stop after this many records. For smoke tests only.")
    parser.add_argument("--out", type=Path, default=None,
                        help="Raw capture directory. Defaults to data/raw/<retrieval-date>. "
                             "An existing non-empty directory is never overwritten; a "
                             "numbered sibling is used instead.")
    parser.add_argument("--interim-dir", type=Path, default=Path("data/interim"),
                        help="Where the parsed records go. Default: data/interim.")
    parser.add_argument("--log-dir", type=Path, default=Path("logs"),
                        help="Where the run log goes. Default: logs.")
    parser.add_argument("--query", default=None,
                        help="Override the config query. For testing the pipeline "
                             "before the search strategy is final. Recorded in the manifest.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Search and report the record count, then stop. No efetch, "
                             "no files written except the log.")
    parser.add_argument("--no-parse", action="store_true",
                        help="Capture the raw XML but do not parse it.")
    parser.add_argument("--allow-shortfall", action="store_true",
                        help="Finish even if the counts do not reconcile: fewer records "
                             "than the slices promised, or a deduplicated total that does "
                             "not match the whole-range count. Off by default. The choice "
                             "is recorded in the manifest.")
    parser.add_argument("--slice-threshold", type=int, default=SLICE_THRESHOLD,
                        help=f"Subdivide any date slice holding more records than this. "
                             f"Default {SLICE_THRESHOLD}, below PubMed's hard ceiling of "
                             "9998 on retstart. Lower it to exercise the subdivision on a "
                             "small corpus.")
    parser.add_argument("--resume", action="store_true",
                        help="Continue the partial capture named by --out instead of "
                             "starting a new directory. Slices whose files still match "
                             "their recorded SHA-256 are kept; everything else is "
                             "refetched. A finished run (one with a manifest.json) is "
                             "never resumed into.")
    parser.add_argument("--verbose", action="store_true", help="Debug-level logging.")
    parser.add_argument("--version", action="version", version=f"trends {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one retrieval. Returns a process exit status."""
    argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(argv)

    log_path = setup_logging(args.log_dir, verbose=args.verbose)
    log.info("trends %s starting", __version__)
    log.info("Logging to %s", log_path)

    try:
        config = load_corpus_config(args.config, require_query=not args.query)
    except ConfigError as exc:
        log.error("Configuration is unusable:\n%s", exc)
        return 2
    log.info("Config %s version %d (sha256 %s)",
             config.path, config.version, config.sha256[:12])

    query_source = "config"
    if args.query:
        log.warning("Query overridden on the command line. This is not the corpus query.")
        config = dataclasses.replace(config, query=args.query)
        query_source = "cli-override"
    log.info("Query: %s", config.query)

    settings = config.retrieval
    client = EUtilsClient(
        tool=settings.tool, email=settings.email,
        requests_per_second=settings.requests_per_second,
    )

    try:
        if args.dry_run:
            whole = client.esearch(
                config.query, db=settings.db,
                mindate=config.mindate, maxdate=config.maxdate,
            )
            log.info("Whole range matches %d records", whole.count)
            if whole.query_translation:
                log.info("PubMed translated the query to: %s", whole.query_translation)

            def search_for(window):
                result = client.esearch(
                    config.query, db=settings.db,
                    mindate=window.mindate, maxdate=window.maxdate,
                )
                log.info("Slice %s (%s): %d records",
                         window.label, window.granularity, result.count)
                return result

            slices = plan_slices(
                config.start_date, config.end_date, search_for,
                threshold=args.slice_threshold,
            )
            total = sum(result.count for _, result in slices)
            batches = sum(
                len(plan_batches(result.count, settings.batch_size, args.max_records))
                for _, result in slices
            )
            log.info(
                "Dry run: %d slices (%s), summing to %d records against %d for the "
                "whole range. %d efetch batches of up to %d.",
                len(slices),
                ", ".join(sorted({w.granularity for w, _ in slices})),
                total, whole.count, batches, settings.batch_size,
            )
            log.info("Expect roughly %.1f minutes of fetching at %s requests per second, "
                     "plus the %d searches already made.",
                     batches * 1.2 / 60, client.rate, len(slices) + 1)
            log.info("Overlap to be deduplicated: about %d records (%.1f%%)",
                     total - whole.count,
                     100 * (total - whole.count) / total if total else 0)
            return 0

        if args.resume:
            if not args.out:
                log.error("--resume needs --out to say which capture to continue.")
                return 2
            out_dir = args.out
            if not out_dir.exists():
                log.error("Cannot resume %s: it does not exist.", out_dir)
                return 2
        else:
            base_name = (args.out.name if args.out
                         else datetime.now(timezone.utc).date().isoformat())
            base_dir = args.out.parent if args.out else Path("data/raw")
            out_dir = resolve_output_dir(base_dir, base_name)
            if args.out and out_dir != args.out:
                log.warning("%s already holds a run; writing to %s instead. "
                            "Pass --resume to continue it instead of starting fresh.",
                            args.out, out_dir)
        log.info("Raw capture directory: %s", out_dir)

        manifest = retrieve(
            config, out_dir, client=client,
            max_records=args.max_records,
            allow_shortfall=args.allow_shortfall,
            query_source=query_source,
            slice_threshold=args.slice_threshold,
            resume=args.resume,
            cli_args=argv,
        )
    except PubMedError as exc:
        log.error("Retrieval failed: %s", exc)
        return 1

    counts = manifest["counts"]
    log.info("Retrieved %d records in %.1f s: %d distinct, %d duplicates across slices",
             counts["fetched_records"], manifest["elapsed_seconds"],
             counts["unique_pmids"], counts["duplicate_pmids"])

    if args.no_parse:
        log.info("Skipping the parse step (--no-parse)")
        return 0

    frame, summary = parse_directory(out_dir)
    paths = write_outputs(frame, summary, args.interim_dir)
    log.info("Parsed %d records -> %s", len(frame), paths["parquet"])
    log.info("Abstracts: %d missing, %d structured, %d unstructured",
             summary.without_abstract, summary.with_structured_abstract,
             summary.records - summary.without_abstract - summary.with_structured_abstract)
    log.info("Year sources: %s", summary.year_sources)
    if summary.without_year:
        log.warning("%d records carry no usable year", summary.without_year)
    return 0


if __name__ == "__main__":
    sys.exit(main())
