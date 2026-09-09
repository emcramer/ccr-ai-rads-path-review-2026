"""Figure layouts.

The figure is published portrait and also built landscape, panels side by side.
Both come from one run over one set of tables, so they cannot disagree about a
number -- but they can disagree about geometry, and one geometry constraint is
subtle enough to be worth a test of its own.

Panel A's gutter labels are placed in DATA coordinates a fixed number of years
past the last point, while their text has a fixed PHYSICAL width. The gutter is
therefore only 1.53 in wide while Panel A's axes are 4.85 in wide over the same
thirty-two years. Narrowing Panel A in the landscape layout would not shrink the
labels; it would push them into Panel B. That invariant is not visible in either
rect on its own, so it is asserted here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from clinops import plot
from clinops.plot import LANDSCAPE, LAYOUTS, PORTRAIT, Layout

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"


def inches(rect: tuple[float, float, float, float], canvas: tuple[float, float]):
    """Convert a figure-fraction rect back to (left, bottom, width, height) inches."""
    width, height = canvas
    return (rect[0] * width, rect[1] * height, rect[2] * width, rect[3] * height)


# --------------------------------------------------------------------------
# The layout table
# --------------------------------------------------------------------------


def test_portrait_keeps_the_unsuffixed_filenames():
    """The manuscript includes `clinical_operations.pdf` by name.

    Giving the published layout a suffix would silently break the LaTeX include
    and leave the old file in place, which builds cleanly and is out of date.
    """
    assert PORTRAIT.suffix == ""
    assert LAYOUTS[0] is PORTRAIT


def test_every_layout_has_a_distinct_name_and_suffix():
    names = [layout.name for layout in LAYOUTS]
    suffixes = [layout.suffix for layout in LAYOUTS]
    assert len(set(names)) == len(names)
    assert len(set(suffixes)) == len(suffixes)


@pytest.mark.parametrize("layout", LAYOUTS, ids=lambda layout: layout.name)
def test_both_panels_fit_on_their_canvas(layout: Layout):
    """A rect running off the canvas draws a panel that is silently clipped."""
    for name, rect in (("A", layout.panel_a_rect), ("B", layout.panel_b_rect)):
        left, bottom, width, height = rect
        assert 0.0 <= left < 1.0, f"{layout.name} panel {name}: left {left}"
        assert 0.0 <= bottom < 1.0, f"{layout.name} panel {name}: bottom {bottom}"
        assert left + width <= 1.0, f"{layout.name} panel {name} runs off the right"
        assert bottom + height <= 1.0, f"{layout.name} panel {name} runs off the top"


@pytest.mark.parametrize("layout", LAYOUTS, ids=lambda layout: layout.name)
def test_the_panels_do_not_overlap(layout: Layout):
    """Portrait stacks them; landscape puts them side by side. Neither overlaps."""
    a_left, a_bottom, a_width, a_height = inches(layout.panel_a_rect, layout.figure_size)
    b_left, b_bottom, b_width, b_height = inches(layout.panel_b_rect, layout.figure_size)
    horizontally_clear = a_left + a_width <= b_left or b_left + b_width <= a_left
    vertically_clear = a_bottom + a_height <= b_bottom or b_bottom + b_height <= a_bottom
    assert horizontally_clear or vertically_clear, (
        f"{layout.name}: Panel A and Panel B overlap"
    )


def test_panel_a_keeps_its_plot_width_across_layouts():
    """The gutter invariant, and the reason the landscape canvas is 12 in wide.

    Panel A's gutter labels sit at a fixed number of YEARS past the last point
    but have a fixed PHYSICAL width. They only clear Panel B while Panel A's
    axes span the same inches over the same years. If a future edit narrows
    Panel A to save canvas, the labels do not follow -- they run into Panel B,
    and `measure_margin` will not catch it because they are still on the paper.
    """
    portrait_width = inches(PORTRAIT.panel_a_rect, PORTRAIT.figure_size)[2]
    landscape_width = inches(LANDSCAPE.panel_a_rect, LANDSCAPE.figure_size)[2]
    assert landscape_width == pytest.approx(portrait_width, abs=0.01), (
        f"Panel A is {landscape_width:.2f} in wide in landscape against "
        f"{portrait_width:.2f} in portrait. Its gutter labels are placed in data "
        "coordinates with a fixed physical width, so changing the plot width moves "
        "them relative to Panel B. Keep the width and change the canvas."
    )


def test_landscape_leaves_the_gutter_clear_of_panel_b():
    """Panel B must begin past Panel A's plot *and* its label gutter."""
    a_left, _, a_width, _ = inches(LANDSCAPE.panel_a_rect, LANDSCAPE.figure_size)
    b_left, _, _, _ = inches(LANDSCAPE.panel_b_rect, LANDSCAPE.figure_size)
    gutter_in = 1.53  # measured; see the geometry comment in plot.py
    assert b_left >= a_left + a_width + gutter_in, (
        f"Panel B's plot starts at {b_left:.2f} in, but Panel A's gutter runs to "
        f"{a_left + a_width + gutter_in:.2f} in. The device labels would overlap it."
    )


def test_landscape_aligns_both_panel_letters():
    """A reader scans for the letters first; two heights makes them hunt."""
    heights = {y for _, _, y in LANDSCAPE.letters}
    assert len(heights) == 1, f"landscape panel letters sit at {sorted(heights)}"


