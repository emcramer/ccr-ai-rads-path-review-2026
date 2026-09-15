"""Tests for the combined four-panel figure.

This project draws nothing. Every mark on the canvas comes from a panel function
that its own project already tests exhaustively, so re-testing what those panels
draw would only duplicate two suites and slow this one down. What is untested
anywhere else is the composition:

1. the four panels are all there, in one figure, under the right letters;
2. they do not overlap each other, and the left column does not run into the
   right one -- the failure a two-column canvas invites and neither source suite
   can see;
3. the geometry preserves the one physical invariant the clinops panel depends
   on, its 4.85 in plot width;
4. the summary sheet carries the panel-letter map, because two panels changed
   letter and the source projects' docs still use the old ones.

Points 2 and 4 are the ones that would go wrong silently.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import matplotlib
import pytest

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.text import Text  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from clinops.plotting import io as clinops_io  # noqa: E402
from combined import plot  # noqa: E402
from trends.plotting import io as trends_io  # noqa: E402
from trends.plotting import style  # noqa: E402


@pytest.fixture(scope="module")
def drawn(trends_dir: Path, clinops_dir: Path):
    """One rendered figure, built once and measured by several tests."""
    trends_data = trends_io.load_figure_data(trends_dir)
    clinops_data = clinops_io.load_figure_data(clinops_dir)
    with plt.rc_context(style.rc_params()):
        figure, *_ = plot.build_figure(trends_data, clinops_data, plot.WIDE)
        figure.canvas.draw()
        yield figure
        plt.close(figure)


def _texts(figure) -> list[Text]:
    return [
        text
        for text in figure.findobj(Text)
        if text.get_visible() and text.get_text().strip()
    ]


# --------------------------------------------------------------------------
# End to end
# --------------------------------------------------------------------------


def test_build_writes_all_four_outputs(trends_dir: Path, clinops_dir: Path, tmp_path: Path):
    """One command produces the vector, the raster, the editable SVG and the numbers."""
    result = plot.build(
        tmp_path, trends_input=trends_dir, clinops_input=clinops_dir, tag="fixture"
    )
    for path in (result.pdf, result.png, result.svg, result.summary):
        assert path.exists(), f"{path} was not written"
        assert path.stat().st_size > 0
    assert result.pdf.name == "combined_figure_fixture.pdf"


def test_untagged_build_uses_the_plain_stem(
    trends_dir: Path, clinops_dir: Path, tmp_path: Path
):
    """The manuscript includes this figure by name, so the stem must not move."""
    result = plot.build(tmp_path, trends_input=trends_dir, clinops_input=clinops_dir)
    assert result.pdf.name == "combined_figure.pdf"
    assert result.summary.name == "combined_figure_summary.txt"


def test_cli_runs(trends_dir: Path, clinops_dir: Path, tmp_path: Path):
    """The documented command line works, from a cwd that is not the project."""
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "combined.plot",
            "--output",
            str(tmp_path),
            "--trends-input",
            str(trends_dir),
            "--clinops-input",
            str(clinops_dir),
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={"PYTHONPATH": str(SRC), "PATH": "/usr/bin:/bin"},
    )
    assert completed.returncode == 0, completed.stderr
    assert "wrote" in completed.stdout


def test_a_bad_cap_is_refused(trends_dir: Path, clinops_dir: Path, tmp_path: Path):
    """The Panel A cap is passed through, so its validation must be too."""
    with pytest.raises(ValueError, match="top_n"):
        plot.build(tmp_path, trends_input=trends_dir, clinops_input=clinops_dir, top_n=0)


def test_a_malformed_table_stops_the_build(clinops_dir: Path, tmp_path: Path):
    """A missing input raises rather than drawing three panels and a hole."""
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(trends_io.SchemaError):
        plot.build(tmp_path, trends_input=empty, clinops_input=clinops_dir)


# --------------------------------------------------------------------------
# The composition -- what no other suite can see
# --------------------------------------------------------------------------


def test_all_four_panels_are_drawn(drawn):
    """Four panels means four sets of axes, not three and an empty rectangle.

    Panel A draws a matrix and a bar axes per theme block, Panel B two stacked
    plots, and Panels C and D one each, so the count is a floor rather than an
    equality: what matters is that every panel's rect got axes in it.
    """
    assert len(drawn.axes) >= 4
    for name in ("panel_a_rect", "panel_b_rect", "panel_c_rect", "panel_d_rect"):
        rect = getattr(plot.WIDE, name)
        left, bottom, width, height = rect
        inside = [
            ax
            for ax in drawn.axes
            if left - 1e-6 <= ax.get_position().x0
            and ax.get_position().x1 <= left + width + 1e-6
            and bottom - 1e-6 <= ax.get_position().y0
            and ax.get_position().y1 <= bottom + height + 1e-6
        ]
        assert inside, f"{name} has no axes in it"


def test_the_panel_letters_are_a_b_c_d(drawn):
    """Exactly four letters, and they read A, B, C, D.

    Two of these panels were called something else in the figure they came from.
    A stale letter here is a legend that points at the wrong picture.
    """
    letters = [
        text.get_text()
        for text in _texts(drawn)
        if text.get_text() in {"A", "B", "C", "D"}
        and text.get_fontsize() == style.FS_PANEL_LETTER
    ]
    assert sorted(letters) == ["A", "B", "C", "D"]


def test_the_top_two_letters_share_a_line(drawn):
    """A and C are the line a reader enters the figure on.

    B and D are deliberately staggered -- see the geometry note in ``plot`` --
    but the top pair is not, and nothing about a later height change may quietly
    break that.
    """
    letters = {
        text.get_text(): text.get_position()[1]
        for text in _texts(drawn)
        if text.get_text() in {"A", "C"} and text.get_fontsize() == style.FS_PANEL_LETTER
    }
    assert letters["A"] == pytest.approx(letters["C"])


def test_no_two_panels_overlap():
    """The four rects are disjoint.

    Pure geometry, so it needs no draw: an overlap here would put one panel's
    axes on top of another's and the figure would still render.
    """
    rects = [
        ("A", plot.WIDE.panel_a_rect),
        ("B", plot.WIDE.panel_b_rect),
        ("C", plot.WIDE.panel_c_rect),
        ("D", plot.WIDE.panel_d_rect),
    ]
    for index, (name, first) in enumerate(rects):
        for other_name, second in rects[index + 1 :]:
            overlap_x = min(first[0] + first[2], second[0] + second[2]) - max(
                first[0], second[0]
            )
            overlap_y = min(first[1] + first[3], second[1] + second[3]) - max(
                first[1], second[1]
            )
            assert overlap_x <= 0 or overlap_y <= 0, f"{name} and {other_name} overlap"


def test_no_label_runs_off_the_canvas(drawn):
    """Every label is measured against the paper, as the clinops build measures its own."""
    from clinops import plot as clinops_plot

    margin_in, overflows = clinops_plot.measure_margin(drawn)
    assert not overflows, overflows[:5]
    assert margin_in > 0


def test_no_left_column_label_crosses_the_gutter(drawn):
    """Trends Panel B labels its lines directly, and those labels point at Panel C.

    This is the failure a two-column canvas invites and that neither source suite
    can see: a longer series name grows that gutter sideways into the next panel,
    where it renders on top of it and nothing complains.
    """
    boundary = plot.WIDE.panel_c_rect[0] * plot.WIDE.figure_size[0] - 0.62
    clearance, crossings = plot.measure_gutter(drawn, boundary)
    assert not crossings, crossings[:5]
    assert clearance > 0.1, f"only {clearance:.3f} in of gutter left"


def test_panel_c_keeps_its_native_plot_width():
    """Clinops Panel A's 4.85 in plot width is a physical invariant, not a preference.

    Its nine device labels are placed in DATA coordinates while their text has a
    fixed physical width, so the gutter only stays 1.53 in wide while the axes
    stay 4.85 in over the same span of years. Its own suite pins this across its
    two layouts; this figure is a third canvas and has to honour it too.
    """
    width_in = plot.WIDE.panel_c_rect[2] * plot.WIDE.figure_size[0]
    assert width_in == pytest.approx(4.85, abs=1e-6)


def test_panel_d_keeps_its_native_bar_width():
    """Panel D's rect width is the portrait's, so its 'n = ...' totals land where they fit."""
    width_in = plot.WIDE.panel_d_rect[2] * plot.WIDE.figure_size[0]
    assert width_in == pytest.approx(5.20, abs=1e-6)


def test_the_left_column_is_the_trends_figure_untouched():
    """Panels A and B are trends.plot's own rects, in inches, at offset zero.

    If the trends figure moves its geometry, this figure should move with it
    rather than quietly keep drawing the old arrangement.
    """
    from trends import plot as trends_plot

    canvas = plot.WIDE.figure_size
    trends_canvas = trends_plot.FIGURE_SIZE
    for ours, theirs in (
        (plot.WIDE.panel_a_rect, trends_plot._PANEL_A_RECT),
        (plot.WIDE.panel_b_rect, trends_plot._PANEL_B_RECT),
    ):
        for index, axis in enumerate((0, 1, 0, 1)):
            here = ours[index] * canvas[axis]
            there = theirs[index] * trends_canvas[axis]
            assert here == pytest.approx(there, abs=0.002), (
                f"component {index}: {here:.3f} in here against {there:.3f} in "
                "in trends.plot -- the sibling's geometry moved"
            )


# --------------------------------------------------------------------------
# The summary sheet
# --------------------------------------------------------------------------


def test_the_summary_maps_every_letter_to_its_source(
    trends_dir: Path, clinops_dir: Path, tmp_path: Path
):
    """Two panels changed letter. The sheet must say which, or a legend will lie."""
    result = plot.build(tmp_path, trends_input=trends_dir, clinops_input=clinops_dir)
    text = result.summary.read_text(encoding="utf-8")
    for letter, project, _ in plot.PANEL_SOURCES:
        assert project in text
    assert "PANEL LETTERS" in text
    assert "trends-figure" in text and "clinical-operations" in text


def test_the_summary_warns_that_the_populations_differ(
    trends_dir: Path, clinops_dir: Path, tmp_path: Path
):
    """Merging four panels with three denominators onto one float is the new hazard."""
    result = plot.build(tmp_path, trends_input=trends_dir, clinops_input=clinops_dir)
    text = result.summary.read_text(encoding="utf-8")
    assert "THREE DIFFERENT POPULATIONS" in text
    assert "may be quoted against another" in text


def test_the_summary_carries_both_projects_own_numbers(
    trends_dir: Path, clinops_dir: Path, tmp_path: Path
):
    """The body is the siblings' own sheets, so every number traces to its pipeline."""
    result = plot.build(tmp_path, trends_input=trends_dir, clinops_input=clinops_dir)
    text = result.summary.read_text(encoding="utf-8")
    assert "Trends figure — numbers for the legend" in text
    assert "Clinical operations figure — numbers for the legend" in text
    # The clinops sheet reports the canvas it was drawn on, which is this one.
    assert "wide, 14.6 x 10 in" in text


