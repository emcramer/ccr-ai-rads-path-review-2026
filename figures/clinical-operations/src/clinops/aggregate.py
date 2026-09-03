"""Reduce the labelled devices to the three tables the figure is drawn from.

Usage::

    python -m clinops.aggregate

:mod:`clinops.classify` produces one labelled row per device. This module writes
``authorizations.csv``, ``cumulative_by_year.csv`` and ``pathway_by_domain.csv``
exactly to the schemas the figure is being built against, plus the run manifest.

It owns the output schema, so the column order is declared in one place. It
classifies nothing and reads no source configuration beyond the provenance the
classification run recorded.

Two invariants the tables hold, and the reason for each:

* **The count tables are dense.** ``cumulative_by_year.csv`` carries every
  ``(year, category)`` pair from the first year any authorization exists through
  the last, zeros filled, and ``pathway_by_domain.csv`` carries every
  ``(category, pathway)`` pair. Density costs a few hundred rows and means the
  plotting code never reindexes: a missing year draws as a zero rather than as a
  gap, and a pathway with no devices draws as an empty segment rather than
  vanishing and shifting the ones beside it.
* **``cumulative_count`` is a running sum within a category**, over the dense
  year axis, so it never decreases and the last row of a category equals that
  category's device count in ``authorizations.csv``.

Every table is written with a ``#`` provenance header naming the snapshot, the
config versions, and the generation time. The figure's reader parses with
``comment="#"``, so the header travels with the data.
"""

from __future__ import annotations

import argparse
import json
import logging
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, Iterable, Sequence

import pandas as pd

from clinops import __version__
from clinops.classify import (
    CLASSIFICATION_RUN,
    DEFAULT_INTERIM_DIR,
    DEFAULT_PROCESSED_DIR,
    LABELED_DEVICES,
)
from clinops.config import CATEGORY_KEYS
from clinops.fetch import file_digest

log = logging.getLogger("clinops.aggregate")

#: Column order of ``authorizations.csv``: one row per counted device.
AUTHORIZATION_COLUMNS: Final[tuple[str, ...]] = (
    "submission_number",
    "decision_date",
    "year",
    "device",
    "company",
    "panel_lead",
    "product_code",
    "domain",
    "category",
    "category_label",
    "pathway",
    "regulation_number",
)

#: Column order of ``cumulative_by_year.csv``.
CUMULATIVE_COLUMNS: Final[tuple[str, ...]] = (
    "year", "category", "domain", "annual_count", "cumulative_count",
)

#: Column order of ``pathway_by_domain.csv``.
PATHWAY_COLUMNS: Final[tuple[str, ...]] = ("domain", "category", "pathway", "count")

#: Marketing pathways in figure order: the ordinary route first, then the two
#: rare ones. Fixed here so a stacked bar's segments do not reorder between runs
#: when a category happens to gain its first De Novo.
PATHWAY_ORDER: Final[tuple[str, ...]] = ("510(k)", "De Novo", "PMA")

#: File names written into the processed directory.
AUTHORIZATIONS: Final[str] = "authorizations.csv"
CUMULATIVE_BY_YEAR: Final[str] = "cumulative_by_year.csv"
PATHWAY_BY_DOMAIN: Final[str] = "pathway_by_domain.csv"
RUN_MANIFEST: Final[str] = "run_manifest.json"


class AggregateError(ValueError):
    """The labelled table is missing or is not in the shape this module expects."""