# --------------------------------------------------------------------------
# Building
# --------------------------------------------------------------------------


@pytest.mark.skipif(
    not (FIXTURES / "authorizations.csv").exists(), reason="no plotting fixtures"
)
@pytest.mark.parametrize("layout", LAYOUTS, ids=lambda layout: layout.name)
def test_each_layout_builds_without_a_label_running_off(tmp_path, layout: Layout):
    """`build` raises LabelOverflow rather than printing half a label."""
    result = plot.build(FIXTURES, tmp_path, tag="test", layout=layout)
    for path in (result.pdf, result.png, result.svg, result.summary):
        assert path.exists(), f"{layout.name}: {path.name} not written"
    assert result.margin_in > 0, f"{layout.name}: a label reached the paper edge"
    assert result.layout is layout


@pytest.mark.skipif(
    not (FIXTURES / "authorizations.csv").exists(), reason="no plotting fixtures"
)
def test_the_two_layouts_write_different_files(tmp_path):
    """Same stem would mean the second build silently overwrote the first."""
    written = set()
    for layout in LAYOUTS:
        result = plot.build(FIXTURES, tmp_path, layout=layout)
        assert result.pdf not in written, f"{layout.name} overwrote an earlier layout"
        written.add(result.pdf)
    assert len(written) == len(LAYOUTS)


@pytest.mark.skipif(
    not (FIXTURES / "authorizations.csv").exists(), reason="no plotting fixtures"
)
def test_the_layouts_report_the_same_counts(tmp_path):
    """Geometry may differ between layouts. Numbers may not.

    Both are drawn from one set of tables by one code path, so a disagreement
    here would mean a layout is filtering or reordering data, which is the one
    way an alternative arrangement could become a second, wrong figure.
    """
    summaries = {}
    for layout in LAYOUTS:
        result = plot.build(FIXTURES, tmp_path, layout=layout)
        summaries[layout.name] = result.summary.read_text(encoding="utf-8")

    def counts(text: str) -> list[str]:
        # Drop the header lines that legitimately differ: the layout name and
        # the measured margin. Everything else must match verbatim.
        return [
            line
            for line in text.splitlines()
            if not line.startswith(("layout", "Least clearance"))
        ]

    reference = counts(summaries[LAYOUTS[0].name])
    for name, text in summaries.items():
        assert counts(text) == reference, f"{name} reports different numbers"


# --------------------------------------------------------------------------
# Panel B's orientation
# --------------------------------------------------------------------------


def test_orientation_follows_the_shape_of_the_panel():
    """Rows for a wide short panel, columns for a narrow tall one.

    This is the rule the orientation flag encodes, and it is worth asserting
    because the flag is a boolean sitting next to a rect: nothing else stops
    someone setting one without the other and drawing two rows in a column of
    space.
    """
    for layout in LAYOUTS:
        _, _, width_in, height_in = inches(layout.panel_b_rect, layout.figure_size)
        landscape_shaped = width_in > height_in
        assert layout.panel_b_vertical is not landscape_shaped, (
            f"{layout.name}: Panel B is {width_in:.2f} x {height_in:.2f} in and "
            f"panel_b_vertical={layout.panel_b_vertical}. Columns belong in a panel "
            "taller than it is wide, rows in one wider than it is tall."
        )


@pytest.mark.skipif(
    not (FIXTURES / "authorizations.csv").exists(), reason="no plotting fixtures"
)
def test_both_orientations_draw_the_same_segments(tmp_path):
    """Turning the bars upright must not change what they say.

    One code path draws both, with the stacked and categorical directions mapped
    onto x and y differently. A divergence here would mean the mapping is
    dropping or reordering a segment.
    """
    drawn = {}
    for layout in LAYOUTS:
        result = plot.build(FIXTURES, tmp_path, layout=layout)
        drawn[layout.name] = (
            [
                (s.domain, s.pathway, s.count, round(s.share, 9))
                for s in result.panel_b.segments
            ],
            result.panel_b.totals,
        )
    reference = drawn[LAYOUTS[0].name]
    for name, value in drawn.items():
        assert value == reference, f"{name}: Panel B drew different segments"


@pytest.mark.skipif(
    not (FIXTURES / "authorizations.csv").exists(), reason="no plotting fixtures"
)
def test_turning_the_bars_upright_gives_the_thin_segments_more_room(tmp_path):
    """The reason for the column layout, stated as a measurement.

    Radiology's De Novo segment is about 1 % of its bar. Horizontally, in a
    3.3 in panel, that is a third of a tenth of an inch. Vertically, in a 3.55 in
    column, it is the same fraction of a taller span. If a future edit makes the
    landscape Panel B short and wide again, the column layout stops buying
    anything and this says so.
    """
    spans = {}
    for layout in LAYOUTS:
        _, _, width_in, height_in = inches(layout.panel_b_rect, layout.figure_size)
        spans[layout.name] = height_in if layout.panel_b_vertical else width_in
    assert spans["landscape"] > spans["portrait"] * 0.6, (
        "the landscape Panel B's stacked span has collapsed relative to portrait; "
        f"{spans}. A 1 % segment needs the span to stay legible."
    )
