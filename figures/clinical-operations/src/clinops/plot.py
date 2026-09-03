"""Build the two-panel clinical-operations figure from the processed tables.

The module reads ``cumulative_by_year.csv``, ``pathway_by_domain.csv`` and
``authorizations.csv`` from a directory, draws Panel A and Panel B, and writes a
PDF, a PNG and an SVG. It classifies nothing, filters nothing, and counts nothing
beyond what the layout needs: which year the snapshot stops in, and how each
domain's authorizations divide between the three marketing pathways.

Command line::

    PYTHONPATH=src python -m clinops.plot \\
        --input data/processed --output figures/

Alongside the figure it writes a summary text file holding the numbers the figure
legend needs, so nobody has to read them off the picture.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (backend must be set first)
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.text import Text  # noqa: E402
from trends.plotting import style  # noqa: E402

from .plotting import (  # noqa: E402
    CATEGORY_DOMAIN,
    CATEGORY_ORDER,
    DOMAIN_ORDER,
    PATHWAY_ORDER,
    category_label,
    domain_label,
    io,
    panel_a,
    panel_b,
)

#: Figure size in inches. Portrait, and the width is a single CCR manuscript
#: page. The width is set by Panel A's right-hand gutter, which carries nine
#: device names and two series labels: at 5.8 pt the widest of them measures
#: about 1.35 in, and the plot needs the rest to keep thirty-two years at a
#: pitch where a marker is not touching its neighbour. The height is what Panel
#: A needs for a log axis that spans 0.8 to about 140 with eleven gutter labels
#: stacked beside it, plus Panel B and its key. Nothing is shrunk to hide
#: crowding.
FIGURE_SIZE: tuple[float, float] = (7.0, 8.0)

#: Base name of the output files, before the optional tag.
OUTPUT_STEM = "clinical_operations"

# Figure-fraction geometry. Read these as the inches they stand for on the
# 7.0 x 8.0 in canvas:
#
#   Panel A   left 0.62 in, bottom 3.30 in, 4.85 x 4.05 in
#   Panel B   left 0.95 in, bottom 0.95 in, 5.20 x 1.45 in
#
# Panel A's left edge is where the plot begins; the 0.62 in to its left holds
# the y tick labels and the rotated axis title. It stops 1.53 in short of the
# right edge, and that gutter is the reason the figure is 7.0 in wide rather
# than narrower: it holds nine device labels and two series labels, and a longer
# device name needs the gutter widened, not the type shrunk.
#
# Panel B's left edge leaves 0.95 in for the two domain labels and its right
# edge 0.85 in for the "n = ..." totals; below it sit the axis title and the
# three-swatch pathway key, which is why its bottom is 0.95 in up from the paper
# edge rather than tight against it.
#
# Change history:
#   2026-09-03  first geometry, at 7.0 x 8.0 in.
_PANEL_A_RECT = (0.0886, 0.4125, 0.6929, 0.5063)
_PANEL_B_RECT = (0.1357, 0.1188, 0.7429, 0.1813)

# Both panel titles start 0.36 in from the paper edge, immediately right of
# their panel letter, rather than at their own plot's left edge -- which would
# indent Panel A's title by 0.62 in and Panel B's by 0.95 in and leave the two
# titles on different margins for no reason but their gutters. In axes
# fractions, that is -(gutter - 0.36) / plot width.
_PANEL_A_TITLE_X = -(0.62 - 0.36) / 4.85
_PANEL_B_TITLE_X = -(0.95 - 0.36) / 5.20

#: Figure-fraction position of each panel letter, and of the panel it names.
_PANEL_LETTERS = (("A", 0.988), ("B", 0.345))

#: A snapshot whose last decision falls before this month leaves the final year
#: partial. FDA's device list is a snapshot with a cut-off, not a closed year:
#: the 2026-03-30 file holds one quarter of 2026 and the rest of the year has
#: not happened yet. Drawing that year like a complete one would invite a
#: statement about a slowdown that is an artefact of the retrieval date, so the
#: final year is banded, its segment dotted and its marker drawn open, exactly
#: as the sibling trends figure draws its partial year.
PARTIAL_YEAR_CUTOFF_MONTH: int = 12


class LabelOverflow(RuntimeError):
    """A label was drawn outside the canvas.

    Raised rather than warned. A label that runs off the paper still renders --
    it simply prints half, or prints nothing, depending on the device -- which
    is the failure mode this project keeps designing against: a figure that is
    wrong in a way nobody notices.
    """


@dataclass(frozen=True)
class BuildResult:
    """What one figure build produced.

    Attributes:
        pdf: Path of the vector output.
        png: Path of the raster output.
        svg: Path of the editable vector output.
        summary: Path of the text summary of legend numbers.
        data: The validated tables the figure was drawn from.
        panel_a: What Panel A drew.
        panel_b: What Panel B drew.
        margin_in: Least clearance between any label and the paper edge, in
            inches, measured on the rendered canvas.
    """

    pdf: Path
    png: Path
    svg: Path
    summary: Path
    data: io.FigureData
    panel_a: panel_a.PanelA
    panel_b: panel_b.PanelB
    margin_in: float


def partial_year(data: io.FigureData) -> int | None:
    """Return the final year, if the snapshot does not cover all of it.

    Derived from the latest decision date in ``authorizations.csv`` rather than
    from a column, because the schema has none: the snapshot's cut-off *is* its
    last decision date. See :data:`PARTIAL_YEAR_CUTOFF_MONTH`.
    """
    last_year = data.years[-1]
    latest = data.authorizations["decision_date"].max()
    if int(latest.year) < last_year:
        return last_year
    return last_year if int(latest.month) < PARTIAL_YEAR_CUTOFF_MONTH else None


def measure_margin(figure: Figure) -> tuple[float, list[tuple[str, float]]]:
    """Measure every drawn label against the canvas.

    Panel A's device gutter and Panel B's ``n = …`` totals are both drawn
    outside their axes with clipping off, which is the only way to place them
    and also the only way to lose them: a label that overruns the paper still
    renders, half of it, and nothing in matplotlib says so. So every text on the
    figure is measured after the draw.

    Args:
        figure: A figure that has already been drawn once, so the renderer knows
            where its text landed.

    Returns:
        The least clearance between any label and the paper edge, in inches --
        negative if something overran -- and the labels that overran, worst
        first.
    """
    renderer = figure.canvas.get_renderer()
    width, height = figure.get_size_inches()
    dpi = figure.dpi
    margin = min(width, height)
    overflows: list[tuple[str, float]] = []
    for text in figure.findobj(Text):
        if not text.get_visible() or not text.get_text().strip():
            continue
        box = text.get_window_extent(renderer)
        clearance = min(
            box.x0 / dpi,
            box.y0 / dpi,
            width - box.x1 / dpi,
            height - box.y1 / dpi,
        )
        margin = min(margin, clearance)
        if clearance < 0:
            overflows.append((text.get_text().replace("\n", " / "), clearance))
    overflows.sort(key=lambda item: item[1])
    return margin, overflows


def build_figure(data: io.FigureData) -> tuple[Figure, panel_a.PanelA, panel_b.PanelB]:
    """Draw both panels onto a new figure.

    Args:
        data: Validated input tables.

    Returns:
        The figure, what Panel A drew, and what Panel B drew.
    """
    figure = plt.figure(figsize=FIGURE_SIZE)
    first = panel_a.draw(
        figure,
        data.cumulative,
        data.authorizations,
        _PANEL_A_RECT,
        partial_year=partial_year(data),
        title_x=_PANEL_A_TITLE_X,
    )
    second = panel_b.draw(
        figure, data.pathways, _PANEL_B_RECT, title_x=_PANEL_B_TITLE_X
    )

    # Panel letters: bold serif in ink, and the largest type on the page, per
    # section 2 of ``../../ink_style_guide.md``. They are the only element of
    # the figure that has to be findable before anything is read.
    for letter, y in _PANEL_LETTERS:
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
    return figure, first, second


def summary_text(
    data: io.FigureData,
    first: panel_a.PanelA,
    second: panel_b.PanelB,
    tag: str | None,
    margin_in: float,
) -> str:
    """Compose the numbers the figure legend needs, as plain text."""
    years = data.years
    radiology_total = data.domain_total("radiology")
    pathology_total = data.domain_total("pathology")
    ratio = radiology_total / pathology_total if pathology_total else float("nan")
    detection = data.category_total("radiology_cancer_detection")
    detection_ratio = detection / pathology_total if pathology_total else float("nan")

    lines = [
        "Clinical operations figure — numbers for the legend",
        f"source directory : {data.source}",
        f"tag              : {tag or '(none)'}",
        f"snapshot through : {data.snapshot_date} (latest decision date in the table)",
        f"year range       : {years[0]}-{years[-1]}",
        f"partial year     : {first.partial_year if first.partial_year else 'none'}",
        f"authorizations   : {len(data.authorizations):,} oncology-certain rows",
        "",
        "The counts are a FLOOR, not an estimate. A product code counts only where FDA's",
        "own regulation definition or device-type name states the cancer indication, so",
        "devices under generic codes (QIH alone holds 274) are excluded even where some",
        "of them are certainly oncologic. See config/oncology_codes.yaml.",
        "",
        "Panel A — cumulative authorizations, log y axis",
        f"  y axis           : {first.y_limits[0]:g} to {first.y_limits[1]:,.0f}, log scale;"
        f" ticks {', '.join(str(tick) for tick in panel_a.Y_TICKS)}",
        "  x axis           : "
        f"{years[0]}-{years[-1]}, continuous, no break in either axis",
        "",
        f"  {'category':<30}{'total':>7}{'first year':>12}{'zero years not drawn':>24}",
    ]
    for category in CATEGORY_ORDER:
        run = first.undrawn_years.get(category)
        span = "none" if run is None else f"{run[0]}-{run[1]} ({run[1] - run[0] + 1} years)"
        first_year = first.first_years.get(category)
        lines.append(
            f"  {category_label(category):<30}{first.totals.get(category, 0):>7,}"
            f"{first_year if first_year else '-':>12}{span:>24}"
        )
    lines += [
        "",
        "  Each line is drawn only from the first year its cumulative count reaches one.",
        "  A log axis cannot draw a zero, so the years above are drawn as no line at all",
        "  rather than as a line along the axis floor. The legend must say so.",
        "",
        f"  radiology total  : {radiology_total:,} "
        f"({detection:,} cancer detection + "
        f"{data.category_total('radiology_radiation_therapy'):,} radiation therapy)",
        f"  pathology total  : {pathology_total:,}",
        f"  gap              : {ratio:.1f}x radiology over pathology; "
        f"{detection_ratio:.1f}x on cancer detection alone",
        "",
        "  pathology devices, in decision order (Panel A labels each one):",
    ]
    for index, row in first.devices.iterrows():
        lines.append(
            f"    {index + 1:>2}. {row['decision_date'].date()}  "
            f"{str(row['submission_number']):<10}{str(row['pathway']):<9}{row['device']}"
        )

    lines += [
        "",
        "Panel B — marketing pathway, normalized to each field's own total",
        f"  {'domain':<12}{'pathway':<10}{'count':>7}{'share':>9}  {'count printed':<20}",
    ]
    for domain in DOMAIN_ORDER:
        for pathway in PATHWAY_ORDER:
            segment = next(
                (
                    item
                    for item in second.segments
                    if item.domain == domain and item.pathway == pathway
                ),
                None,
            )
            if segment is None:
                continue
            placed = "inside the segment" if segment.inside else "above, on a leader"
            lines.append(
                f"  {domain_label(domain):<12}{pathway:<10}{segment.count:>7,}"
                f"{segment.share:>8.1%}  {placed:<20}"
            )
    lines += [
        "",
        f"  totals           : "
        + ", ".join(f"{domain_label(key)} n = {value:,}" for key, value in second.totals.items()),
        "",
        "  by category, which Panel B aggregates into its two bars:",
        f"    {'category':<30}" + "".join(f"{pathway:>10}" for pathway in PATHWAY_ORDER),
    ]
    for category in CATEGORY_ORDER:
        cells = []
        for pathway in PATHWAY_ORDER:
            value = data.pathways.loc[
                (data.pathways["category"] == category)
                & (data.pathways["pathway"] == pathway),
                "count",
            ]
            cells.append(f"{int(value.iloc[0]) if len(value) else 0:>10,}")
        lines.append(f"    {category_label(category):<30}" + "".join(cells))

    lines += [
        "",
        f"Least clearance between any label and the paper edge: {margin_in:.3f} in",
        "",
    ]
    return "\n".join(lines)


def build(
    input_dir: str | Path,
    output_dir: str | Path,
    tag: str | None = None,
) -> BuildResult:
    """Read the tables, draw the figure, and write PDF, PNG, SVG, and summary.

    Args:
        input_dir: Directory holding the processed CSVs.
        output_dir: Directory the outputs are written to; created if absent.
        tag: Optional suffix, so a draft built from stand-in fixtures cannot be
            mistaken for one built from the real snapshot.

    Returns:
        A :class:`BuildResult` naming what was written.

    Raises:
        io.SchemaError: If an input table is missing, malformed, or disagrees
            with another table.
        LabelOverflow: If any label was drawn off the canvas.
    """
    data = io.load_figure_data(input_dir)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    stem = OUTPUT_STEM if not tag else f"{OUTPUT_STEM}_{tag}"

    with plt.rc_context(style.rc_params()):
        figure, first, second = build_figure(data)
        figure.canvas.draw()
        margin_in, overflows = measure_margin(figure)
        if overflows:
            plt.close(figure)
            worst = "; ".join(f"{text!r} by {-amount:.3f} in" for text, amount in overflows[:5])
            raise LabelOverflow(
                f"{len(overflows)} label(s) drawn off the canvas: {worst}. Widen the "
                "gutter or shorten the label; do not shrink the type below the ladder "
                "in trends.plotting.style."
            )
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
    text = summary_text(data, first, second, tag, margin_in)
    summary.write_text(text, encoding="utf-8")
    return BuildResult(
        pdf=pdf,
        png=png,
        svg=svg,
        summary=summary,
        data=data,
        panel_a=first,
        panel_b=second,
        margin_in=margin_in,
    )


def main(argv: list[str] | None = None) -> int:
    """Command line entry point."""
    parser = argparse.ArgumentParser(
        prog="python -m clinops.plot",
        description=(
            "Build the two-panel clinical-operations figure from the processed tables."
        ),
    )
    parser.add_argument("--input", required=True, help="directory holding the processed CSVs")
    parser.add_argument(
        "--output", default="figures/", help="directory for the PDF, PNG and SVG"
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="suffix for the output file names, e.g. 'fixture'",
    )
    args = parser.parse_args(argv)

    result = build(args.input, args.output, tag=args.tag)
    print(f"wrote {result.pdf}")
    print(f"wrote {result.png}")
    print(f"wrote {result.svg}")
    print(f"wrote {result.summary}")
    print()
    print(summary_text(result.data, result.panel_a, result.panel_b, args.tag, result.margin_in))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