def read_labeled(interim_dir: str | Path = DEFAULT_INTERIM_DIR) -> pd.DataFrame:
    """Read ``labeled_devices.csv`` from a classification run.

    Raises:
        AggregateError: The file is absent or lacks a column the schema needs.
    """
    path = Path(interim_dir) / LABELED_DEVICES
    if not path.exists():
        raise AggregateError(
            f"{path} not found. Run: python -m clinops.classify --config-dir config "
            "--report"
        )
    # Every column is read as text. `regulation_number` is the reason: pandas
    # infers "892.2050" as a float and writes it back as 892.205, silently
    # dropping the trailing digit of an FDA regulation citation. Nothing in this
    # table is arithmetic except `year`, which is cast back below.
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[])
    missing = [c for c in (*AUTHORIZATION_COLUMNS, "counted") if c not in frame.columns]
    if missing:
        raise AggregateError(
            f"{path} is missing column(s): {', '.join(missing)}. It was written by a "
            "different version of clinops.classify; re-run that stage."
        )
    frame["year"] = pd.to_numeric(frame["year"], errors="coerce").astype("Int64")
    for column in ("counted", "code_overridden", "has_classification"):
        if column in frame.columns:
            frame[column] = frame[column].str.strip().str.lower() == "true"
    return frame


def read_run_record(interim_dir: str | Path = DEFAULT_INTERIM_DIR) -> dict[str, Any]:
    """Read the classification run's provenance record.

    A missing record is not fatal: the tables can still be built, and the
    manifest says so rather than inventing a provenance it does not have.
    """
    path = Path(interim_dir) / CLASSIFICATION_RUN
    if not path.exists():
        log.warning(
            "%s not found. The tables will be built, but the run manifest will carry "
            "no input digest or config versions. Re-run clinops.classify to restore "
            "full provenance.", path,
        )
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_authorizations(labeled: pd.DataFrame) -> pd.DataFrame:
    """Select the counted devices, in the frozen schema and a stable order.

    Rows are ordered by decision date then submission number, so two runs over
    the same snapshot produce identical data and a diff between snapshots shows
    only what actually changed. Only the `#` header moves between runs, because
    it carries the generation time.
    """
    counted = labeled.loc[labeled["counted"].astype(bool)].copy()
    frame = counted.loc[:, list(AUTHORIZATION_COLUMNS)]
    frame = frame.sort_values(
        ["decision_date", "submission_number"], kind="stable"
    ).reset_index(drop=True)
    frame["year"] = frame["year"].astype("int64")
    return frame


def build_cumulative_by_year(
    authorizations: pd.DataFrame, *, years: Sequence[int] | None = None
) -> pd.DataFrame:
    """Count authorizations per category and year, densely, with a running total.

    The year axis runs from the earliest authorization in the table to the
    latest, over every category, so the plotting code can index straight into it.
    That means the radiology categories carry explicit zeros back to 1995, where
    pathology's two Pap screeners sit: a 26-year gap in the radiology series is
    the shape of the story, and drawing it as zeros rather than as a missing
    range is what makes it visible.

    Args:
        authorizations: ``authorizations.csv`` as a frame.
        years: Override the year axis. Defaults to the range observed.

    Returns:
        ``cumulative_by_year.csv`` as a frame, categories in figure order.
    """
    if authorizations.empty:
        return pd.DataFrame(columns=list(CUMULATIVE_COLUMNS))

    values = authorizations["year"].astype("int64")
    axis = list(years) if years is not None else list(range(int(values.min()), int(values.max()) + 1))
    present = [key for key in CATEGORY_KEYS if key in set(authorizations["category"])]
    present += sorted(set(authorizations["category"]) - set(CATEGORY_KEYS))

    rows: list[dict[str, Any]] = []
    for category in present:
        block = authorizations.loc[authorizations["category"] == category]
        # A category maps to exactly one domain, so reading it off the first row
        # is safe; the assertion is cheap and catches a hand-edited table.
        domains = set(block["domain"])
        if len(domains) != 1:
            raise AggregateError(
                f"category {category!r} carries domains {sorted(domains)}. A category "
                "belongs to exactly one domain; the labelled table has been edited or "
                "oncology_codes.yaml declares the category twice."
            )
        domain = domains.pop()
        counts = block["year"].astype("int64").value_counts()
        running = 0
        for year in axis:
            annual = int(counts.get(year, 0))
            running += annual
            rows.append(
                {
                    "year": int(year),
                    "category": category,
                    "domain": domain,
                    "annual_count": annual,
                    "cumulative_count": running,
                }
            )
    return pd.DataFrame(rows, columns=list(CUMULATIVE_COLUMNS))


