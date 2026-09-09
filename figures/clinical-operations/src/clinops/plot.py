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

#: Base name of the output files, before the layout suffix and optional tag.
OUTPUT_STEM = "clinical_operations"


@dataclass(frozen=True)
class Layout:
    """One arrangement of the two panels on a canvas.

    The figure is published portrait, one panel above the other, which is what a
    single-column CCR page takes. The landscape arrangement exists because a
    two-panel figure sometimes has to sit across a spread or a slide, and
    redrawing it by hand for that would mean two figures that could drift apart.
    Both are built from the same data on every run, so they cannot disagree.

    Every geometry field is a figure fraction, because that is what matplotlib
    takes, but each is written below as the inches it stands for on its own
    canvas. Read the inches; the fractions are arithmetic.

    Attributes:
        name: Human name, used in the summary sheet.
        suffix: Appended to :data:`OUTPUT_STEM`. Empty for the published
            portrait, so its filenames do not move and the manuscript keeps
            working.
        figure_size: Canvas, in inches.
        panel_a_rect: Panel A's axes rect, figure fractions.
        panel_b_rect: Panel B's axes rect, figure fractions.
        panel_a_title_x: Panel A's title offset, in axes fractions.
        panel_b_title_x: Panel B's title offset, in axes fractions.
        letters: ``(letter, x, y)`` in figure fractions, one per panel.
        panel_b_vertical: Draw Panel B as columns rather than rows. Follows the
            shape of ``panel_b_rect``, not taste: rows suit a wide short panel,
            columns a narrow tall one.
        note: Why this canvas is the size it is.
    """

    name: str
    suffix: str
    figure_size: tuple[float, float]
    panel_a_rect: tuple[float, float, float, float]
    panel_b_rect: tuple[float, float, float, float]
    panel_a_title_x: float
    panel_b_title_x: float
    letters: tuple[tuple[str, float, float], ...]
    note: str
    panel_b_vertical: bool = False


def _rect(
    left_in: float,
    bottom_in: float,
    width_in: float,
    height_in: float,
    canvas: tuple[float, float],
) -> tuple[float, float, float, float]:
    """Convert a rect in inches to figure fractions.

    The geometry is reasoned about in inches -- gutters hold labels of a known
    physical width -- and matplotlib wants fractions. Doing the division here
    rather than by hand keeps the two from drifting apart when a canvas changes.
    """
    width, height = canvas
    return (left_in / width, bottom_in / height, width_in / width, height_in / height)


# -- Portrait: the published arrangement -------------------------------------
#
#   canvas    7.0 x 8.0 in
#   Panel A   left 0.62 in, bottom 3.30 in, 4.85 x 4.05 in
#   Panel B   left 0.95 in, bottom 0.95 in, 5.20 x 1.45 in
#
# Panel A's left edge is where the plot begins; the 0.62 in to its left holds
# the y tick labels and the rotated axis title. It stops 1.53 in short of the
# right edge, and that gutter is the reason the figure is 7.0 in wide rather
# than narrower: it holds the device labels and two series labels, and a longer
# device name needs the gutter widened, not the type shrunk.
#
# Panel B's left edge leaves 0.95 in for the two domain labels and its right
# edge 0.85 in for the "n = ..." totals; below it sit the axis title and the
# three-swatch pathway key, which is why its bottom is 0.95 in up from the paper
# edge rather than tight against it.
#
# Both panel titles start 0.36 in from the paper edge, immediately right of
# their panel letter, rather than at their own plot's left edge -- which would
# indent Panel A's title by 0.62 in and Panel B's by 0.95 in and leave the two
# titles on different margins for no reason but their gutters.
#
# Change history:
#   2026-09-03  first geometry, at 7.0 x 8.0 in.
_PORTRAIT_CANVAS = (7.0, 8.0)
PORTRAIT = Layout(
    name="portrait",
    suffix="",
    figure_size=_PORTRAIT_CANVAS,
    panel_a_rect=_rect(0.62, 3.30, 4.85, 4.05, _PORTRAIT_CANVAS),
    panel_b_rect=_rect(0.95, 0.95, 5.20, 1.45, _PORTRAIT_CANVAS),
    panel_a_title_x=-(0.62 - 0.36) / 4.85,
    panel_b_title_x=-(0.95 - 0.36) / 5.20,
    letters=(("A", 0.012, 0.988), ("B", 0.012, 0.345)),
    note=(
        "Single CCR manuscript column. Width set by Panel A's 1.53 in gutter, "
        "height by its log axis plus Panel B and its key."
    ),
)

