"""Join every device row to its product code's openFDA classification record.

Usage::

    python -m clinops.enrich --snapshot data/raw/2026-03-30

The FDA AI-enabled device list publishes no indication-for-use field. Its only
free-text column is ``Device``, and that holds brand names -- Transpara,
ProFound AI, AIR Recon DL -- which cannot carry a cancer/not-cancer decision.
What the list does publish is ``Primary Product Code``, and a product code
resolves through openFDA to an FDA regulation number and a regulation
definition that states what the device type is *for*.

This module performs that resolution and nothing else. It reads a snapshot,
holds the column contract, derives the three fields the list implies rather than
states (decision date, year, marketing pathway), and attaches the classification
record. It makes no oncology judgment: that is :mod:`clinops.classify`, reading
``oncology_codes.yaml``.

A device whose code returned no classification record keeps its row, with
``has_classification`` false. Dropping it here would silently shrink the
denominator every count is reported against.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Final

import pandas as pd

from clinops import __version__
from clinops.config import ConfigError, SourceConfig, load_source_config
from clinops.fetch import (
    CLASSIFICATION_PREFIX,
    DEVICE_LIST_FILE,
    DEFAULT_RAW_ROOT,
    MANIFEST_FILE,
    file_digest,
    normalise_columns,
    read_device_frame,
)

log = logging.getLogger("clinops.enrich")

#: Columns carried out of the FDA list, renamed to the frozen output schema.
#: ``authorizations.csv`` uses these names, so the rename happens once, here.
COLUMN_RENAMES: Final[dict[str, str]] = {
    "Submission Number": "submission_number",
    "Device": "device",
    "Company": "company",
    "Panel (Lead)": "panel_lead",
    "Primary Product Code": "product_code",
}

#: Prefix under which an openFDA field is carried on a device row, so that a
#: lookup value can never be mistaken for something the FDA list itself said.
OPENFDA_PREFIX: Final[str] = "openfda_"

#: The date format FDA writes in ``Date of Final Decision``.
DECISION_DATE_FORMAT: Final[str] = "%m/%d/%Y"


class SnapshotError(ValueError):
    """A raw snapshot is missing, incomplete, or does not match ``source.yaml``.

    The message names the directory and says what to do, because the usual
    cause is a snapshot that was never fetched rather than one that is corrupt.
    """


@dataclass(frozen=True)
class Snapshot:
    """One raw capture, read back and joined.

    Attributes:
        directory: The snapshot directory.
        snapshot_date: Maximum ``Date of Final Decision`` in the list, which is
            what the directory is named for.
        devices: One row per device, in the enriched schema.
        classifications: Product code to the fields ``source.yaml`` keeps.
        codes_without_record: Distinct codes in the list that openFDA had no
            record for. Reported, never silently dropped.
        device_csv_sha256: Digest of ``devices.csv`` as read back, which is what
            a run manifest records as its input.
        n_device_rows: Rows read.
        manifest: ``manifest.json`` as written by :mod:`clinops.fetch`.
    """

    directory: Path
    snapshot_date: date
    devices: pd.DataFrame
    classifications: dict[str, dict[str, Any]]
    codes_without_record: tuple[str, ...]
    device_csv_sha256: str
    n_device_rows: int
    manifest: dict[str, Any] = field(default_factory=dict, repr=False)


def latest_snapshot(raw_root: str | Path = DEFAULT_RAW_ROOT) -> Path:
    """Return the newest finished snapshot under ``raw_root``.

    "Newest" is by directory name, which is the snapshot date, so a re-pull of
    an older list does not become the default input. Only directories holding a
    ``manifest.json`` count: a manifest is written last, so its presence is what
    makes a directory finished.

    Raises:
        SnapshotError: There is no finished snapshot.
    """
    raw_root = Path(raw_root)
    finished = sorted(
        (path for path in raw_root.glob("*") if (path / MANIFEST_FILE).exists()),
        key=lambda path: path.name,
    )
    if not finished:
        raise SnapshotError(
            f"No finished snapshot under {raw_root}. A finished one holds "
            f"{MANIFEST_FILE}. Run: python -m clinops.fetch --config config/source.yaml"
        )
    return finished[-1]


def read_classifications(
    directory: Path, source: SourceConfig
) -> dict[str, dict[str, Any]]:
    """Read every ``classification_*.json`` in a snapshot into one lookup table.

    Only the fields ``classification_lookup.fields`` names are kept. The rest of
    each record -- the registration, FEI and K numbers openFDA attaches, which
    are most of its bulk -- is discarded here and preserved in the raw file.

    Raises:
        SnapshotError: A batch file is not readable as openFDA JSON.
    """
    wanted = source.classification_lookup.fields
    records: dict[str, dict[str, Any]] = {}
    paths = sorted(directory.glob(f"{CLASSIFICATION_PREFIX}*.json"))
    if not paths:
        raise SnapshotError(
            f"{directory} holds no {CLASSIFICATION_PREFIX}*.json files. Without the "
            "classification records no product code can be resolved. Re-run "
            "clinops.fetch."
        )
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SnapshotError(f"{path} is not readable as JSON: {exc}") from exc
        for record in payload.get("results") or []:
            code = str(record.get("product_code", "")).strip()
            if not code:
                continue
            # openFDA returns "" rather than null for an absent regulation
            # number or definition. Normalising to None keeps the "no value"
            # case from reading as a value in the report and the tables.
            kept: dict[str, Any] = {}
            for key in wanted:
                value = record.get(key)
                kept[key] = (value.strip() or None) if isinstance(value, str) else value
            records[code] = kept
    log.info("Read %d classification record(s) from %d file(s)", len(records), len(paths))
    return records


def read_devices(directory: Path, source: SourceConfig) -> tuple[pd.DataFrame, str]:
    """Read and validate ``devices.csv``, returning the frame and its digest.

    The column contract is applied here as it was at fetch time, so a snapshot
    edited by hand after capture fails the same way a drifted download does.
    """
    path = directory / DEVICE_LIST_FILE
    if not path.exists():
        raise SnapshotError(
            f"{path} is missing. {directory} is not a usable snapshot; re-run "
            "clinops.fetch."
        )
    content = path.read_bytes()
    frame = normalise_columns(read_device_frame(content), source)
    return frame, file_digest(path)


def derive_fields(frame: pd.DataFrame, source: SourceConfig) -> pd.DataFrame:
    """Add the three fields the FDA list implies but does not state.

    ``decision_date``
        ``Date of Final Decision`` as an ISO date. FDA writes ``MM/DD/YYYY``.
    ``year``
        Calendar year of that date. The figure's time axis.
    ``pathway``
        Read from the submission number's prefix, per ``source.yaml``. FDA
        publishes no pathway column, but the prefix is unambiguous and stable,
        and a supplement keeps its parent's prefix, so ``P140011/S008`` is a PMA.
        A number matching no configured prefix gets an empty string, which
        :mod:`clinops.classify` treats as an exclusion rather than a default.
    """
    frame = frame.rename(columns=COLUMN_RENAMES).copy()
    for column in ("submission_number", "device", "company", "panel_lead", "product_code"):
        frame[column] = frame[column].fillna("").astype(str).str.strip()

    parsed = pd.to_datetime(
        frame["Date of Final Decision"], format=DECISION_DATE_FORMAT, errors="coerce"
    )
    frame["decision_date"] = parsed.dt.strftime("%Y-%m-%d").fillna("")
    frame["year"] = parsed.dt.year.astype("Int64")
    frame = frame.drop(columns=["Date of Final Decision"])

    frame["pathway"] = [
        source.pathway_of(number) or "" for number in frame["submission_number"]
    ]
    unknown = frame.loc[frame["pathway"] == "", "submission_number"]
    if len(unknown):
        log.warning(
            "%d submission number(s) match no pathway prefix in %s: %s. They cannot be "
            "given a marketing pathway and will be excluded.",
            len(unknown), source.path, ", ".join(sorted(unknown.unique())[:10]),
        )
    return frame


def attach_classifications(
    frame: pd.DataFrame, classifications: dict[str, dict[str, Any]], source: SourceConfig
) -> pd.DataFrame:
    """Attach each row's classification record under the ``openfda_`` prefix.

    The prefix is not decoration. ``regulation_number`` appears in both the
    config and the lookup and the two can disagree -- code NMN is the case that
    proves it -- so a column that came from openFDA must never be readable as
    something FDA's own list asserted.
    """
    frame = frame.copy()
    for field_name in source.classification_lookup.fields:
        frame[f"{OPENFDA_PREFIX}{field_name}"] = [
            classifications.get(code, {}).get(field_name)
            for code in frame["product_code"]
        ]
    frame["has_classification"] = frame["product_code"].isin(classifications)
    return frame


def load_snapshot(
    directory: str | Path | None = None,
    source: SourceConfig | None = None,
    *,
    config_path: str | Path = Path("config/source.yaml"),
    raw_root: str | Path = DEFAULT_RAW_ROOT,
) -> Snapshot:
    """Read one snapshot and return it joined and ready to classify.

    Args:
        directory: The snapshot to read. ``None`` takes the newest finished one
            under ``raw_root``.
        source: A loaded ``source.yaml``. ``None`` loads ``config_path``.
        config_path: Where to load ``source.yaml`` from when ``source`` is None.
        raw_root: Where snapshots live.

    Returns:
        The joined snapshot.

    Raises:
        SnapshotError: The snapshot is missing or incomplete.
        clinops.fetch.SchemaError: Its columns are not the required set.
        ConfigError: ``source.yaml`` is unusable.
    """
    source = source if source is not None else load_source_config(config_path)
    directory = Path(directory) if directory is not None else latest_snapshot(raw_root)
    if not directory.is_dir():
        raise SnapshotError(f"{directory} is not a directory.")

    manifest_path = directory / MANIFEST_FILE
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        log.warning(
            "%s has no %s, so it is an unfinished or hand-assembled snapshot. Reading "
            "it anyway; its provenance will be thinner in the run manifest.",
            directory, MANIFEST_FILE,
        )

    raw, csv_sha256 = read_devices(directory, source)
    classifications = read_classifications(directory, source)
    frame = attach_classifications(derive_fields(raw, source), classifications, source)

    present = set(frame["product_code"]) - {""}
    missing = tuple(sorted(present - set(classifications)))
    if missing:
        log.warning(
            "%d product code(s) in the list have no openFDA record: %s",
            len(missing), ", ".join(missing),
        )

    stamp = manifest.get("snapshot_date")
    if stamp:
        snapshot_date = date.fromisoformat(str(stamp))
    else:
        snapshot_date = date.fromisoformat(max(frame.loc[frame["decision_date"] != "", "decision_date"]))

    log.info("Snapshot %s: %d device rows, %d distinct product codes, %d classified",
             directory, len(frame), len(present), len(present) - len(missing))
    return Snapshot(
        directory=directory,
        snapshot_date=snapshot_date,
        devices=frame,
        classifications=classifications,
        codes_without_record=missing,
        device_csv_sha256=csv_sha256,
        n_device_rows=len(frame),
        manifest=manifest,
    )


def build_parser() -> argparse.ArgumentParser:
    """Define the command line."""
    parser = argparse.ArgumentParser(
        prog="python -m clinops.enrich",
        description=(
            "Join each device row in a raw snapshot to its product code's openFDA "
            "classification record, and derive decision date, year, and marketing "
            "pathway."
        ),
        epilog=(
            "This stage makes no oncology judgment; it only resolves what each "
            "product code is. Run it on its own to inspect the join -- which codes "
            "openFDA had no record for, and what its regulation definitions say -- "
            "before clinops.classify applies the rule in oncology_codes.yaml. "
            "clinops.classify performs this join itself, so running this stage is "
            "never required."
        ),
    )
    parser.add_argument("--snapshot", type=Path, default=None,
                        help="Snapshot directory. Default: the newest finished one "
                             "under --raw-root.")
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT,
                        help=f"Where snapshots live. Default: {DEFAULT_RAW_ROOT}.")
    parser.add_argument("--config", type=Path, default=Path("config/source.yaml"),
                        help="Path to source.yaml. Default: config/source.yaml.")
    parser.add_argument("--output", type=Path, default=None,
                        help="Write the joined table here as CSV. Default: print a "
                             "summary and write nothing.")
    parser.add_argument("--version", action="version", version=f"clinops {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Join one snapshot from the command line. Returns a process exit status."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    try:
        source = load_source_config(args.config)
        snapshot = load_snapshot(args.snapshot, source, raw_root=args.raw_root)
    except (ConfigError, SnapshotError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    frame = snapshot.devices
    print(f"snapshot          : {snapshot.directory}")
    print(f"snapshot_date     : {snapshot.snapshot_date}")
    print(f"device rows       : {len(frame):,}")
    print(f"distinct codes    : {frame['product_code'].nunique():,}")
    print(f"codes unresolved  : {len(snapshot.codes_without_record)}"
          + (f" ({', '.join(snapshot.codes_without_record)})"
             if snapshot.codes_without_record else ""))
    print(f"rows unresolved   : {int((~frame['has_classification']).sum()):,}")
    print(f"pathway unknown   : {int((frame['pathway'] == '').sum()):,}")
    print()
    print("panel (lead), top 10:")
    for panel, count in frame["panel_lead"].value_counts().head(10).items():
        print(f"  {panel:<32}{count:>7,}")

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.output, index=False)
        print(f"\nwrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
