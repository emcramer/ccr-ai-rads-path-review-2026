"""Draw the two sibling figures onto one four-panel canvas.

The module reads the processed tables of ``../trends-figure`` and
``../clinical-operations`` through those projects' own loaders, calls their four
panel functions into four rectangles of one figure, and writes a PDF, a PNG, an
SVG and a summary sheet. It classifies nothing, filters nothing, aggregates
nothing, and re-implements no panel. The only thing it decides is where the four
panels go and what letters they carry.

Command line::

    PYTHONPATH=src python -m combined.plot --output figures/

Alongside the figure it writes a summary text file holding the numbers the figure
legend needs, so nobody has to read them off the picture. That file is the two
siblings' own summary sheets, concatenated under a panel-letter map, because a
number quoted in the merged legend must still trace to the pipeline that
computed it.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (backend must be set first)
from matplotlib.figure import Figure  # noqa: E402

from clinops import plot as clinops_plot  # noqa: E402
from clinops.plotting import io as clinops_io  # noqa: E402
from clinops.plotting import panel_a as clinops_a  # noqa: E402
from clinops.plotting import panel_b as clinops_b  # noqa: E402
from trends import classify as trends_classify  # noqa: E402
from trends import plot as trends_plot  # noqa: E402
from trends.plotting import io as trends_io  # noqa: E402
from trends.plotting import panel_a as trends_a  # noqa: E402
from trends.plotting import panel_b as trends_b  # noqa: E402
from trends.plotting import style  # noqa: E402

#: Base name of the output files, before the optional tag.
OUTPUT_STEM = "combined_figure"

#: This file is ``<project>/src/combined/plot.py``; the sibling projects sit
#: beside ``<project>``. Resolved from the module rather than from the working
#: directory, so the build gives the same figure from any cwd -- the trap the
#: trends staleness guard falls into with its ``Path("config")``.
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
FIGURES_ROOT: Path = PROJECT_ROOT.parent

TRENDS_ROOT: Path = FIGURES_ROOT / "trends-figure"
CLINOPS_ROOT: Path = FIGURES_ROOT / "clinical-operations"

DEFAULT_TRENDS_INPUT: Path = TRENDS_ROOT / "data" / "processed"
DEFAULT_CLINOPS_INPUT: Path = CLINOPS_ROOT / "data" / "processed"
DEFAULT_TRENDS_CONFIG: Path = TRENDS_ROOT / "config"

#: Which project each panel letter came from, and what it was called there. The
#: summary sheet prints this, because the two source projects still build their
#: own two-panel figures and their docs still say "Panel A" and "Panel B" -- so
#: without a map, four of the eight panel references in this repository point at
#: the wrong picture.
PANEL_SOURCES: tuple[tuple[str, str, str], ...] = (
    ("A", "trends-figure", "Panel A — modality combinations by theme"),
    ("B", "trends-figure", "Panel B — theme volume over time"),
    ("C", "clinical-operations", "Panel A — cumulative oncology AI authorizations"),
    ("D", "clinical-operations", "Panel B — authorization pathway"),
)


@dataclass(frozen=True)
class Layout:
    """One arrangement of the four panels on a canvas.

    Every geometry field is a figure fraction, because that is what matplotlib
    takes, but each is written below as the inches it stands for. Read the
    inches; the fractions are arithmetic.

    ``name`` and ``figure_size`` are not decoration: :func:`clinops.plot.summary_text`
    reads exactly those two attributes off its ``layout`` argument, so this class
    stands in for ``clinops.plot.Layout`` there and the clinops number sheet needs
    no fork to report the canvas it was actually drawn on.

    Attributes:
        name: Human name, used in the summary sheet.
        suffix: Appended to :data:`OUTPUT_STEM`.
        figure_size: Canvas, in inches.
        panel_a_rect: Trends Panel A (the UpSet matrix), figure fractions.
        panel_b_rect: Trends Panel B (the two stacked line plots).
        panel_c_rect: Clinical-operations Panel A (the cumulative log plot).
        panel_d_rect: Clinical-operations Panel B (the pathway bars).
        panel_c_title_x: Panel C's title offset, in axes fractions.
        panel_d_title_x: Panel D's title offset, in axes fractions.
        letters: ``(letter, x, y)`` in figure fractions, one per panel.
        panel_d_vertical: Draw Panel D as columns rather than rows.
        note: Why this canvas is the size it is.
    """

    name: str
    suffix: str
    figure_size: tuple[float, float]
    panel_a_rect: tuple[float, float, float, float]
    panel_b_rect: tuple[float, float, float, float]
    panel_c_rect: tuple[float, float, float, float]
    panel_d_rect: tuple[float, float, float, float]
    panel_c_title_x: float
    panel_d_title_x: float
    letters: tuple[tuple[str, float, float], ...]
    note: str
    panel_d_vertical: bool = False


def _rect(
    left_in: float,
    bottom_in: float,
    width_in: float,
    height_in: float,
    canvas: tuple[float, float],
) -> tuple[float, float, float, float]:
    """Convert a rect in inches to figure fractions.

    Lifted from ``clinops.plot``. The geometry is reasoned about in inches --
    gutters hold labels of a known physical width -- and matplotlib wants
    fractions. Doing the division here rather than by hand keeps the two from
    drifting apart when a canvas changes.
    """
    width, height = canvas
    return (left_in / width, bottom_in / height, width_in / width, height_in / height)


# -- Wide: the two source figures side by side, at their native widths ---------
#
#   canvas    14.6 x 10.0 in
#   Panel A   left 1.44 in, bottom 4.968 in, 5.895 x 4.922 in   (trends, native)
#   Panel B   left 0.72 in, bottom 0.414 in, 5.295 x 4.184 in   (trends, native)
#   Panel C   left 8.42 in, bottom 4.200 in, 4.850 x 5.200 in   (clinops, native width)
#   Panel D   left 8.75 in, bottom 1.400 in, 5.200 x 1.900 in   (clinops, native width)
#
# EVERY WIDTH AND EVERY LEFT EDGE IS ITS SOURCE FIGURE'S OWN, in inches,
# translated. The left column is ``trends.plot``'s 7.5 x 10.0 canvas at offset
# (0, 0), rect for rect. The right column is ``clinops.plot.PORTRAIT``'s
# geometry translated by 7.80 in horizontally, with only the two heights changed
# -- see "The right column's heights" below. So no panel is rescaled
# horizontally, no panel draws narrower than the figure it came from, and
# neither sibling had to be touched.
#
# Why the canvas is wide rather than a page. Stacked at native geometry the four
# panels need 4.92 + 4.18 + 4.05 + 1.45 = 14.6 in of panel height against about
# 9.5 in on a printed page, and none of the three tall panels can move sideways
# to recover it: each needs 6.8-7.0 in of width, and those widths are floors
# rather than preferences. Trends Panel A's thirteen columns per block sit at
# 0.102 in against ``trends.plotting.panel_a.MIN_COLUMN_WIDTH_IN`` of 0.085, and
# its fifteen-row pitch of 13.2 pt is pinned by its own test suite. Clinops Panel
# A places its nine device labels in DATA coordinates while their text has a
# fixed physical width, so its 4.85 in plot width is an invariant that project
# tests in two places.
#
# Fitting a page would therefore mean reversing two decisions argued at length in
# the sibling DECISIONS logs -- trends Panel B's direct end-of-line labels, and
# the clinops device gutter whose whole point is that nine devices are namable.
# Author's decision, 2026-09-09: do not. AACR redraws every figure from the
# author's sketch (``CCR_reviews/Editor_instructions.md`` section 4) and the
# five-float limit counts items, not area, so a wide canvas costs nothing here
# and no content is cut. See ``docs/DECISIONS.md``.
#
# The 7.80 in column offset. Trends Panel A's right edge is at 7.335 in and
# Panel B's end-of-line labels reach about 7.50 in, so the clinops block starts
# at 7.80 for a 0.30 in inter-column gutter, which :func:`measure_gutter`
# measures on every build. The canvas width is then set from the right: the
# furthest label is Panel C's "Detection and assessment (radiology)" at 14.38 in,
# so 14.6 leaves about 0.2 in. A longer device or series label needs the canvas
# widened, not the type shrunk.
#
# The right column's heights. Clinops is an 8 in figure in a 10 in column, and
# at its native heights that surplus lands as a 2.4 in block of white below
# Panel D -- the whole bottom-right corner of the figure empty. So the two right
# panels grow into it instead: Panel C from 4.05 to 5.20 in and Panel D from 1.45
# to 1.90 in, with Panel D moved down to close the gap. Only heights change.
# Panel C's WIDTH is the invariant its own project tests, because its device
# labels are placed in data coordinates against fixed-width text; its height is
# free, and giving it more of it spreads those nine labels further apart than the
# source figure manages. Panel D's two bars simply get thicker.
#
# The cost, and it is a real one: letter D no longer sits on letter B's line.
# ``clinops.plot.LANDSCAPE`` aligns its two letters and says why -- a reader
# scans for the letters first. That argument is kept where it counts, at the top:
# A and C are both at 9.95 in, which is the line a reader enters the figure on.
# Below that the two columns hold different numbers of panels at different
# heights, so B at 4.79 in and D at 3.66 in are staggered. Rendered both ways on
# 2026-09-09; the staggered pair reads as two columns, and the aligned pair read
# as an unfinished corner. Author's decision.
#
# Panel D keeps the horizontal-bar form. ``clinops.plot.LANDSCAPE`` turns that
# panel upright because it puts it in a 3.30 x 3.55 in slot where rows would
# waste the height and crush radiology's thin segments. Here the slot is wide and
# short, as in the portrait, so the portrait's own orientation is right.
#
# Change history:
#   2026-09-09  first geometry, at 15.0 x 10.0 in, right column at native heights.
#   2026-09-09  right column grown into its slack; canvas 15.0 -> 14.6 in.
#               Panel C 4.05 -> 5.20 in tall, Panel D 1.45 -> 1.90 in and moved
#               down. Letters B and D no longer share a line.
_WIDE_CANVAS = (14.6, 10.0)
_CLINOPS_DX = 7.80
_PANEL_C_BOTTOM, _PANEL_C_HEIGHT = 4.20, 5.20
_PANEL_D_BOTTOM, _PANEL_D_HEIGHT = 1.40, 1.90
WIDE = Layout(
    name="wide",
    suffix="",
    figure_size=_WIDE_CANVAS,
    panel_a_rect=_rect(1.440, 4.968, 5.895, 4.922, _WIDE_CANVAS),
    panel_b_rect=_rect(0.720, 0.414, 5.295, 4.184, _WIDE_CANVAS),
    panel_c_rect=_rect(
        0.62 + _CLINOPS_DX, _PANEL_C_BOTTOM, 4.85, _PANEL_C_HEIGHT, _WIDE_CANVAS
    ),
    panel_d_rect=_rect(
        0.95 + _CLINOPS_DX, _PANEL_D_BOTTOM, 5.20, _PANEL_D_HEIGHT, _WIDE_CANVAS
    ),
    # The portrait's own title offsets, unchanged. They put each title 0.36 in
    # right of its own block's left edge, and because the clinops block is
    # translated horizontally by one vector and these depend only on the widths,
    # which did not change, "0.36 in past the block edge" still resolves to 0.36
    # in past the panel letter here. Recomputing them gives the same two numbers.
    panel_c_title_x=-(0.62 - 0.36) / 4.85,
    panel_d_title_x=-(0.95 - 0.36) / 5.20,
    # Letters sit 0.36 in above their own panel's top edge, which is where the
    # source figures put them, except A and C: those are pinned to 9.95 in so
    # they share the line a reader enters the figure on.
    letters=(
        ("A", 0.090 / 14.6, 9.950 / 10.0),
        ("B", 0.090 / 14.6, 4.790 / 10.0),
        ("C", (0.084 + _CLINOPS_DX) / 14.6, 9.950 / 10.0),
        (
            "D",
            (0.084 + _CLINOPS_DX) / 14.6,
            (_PANEL_D_BOTTOM + _PANEL_D_HEIGHT + 0.36) / 10.0,
        ),
    ),
    note=(
        "The two source figures side by side, every panel at its native width. "
        "Wide rather than page-fit so that nothing is cut; AACR redraws from the "
        "sketch and the float limit counts items, not area."
    ),
)

#: Every layout built on a run.
LAYOUTS: tuple[Layout, ...] = (WIDE,)

#: Layouts by name, for the command line.
LAYOUTS_BY_NAME: dict[str, Layout] = {layout.name: layout for layout in LAYOUTS}


class StaleInputs(RuntimeError):
    """Raised when the trends tables were built from configs that have since changed."""


class LabelOverflow(RuntimeError):
    """A label was drawn outside the canvas.

    Raised rather than warned, for the reason ``clinops.plot.LabelOverflow``
    gives: a label that runs off the paper still renders, printing half of
    itself, which is a figure that is wrong in a way nobody notices.
    """


@dataclass(frozen=True)
class BuildResult:
    """What one figure build produced.

    Attributes:
        pdf: Path of the vector output.
        png: Path of the raster output.
        svg: Path of the editable vector output.
        summary: Path of the text summary of legend numbers.
        trends_data: The validated trends tables, as its own loader returned them.
        clinops_data: The validated clinical-operations tables, likewise.
        tails: Panel A's per-theme account of what its cap hid.
        series: What Panel B's two stacked plots drew.
        cumulative: What Panel C drew.
        pathway: What Panel D drew.
        margin_in: Least clearance between any label and the paper edge, in
            inches, measured on the rendered canvas.
        gutter_in: Least clearance between any left-column label and the right
            column's left edge, in inches.
        top_n: The cap that was applied to Panel A.
        scale: The Panel A bar scale that was drawn.
        layout: The geometry that was used.
    """

    pdf: Path
    png: Path
    svg: Path
    summary: Path
    trends_data: trends_io.FigureData
    clinops_data: clinops_io.FigureData
    tails: list[trends_a.TailSummary]
    series: trends_b.PanelB
    cumulative: clinops_a.PanelA
    pathway: clinops_b.PanelB
    margin_in: float
    gutter_in: float
    top_n: int
    scale: str
    layout: Layout = WIDE


def _refuse_if_stale(input_dir: str | Path, config_dir: str | Path, stale_ok: bool) -> None:
    """Refuse to draw from labels the current trends configuration would not produce.

    ``trends.plot`` runs this check too, but through a private helper that
    resolves its configuration as ``Path("config")`` -- relative to the working
    directory, which is the trends project only when the build is run from
    inside it. Calling :func:`trends.classify.check_freshness` here with an
    absolute path keeps the guard and drops the assumption, rather than reaching
    into the sibling's private function or quietly going without.

    A directory with no run manifest is skipped, exactly as the sibling skips it:
    the synthetic tables have none, and a missing manifest is the classifier's
    own ``--check`` to report.

    The clinical-operations project has no equivalent ledger, so nothing is
    checked on that side.
    """
    directory = Path(input_dir)
    if not (directory / "run_manifest.json").exists():
        return
    freshness = trends_classify.check_freshness(directory, Path(config_dir))
    if not freshness.problems or stale_ok:
        return
    problems = "\n  - ".join(freshness.problems)
    raise StaleInputs(
        f"{directory} was built from a configuration that has since changed:\n"
        f"  - {problems}\n"
        "Re-run trends.classify before drawing, or pass stale_ok=True "
        "(--stale-ok) if you know the drawing is a deliberate look at old labels."
    )


def measure_gutter(figure: Figure, boundary_in: float) -> tuple[float, list[tuple[str, float]]]:
    """Measure the left column's labels against the right column's left edge.

    ``clinops.plot.measure_margin`` measures every label against the paper edge,
    which catches a label that runs off the page but says nothing about one that
    runs into the panel beside it. On a two-column canvas that is the more likely
    failure: trends Panel B labels its lines directly, in a gutter whose width
    depends on how long the series names happen to be, and a longer name grows
    that gutter toward Panel C rather than toward the paper edge.

    Args:
        figure: A figure that has already been drawn once, so the renderer knows
            where its text landed.
        boundary_in: The right column's left edge, in inches from the left of the
            canvas.

    Returns:
        The least clearance between any left-of-boundary label and the boundary,
        in inches -- negative if something crossed it -- and the labels that
        crossed, worst first.
    """
    from matplotlib.text import Text

    renderer = figure.canvas.get_renderer()
    dpi = figure.dpi
    clearance = boundary_in
    crossings: list[tuple[str, float]] = []
    for text in figure.findobj(Text):
        if not text.get_visible() or not text.get_text().strip():
            continue
        box = text.get_window_extent(renderer)
        # A label belongs to the left column if it STARTS left of the boundary.
        # Right-column labels legitimately live past it, and the panel letters C
        # and D sit exactly on it.
        if box.x0 / dpi >= boundary_in:
            continue
        gap = boundary_in - box.x1 / dpi
        clearance = min(clearance, gap)
        if gap < 0:
            crossings.append((text.get_text().replace("\n", " / "), gap))
    crossings.sort(key=lambda item: item[1])
    return clearance, crossings


def build_figure(
    trends_data: trends_io.FigureData,
    clinops_data: clinops_io.FigureData,
    layout: Layout = WIDE,
    top_n: int = trends_a.DEFAULT_TOP_N,
    scale: str = trends_a.DEFAULT_BAR_SCALE,
) -> tuple[
    Figure,
    list[trends_a.TailSummary],
    trends_b.PanelB,
    clinops_a.PanelA,
    clinops_b.PanelB,
]:
    """Draw all four panels onto a new figure.

    Args:
        trends_data: Validated trends tables.
        clinops_data: Validated clinical-operations tables.
        layout: Where the panels go.
        top_n: Combinations drawn per theme in Panel A.
        scale: Panel A bar scale, ``"count"`` or ``"share"``.

    Returns:
        The figure and the four panel records, in letter order.
    """
    figure = plt.figure(figsize=layout.figure_size)
    tails = trends_a.draw(
        figure, trends_data.combinations, layout.panel_a_rect, top_n=top_n, scale=scale
    )
    series = trends_b.draw(figure, trends_data.theme_years, layout.panel_b_rect)
    cumulative = clinops_a.draw(
        figure,
        clinops_data.cumulative,
        clinops_data.authorizations,
        layout.panel_c_rect,
        partial_year=clinops_plot.partial_year(clinops_data),
        title_x=layout.panel_c_title_x,
    )
    pathway = clinops_b.draw(
        figure,
        clinops_data.pathways,
        layout.panel_d_rect,
        title_x=layout.panel_d_title_x,
        vertical=layout.panel_d_vertical,
    )

    # Panel letters: bold serif in ink, and the largest type on the page, per
    # section 2 of ``../ink_style_guide.md``. They are the only element of the
    # figure that has to be findable before anything is read -- which is more
    # true here than on either source figure, because there are now four of them
    # and two of them changed letter.
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
    return figure, tails, series, cumulative, pathway


def summary_text(
    result_parts: tuple[
        trends_io.FigureData,
        clinops_io.FigureData,
        list[trends_a.TailSummary],
        trends_b.PanelB,
        clinops_a.PanelA,
        clinops_b.PanelB,
    ],
    tag: str | None,
    margin_in: float,
    gutter_in: float,
    top_n: int,
    scale: str,
    layout: Layout = WIDE,
) -> str:
    """Compose the numbers the merged figure legend needs, as plain text.

    The body is the two source projects' own summary sheets, called unchanged and
    concatenated. Nothing is recomputed here, because a number recomputed in a
    third place is a number that can disagree with the table it came from.
    """
    trends_data, clinops_data, tails, series, cumulative, pathway = result_parts

    lines = [
        "Combined figure — numbers for the legend",
        f"tag              : {tag or '(none)'}",
        f"layout           : {layout.name}, "
        f"{layout.figure_size[0]:g} x {layout.figure_size[1]:g} in",
        "",
        "PANEL LETTERS. Two of these panels changed letter when the figures were",
        "merged. The source projects still build their own two-panel figures and",
        "their docs still say Panel A and Panel B, so read this map before quoting",
        "anything out of them:",
        "",
        f"  {'here':<6}{'source project':<24}{'called there'}",
    ]
    for letter, project, source_name in PANEL_SOURCES:
        lines.append(f"  {letter:<6}{project:<24}{source_name}")
    lines += [
        "",
        f"  A, B drawn from : {trends_data.source}",
        f"  C, D drawn from : {clinops_data.source}",
        "",
        "THE FOUR PANELS CARRY THREE DIFFERENT POPULATIONS, and no number from one",
        "may be quoted against another:",
        "",
        "  A     primary research only, papers",
        "  B     all article types including reviews and perspectives, papers",
        "  C, D  FDA authorizations — devices, not papers, and a floor, not an estimate",
        "",
        "Each source project already warned about the two denominators inside it.",
        "Merging makes that warning load-bearing: A and B differ in population, and",
        "C and D are not papers at all.",
        "",
        f"Least clearance between any label and the paper edge : {margin_in:.3f} in",
        f"Least clearance between a left-column label and the",
        f"right column's left edge                             : {gutter_in:.3f} in",
        "",
        "=" * 74,
        "PANELS A AND B — from ../trends-figure, verbatim from trends.plot.summary_text",
        "Its 'Panel A' is this figure's A; its 'Panel B' is this figure's B.",
        "=" * 74,
        "",
        trends_plot.summary_text(trends_data, tails, top_n, tag, scale, series),
        "=" * 74,
        "PANELS C AND D — from ../clinical-operations, verbatim from",
        "clinops.plot.summary_text. Its 'Panel A' is this figure's C; its 'Panel B'",
        "is this figure's D. Its clearance line is measured on THIS canvas.",
        "=" * 74,
        "",
        clinops_plot.summary_text(clinops_data, cumulative, pathway, tag, margin_in, layout),
    ]
    return "\n".join(lines)


def build(
    output_dir: str | Path,
    trends_input: str | Path = DEFAULT_TRENDS_INPUT,
    clinops_input: str | Path = DEFAULT_CLINOPS_INPUT,
    trends_config: str | Path = DEFAULT_TRENDS_CONFIG,
    tag: str | None = None,
    layout: Layout = WIDE,
    top_n: int = trends_a.DEFAULT_TOP_N,
    scale: str = trends_a.DEFAULT_BAR_SCALE,
    stale_ok: bool = False,
) -> BuildResult:
    """Read both projects' tables, draw the figure, and write PDF, PNG, SVG, and summary.

    Args:
        output_dir: Directory the outputs are written to; created if absent.
        trends_input: Directory holding the trends project's processed CSVs.
        clinops_input: Directory holding the clinical-operations CSVs.
        trends_config: The trends configuration directory, for the freshness check.
        tag: Optional suffix, so a draft built from stand-in fixtures cannot be
            mistaken for one built from the real tables.
        layout: Where the panels go.
        top_n: Combinations drawn per theme in Panel A.
        scale: Panel A bar scale, ``"count"`` or ``"share"``.
        stale_ok: Draw even if the trends tables predate a configuration change.

    Returns:
        A :class:`BuildResult` naming what was written.

    Raises:
        trends_io.SchemaError: If a trends input table is missing or malformed.
        clinops_io.SchemaError: If a clinical-operations table is missing,
            malformed, or disagrees with another.
        StaleInputs: If the trends tables predate a configuration change.
        LabelOverflow: If any label was drawn off the canvas or across the
            column gutter.
        ValueError: If ``top_n`` is not positive.
    """
    if top_n < 1:
        raise ValueError(f"top_n must be at least 1, got {top_n}")
    _refuse_if_stale(trends_input, trends_config, stale_ok)
    trends_data = trends_io.load_figure_data(trends_input)
    clinops_data = clinops_io.load_figure_data(clinops_input)

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    stem = f"{OUTPUT_STEM}{layout.suffix}"
    if tag:
        stem = f"{stem}_{tag}"

    boundary_in = layout.panel_c_rect[0] * layout.figure_size[0] - 0.62

    with plt.rc_context(style.rc_params()):
        figure, tails, series, cumulative, pathway = build_figure(
            trends_data, clinops_data, layout, top_n=top_n, scale=scale
        )
        figure.canvas.draw()
        margin_in, overflows = clinops_plot.measure_margin(figure)
        gutter_in, crossings = measure_gutter(figure, boundary_in)
        if overflows or crossings:
            plt.close(figure)
            problems = []
            if overflows:
                worst = "; ".join(f"{text!r} by {-amount:.3f} in" for text, amount in overflows[:5])
                problems.append(f"{len(overflows)} label(s) drawn off the canvas: {worst}")
            if crossings:
                worst = "; ".join(f"{text!r} by {-amount:.3f} in" for text, amount in crossings[:5])
                problems.append(
                    f"{len(crossings)} left-column label(s) crossed the column gutter "
                    f"at {boundary_in:.2f} in: {worst}"
                )
            raise LabelOverflow(
                f"{layout.name}: "
                + "; and ".join(problems)
                + ". Widen the canvas or the column gutter; do not shrink the type "
                "below the ladder in trends.plotting.style."
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
    text = summary_text(
        (trends_data, clinops_data, tails, series, cumulative, pathway),
        tag,
        margin_in,
        gutter_in,
        top_n,
        scale,
        layout,
    )
    summary.write_text(text, encoding="utf-8")
    return BuildResult(
        pdf=pdf,
        png=png,
        svg=svg,
        summary=summary,
        trends_data=trends_data,
        clinops_data=clinops_data,
        tails=tails,
        series=series,
        cumulative=cumulative,
        pathway=pathway,
        margin_in=margin_in,
        gutter_in=gutter_in,
        top_n=top_n,
        scale=scale,
        layout=layout,
    )


def main(argv: list[str] | None = None) -> int:
    """Command line entry point."""
    parser = argparse.ArgumentParser(
        prog="python -m combined.plot",
        description=(
            "Draw the trends figure and the clinical-operations figure onto one "
            "four-panel canvas, so they cost one manuscript float instead of two."
        ),
    )
    parser.add_argument(
        "--output", default="figures/", help="directory for the PDF, PNG and SVG"
    )
    parser.add_argument(
        "--trends-input",
        default=str(DEFAULT_TRENDS_INPUT),
        help="directory holding the trends project's processed CSVs",
    )
    parser.add_argument(
        "--clinops-input",
        default=str(DEFAULT_CLINOPS_INPUT),
        help="directory holding the clinical-operations processed CSVs",
    )
    parser.add_argument(
        "--trends-config",
        default=str(DEFAULT_TRENDS_CONFIG),
        help="the trends configuration directory, for the staleness check",
    )
    parser.add_argument(
        "--tag", default=None, help="suffix for the output file names, e.g. 'fixture'"
    )
    parser.add_argument(
        "--layout",
        default=WIDE.name,
        choices=tuple(LAYOUTS_BY_NAME),
        help="which arrangement to build",
    )
    parser.add_argument(
        "--stale-ok",
        action="store_true",
        help="draw even if the trends tables were built from configs that have since changed",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=trends_a.DEFAULT_TOP_N,
        help=f"modality combinations drawn per theme in Panel A (default {trends_a.DEFAULT_TOP_N})",
    )
    parser.add_argument(
        "--panel-a-scale",
        choices=trends_a.BAR_SCALES,
        default=trends_a.DEFAULT_BAR_SCALE,
        help=(
            "Panel A bar scale, passed straight through to the trends panel "
            f"(default {trends_a.DEFAULT_BAR_SCALE})"
        ),
    )
    args = parser.parse_args(argv)

    result = build(
        args.output,
        trends_input=args.trends_input,
        clinops_input=args.clinops_input,
        trends_config=args.trends_config,
        tag=args.tag,
        layout=LAYOUTS_BY_NAME[args.layout],
        top_n=args.top_n,
        scale=args.panel_a_scale,
        stale_ok=args.stale_ok,
    )
    print(f"[{result.layout.name}] {result.layout.note}")
    for path in (result.pdf, result.png, result.svg, result.summary):
        print(f"  wrote {path}")
    print(f"  least clearance to the paper edge   : {result.margin_in:.3f} in")
    print(f"  least clearance across the gutter   : {result.gutter_in:.3f} in")
    print()
    print(
        summary_text(
            (
                result.trends_data,
                result.clinops_data,
                result.tails,
                result.series,
                result.cumulative,
                result.pathway,
            ),
            args.tag,
            result.margin_in,
            result.gutter_in,
            result.top_n,
            result.scale,
            result.layout,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