# -- Landscape: panels side by side ------------------------------------------
#
#   canvas    12.0 x 5.5 in
#   Panel A   left 0.62 in, bottom 0.80 in, 4.85 x 4.05 in
#   Panel B   left 7.85 in, bottom 1.30 in, 3.30 x 3.55 in, drawn as COLUMNS
#
# Panel A keeps its portrait plot width of 4.85 in exactly, and this is not
# cosmetic. Its gutter labels are placed in DATA coordinates a fixed number of
# years past the last point, but their text has a fixed physical width, so the
# gutter only stays 1.53 in wide while the axes stay 4.85 in wide over the same
# thirty-two years. Narrow the plot and the labels do not shrink -- they run
# into Panel B. So Panel A occupies 0.62 + 4.85 + 1.53 = 7.00 in, and Panel B's
# block begins there.
#
# Panel B is drawn as columns here rather than as rows. Beside Panel A the space
# is narrow and tall, which is the wrong shape for horizontal bars twice over:
# they leave most of the height empty, and they squeeze radiology's two thin
# segments into the width that is left. At 3.30 in wide, radiology's 1.0 % De
# Novo segment is 0.03 in across. Turned upright in a 3.55 in column it is
# 0.13 in tall -- four times the room, in a panel that now fills its space.
# The bars stay 100 %-normalized, so nothing about the comparison changes.
#
# Panel B's top is aligned with Panel A's top rather than centred against it, so
# both panel letters and both panel titles sit on one line. A reader scans for
# the letters first, and two letters at different heights makes them hunt.
#
# Change history:
#   2026-09-03  first geometry, at 12.0 x 5.5 in, Panel B as rows.
#   2026-09-03  Panel B turned upright; its rect went 3.45 x 1.75 -> 3.30 x 3.55.
_LANDSCAPE_CANVAS = (12.0, 5.5)
LANDSCAPE = Layout(
    name="landscape",
    suffix="_landscape",
    figure_size=_LANDSCAPE_CANVAS,
    panel_a_rect=_rect(0.62, 0.80, 4.85, 4.05, _LANDSCAPE_CANVAS),
    panel_b_rect=_rect(7.85, 1.30, 3.30, 3.55, _LANDSCAPE_CANVAS),
    panel_a_title_x=-(0.62 - 0.36) / 4.85,
    # Panel B's block starts at 7.00 in, so its title starts 0.36 in past that,
    # the same offset from its own letter that Panel A's title has from its own.
    panel_b_title_x=(7.00 + 0.36 - 7.85) / 3.30,
    letters=(("A", 0.012, 0.988), ("B", 7.00 / 12.0, 0.988)),
    panel_b_vertical=True,
    note=(
        "Two panels side by side, for a spread or a slide. Panel A keeps its "
        "portrait plot width so its gutter geometry is unchanged; Panel B is "
        "drawn as columns to use the height."
    ),
)

#: Every layout built on a run. The published portrait is first.
LAYOUTS: tuple[Layout, ...] = (PORTRAIT, LANDSCAPE)

#: Layouts by name, for the command line.
LAYOUTS_BY_NAME: dict[str, Layout] = {layout.name: layout for layout in LAYOUTS}

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
    layout: Layout = PORTRAIT


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


