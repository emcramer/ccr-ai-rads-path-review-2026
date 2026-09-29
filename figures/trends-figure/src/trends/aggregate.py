"""Turn per-paper labels into the three tables the figure is drawn from.

:mod:`trends.classify` produces one labelled row per paper. This module reduces
those rows to ``paper_labels.csv``, ``combination_counts.csv``, and
``theme_year_counts.csv``, exactly to the schemas fixed in
``docs/figure-spec.md``, and writes them with a provenance header.

It owns the canonical keys and the output column order, so the schema is
declared in one place. It classifies nothing and reads no configuration.

Two properties the tests hold it to:

* Within a theme, the combination counts sum to that theme's paper count in
  Panel A's view. Every paper carries at least one modality, because a paper
  matching none is given ``other``, so every paper falls in exactly one column of
  its theme's block. Panel A then leaves out the papers whose ``other`` came from
  that fallback alone; see :data:`MODALITY_DETERMINED`.
* The two output tables draw on **different populations**, per the author's ruling
  of 2026-09-08 and the "two panels draw on different populations" section of
  ``docs/figure-spec.md``. ``combination_counts.csv``, which Panel A reads, is
  built from primary research only: Panel A asks what data primary research
  actually uses, and a review discussing a modality without using one would
  corrupt it. ``theme_year_counts.csv``, which Panel B reads, is built from every
  retained record including reviews and editorials: Panel B asks how attention to
  a theme moves over time, and a review naming a theme is evidence of attention.
  The two therefore have different denominators and **no number from one may be
  quoted against the other**.
* ``theme_year_counts.csv`` carries the full domain breakdown of every theme,
  and the four domain rows partition it: ``radiology + pathology + both + none``
  equals ``all``. ``radiology + pathology`` alone does not, because a
  cross-specialty paper sits in ``both`` rather than in each side.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final, Iterable, Sequence

import pandas as pd

# --------------------------------------------------------------------------
# Canonical keys, from the "Canonical keys" section of docs/figure-spec.md.
# trends.plotting.style holds the same lists for the drawing code; a test keeps
# the two equal.
# --------------------------------------------------------------------------

#: Theme keys, in figure block order.
THEME_KEYS: Final[tuple[str, ...]] = (
    "foundation_models",
    "multimodal_integration",
    "digital_twins",
    "clinical_fda",
    "virtual_staining",
    "agentic_ai",
)

#: Modality keys, in figure row order: pathology, then radiology, then the
#: non-imaging data types, then ``other``.
MODALITY_KEYS: Final[tuple[str, ...]] = (
    "he_histology",
    "ihc",
    "spatial_proteomics",
    "spatial_transcriptomics",
    "pathology_report",
    "mri",
    "ct",
    "pet",
    "ultrasound",
    "mammography",
    "xray",
    "radiology_report",
    "genomics",
    "clinical_data",
    "other",
)

#: The catch-all modality. Additive: a paper carries it when an ``other``
#: include pattern matched, when no named modality matched, or both.
OTHER_MODALITY: Final[str] = "other"

#: Minimum modality labels a theme requires **for Panel A's view**, by theme key.
#:
#: Some themes are defined by combination: a multimodal model has, by definition,
#: at least two modalities in its training. A paper carrying the theme and one
#: modality label is a term match, not a multimodal study.
#:
#: This is a condition on Panel A's **view**, not on the label. The predicate is
#: derived from what a multimodal *model* is — it used two modalities while being
#: built — and that applies to a study that built something. It does not apply to
#: a review, which uses no modalities at all. Enforcing it on the label would drop
#: reviews that genuinely discuss multimodal integration because their abstract
#: happens to name one modality, which for an engagement measure is a category
#: error, and would re-open the conflict the panel split resolved. Author's
#: wording, 2026-09-09: "none of the papers classified as primary research in
#: multimodal integration should have only one modality."
#:
#: ``other`` counts toward the minimum — CT plus a liquid biopsy is a genuine
#: pairing. ``non_specialty`` cannot, because it is never a label at all.
#:
#: The coupling this creates is worth understanding before adding an entry: a
#: theme here is no longer decided by its own dictionary alone, because a modality
#: the classifier misses can push a genuinely multimodal paper below the minimum.
#: That is why two counts are always reported side by side; see
#: :func:`minimum_modality_shortfalls`.
MINIMUM_MODALITIES: Final[dict[str, int]] = {"multimodal_integration": 2}

#: Name of the flag that separates the two panels' populations: 1 for a primary
#: research article, 0 for a review, editorial, comment, letter, meta-analysis or
#: other secondary publication type. Both are retained; only Panel A filters.
PRIMARY_RESEARCH: Final[str] = "is_primary_research"

#: Name of the flag that marks whether a paper's modality could be determined: 0
#: when ``other`` was assigned only by the fallback, meaning no named modality and
#: no ``other`` pattern matched, and 1 otherwise. Panel A excludes the 0s; Panel B
#: reads every row. Those papers are mostly reviews and decision-support studies
#: that say "imaging" without naming a kind, so drawing them as "Other" read as an
#: exotic modality they do not have. Author's ruling, 2026-09-29.
MODALITY_DETERMINED: Final[str] = "modality_determined"

#: The ``domain`` values emitted for every theme, in the order they are written.
#:
#: ``all`` is the theme total. The other four are the values of the ``domain``
#: column of ``paper_labels.csv``, so each paper falls in exactly one of them and
#: ``radiology + pathology + both + none == all``. ``radiology`` therefore means
#: "radiologic and not pathologic": a paper touching both sides is in ``both``,
#: not in each side. The figure displays ``both`` as "cross-specialty"; the value
#: stays ``both`` here so that this table and ``paper_labels.csv`` agree.
DOMAIN_SERIES: Final[tuple[str, ...]] = ("all", "radiology", "pathology", "both", "none")

def order_keys(keys: Iterable[str], canonical: Sequence[str]) -> tuple[str, ...]:
    """Put a dictionary's category keys into figure order.

    Keys the canonical list knows come first, in its order; keys it does not
    come after, in the order given. A term dictionary that gains a category the
    figure specification has not caught up with therefore still produces a
    usable table, with the new category at the end, rather than a crash or a
    missing column.
    """
    keys = list(keys)
    known = [key for key in canonical if key in keys]
    return tuple(known + [key for key in keys if key not in set(canonical)])


def paper_label_columns(
    theme_keys: Sequence[str] = THEME_KEYS, modality_keys: Sequence[str] = MODALITY_KEYS
) -> tuple[str, ...]:
    """Return the columns of ``paper_labels.csv`` for a given set of categories.

    The schema is a shape, not a fixed list: three identity columns, one flag per
    theme, one flag per modality, and ``domain``. Callers pass the keys of the
    dictionaries they actually loaded, so adding a modality to
    ``config/modalities.yaml`` adds its column with no code change.
    """
    return (
        ("pmid", "year", "year_source")
        + tuple(f"theme_{key}" for key in theme_keys)
        + tuple(f"mod_{key}" for key in modality_keys)
        + ("domain", PRIMARY_RESEARCH, MODALITY_DETERMINED)
    )


def theme_keys_of(labels: pd.DataFrame) -> tuple[str, ...]:
    """Return the theme keys a labels table carries, in figure order."""
    found = [c[len("theme_"):] for c in labels.columns if c.startswith("theme_")]
    return order_keys(found, THEME_KEYS)


def modality_keys_of(labels: pd.DataFrame) -> tuple[str, ...]:
    """Return the modality keys a labels table carries, in figure order.

    Every reduction in this module reads its category set from the table in
    front of it rather than from a constant. The constants below stay as the
    canonical defaults and as the thing the cross-check test compares against
    ``config/`` and ``trends.plotting.style``; they are not a list that has to be
    edited whenever the dictionary gains a row.
    """
    found = [c[len("mod_"):] for c in labels.columns if c.startswith("mod_")]
    return order_keys(found, MODALITY_KEYS)


#: Column order of ``paper_labels.csv`` for the canonical categories. Equal to
#: ``paper_label_columns()``; kept as a name the tests and the docs can point at.
PAPER_LABEL_COLUMNS: Final[tuple[str, ...]] = (
    ("pmid", "year", "year_source")
    + tuple(f"theme_{key}" for key in THEME_KEYS)
    + tuple(f"mod_{key}" for key in MODALITY_KEYS)
    + ("domain", PRIMARY_RESEARCH, MODALITY_DETERMINED)
)

#: Column order of ``combination_counts.csv``.
COMBINATION_COLUMNS: Final[tuple[str, ...]] = (
    "theme", "modality_set", "n_modalities", "n_papers", "rank_in_theme",
)

#: Column order of ``theme_year_counts.csv``.
THEME_YEAR_COLUMNS: Final[tuple[str, ...]] = (
    "theme", "domain", "year", "n_papers", "partial_year",
)

#: Column order of ``pattern_hits.csv``, the provenance table.
PATTERN_HIT_COLUMNS: Final[tuple[str, ...]] = (
    "pmid", "dictionary", "category", "role", "pattern_id", "kind",
    "case_sensitive", "pattern", "n_hits", "category_matched", "excerpt",
)

#: File names written into the output directory.
PAPER_LABELS = "paper_labels.csv"
COMBINATION_COUNTS = "combination_counts.csv"
THEME_YEAR_COUNTS = "theme_year_counts.csv"


def modality_set(row: pd.Series | dict, modality_keys: Sequence[str] = MODALITY_KEYS) -> str:
    """Return one paper's modality set as the string the figure spec asks for.

    Keys are sorted alphabetically and joined by ``+``. ``other`` alone is a
    legitimate value; a paper never has an empty set.
    """
    return "+".join(sorted(key for key in modality_keys if row[f"mod_{key}"]))


def add_modality_set(labels: pd.DataFrame) -> pd.Series:
    """Return the modality-set string for every row of a labels table.

    The modality set is read from the table's own ``mod_`` columns, so it covers
    whatever the dictionary declared.
    """
    keys = modality_keys_of(labels)
    flags = labels[[f"mod_{key}" for key in keys]].to_numpy(dtype=bool)
    order = sorted(range(len(keys)), key=lambda i: keys[i])
    return pd.Series(
        ["+".join(keys[i] for i in order if row[i]) for row in flags],
        index=labels.index,
        dtype="object",
    )


def primary_research(labels: pd.DataFrame) -> pd.DataFrame:
    """Return the primary-research subset of a labels table.

    A table without the flag is returned unchanged, so a hand-built frame in a
    test still reduces. In production the flag is always present.
    """
    if PRIMARY_RESEARCH not in labels.columns:
        return labels
    return labels.loc[labels[PRIMARY_RESEARCH].astype("int64") == 1]


def modality_determined(labels: pd.DataFrame) -> pd.DataFrame:
    """Return the papers whose modality could be determined.

    Drops the rows where ``other`` came from the fallback alone. A table without
    the flag is returned unchanged, as :func:`primary_research` does.
    """
    if MODALITY_DETERMINED not in labels.columns:
        return labels
    return labels.loc[labels[MODALITY_DETERMINED].astype("int64") == 1]


def minimum_modality_shortfalls(
    labels: pd.DataFrame,
) -> tuple[dict[str, int], dict[str, int]]:
    """Count papers falling below a theme's combination minimum, two ways.

    Both numbers matter and must be read together, because the shortfall measures
    two different things at once: how far a theme's language over-calls, and how
    far modality recall falls short. A paper predicting Ki-67 from CT is
    multimodal and reads as single-modality only because the target was not
    labelled.

    Returns:
        ``panel_a`` — primary-research papers excluded from Panel A's block for
        that theme, the removal that actually happens (papers already excluded
        as modality-not-determined are not counted again); and ``corpus_wide`` — every
        retained paper carrying the theme below the minimum, whatever its
        publication type. The second is the over-call measure and is the number
        that should fall as the theme's vocabulary is tightened.
    """
    panel_a: dict[str, int] = {}
    corpus_wide: dict[str, int] = {}
    if labels.empty:
        return panel_a, corpus_wide
    counts = labels[[f"mod_{key}" for key in modality_keys_of(labels)]].sum(axis=1)
    primary = (
        labels[PRIMARY_RESEARCH].astype("int64") == 1
        if PRIMARY_RESEARCH in labels.columns
        else pd.Series(True, index=labels.index)
    )
    # A paper whose modality was not determined is already out of Panel A, and
    # is reported under that reason; counting it here too would remove it twice.
    if MODALITY_DETERMINED in labels.columns:
        primary = primary & (labels[MODALITY_DETERMINED].astype("int64") == 1)
    for theme, minimum in MINIMUM_MODALITIES.items():
        column = f"theme_{theme}"
        if column not in labels.columns:
            continue
        short = (labels[column].astype("int64") == 1) & (counts < minimum)
        corpus_wide[theme] = int(short.sum())
        panel_a[theme] = int((short & primary).sum())
    return panel_a, corpus_wide


def build_combination_counts(
    labels: pd.DataFrame, *, primary_only: bool = True
) -> pd.DataFrame:
    """Count papers per theme and exact modality combination.

    A paper appears once in each theme it carries, in the single column for its
    exact modality set. Rows are ranked by paper count descending; ties break on
    set size ascending, then on the set string, so the ranking is reproducible.

    Panel A reads this table, so by default it applies **all three** of that
    panel's view conditions: primary research only; a determined modality only
    (see :data:`MODALITY_DETERMINED`); and, for a theme in
    :data:`MINIMUM_MODALITIES`, only papers carrying at least that many modality
    labels. The conditions belong together; a reader who finds one and not the
    others will misread the table.
    A review that discusses a modality without using one is evidence of attention,
    not of data use, and would corrupt a panel whose question is what primary
    research consumes. ``primary_only=False`` is for diagnostics that want the
    whole retained corpus; the shipped table never uses it.

    Args:
        labels: The per-paper table, in ``paper_labels.csv`` shape.
        primary_only: Restrict to Panel A's view: rows flagged
            ``is_primary_research`` and ``modality_determined``.

    Returns:
        ``combination_counts.csv`` as a frame, themes in figure block order.
    """
    if primary_only:
        labels = modality_determined(primary_research(labels))
    if labels.empty:
        return pd.DataFrame(columns=list(COMBINATION_COLUMNS))
    sets = add_modality_set(labels)
    modality_count = labels[
        [f"mod_{key}" for key in modality_keys_of(labels)]
    ].sum(axis=1)
    rows: list[dict] = []
    for theme in theme_keys_of(labels):
        in_theme = labels[f"theme_{theme}"].to_numpy(dtype=bool)
        # The second condition on Panel A's view, beside primary research: a
        # theme defined by combination admits only papers that carry its minimum.
        minimum = MINIMUM_MODALITIES.get(theme)
        if primary_only and minimum:
            in_theme = in_theme & (modality_count >= minimum).to_numpy(dtype=bool)
        counts = sets.loc[in_theme].value_counts()
        block = pd.DataFrame(
            {
                "theme": theme,
                "modality_set": counts.index.astype(str),
                "n_papers": counts.to_numpy(dtype="int64"),
            }
        )
        if block.empty:
            continue
        block["n_modalities"] = block["modality_set"].str.count(r"\+") + 1
        block = block.sort_values(
            ["n_papers", "n_modalities", "modality_set"], ascending=[False, True, True]
        ).reset_index(drop=True)
        block["rank_in_theme"] = range(1, len(block) + 1)
        rows.append(block)
    if not rows:
        return pd.DataFrame(columns=list(COMBINATION_COLUMNS))
    frame = pd.concat(rows, ignore_index=True)
    return frame.loc[:, list(COMBINATION_COLUMNS)]


def build_theme_year_counts(
    labels: pd.DataFrame,
    *,
    partial_year: int | None = None,
    years: Sequence[int] | None = None,
) -> pd.DataFrame:
    """Count papers per theme, domain, and year.

    Panel B reads this table, so it counts **every retained record**, reviews and
    editorials included. Its question is how attention to a theme moves over
    time, and a review naming a theme as a future direction is attention. This is
    the deliberate counterpart to :func:`build_combination_counts`, which counts
    primary research only; the two denominators differ and must never be quoted
    against each other.

    Every theme gets the full set of :data:`DOMAIN_SERIES`, and the figure
    chooses which rows to draw. Emitting the whole breakdown costs a few hundred
    rows and saves a schema change every time the author wants a different
    theme split.

    The four domain rows partition the theme, because each paper carries exactly
    one ``domain`` value, so ``radiology + pathology + both + none == all``.
    ``radiology`` means radiologic and *not* pathologic; a paper touching both
    sides is in ``both``. ``radiology + pathology`` alone therefore does not sum
    to the theme, which is the property the legend has to explain.

    The year axis is dense between the first and last year in the corpus, so a
    year with no papers draws as a zero rather than as a gap.

    Args:
        labels: The per-paper table.
        partial_year: The retrieval year, flagged 1 in ``partial_year``. Only
            one year may carry the flag.
        years: Override the year axis. Defaults to the range observed.

    Returns:
        ``theme_year_counts.csv`` as a frame.
    """
    if labels.empty:
        return pd.DataFrame(columns=list(THEME_YEAR_COLUMNS))
    year_values = labels["year"].astype("int64")
    axis = (
        list(years)
        if years is not None
        else list(range(int(year_values.min()), int(year_values.max()) + 1))
    )

    domain = labels["domain"].astype(str)
    series: list[tuple[str, str, pd.Series]] = []
    for theme in theme_keys_of(labels):
        in_theme = labels[f"theme_{theme}"].to_numpy(dtype=bool)
        for side in DOMAIN_SERIES:
            selected = (
                in_theme
                if side == "all"
                else in_theme & (domain == side).to_numpy(dtype=bool)
            )
            series.append((theme, side, year_values[selected]))

    rows: list[dict] = []
    for theme, side, selected_years in series:
        counts = selected_years.value_counts()
        for year in axis:
            rows.append(
                {
                    "theme": theme,
                    "domain": side,
                    "year": int(year),
                    "n_papers": int(counts.get(year, 0)),
                    "partial_year": int(partial_year is not None and year == partial_year),
                }
            )
    return pd.DataFrame(rows, columns=list(THEME_YEAR_COLUMNS))


def order_labels(labels: pd.DataFrame) -> pd.DataFrame:
    """Return the labels table in the spec's column order.

    The theme and modality columns are whichever ones the table carries, put
    into figure order; the identity columns and ``domain`` are required.

    Raises:
        KeyError: A required column is absent.
    """
    columns = paper_label_columns(theme_keys_of(labels), modality_keys_of(labels))
    missing = [column for column in columns if column not in labels.columns]
    if missing:
        raise KeyError(f"paper labels missing column(s): {', '.join(missing)}")
    return labels.loc[:, list(columns)]


def _write_csv(frame: pd.DataFrame, path: Path, header: Iterable[str]) -> Path:
    """Write one table with a commented provenance header.

    ``trends.plotting.io`` reads these files with ``comment="#"``, so the header
    travels with the data without breaking the reader.
    """
    lines = "".join(f"# {line}\n" for line in header)
    path.write_text(lines + frame.to_csv(index=False), encoding="utf-8")
    return path


def write_tables(
    labels: pd.DataFrame,
    output_dir: str | Path,
    *,
    partial_year: int | None = None,
    provenance: Iterable[str] = (),
) -> dict[str, Path]:
    """Write the three processed tables into a directory.

    Args:
        labels: The per-paper table.
        output_dir: Directory to write into; created if absent.
        partial_year: Year flagged partial in ``theme_year_counts.csv``.
        provenance: Lines written as a ``#`` header on every file: the record
            table and the dictionary versions and digests the labels came from.

    Returns:
        A mapping from table name to the path written.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    header = list(provenance)

    paths = {
        "paper_labels": _write_csv(
            order_labels(labels),
            output_dir / PAPER_LABELS,
            [f"file: {PAPER_LABELS}", *header],
        ),
        "combination_counts": _write_csv(
            build_combination_counts(labels),
            output_dir / COMBINATION_COUNTS,
            [f"file: {COMBINATION_COUNTS}", *header],
        ),
        "theme_year_counts": _write_csv(
            build_theme_year_counts(labels, partial_year=partial_year),
            output_dir / THEME_YEAR_COUNTS,
            [f"file: {THEME_YEAR_COUNTS}", *header],
        ),
    }
    return paths
