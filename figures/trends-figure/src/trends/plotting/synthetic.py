"""Generate a synthetic stand-in corpus with the schema of the real one.

The figure code had to be written and proved before the PubMed retrieval and the
classifier existed. This module invents a corpus that obeys the schema in
``docs/figure-spec.md`` exactly, and that is shaped to stress the layout in the
ways the real corpus is expected to:

* a fat tail of rare modality combinations, so the top-N cap has real work to do;
* Digital Twins with very few papers, so a near-empty block must still draw;
* heavy CT and PET co-occurrence, because most oncologic PET is acquired as PET/CT;
* mammography concentrated in the clinical theme and radiography concentrated in
  foundation-model work, since chest radiographs are the classic radiology
  pre-training corpus; both produce large single-modality bars;
* imaging paired with genomics or with clinical/EHR data inside the multimodal
  theme, because that pairing is the multimodal integration the review argues
  about and a stand-in that omits it would let a unimodal bug through unnoticed;
* ``other`` drawn additively, alongside named modalities as well as alone, per the
  matching contract in ``docs/figure-spec.md``;
* a partial final year, truncated at the 2026-09-01 retrieval date.

Everything it writes is labelled synthetic: a header comment in each CSV, a
``README.md``, and a ``MANIFEST.txt`` recording the seed. The numbers are
invented. They must never be quoted, and no conclusion may rest on them.

Run it with::

    PYTHONPATH=src python -m trends.plotting.synthetic --output data/processed/synthetic
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import style

#: Default seed. Recorded in MANIFEST.txt; change it only on purpose.
DEFAULT_SEED = 20260901

#: Years the invented corpus spans. The last is partial by construction.
FIRST_YEAR = 2015
LAST_YEAR = 2026

#: Fraction of a full year's output that the partial final year receives.
#: Retrieval on 2026-09-01 covers two thirds of the year; indexing lag takes more.
PARTIAL_YEAR_FRACTION = 0.62

#: Chance that a paper's modality set is drawn from the rare tail instead of a template.
TAIL_PROBABILITY = 0.11

#: Chance that ``other`` is added to a set that already names something. ``other``
#: is additive: it marks a data type outside the named rows and may sit beside
#: named modalities, as well as standing alone for a paper that names none. A
#: stand-in that only ever drew ``other`` alone would not exercise that.
ADDITIVE_OTHER_PROBABILITY = 0.16

_BANNER = "SYNTHETIC DATA - INVENTED NUMBERS - NOT THE REAL CORPUS"

# Modality templates per theme, as (modality keys, weight). Weights are relative.
_TEMPLATES: dict[str, list[tuple[tuple[str, ...], float]]] = {
    "foundation_models": [
        (("he_histology",), 24),
        (("ct",), 12),
        (("mri",), 12),
        (("other",), 10),
        (("radiology_report",), 8),
        (("ct", "pet"), 7),
        (("he_histology", "pathology_report"), 6),
        (("he_histology", "ihc"), 4),
        (("ct", "mri"), 4),
        (("ct", "radiology_report"), 3),
        (("he_histology", "spatial_transcriptomics"), 2),
        (("xray",), 14),
        (("radiology_report", "xray"), 6),
        (("mammography",), 3),
        (("genomics",), 5),
        (("he_histology", "genomics"), 3),
        (("clinical_data",), 3),
    ],
    "multimodal_integration": [
        (("ct", "pet"), 16),
        (("he_histology", "spatial_transcriptomics"), 12),
        (("he_histology", "pathology_report"), 10),
        (("ct", "mri"), 8),
        (("he_histology", "ihc"), 8),
        (("ct", "pet", "radiology_report"), 6),
        (("mri", "radiology_report"), 6),
        (("he_histology", "ihc", "spatial_proteomics"), 5),
        (("he_histology", "radiology_report"), 4),
        (("he_histology", "spatial_proteomics", "spatial_transcriptomics"), 4),
        (("ct", "mri", "pet"), 4),
        (("ct", "he_histology"), 4),
        (("other",), 3),
        (("radiology_report", "xray"), 7),
        (("mammography", "ultrasound"), 4),
        (("mammography",), 2),
        (("he_histology", "genomics"), 15),
        (("ct", "genomics"), 9),
        (("genomics", "clinical_data"), 8),
        (("mri", "clinical_data"), 7),
        (("he_histology", "genomics", "clinical_data"), 6),
        (("ct", "clinical_data"), 6),
        (("he_histology", "ihc", "genomics"), 4),
        (("ct", "mri", "clinical_data"), 3),
    ],
    "digital_twins": [
        (("other",), 7),
        (("ct",), 6),
        (("mri",), 5),
        (("ct", "pet"), 3),
        (("ct", "mri"), 2),
        (("he_histology",), 2),
        (("ct", "mri", "pet"), 1),
        (("xray",), 1),
        (("clinical_data",), 5),
        (("ct", "clinical_data"), 3),
        (("genomics", "clinical_data"), 2),
    ],
    "clinical_fda": [
        (("ct",), 20),
        (("mri",), 16),
        (("ct", "pet"), 12),
        (("he_histology",), 12),
        (("ultrasound",), 10),
        (("radiology_report",), 8),
        (("other",), 6),
        (("ct", "mri"), 5),
        (("he_histology", "ihc"), 4),
        (("ct", "radiology_report"), 3),
        (("pathology_report",), 3),
        (("mammography",), 14),
        (("xray",), 9),
        (("mammography", "ultrasound"), 5),
        (("clinical_data",), 4),
        (("genomics",), 2),
    ],
}

# Relative frequency of each modality when a rare tail combination is drawn.
_TAIL_WEIGHTS: dict[str, float] = {
    "he_histology": 6.0,
    "ihc": 3.0,
    "spatial_proteomics": 1.6,
    "spatial_transcriptomics": 2.0,
    "pathology_report": 2.4,
    "mri": 5.0,
    "ct": 6.0,
    "pet": 3.4,
    "ultrasound": 2.2,
    "mammography": 2.6,
    "xray": 4.0,
    "radiology_report": 3.0,
    "genomics": 3.6,
    "clinical_data": 3.2,
}


def _logistic(year: np.ndarray | float, midpoint: float, width: float) -> np.ndarray | float:
    """Return a logistic ramp in calendar years, used for theme growth curves."""
    return 1.0 / (1.0 + np.exp(-(np.asarray(year, dtype=float) - midpoint) / width))


def _theme_probability(theme: str, year: int) -> float:
    """Return the chance that a paper published in ``year`` carries ``theme``.

    The curves are invented but not arbitrary: foundation-model work is nearly
    absent before 2022 and rises steeply, multimodal work rises earlier and more
    gently, digital-twin work stays rare throughout, and clinical and regulatory
    work grows steadily from an already meaningful base.
    """
    if theme == "foundation_models":
        return float(0.015 + 0.55 * _logistic(year, 2023.2, 0.85))
    if theme == "multimodal_integration":
        return float(0.09 + 0.34 * _logistic(year, 2022.4, 1.5))
    if theme == "digital_twins":
        return float(0.004 + 0.030 * _logistic(year, 2023.6, 1.2))
    if theme == "clinical_fda":
        return float(0.17 + 0.21 * _logistic(year, 2021.0, 2.0))
    raise KeyError(theme)


def _year_volume(n_papers: int) -> dict[int, int]:
    """Split a corpus size across years, growing exponentially, final year partial."""
    years = np.arange(FIRST_YEAR, LAST_YEAR + 1)
    weights = 1.32 ** (years - FIRST_YEAR)
    weights[-1] *= PARTIAL_YEAR_FRACTION
    counts = np.maximum(1, np.round(n_papers * weights / weights.sum())).astype(int)
    return dict(zip(years.tolist(), counts.tolist()))


def _draw_tail_set(rng: np.random.Generator) -> tuple[str, ...]:
    """Draw one rare modality combination, biased toward the commoner modalities."""
    keys = list(_TAIL_WEIGHTS)
    probabilities = np.array([_TAIL_WEIGHTS[key] for key in keys], dtype=float)
    probabilities /= probabilities.sum()
    size = int(rng.choice([2, 3, 4, 5], p=[0.44, 0.31, 0.17, 0.08]))
    chosen = rng.choice(len(keys), size=size, replace=False, p=probabilities)
    return tuple(sorted(keys[index] for index in chosen))


def _derive_domain(modalities: tuple[str, ...]) -> str:
    """Return the ``domain`` value implied by a modality set, per the figure spec."""
    has_radiology = bool(set(modalities) & style.RADIOLOGY_MODALITIES)
    has_pathology = bool(set(modalities) & style.PATHOLOGY_MODALITIES)
    if has_radiology and has_pathology:
        return "both"
    if has_radiology:
        return "radiology"
    if has_pathology:
        return "pathology"
    return "none"


def build_paper_labels(rng: np.random.Generator, n_papers: int) -> pd.DataFrame:
    """Invent one row per paper, conforming to the ``paper_labels.csv`` schema."""
    template_sets = {
        theme: [entry[0] for entry in entries] for theme, entries in _TEMPLATES.items()
    }
    template_probabilities = {}
    for theme, entries in _TEMPLATES.items():
        weights = np.array([entry[1] for entry in entries], dtype=float)
        template_probabilities[theme] = weights / weights.sum()

    rows: list[dict] = []
    serial = 0
    for year, volume in _year_volume(n_papers).items():
        for _ in range(volume):
            serial += 1
            labels = {
                theme: int(rng.random() < _theme_probability(theme, year))
                for theme in style.THEME_ORDER
            }
            if not any(labels.values()):
                fallback_weights = np.array(
                    [_theme_probability(theme, year) for theme in style.THEME_ORDER]
                )
                fallback = style.THEME_ORDER[
                    int(rng.choice(len(style.THEME_ORDER), p=fallback_weights / fallback_weights.sum()))
                ]
                labels[fallback] = 1

            carried = [theme for theme in style.THEME_ORDER if labels[theme]]
            primary = carried[int(rng.integers(len(carried)))]
            if rng.random() < TAIL_PROBABILITY:
                modalities = _draw_tail_set(rng)
            else:
                index = int(rng.choice(len(template_sets[primary]), p=template_probabilities[primary]))
                modalities = tuple(sorted(template_sets[primary][index]))
            if modalities != ("other",) and rng.random() < ADDITIVE_OTHER_PROBABILITY:
                modalities = tuple(sorted(modalities + ("other",)))

            row = {
                "pmid": f"SYN{serial:07d}",
                "year": year,
                "year_source": str(
                    rng.choice(["pubdate", "epubdate", "articledate"], p=[0.72, 0.2, 0.08])
                ),
            }
            row.update({f"theme_{theme}": labels[theme] for theme in style.THEME_ORDER})
            row.update(
                {
                    f"mod_{key}": int(key in modalities)
                    for key in style.MODALITY_ORDER
                }
            )
            row["domain"] = _derive_domain(modalities)
            rows.append(row)

    columns = (
        ["pmid", "year", "year_source"]
        + [f"theme_{theme}" for theme in style.THEME_ORDER]
        + [f"mod_{key}" for key in style.MODALITY_ORDER]
        + ["domain"]
    )
    return pd.DataFrame(rows, columns=columns)


def tabulate_combinations(papers: pd.DataFrame) -> pd.DataFrame:
    """Tabulate ``combination_counts.csv`` from a paper table.

    A paper falls in exactly one column of the block for each theme it carries:
    the column for its exact modality set.
    """
    modality_columns = [f"mod_{key}" for key in style.MODALITY_ORDER]
    sets = papers[modality_columns].to_numpy(dtype=bool)
    keys = np.array(style.MODALITY_ORDER)
    modality_set = ["+".join(sorted(keys[mask])) for mask in sets]
    working = papers.assign(modality_set=modality_set, n_modalities=sets.sum(axis=1))

    frames = []
    for theme in style.THEME_ORDER:
        subset = working.loc[working[f"theme_{theme}"] == 1]
        if subset.empty:
            continue
        counted = (
            subset.groupby(["modality_set", "n_modalities"], as_index=False)
            .size()
            .rename(columns={"size": "n_papers"})
        )
        counted = counted.sort_values(
            ["n_papers", "modality_set"], ascending=[False, True]
        ).reset_index(drop=True)
        counted.insert(0, "theme", theme)
        counted["rank_in_theme"] = np.arange(1, len(counted) + 1)
        frames.append(counted[["theme", "modality_set", "n_modalities", "n_papers", "rank_in_theme"]])
    return pd.concat(frames, ignore_index=True)


def tabulate_theme_years(papers: pd.DataFrame) -> pd.DataFrame:
    """Tabulate ``theme_year_counts.csv`` from a paper table.

    Themes other than the clinical one get a single ``all`` series. The clinical
    theme is split into ``radiology`` and ``pathology``; a paper whose domain is
    ``both`` counts in each, and one whose domain is ``none`` counts in neither.
    Years with no papers are written as zeros so the lines stay continuous.
    """
    years = list(range(FIRST_YEAR, LAST_YEAR + 1))
    rows: list[dict] = []
    for theme in style.THEME_ORDER:
        subset = papers.loc[papers[f"theme_{theme}"] == 1]
        if theme == "clinical_fda":
            series = {
                "radiology": subset.loc[subset["domain"].isin(["radiology", "both"])],
                "pathology": subset.loc[subset["domain"].isin(["pathology", "both"])],
            }
        else:
            series = {"all": subset}
        for domain, frame in series.items():
            per_year = frame.groupby("year").size().to_dict()
            for year in years:
                rows.append(
                    {
                        "theme": theme,
                        "domain": domain,
                        "year": year,
                        "n_papers": int(per_year.get(year, 0)),
                        "partial_year": int(year == LAST_YEAR),
                    }
                )
    return pd.DataFrame(rows, columns=["theme", "domain", "year", "n_papers", "partial_year"])


def generate(seed: int = DEFAULT_SEED, n_papers: int = 3800) -> dict[str, pd.DataFrame]:
    """Generate the three synthetic tables.

    Args:
        seed: Seed for the random generator; recorded in the manifest.
        n_papers: Approximate corpus size before rounding across years.

    Returns:
        Mapping from file name to the table that belongs in it.
    """
    rng = np.random.default_rng(seed)
    papers = build_paper_labels(rng, n_papers)
    return {
        "paper_labels.csv": papers,
        "combination_counts.csv": tabulate_combinations(papers),
        "theme_year_counts.csv": tabulate_theme_years(papers),
    }


def _write_csv(frame: pd.DataFrame, path: Path, seed: int) -> None:
    """Write one table with a provenance header comment above the column row."""
    header = (
        f"# {_BANNER}\n"
        f"# file: {path.name}\n"
        f"# generated by src/trends/plotting/synthetic.py, seed={seed}\n"
        f"# Schema matches docs/figure-spec.md. The values are invented and describe\n"
        f"# no real literature. Do not quote them. Do not draw a conclusion from them.\n"
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(header)
        frame.to_csv(handle, index=False, lineterminator="\n")


def write(directory: str | Path, seed: int = DEFAULT_SEED, n_papers: int = 3800) -> Path:
    """Generate the tables and write them, with a README and a manifest.

    Args:
        directory: Destination directory; created if it does not exist.
        seed: Seed for the random generator.
        n_papers: Approximate corpus size.

    Returns:
        The directory written to.
    """
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    tables = generate(seed=seed, n_papers=n_papers)
    for name, frame in tables.items():
        _write_csv(frame, target / name, seed)

    papers = tables["paper_labels.csv"]
    combinations = tables["combination_counts.csv"]
    (target / "README.md").write_text(
        _readme_text(seed, papers, combinations, tables["theme_year_counts.csv"]), encoding="utf-8"
    )
    (target / "MANIFEST.txt").write_text(
        _manifest_text(seed, n_papers, tables), encoding="utf-8"
    )
    return target


def _readme_text(
    seed: int,
    papers: pd.DataFrame,
    combinations: pd.DataFrame,
    theme_years: pd.DataFrame,
) -> str:
    """Compose the directory README that warns readers off the invented numbers."""
    per_theme = combinations.groupby("theme")["n_papers"].sum().to_dict()
    lines = [
        "# SYNTHETIC DATA — NOT THE REAL CORPUS",
        "",
        "Every number in this directory is invented. The tables exist so the plotting",
        "code could be written and tested before the PubMed retrieval and the classifier",
        "were finished. They describe no real literature.",
        "",
        "**Do not quote these numbers. Do not put them in the manuscript. Do not draw a",
        "conclusion from them.** When the real tables land in `data/processed/`, rebuild",
        "the figure from those and compare.",
        "",
        "## Provenance",
        "",
        f"- Generator: `src/trends/plotting/synthetic.py`, seed `{seed}`.",
        "- Rebuild with:",
        "  `PYTHONPATH=src python -m trends.plotting.synthetic --output data/processed/synthetic`",
        "- Schema: `docs/figure-spec.md`. The three files match it column for column.",
        "",
        "## What the invented corpus contains",
        "",
        f"- {len(papers):,} papers, {FIRST_YEAR}–{LAST_YEAR}, the final year partial by construction",
        f"  ({PARTIAL_YEAR_FRACTION:.0%} of a full year's volume).",
        "- Papers are multi-label: one paper may carry several themes.",
        "- Theme totals (papers carrying the label):",
    ]
    for theme in style.THEME_ORDER:
        lines.append(f"  - `{theme}`: {per_theme.get(theme, 0):,}")
    lines += [
        "",
        "## What it was shaped to stress",
        "",
        "- A fat tail of rare modality combinations, so the top-N cap in Panel A has",
        "  something real to hide and the legend must report it.",
        "- `digital_twins` deliberately sparse, so a near-empty block must still draw.",
        "- Heavy CT and PET co-occurrence, as in oncologic PET/CT.",
        "- Imaging paired with genomics and with clinical/EHR data, so the multimodal",
        "  theme cannot draw as overwhelmingly unimodal without the figure showing it.",
        "- `other` used additively, beside named modalities as well as alone.",
        "- A partial final year, so Panel B's partial-year treatment is exercised.",
        "",
        "## What it does not stress",
        "",
        "- Real term ambiguity, classifier error, or missing publication years.",
        "- A theme with zero papers; that case is covered in `tests/test_plot.py` instead.",
        "- The two-order-of-magnitude gap between theme sizes that Panel B's split scale",
        "  exists for. The invented themes sit within a factor of two of each other, so the",
        "  split draws but its scale callouts stay quiet. The measured magnitudes, and the",
        "  real clinical radiology and pathology series, are in",
        "  `tests/fixtures/plot_theme_year_counts_measured.csv` instead.",
        "",
        "## Files",
        "",
        "| File | Rows | Contents |",
        "|---|---|---|",
        f"| `paper_labels.csv` | {len(papers):,} | one row per invented paper |",
        f"| `combination_counts.csv` | {len(combinations):,} | one row per theme and modality set; drives Panel A |",
        f"| `theme_year_counts.csv` | {len(theme_years):,} | one row per theme, domain, and year; drives Panel B |",
        "| `MANIFEST.txt` | — | seed, timestamp, and row counts for this build |",
        "",
    ]
    return "\n".join(lines)


def _manifest_text(seed: int, n_papers: int, tables: dict[str, pd.DataFrame]) -> str:
    """Compose the manifest recording exactly how this build was produced."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        _BANNER,
        "",
        f"generated_utc      : {stamp}",
        f"generator          : src/trends/plotting/synthetic.py",
        f"seed               : {seed}",
        f"requested_n_papers : {n_papers}",
        f"year_range         : {FIRST_YEAR}-{LAST_YEAR} (final year partial)",
        f"partial_fraction   : {PARTIAL_YEAR_FRACTION}",
        f"tail_probability   : {TAIL_PROBABILITY}",
        "",
        "row counts",
    ]
    for name, frame in tables.items():
        lines.append(f"  {name:<24} {len(frame):>7,} rows")
    lines.append("")
    lines.append("The same seed reproduces these files byte for byte, apart from this timestamp.")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Command line entry point for regenerating the synthetic tables."""
    parser = argparse.ArgumentParser(
        prog="python -m trends.plotting.synthetic",
        description="Write a synthetic stand-in corpus matching the figure input schema.",
    )
    parser.add_argument(
        "--output", default="data/processed/synthetic", help="destination directory"
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="random seed")
    parser.add_argument("--n-papers", type=int, default=3800, help="approximate corpus size")
    args = parser.parse_args(argv)
    target = write(args.output, seed=args.seed, n_papers=args.n_papers)
    print(f"wrote synthetic tables to {target}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