# --------------------------------------------------------------------------
# Style, per ../AGENTS.md
# --------------------------------------------------------------------------


def test_the_figure_is_drawn_in_ibm_plex(drawn):
    """Proof the vendored faces loaded and matplotlib substituted nothing.

    ``style`` raises at import if a face is missing, but that check is about the
    files on disk. This one is about the figure: both generic families the rc
    context installs must resolve to a vendored file, because matplotlib's own
    failure mode is to warn once and render the whole page in DejaVu Sans.
    """
    from matplotlib import font_manager

    assert plt.rcParams["font.sans-serif"][0] == style.SANS
    assert plt.rcParams["font.serif"][0] == style.SERIF
    for generic in ("sans-serif", "serif"):
        for weight in ("normal", "bold"):
            resolved = Path(
                font_manager.findfont(
                    font_manager.FontProperties(
                        family=plt.rcParams[f"font.{generic}"][0], weight=weight
                    )
                )
            )
            assert resolved.name.startswith("IBMPlex"), f"{generic}/{weight} -> {resolved}"

    # And the figure actually asks for them: the panel letters are serif, per
    # section 2 of ../ink_style_guide.md, and everything else follows the rc
    # default rather than naming a family of its own.
    letters = [
        text
        for text in _texts(drawn)
        if text.get_text() in {"A", "B", "C", "D"}
        and text.get_fontsize() == style.FS_PANEL_LETTER
    ]
    assert len(letters) == 4
    for letter in letters:
        assert letter.get_fontfamily() == ["serif"]
        assert letter.get_fontweight() == "bold"
        assert letter.get_color() == style.INK


def test_the_panel_letters_are_the_largest_type_on_the_page(drawn):
    """Section 2 of ../ink_style_guide.md. With four of them it matters more, not less."""
    sizes = [text.get_fontsize() for text in _texts(drawn)]
    assert max(sizes) == style.FS_PANEL_LETTER


# --------------------------------------------------------------------------
# The real tables
# --------------------------------------------------------------------------


def test_the_real_figure_has_no_collisions(real_inputs, tmp_path: Path):
    """The fixtures are smaller than the corpus, and label collisions follow the data.

    The published figure is drawn from ``data/processed``, so that is what has to
    be measured. Both guards are inside ``build``; this asserts it was actually
    run against the real tables and came back clean.
    """
    trends_input, clinops_input = real_inputs
    result = plot.build(
        tmp_path,
        trends_input=trends_input,
        clinops_input=clinops_input,
        stale_ok=True,
    )
    assert result.margin_in > 0
    assert result.gutter_in > 0.1