def build_pathway_by_domain(authorizations: pd.DataFrame) -> pd.DataFrame:
    """Count authorizations per domain, category, and marketing pathway.

    Dense over :data:`PATHWAY_ORDER`, for the same reason the year axis is
    dense: a category with no De Novo authorization emits a zero rather than
    dropping a segment, so a stacked bar's segments keep their order and their
    colours between runs.
    """
    if authorizations.empty:
        return pd.DataFrame(columns=list(PATHWAY_COLUMNS))

    pairs = (
        authorizations.loc[:, ["domain", "category"]]
        .drop_duplicates()
        .to_records(index=False)
    )
    order = {key: index for index, key in enumerate(CATEGORY_KEYS)}
    pairs = sorted(pairs, key=lambda pair: (order.get(pair[1], len(order)), pair[1]))
    counts = authorizations.groupby(["domain", "category", "pathway"]).size()

    rows = [
        {
            "domain": domain,
            "category": category,
            "pathway": pathway,
            "count": int(counts.get((domain, category, pathway), 0)),
        }
        for domain, category in pairs
        for pathway in PATHWAY_ORDER
    ]
    frame = pd.DataFrame(rows, columns=list(PATHWAY_COLUMNS))

    unknown = sorted(set(authorizations["pathway"]) - set(PATHWAY_ORDER))
    if unknown:
        raise AggregateError(
            f"authorizations.csv carries pathway value(s) {', '.join(unknown)}, which "
            f"the frozen schema does not declare ({', '.join(PATHWAY_ORDER)}). Add the "
            "pathway to clinops.aggregate.PATHWAY_ORDER and to the figure together, or "
            "fix the prefix rule in source.yaml."
        )
    return frame


def provenance_lines(record: dict[str, Any], *, table: str) -> list[str]:
    """Build the ``#`` header every processed table carries.

    Snapshot, config versions and digests, and the generation time -- enough
    that a table found on its own can be traced back to the bytes that made it.
    """
    source = ((record.get("config") or {}).get("source")) or {}
    codes = ((record.get("config") or {}).get("oncology_codes")) or {}
    input_block = record.get("input") or {}
    return [
        f"file: {table}",
        f"generated_utc: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"snapshot: {input_block.get('snapshot', '(unknown)')}",
        f"snapshot_date: {input_block.get('snapshot_date', '(unknown)')}"
        "  (max Date of Final Decision in the FDA list)",
        f"devices.csv sha256: {str(input_block.get('sha256', ''))[:16]}",
        f"source.yaml v{source.get('version', '?')} "
        f"sha256:{str(source.get('sha256', ''))[:16]}",
        f"oncology_codes.yaml v{codes.get('version', '?')} "
        f"sha256:{str(codes.get('sha256', ''))[:16]}",
        f"tool: clinops.aggregate {__version__}",
    ]


def _write_csv(frame: pd.DataFrame, path: Path, header: Iterable[str]) -> Path:
    """Write one table with a commented provenance header.

    The figure's reader parses these with ``comment='#'``, so the header travels
    with the data without breaking the reader.
    """
    lines = "".join(f"# {line}\n" for line in header)
    path.write_text(lines + frame.to_csv(index=False), encoding="utf-8")
    log.info("Wrote %s (%d rows)", path, len(frame))
    return path


