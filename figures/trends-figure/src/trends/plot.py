"""Build the two-panel trends figure from the processed tables.

The module reads ``combination_counts.csv`` and ``theme_year_counts.csv`` from a
directory, draws Panel A and Panel B, and writes a PDF and a PNG. It classifies
nothing, filters nothing, and counts nothing beyond what the layout needs: which
combinations fall inside the top-N cap, and how many papers fall outside it.

Command line::

    PYTHONPATH=src python -m trends.plot \\
        --input data/processed/synthetic --output figures/ --tag synthetic

Alongside the figure it writes a summary text file holding the numbers the
figure legend needs, so nobody has to read them off the picture.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (backend must be set first)
from matplotlib.figure import Figure  # noqa: E402

from .plotting import io, panel_a, panel_b, style  # noqa: E402

#: Figure size in inches. The width fits a single manuscript page; the height is
#: whatever the fifteen matrix rows and a readable Panel B require. Nothing is
#: shrunk to hide crowding. The height grew from 8.3 in when the modality list
#: went from eleven rows to thirteen, so that the matrix row pitch stayed near
#: 13.5 pt; from 8.7 in when Panel B became two stacked plots; and from 9.2 in on
#: 2026-09-02, when Panel B went from five lines to ten.
#:
#: That last growth is bought entirely for Panel B's end-of-line labels. Panel B
#: labels its lines directly rather than with a legend box, and six labels now
#: stack beside the upper plot, most of them two lines deep: about 1.8 in of type
#: that has to sit near the line ends rather than in a solid block. Panel A keeps
#: its absolute size across all of these -- 4.92 in -- so every added inch is
#: Panel B's. The alternative was type below the floors ``tests/test_plot.py``
#: pins, which is not on the table.
FIGURE_SIZE: tuple[float, float] = (7.5, 10.0)

#: Base name of the output files, before the optional tag.
OUTPUT_STEM = "trends_figure"

# Figure-fraction geometry. These are fractions of a canvas whose height changed
# on 2026-09-02, so read them as the inches they stand for: Panel A is 4.92 in
# tall, unchanged, and Panel B is 4.18 in, up from 3.39 in.
#
# Panel A's left edge is where the matrix begins; the
# space to its left holds the modality row labels and the bar axis, and so must
# be at least as wide as the longest modality label plus its tick pad -- 1.42 in
# for "Genomics / Transcriptomics" at 7.5 pt, which is why the gutter widened when
# the modality list went from thirteen rows to fifteen. Panel B's
# rectangle covers both of its stacked plots and the gap between them; the space
# to its right holds the end-of-line labels and the space below it the shared
# x axis.
#
# Panel A stops short of the right edge rather than running to 0.995. The last
# block's remainder column sits half a column from that edge and prints its set
# count underneath, centred: at full width that caption ran off the paper and
# still rendered. ``tests/test_plot.py`` now measures every label against the
# canvas, so the next thing to overflow fails instead of printing half.
_PANEL_A_RECT = (0.192, 0.4968, 0.786, 0.4922)
_PANEL_B_RECT = (0.096, 0.0414, 0.706, 0.4184)


@dataclass(frozen=True)
class BuildResult:
    """What one figure build produced.

    Attributes:
        pdf: Path of the vector output.
        png: Path of the raster output.
        svg: Path of the editable vector output.
        summary: Path of the text summary of legend numbers.
        tails: Per-theme account of what Panel A's cap hid.
        data: The validated tables the figure was drawn from.
        top_n: The cap that was applied.
        scale: The Panel A bar scale that was drawn.
        panel: What Panel B's two stacked plots drew.
    """

    pdf: Path
    png: Path
    svg: Path
    summary: Path
    tails: list[panel_a.TailSummary]
    data: io.FigureData
    top_n: int
    scale: str
    panel: panel_b.PanelB


def build_figure(
    data: io.FigureData,
    top_n: int = panel_a.DEFAULT_TOP_N,
    scale: str = panel_a.DEFAULT_BAR_SCALE,
) -> tuple[Figure, list[panel_a.TailSummary], panel_b.PanelB]:
    """Draw both panels onto a new figure.

    Args:
        data: Validated input tables.
        top_n: Combinations drawn per theme in Panel A.
        scale: Panel A bar scale, ``"count"`` or ``"share"``.

    Returns:
        The figure, the per-theme record of what Panel A's cap hid, and what
        Panel B drew.
    """
    figure = plt.figure(figsize=FIGURE_SIZE)
    tails = panel_a.draw(
        figure, data.combinations, _PANEL_A_RECT, top_n=top_n, scale=scale, modality_key=True
    )
    panel = panel_b.draw(figure, data.theme_years, _PANEL_B_RECT)

    # Panel letters: bold serif in ink, and the largest type on the page, per
    # section 2 of ``../ink_style_guide.md``. They are the only element of the
    # figure that has to be findable before anything is read.
    for letter, y in (("A", 0.995), ("B", 0.479)):
        figure.text(
            0.012,
            y,
            letter,
            fontsize=style.FS_PANEL_LETTER,
            fontfamily="serif",
            fontweight="bold",
            color=style.INK,
            va="top",
            ha="left",
        )
    return figure, tails, panel


class StaleInputs(RuntimeError):
    """Raised when the tables were built from configs that have since changed."""


def _refuse_if_stale(input_dir: "str | Path", stale_ok: bool) -> None:
    """Refuse to draw from labels the current configuration would not produce.

    A figure is harder to un-publish than a number. On 2026-09-08 a corpus run
    finished, the dictionaries were edited underneath it, and a figure was built
    and reported from labels no configuration on disk could reproduce. Nothing
    in the output said so.

    The check is skipped for a directory with no run manifest -- the synthetic
    tables have none -- and a missing manifest is reported by the classifier's
    own ``--check`` rather than invented here.
    """
    from pathlib import Path

    from trends import classify

    directory = Path(input_dir)
    if not (directory / "run_manifest.json").exists():
        return
    freshness = classify.check_freshness(directory, Path("config"))
    if not freshness.problems or stale_ok:
        return
    problems = "\n  - ".join(freshness.problems)
    raise StaleInputs(
        f"{directory} was built from a configuration that has since changed:\n"
        f"  - {problems}\n"
        "Re-run trends.classify before drawing, or pass stale_ok=True "
        "(--stale-ok) if you know the drawing is a deliberate look at old labels."
    )


def summary_text(
    data: io.FigureData,
    tails: list[panel_a.TailSummary],
    top_n: int,
    tag: str | None,
    scale: str = panel_a.DEFAULT_BAR_SCALE,
    panel: panel_b.PanelB | None = None,
) -> str:
    """Compose the numbers the figure legend needs, as plain text."""
    years = sorted(data.theme_years["year"].unique().tolist())
    partial = data.theme_years.loc[data.theme_years["partial_year"] == 1, "year"].unique()
    lines = [
        "Trends figure — numbers for the legend",
        f"source directory : {data.source}",
        f"tag              : {tag or '(none)'}",
        f"papers in corpus : {data.n_papers_total if data.n_papers_total is not None else 'unknown (paper_labels.csv absent)'}",
        f"year range       : {years[0]}-{years[-1]}",
        f"partial year     : {int(partial[0]) if len(partial) else 'none flagged'}",
        f"Panel A columns  : top {top_n} modality combinations per theme, plus one"
        " remainder column holding every other paper in the theme",
        f"Panel A bars     : {scale}"
        + (
            " (papers, one shared scale across themes)"
            if scale == "count"
            else " (percent of each theme's own papers)"
        ),
        "",
        f"{'theme':<24}{'papers':>8}{'sets':>7}{'drawn':>7}{'in remainder':>14}"
        f"{'remainder papers':>18}{'share':>8}",
    ]
    for tail in tails:
        lines.append(
            f"{tail.theme:<24}{tail.total_papers:>8}"
            f"{tail.total_sets:>7}{tail.shown_sets:>7}"
            f"{tail.remainder_sets:>14}{tail.remainder_papers:>18}"
            f"{tail.remainder_share:>7.1%}"
        )
    lines += [
        "",
        "Nothing is hidden: the remainder column is drawn, so each block's bars sum to",
        "its theme total.",
        "Papers are multi-label: the theme totals above sum to more than the corpus size.",
        "",
        "Panel B — two stacked plots, per-year counts, separate linear y axes",
        f"  upper plot       : {', '.join(f'{theme}/{domain}' for theme, domain in panel_b.UPPER_SERIES)}",
        f"  lower plot       : {', '.join(f'{theme}/{domain}' for theme, domain in panel_b.LOWER_SERIES)}",
    ]
    if panel is not None:
        if panel.scale_ratio is None:
            ratio = "one plot only; no second scale drawn"
        else:
            # Same rounding rule the figure prints, so the two never disagree.
            shown = (
                f"{panel.scale_ratio:,.0f}"
                if panel.scale_ratio >= 10
                else f"{panel.scale_ratio:.1f}"
            )
            band = (
                "range band drawn on the upper plot"
                if panel.scale_ratio >= panel_b.MIN_RATIO_FOR_BAND
                else f"range band suppressed, ratio below {panel_b.MIN_RATIO_FOR_BAND:g}x"
            )
            ratio = f"{shown}x finer than the upper plot ({band})"
        lines.append(f"  lower y scale    : {ratio}")
        for theme, domain in panel_b.UPPER_SERIES + panel_b.LOWER_SERIES:
            rows = data.theme_years.loc[
                (data.theme_years["theme"] == theme) & (data.theme_years["domain"] == domain)
            ]
            if rows.empty:
                continue
            name = f"{theme}/{domain}"
            lines.append(
                f"  {name:<32} total {int(rows['n_papers'].sum()):>7,}"
                f"   peak year {int(rows['n_papers'].max()):>6,}"
            )
        if panel.zero_run is not None:
            first, last = panel.zero_run
            span = last - first + 1
            lines.append(
                f"  pathology zero run: {first}-{last} ({span} consecutive years at zero)"
            )
    lines.append("")
    return "\n".join(lines)


def build(
    input_dir: str | Path,
    output_dir: str | Path,
    tag: str | None = None,
    top_n: int = panel_a.DEFAULT_TOP_N,
    scale: str = panel_a.DEFAULT_BAR_SCALE,
    stale_ok: bool = False,
) -> BuildResult:
    """Read the tables, draw the figure, and write PDF, PNG, SVG, and summary.

    Args:
        input_dir: Directory holding the processed CSVs.
        output_dir: Directory the outputs are written to; created if absent.
        tag: Optional suffix, so a draft built from stand-in data cannot be
            mistaken for one built from the real corpus.
        top_n: Combinations drawn per theme in Panel A.
        scale: Panel A bar scale, ``"count"`` or ``"share"``.

    Returns:
        A :class:`BuildResult` naming what was written.

    Raises:
        io.SchemaError: If an input table is missing or malformed.
        ValueError: If ``top_n`` is not positive.
    """
    if top_n < 1:
        raise ValueError(f"top_n must be at least 1, got {top_n}")
    _refuse_if_stale(input_dir, stale_ok)
    data = io.load_figure_data(input_dir)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    stem = OUTPUT_STEM if not tag else f"{OUTPUT_STEM}_{tag}"

    with plt.rc_context(style.rc_params()):
        figure, tails, panel = build_figure(data, top_n=top_n, scale=scale)
        pdf = destination / f"{stem}.pdf"
        png = destination / f"{stem}.png"
        svg = destination / f"{stem}.svg"
        figure.savefig(pdf)
        figure.savefig(png, dpi=300)
        # SVG for the journal's illustrators: text stays text, so every label
        # can be restyled without redrawing the figure.
        figure.savefig(svg)
        plt.close(figure)

    summary = destination / f"{stem}_summary.txt"
    text = summary_text(data, tails, top_n, tag, scale, panel)
    summary.write_text(text, encoding="utf-8")
    return BuildResult(
        pdf=pdf,
        png=png,
        svg=svg,
        summary=summary,
        tails=tails,
        data=data,
        top_n=top_n,
        scale=scale,
        panel=panel,
    )


def main(argv: list[str] | None = None) -> int:
    """Command line entry point."""
    parser = argparse.ArgumentParser(
        prog="python -m trends.plot",
        description="Build the two-panel trends figure from the processed tables.",
    )
    parser.add_argument("--input", required=True, help="directory holding the processed CSVs")
    parser.add_argument("--output", default="figures/", help="directory for the PDF and PNG")
    parser.add_argument(
        "--tag", default=None, help="suffix for the output file names, e.g. 'synthetic'"
    )
    parser.add_argument(
        "--stale-ok",
        action="store_true",
        help="draw even if the tables were built from configs that have since changed",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=panel_a.DEFAULT_TOP_N,
        help=f"modality combinations drawn per theme (default {panel_a.DEFAULT_TOP_N})",
    )
    parser.add_argument(
        "--panel-a-scale",
        choices=panel_a.BAR_SCALES,
        default=panel_a.DEFAULT_BAR_SCALE,
        help=(
            "Panel A bar scale: 'count' draws papers on one scale shared by every "
            "theme, so blocks are comparable but a small theme draws flat; 'share' "
            "draws each combination as a percent of its own theme, so every block "
            "is legible but cross-theme volume moves to Panel B "
            f"(default {panel_a.DEFAULT_BAR_SCALE})"
        ),
    )
    args = parser.parse_args(argv)

    result = build(
        args.input,
        args.output,
        tag=args.tag,
        top_n=args.top_n,
        scale=args.panel_a_scale,
        stale_ok=args.stale_ok,
    )
    print(f"wrote {result.pdf}")
    print(f"wrote {result.png}")
    print(f"wrote {result.svg}")
    print(f"wrote {result.summary}")
    print()
    print(
        summary_text(
            result.data, result.tails, result.top_n, args.tag, result.scale, result.panel
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