def build_figure(
    data: io.FigureData, layout: Layout = PORTRAIT
) -> tuple[Figure, panel_a.PanelA, panel_b.PanelB]:
    """Draw both panels onto a new figure.

    Args:
        data: Validated input tables.
        layout: Where the panels go. Both layouts draw the same data with the
            same code; only the geometry differs.

    Returns:
        The figure, what Panel A drew, and what Panel B drew.
    """
    figure = plt.figure(figsize=layout.figure_size)
    first = panel_a.draw(
        figure,
        data.cumulative,
        data.authorizations,
        layout.panel_a_rect,
        partial_year=partial_year(data),
        title_x=layout.panel_a_title_x,
    )
    second = panel_b.draw(
        figure,
        data.pathways,
        layout.panel_b_rect,
        title_x=layout.panel_b_title_x,
        vertical=layout.panel_b_vertical,
    )

    # Panel letters: bold serif in ink, and the largest type on the page, per
    # section 2 of ``../../ink_style_guide.md``. They are the only element of
    # the figure that has to be findable before anything is read.
    for letter, x, y in layout.letters:
        figure.text(
            x,
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
    layout: Layout = PORTRAIT,
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
        f"layout           : {layout.name}, {layout.figure_size[0]:g} x {layout.figure_size[1]:g} in",
        f"snapshot through : {data.snapshot_date} (latest decision date in the table)",
        f"year range       : {years[0]}-{years[-1]}",
        f"partial year     : {first.partial_year if first.partial_year else 'none'}",
        f"authorizations   : {len(data.authorizations):,} oncology-certain rows",
        "",
        "The counts are a FLOOR, not an estimate. Every device on the Radiology and",
        "Pathology panels is classified individually against its authorized indication",
        "(config/adjudication/), because FDA's product codes do not separate cancer",
        "reliably in either direction: the cancer-specific codes were created only around",
        "2018-2020, so earlier computer-aided detection sits under generic ones. Devices",
        "that could not be resolved from the published fields are excluded and reported as",
        "a residual band. One row is one AUTHORIZATION, not one cancer-directed",
        "capability: a clearance covering a platform that bundles a cancer feature among",
        "others is not counted. See docs/source-strategy.md before quoting any number.",
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
    layout: Layout = PORTRAIT,
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
    stem = f"{OUTPUT_STEM}{layout.suffix}"
    if tag:
        stem = f"{stem}_{tag}"

    with plt.rc_context(style.rc_params()):
        figure, first, second = build_figure(data, layout)
        figure.canvas.draw()
        margin_in, overflows = measure_margin(figure)
        if overflows:
            plt.close(figure)
            worst = "; ".join(f"{text!r} by {-amount:.3f} in" for text, amount in overflows[:5])
            raise LabelOverflow(
                f"{layout.name}: {len(overflows)} label(s) drawn off the canvas: "
                f"{worst}. Widen the gutter or shorten the label; do not shrink the "
                "type below the ladder in trends.plotting.style."
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
    text = summary_text(data, first, second, tag, margin_in, layout)
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
        layout=layout,
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
    parser.add_argument(
        "--layout",
        default="both",
        choices=("both", *LAYOUTS_BY_NAME),
        help=(
            "which arrangement to build. 'portrait' is the published figure and keeps "
            "the unsuffixed filenames; 'landscape' puts the panels side by side and "
            "writes *_landscape.*. Default builds both, so they cannot drift apart."
        ),
    )
    args = parser.parse_args(argv)

    if args.layout == "both":
        chosen = LAYOUTS
    else:
        chosen = (LAYOUTS_BY_NAME[args.layout],)

    results = [
        build(args.input, args.output, tag=args.tag, layout=layout) for layout in chosen
    ]
    for result in results:
        print(f"[{result.layout.name}] {result.layout.note}")
        for path in (result.pdf, result.png, result.svg, result.summary):
            print(f"  wrote {path}")
        print(f"  least clearance to the paper edge: {result.margin_in:.3f} in")
    print()
    # One number sheet on stdout. The counts are identical across layouts by
    # construction -- same data, same drawing code -- so printing them twice
    # would only invite a reader to look for a difference that cannot exist.
    first = results[0]
    print(summary_text(
        first.data, first.panel_a, first.panel_b, args.tag, first.margin_in, first.layout
    ))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