def write_tables(
    labeled: pd.DataFrame, output_dir: str | Path, record: dict[str, Any]
) -> tuple[dict[str, Path], dict[str, pd.DataFrame]]:
    """Build and write the three processed tables.

    Returns:
        The paths written and the frames written, keyed alike.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    authorizations = build_authorizations(labeled)
    frames = {
        "authorizations": authorizations,
        "cumulative_by_year": build_cumulative_by_year(authorizations),
        "pathway_by_domain": build_pathway_by_domain(authorizations),
    }
    names = {
        "authorizations": AUTHORIZATIONS,
        "cumulative_by_year": CUMULATIVE_BY_YEAR,
        "pathway_by_domain": PATHWAY_BY_DOMAIN,
    }
    paths = {
        key: _write_csv(
            frame, output_dir / names[key], provenance_lines(record, table=names[key])
        )
        for key, frame in frames.items()
    }
    return paths, frames


def build_manifest(
    record: dict[str, Any],
    labeled: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    paths: dict[str, Path],
) -> dict[str, Any]:
    """Assemble the run manifest written beside the tables.

    It records what went in, which config versions and digests produced the
    labels, what came out, and what was excluded and why, so a figure can be
    traced to the snapshot and the rule that made it.
    """
    authorizations = frames["authorizations"]
    counts = record.get("counts") or {}
    return {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool": "clinops.aggregate",
        "clinops": __version__,
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "input": record.get("input") or {"note": "no classification_run.json was found"},
        "config": record.get("config") or {},
        "classification": {
            "tool": record.get("tool"),
            "generated_utc": record.get("generated_utc"),
        },
        "counts": {
            "devices_in": counts.get("devices_in", int(len(labeled))),
            "devices_counted": counts.get(
                "devices_counted", int(labeled["counted"].astype(bool).sum())
            ),
            "authorizations_written": int(len(authorizations)),
            "exclusions": counts.get("exclusions", {}),
            "by_category": {
                str(key): int(value)
                for key, value in authorizations["category"].value_counts().items()
            },
            "by_domain": {
                str(key): int(value)
                for key, value in authorizations["domain"].value_counts().items()
            },
            "by_domain_pathway": {
                f"{domain}|{pathway}": int(n)
                for (domain, pathway), n in
                authorizations.groupby(["domain", "pathway"]).size().items()
            },
            "year_range": (
                [int(authorizations["year"].min()), int(authorizations["year"].max())]
                if len(authorizations) else None
            ),
            "cumulative_final": {
                str(category): int(
                    block.sort_values("year")["cumulative_count"].iloc[-1]
                )
                for category, block in frames["cumulative_by_year"].groupby("category")
            },
        },
        "checks": record.get("checks") or {},
        "outputs": {
            name: {
                "path": str(path),
                "sha256": file_digest(path),
                "n_rows": int(len(frames[name])),
            }
            for name, path in paths.items()
        },
    }


def run(
    interim_dir: str | Path = DEFAULT_INTERIM_DIR,
    output_dir: str | Path = DEFAULT_PROCESSED_DIR,
) -> dict[str, Any]:
    """Build the processed tables from a classification run and write them.

    Returns:
        The run manifest, as written.
    """
    labeled = read_labeled(interim_dir)
    record = read_run_record(interim_dir)
    paths, frames = write_tables(labeled, output_dir, record)
    manifest = build_manifest(record, labeled, frames, paths)
    manifest_path = Path(output_dir) / RUN_MANIFEST
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    log.info("Wrote %s", manifest_path)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    """Define the command line."""
    parser = argparse.ArgumentParser(
        prog="python -m clinops.aggregate",
        description=(
            "Build the three tables the figure is drawn from -- authorizations.csv, "
            "cumulative_by_year.csv, pathway_by_domain.csv -- plus run_manifest.json."
        ),
        epilog=(
            "Reads data/interim/labeled_devices.csv, which clinops.classify writes. "
            "The count tables are dense: every (year, category) and every "
            "(category, pathway) pair is present, zeros filled, so the plotting code "
            "never has to reindex. Each table carries a '#' provenance header naming "
            "the snapshot and the config versions; read them with comment='#'."
        ),
    )
    parser.add_argument("--interim-dir", type=Path, default=DEFAULT_INTERIM_DIR,
                        help=f"Where labeled_devices.csv lives. "
                             f"Default: {DEFAULT_INTERIM_DIR}.")
    parser.add_argument("--output", type=Path, default=DEFAULT_PROCESSED_DIR,
                        help=f"Where the tables and the run manifest go. "
                             f"Default: {DEFAULT_PROCESSED_DIR}.")
    parser.add_argument("--version", action="version", version=f"clinops {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Build the processed tables from the command line. Returns an exit status."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    try:
        manifest = run(args.interim_dir, args.output)
    except AggregateError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(json.dumps(manifest["counts"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
