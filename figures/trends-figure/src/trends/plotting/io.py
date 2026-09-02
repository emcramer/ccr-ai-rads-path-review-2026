"""Read and validate the three processed tables that the figure is drawn from.

The plotting code trusts nothing. Every table is checked against the schema in
``docs/figure-spec.md`` before a single artist is created, and a table that fails
raises :class:`SchemaError` naming the file, the column, and the problem. A
figure drawn from a malformed table is worse than no figure, because it looks
finished.

Only ``combination_counts.csv`` and ``theme_year_counts.csv`` are needed to
draw. ``paper_labels.csv`` is read when present, checked, and used only for the
corpus size quoted in the run summary; the panels never touch it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import style

#: Files read from the input directory.
COMBINATION_COUNTS = "combination_counts.csv"
THEME_YEAR_COUNTS = "theme_year_counts.csv"
PAPER_LABELS = "paper_labels.csv"

_COMBINATION_COLUMNS = ("theme", "modality_set", "n_modalities", "n_papers", "rank_in_theme")
_THEME_YEAR_COLUMNS = ("theme", "domain", "year", "n_papers", "partial_year")


class SchemaError(ValueError):
    """An input table is missing, unreadable, or does not match the figure schema."""


@dataclass(frozen=True)
class FigureData:
    """The validated tables the figure is drawn from.

    Attributes:
        combinations: One row per theme and observed modality combination.
        theme_years: One row per theme, domain, and year.
        papers: ``paper_labels.csv`` if it was present, else ``None``.
        source: The directory the tables were read from.
    """

    combinations: pd.DataFrame
    theme_years: pd.DataFrame
    papers: pd.DataFrame | None
    source: Path

    @property
    def n_papers_total(self) -> int | None:
        """Corpus size, or ``None`` when ``paper_labels.csv`` was absent."""
        return None if self.papers is None else int(len(self.papers))


def _read_csv(path: Path, required: tuple[str, ...]) -> pd.DataFrame:
    """Read one CSV and confirm the required columns are present.

    Lines beginning with ``#`` are treated as comments so a generated table can
    carry a provenance header without breaking the reader.
    """
    if not path.exists():
        raise SchemaError(f"{path}: required input table is missing")
    try:
        frame = pd.read_csv(path, comment="#")
    except Exception as exc:  # pragma: no cover - pandas message is the useful part
        raise SchemaError(f"{path}: could not be parsed as CSV ({exc})") from exc
    if frame.empty:
        raise SchemaError(f"{path}: table has no rows")
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise SchemaError(f"{path}: missing required column(s): {', '.join(missing)}")
    return frame


def _as_int(frame: pd.DataFrame, column: str, path: Path, *, minimum: int | None = None) -> None:
    """Coerce ``column`` to integer in place, raising if a value will not convert."""
    coerced = pd.to_numeric(frame[column], errors="coerce")
    bad = frame.loc[coerced.isna(), column]
    if len(bad):
        raise SchemaError(
            f"{path}: column '{column}' must be integer; "
            f"{len(bad)} value(s) are not, first is {bad.iloc[0]!r}"
        )
    if (coerced % 1 != 0).any():
        raise SchemaError(f"{path}: column '{column}' must be whole numbers, not fractions")
    if minimum is not None and (coerced < minimum).any():
        offender = coerced[coerced < minimum].iloc[0]
        raise SchemaError(f"{path}: column '{column}' must be >= {minimum}; found {offender}")
    frame[column] = coerced.astype("int64")


def _check_membership(
    frame: pd.DataFrame, column: str, allowed: frozenset[str] | set[str], path: Path
) -> None:
    """Raise if ``column`` holds a value outside the canonical vocabulary."""
    values = frame[column].astype(str)
    unknown = sorted(set(values) - set(allowed))
    if unknown:
        raise SchemaError(
            f"{path}: column '{column}' holds unknown value(s): {', '.join(unknown[:5])}"
        )


def load_combination_counts(path: Path) -> pd.DataFrame:
    """Load and validate ``combination_counts.csv``."""
    frame = _read_csv(path, _COMBINATION_COLUMNS)
    frame = frame.loc[:, list(_COMBINATION_COLUMNS)].copy()
    if frame[["theme", "modality_set"]].isna().any().any():
        raise SchemaError(f"{path}: 'theme' and 'modality_set' may not be blank")
    _check_membership(frame, "theme", set(style.THEME_ORDER), path)
    _as_int(frame, "n_modalities", path, minimum=1)
    _as_int(frame, "n_papers", path, minimum=0)
    _as_int(frame, "rank_in_theme", path, minimum=1)

    known = set(style.MODALITY_ORDER)
    for raw in frame["modality_set"].astype(str):
        members = [part for part in raw.split("+") if part]
        if not members:
            raise SchemaError(f"{path}: empty 'modality_set' value")
        unknown = sorted(set(members) - known)
        if unknown:
            raise SchemaError(
                f"{path}: 'modality_set' {raw!r} names unknown modality/ies: {', '.join(unknown)}"
            )

    duplicated = frame.duplicated(subset=["theme", "modality_set"])
    if duplicated.any():
        offender = frame.loc[duplicated].iloc[0]
        raise SchemaError(
            f"{path}: repeated (theme, modality_set) row for "
            f"{offender['theme']} / {offender['modality_set']}"
        )
    return frame


def load_theme_year_counts(path: Path) -> pd.DataFrame:
    """Load and validate ``theme_year_counts.csv``."""
    frame = _read_csv(path, _THEME_YEAR_COLUMNS)
    frame = frame.loc[:, list(_THEME_YEAR_COLUMNS)].copy()
    _check_membership(frame, "theme", set(style.THEME_ORDER), path)
    _check_membership(frame, "domain", style.DOMAIN_VALUES, path)
    _as_int(frame, "year", path, minimum=1800)
    _as_int(frame, "n_papers", path, minimum=0)
    _as_int(frame, "partial_year", path, minimum=0)
    if not frame["partial_year"].isin([0, 1]).all():
        raise SchemaError(f"{path}: column 'partial_year' must be 0 or 1")

    duplicated = frame.duplicated(subset=["theme", "domain", "year"])
    if duplicated.any():
        offender = frame.loc[duplicated].iloc[0]
        raise SchemaError(
            f"{path}: repeated (theme, domain, year) row for "
            f"{offender['theme']} / {offender['domain']} / {offender['year']}"
        )

    flagged = frame.loc[frame["partial_year"] == 1, "year"].unique()
    if len(flagged) > 1:
        raise SchemaError(
            f"{path}: more than one year is flagged partial: {sorted(flagged)}"
        )
    return frame


def load_paper_labels(path: Path) -> pd.DataFrame:
    """Load and validate ``paper_labels.csv``.

    Checked for completeness even though the panels do not read it, so that a
    broken corpus table is caught here rather than downstream.
    """
    required = ("pmid", "year", "year_source", "domain") + tuple(
        f"theme_{key}" for key in style.THEME_ORDER
    ) + tuple(f"mod_{key}" for key in style.MODALITY_ORDER)
    frame = _read_csv(path, required)
    _as_int(frame, "year", path, minimum=1800)
    for key in style.THEME_ORDER:
        _as_int(frame, f"theme_{key}", path, minimum=0)
    for key in style.MODALITY_ORDER:
        _as_int(frame, f"mod_{key}", path, minimum=0)
    _check_membership(frame, "domain", {"radiology", "pathology", "both", "none"}, path)
    if frame["pmid"].duplicated().any():
        raise SchemaError(f"{path}: 'pmid' must be unique")
    return frame


def load_figure_data(directory: str | Path) -> FigureData:
    """Read every table in ``directory`` and return the validated set.

    Args:
        directory: Directory holding the three processed CSVs.

    Returns:
        A :class:`FigureData` holding the validated tables.

    Raises:
        SchemaError: If the directory or any required table is missing or malformed.
    """
    source = Path(directory)
    if not source.is_dir():
        raise SchemaError(f"{source}: input directory does not exist")
    combinations = load_combination_counts(source / COMBINATION_COUNTS)
    theme_years = load_theme_year_counts(source / THEME_YEAR_COUNTS)
    papers_path = source / PAPER_LABELS
    papers = load_paper_labels(papers_path) if papers_path.exists() else None
    return FigureData(
        combinations=combinations, theme_years=theme_years, papers=papers, source=source
    )
