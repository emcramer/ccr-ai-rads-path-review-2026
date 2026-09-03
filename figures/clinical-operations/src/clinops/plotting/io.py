"""Read and validate the three processed tables that the figure is drawn from.

The plotting code trusts nothing. Every table is checked against the schema in
``docs/figure-spec.md`` before a single artist is created, and a table that fails
raises :class:`SchemaError` naming the file, the column, and the problem. A
figure drawn from a malformed table is worse than no figure, because it looks
finished.

All three tables are read with ``comment="#"``: the pipeline writes a provenance
header into each file, and a reader that choked on it would make the tables
harder to audit, which is the opposite of the point.

Beyond the per-table schema there are three **cross-table** checks, because this
figure quotes the same quantity in two panels and in the run summary. Panel A's
last cumulative point, Panel B's ``n = …``, and the summary's per-category
totals must all be the same number, or the figure states two different facts
about one snapshot. See :func:`_check_cross_table`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import CATEGORY_DOMAIN, CATEGORY_ORDER, DOMAIN_ORDER, PATHWAY_ORDER

#: Files read from the input directory.
CUMULATIVE_BY_YEAR = "cumulative_by_year.csv"
PATHWAY_BY_DOMAIN = "pathway_by_domain.csv"
AUTHORIZATIONS = "authorizations.csv"

_CUMULATIVE_COLUMNS = ("year", "category", "domain", "annual_count", "cumulative_count")
_PATHWAY_COLUMNS = ("domain", "category", "pathway", "count")
_AUTHORIZATION_COLUMNS = (
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

#: Earliest year the schema will accept. FDA's first AI authorization on the
#: list is 1995; anything before 1980 is a parsing accident, not a device.
_MIN_YEAR = 1980


class SchemaError(ValueError):
    """An input table is missing, unreadable, or does not match the figure schema."""


@dataclass(frozen=True)
class FigureData:
    """The validated tables the figure is drawn from.

    Attributes:
        cumulative: One row per year and category, dense, zeros filled.
        pathways: One row per category and marketing pathway.
        authorizations: One row per authorization.
        source: The directory the tables were read from.
    """

    cumulative: pd.DataFrame
    pathways: pd.DataFrame
    authorizations: pd.DataFrame
    source: Path

    @property
    def years(self) -> list[int]:
        """Every year in the cumulative table, ascending."""
        return sorted(int(year) for year in self.cumulative["year"].unique())

    @property
    def snapshot_date(self) -> str:
        """The latest decision date in the authorization table, as ISO text."""
        return str(self.authorizations["decision_date"].max().date())

    def category_total(self, category: str) -> int:
        """Authorizations in one category, from its last cumulative point."""
        rows = self.cumulative.loc[self.cumulative["category"] == category]
        if rows.empty:
            return 0
        return int(rows.sort_values("year")["cumulative_count"].iloc[-1])

    def domain_total(self, domain: str) -> int:
        """Authorizations in one domain, summed over its categories."""
        return sum(
            self.category_total(category)
            for category in CATEGORY_ORDER
            if CATEGORY_DOMAIN[category] == domain
        )


def _read_csv(path: Path, required: tuple[str, ...]) -> pd.DataFrame:
    """Read one CSV and confirm the required columns are present.

    Lines beginning with ``#`` are treated as comments, so the provenance header
    the pipeline writes into each table does not break the reader.
    """
    if not path.exists():
        raise SchemaError(f"{path}: required input table is missing")
    try:
        frame = pd.read_csv(path, comment="#")
    except Exception as exc:  # pragma: no cover - pandas' message is the useful part
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
    frame: pd.DataFrame, column: str, allowed: tuple[str, ...], path: Path
) -> None:
    """Raise if ``column`` holds a value outside the canonical vocabulary."""
    unknown = sorted(set(frame[column].astype(str)) - set(allowed))
    if unknown:
        raise SchemaError(
            f"{path}: column '{column}' holds unknown value(s): {', '.join(unknown[:5])}; "
            f"the vocabulary is {', '.join(allowed)}"
        )


def _check_domain_agrees(frame: pd.DataFrame, path: Path) -> None:
    """Raise if a row's ``domain`` is not the domain its ``category`` belongs to.

    Checked rather than derived. The two columns are redundant by design -- the
    tables are meant to be readable on their own -- and redundancy that is never
    checked is how two files come to disagree.
    """
    expected = frame["category"].astype(str).map(CATEGORY_DOMAIN)
    wrong = frame.loc[expected != frame["domain"].astype(str)]
    if len(wrong):
        row = wrong.iloc[0]
        raise SchemaError(
            f"{path}: column 'domain' disagrees with 'category'; "
            f"category {row['category']!r} belongs to domain "
            f"{CATEGORY_DOMAIN.get(str(row['category']))!r} but the row says "
            f"{row['domain']!r} ({len(wrong)} row(s) affected)"
        )


def load_cumulative_by_year(path: Path) -> pd.DataFrame:
    """Load and validate ``cumulative_by_year.csv``.

    Checks the schema, then the two properties the panel depends on and cannot
    recover from: that the year grid is dense for every category, and that
    ``cumulative_count`` really is the running sum of ``annual_count``. Panel A
    draws the cumulative column; if it were merely *labelled* cumulative, the
    panel would be a picture of nothing in particular.
    """
    frame = _read_csv(path, _CUMULATIVE_COLUMNS)
    frame = frame.loc[:, list(_CUMULATIVE_COLUMNS)].copy()
    _check_membership(frame, "category", CATEGORY_ORDER, path)
    _check_membership(frame, "domain", DOMAIN_ORDER, path)
    _check_domain_agrees(frame, path)
    _as_int(frame, "year", path, minimum=_MIN_YEAR)
    _as_int(frame, "annual_count", path, minimum=0)
    _as_int(frame, "cumulative_count", path, minimum=0)

    duplicated = frame.duplicated(subset=["year", "category"])
    if duplicated.any():
        offender = frame.loc[duplicated].iloc[0]
        raise SchemaError(
            f"{path}: repeated (year, category) row for "
            f"{offender['year']} / {offender['category']}"
        )

    years = range(int(frame["year"].min()), int(frame["year"].max()) + 1)
    for category, rows in frame.groupby("category", sort=False):
        ordered = rows.sort_values("year")
        missing = sorted(set(years) - set(ordered["year"].tolist()))
        if missing:
            raise SchemaError(
                f"{path}: column 'year' is not dense for category {category!r}; "
                f"{len(missing)} year(s) absent, first is {missing[0]}. Every "
                "(year, category) pair from the first to the last year must be "
                "present with zeros filled."
            )
        running = ordered["annual_count"].cumsum()
        mismatch = ordered.loc[running != ordered["cumulative_count"]]
        if len(mismatch):
            row = mismatch.iloc[0]
            expected = int(running.loc[mismatch.index[0]])
            raise SchemaError(
                f"{path}: column 'cumulative_count' is not the running sum of "
                f"'annual_count' for category {category!r}; in {int(row['year'])} the "
                f"table says {int(row['cumulative_count'])} and the running sum is "
                f"{expected} ({len(mismatch)} year(s) affected)"
            )
    return frame


def load_pathway_by_domain(path: Path) -> pd.DataFrame:
    """Load and validate ``pathway_by_domain.csv``."""
    frame = _read_csv(path, _PATHWAY_COLUMNS)
    frame = frame.loc[:, list(_PATHWAY_COLUMNS)].copy()
    _check_membership(frame, "category", CATEGORY_ORDER, path)
    _check_membership(frame, "domain", DOMAIN_ORDER, path)
    _check_membership(frame, "pathway", PATHWAY_ORDER, path)
    _check_domain_agrees(frame, path)
    _as_int(frame, "count", path, minimum=0)

    duplicated = frame.duplicated(subset=["category", "pathway"])
    if duplicated.any():
        offender = frame.loc[duplicated].iloc[0]
        raise SchemaError(
            f"{path}: repeated (category, pathway) row for "
            f"{offender['category']} / {offender['pathway']}"
        )
    if int(frame["count"].sum()) == 0:
        raise SchemaError(f"{path}: column 'count' is zero in every row")
    return frame


def load_authorizations(path: Path) -> pd.DataFrame:
    """Load and validate ``authorizations.csv``.

    Validated in full even though only the pathology rows are drawn. A detail
    table that disagrees with the aggregates is a broken pipeline whether or not
    this figure happens to draw the disagreeing column, and the cheapest place to
    find that out is here.

    ``decision_date`` is returned parsed, so Panel A can order the pathology
    devices by date rather than by year and by luck.
    """
    frame = _read_csv(path, _AUTHORIZATION_COLUMNS)
    frame = frame.loc[:, list(_AUTHORIZATION_COLUMNS)].copy()
    _check_membership(frame, "category", CATEGORY_ORDER, path)
    _check_membership(frame, "domain", DOMAIN_ORDER, path)
    _check_membership(frame, "pathway", PATHWAY_ORDER, path)
    _check_domain_agrees(frame, path)
    _as_int(frame, "year", path, minimum=_MIN_YEAR)

    blank = frame.loc[frame["submission_number"].isna() | (frame["device"].isna())]
    if len(blank):
        raise SchemaError(
            f"{path}: columns 'submission_number' and 'device' may not be blank; "
            f"{len(blank)} row(s) are"
        )
    duplicated = frame.loc[frame["submission_number"].duplicated()]
    if len(duplicated):
        raise SchemaError(
            f"{path}: column 'submission_number' must be unique; "
            f"{duplicated.iloc[0]['submission_number']!r} appears more than once"
        )

    parsed = pd.to_datetime(frame["decision_date"], errors="coerce", format="ISO8601")
    bad = frame.loc[parsed.isna(), "decision_date"]
    if len(bad):
        raise SchemaError(
            f"{path}: column 'decision_date' must be an ISO date; "
            f"{len(bad)} value(s) are not, first is {bad.iloc[0]!r}"
        )
    frame["decision_date"] = parsed
    off_year = frame.loc[parsed.dt.year != frame["year"]]
    if len(off_year):
        row = off_year.iloc[0]
        raise SchemaError(
            f"{path}: column 'year' disagrees with 'decision_date' for submission "
            f"{row['submission_number']!r}: {int(row['year'])} against "
            f"{row['decision_date'].date()} ({len(off_year)} row(s) affected)"
        )
    return frame


def _check_cross_table(
    cumulative: pd.DataFrame,
    pathways: pd.DataFrame,
    authorizations: pd.DataFrame,
    source: Path,
) -> None:
    """Confirm the three tables describe the same snapshot.

    Panel A's last cumulative point, Panel B's ``n = …`` and the summary's
    per-category totals are the same quantity counted three ways. If they
    disagree, the figure makes two different claims about one snapshot, and does
    it in type, which is the failure this whole project keeps guarding against.

    Raises:
        SchemaError: Naming both files involved in a disagreement.
    """
    counted = authorizations.groupby(["category", "year"], sort=False).size()
    for (category, year), rows in counted.items():
        stated = cumulative.loc[
            (cumulative["category"] == category) & (cumulative["year"] == year),
            "annual_count",
        ]
        expected = int(stated.iloc[0]) if len(stated) else 0
        if rows != expected:
            raise SchemaError(
                f"{source / AUTHORIZATIONS} and {source / CUMULATIVE_BY_YEAR} disagree: "
                f"category {category!r} in {year} has {rows} authorization row(s) but "
                f"'annual_count' says {expected}"
            )
    stated_total = int(cumulative["annual_count"].sum())
    if len(authorizations) != stated_total:
        raise SchemaError(
            f"{source / AUTHORIZATIONS} and {source / CUMULATIVE_BY_YEAR} disagree: "
            f"{len(authorizations)} authorization row(s) against {stated_total} counted "
            "by 'annual_count'"
        )

    by_pathway = authorizations.groupby(["category", "pathway"], sort=False).size()
    for category in CATEGORY_ORDER:
        for pathway in PATHWAY_ORDER:
            rows = int(by_pathway.get((category, pathway), 0))
            stated = pathways.loc[
                (pathways["category"] == category) & (pathways["pathway"] == pathway), "count"
            ]
            expected = int(stated.iloc[0]) if len(stated) else 0
            if rows != expected:
                raise SchemaError(
                    f"{source / AUTHORIZATIONS} and {source / PATHWAY_BY_DOMAIN} disagree: "
                    f"category {category!r} pathway {pathway!r} has {rows} authorization "
                    f"row(s) but 'count' says {expected}"
                )

    for category in CATEGORY_ORDER:
        rows = cumulative.loc[cumulative["category"] == category].sort_values("year")
        if rows.empty:
            continue
        final = int(rows["cumulative_count"].iloc[-1])
        stated = int(pathways.loc[pathways["category"] == category, "count"].sum())
        if final != stated:
            raise SchemaError(
                f"{source / PATHWAY_BY_DOMAIN} and {source / CUMULATIVE_BY_YEAR} disagree: "
                f"category {category!r} totals {stated} across pathways but its final "
                f"'cumulative_count' is {final}"
            )


def load_figure_data(directory: str | Path) -> FigureData:
    """Read every table in ``directory`` and return the validated set.

    Args:
        directory: Directory holding the three processed CSVs.

    Returns:
        A :class:`FigureData` holding the validated tables.

    Raises:
        SchemaError: If the directory or any table is missing, malformed, or
            disagrees with another table.
    """
    source = Path(directory)
    if not source.is_dir():
        raise SchemaError(f"{source}: input directory does not exist")
    cumulative = load_cumulative_by_year(source / CUMULATIVE_BY_YEAR)
    pathways = load_pathway_by_domain(source / PATHWAY_BY_DOMAIN)
    authorizations = load_authorizations(source / AUTHORIZATIONS)
    _check_cross_table(cumulative, pathways, authorizations, source)
    return FigureData(
        cumulative=cumulative,
        pathways=pathways,
        authorizations=authorizations,
        source=source,
    )
