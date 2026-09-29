"""Tests for the trends figure plotting code.

Three things are worth proving before the real corpus exists:

1. the module runs end to end on the synthetic tables and writes both files;
2. a malformed input table stops the run loudly, rather than producing a figure
   that looks finished and is wrong;
3. a theme with no papers lays out instead of crashing, because the real corpus
   may well hand us one;
4. Panel B's split survives the real numbers. The measured series is in
   ``fixtures/plot_theme_year_counts_measured.csv``, copied from the corpus run;
   the tests below hold the drawing to it, because a split-scale panel that reads
   well on invented data and misleads on real data is worse than no split at all.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import matplotlib.colors as mcolors
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trends import plot  # noqa: E402
from trends.plotting import io, panel_a, panel_b, style, synthetic  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def synthetic_dir(tmp_path_factory) -> Path:
    """A small synthetic corpus, generated once for the whole module."""
    target = tmp_path_factory.mktemp("synthetic")
    synthetic.write(target, seed=7, n_papers=400)
    return target


@pytest.fixture()
def minimal_dir(tmp_path: Path) -> Path:
    """A hand-written pair of tables, copied to a scratch directory."""
    for name, fixture in (
        (io.COMBINATION_COUNTS, "plot_combination_counts_minimal.csv"),
        (io.THEME_YEAR_COUNTS, "plot_theme_year_counts_minimal.csv"),
    ):
        shutil.copy(FIXTURES / fixture, tmp_path / name)
    return tmp_path


@pytest.fixture()
def four_digit_dir(tmp_path: Path) -> Path:
    """Tables at the real corpus's order of magnitude.

    The real multimodal block draws four-digit counts in thirteen columns, which
    is what forces the bar labels on end. The synthetic stand-in is too small to
    exercise that, so this fixture carries the magnitude instead.
    """
    rows = ["theme,modality_set,n_modalities,n_papers,rank_in_theme"]
    sets = [
        "mri", "other", "ct", "ultrasound", "genomics+mri", "he_histology",
        "genomics", "clinical_data+ct", "clinical_data+mri",
        "genomics+he_histology", "ct+pet", "ct+genomics", "pet", "xray",
        "mammography",
    ]
    for theme in style.THEME_ORDER:
        for rank, modality_set in enumerate(sets, start=1):
            n_modalities = modality_set.count("+") + 1
            rows.append(
                f"{theme},{modality_set},{n_modalities},{2000 - rank * 100},{rank}"
            )
    (tmp_path / io.COMBINATION_COUNTS).write_text("\n".join(rows) + "\n")
    shutil.copy(
        FIXTURES / "plot_theme_year_counts_minimal.csv", tmp_path / io.THEME_YEAR_COUNTS
    )
    return tmp_path


@pytest.fixture()
def measured_dir(tmp_path: Path) -> Path:
    """The real per-year counts, as the corpus run produced them.

    See the fixture's own header. Every series in it is measured.
    """
    shutil.copy(
        FIXTURES / "plot_combination_counts_measured.csv", tmp_path / io.COMBINATION_COUNTS
    )
    shutil.copy(
        FIXTURES / "plot_theme_year_counts_measured.csv", tmp_path / io.THEME_YEAR_COUNTS
    )
    return tmp_path


# --------------------------------------------------------------------------
# End to end
# --------------------------------------------------------------------------


def test_synthetic_generator_matches_the_schema(synthetic_dir: Path) -> None:
    """Every table the generator writes passes the reader's own validation."""
    data = io.load_figure_data(synthetic_dir)
    assert data.n_papers_total is not None and data.n_papers_total > 0
    assert set(data.combinations["theme"]).issubset(set(plot.style.THEME_ORDER))


def test_generated_files_announce_that_they_are_synthetic(synthetic_dir: Path) -> None:
    """Nobody should be able to mistake the stand-in tables for the real corpus."""
    assert "SYNTHETIC" in (synthetic_dir / "README.md").read_text()
    assert "seed" in (synthetic_dir / "MANIFEST.txt").read_text()
    for name in (io.COMBINATION_COUNTS, io.THEME_YEAR_COUNTS, io.PAPER_LABELS):
        first_line = (synthetic_dir / name).read_text().splitlines()[0]
        assert first_line.startswith("#") and "SYNTHETIC" in first_line


def test_generator_is_deterministic(tmp_path: Path) -> None:
    """The recorded seed reproduces the same tables."""
    first = synthetic.generate(seed=99, n_papers=300)
    second = synthetic.generate(seed=99, n_papers=300)
    for name in first:
        pd.testing.assert_frame_equal(first[name], second[name])


def test_build_writes_pdf_and_png(synthetic_dir: Path, tmp_path: Path) -> None:
    """The documented command produces both output files."""
    result = plot.build(synthetic_dir, tmp_path / "figures", tag="synthetic")
    assert result.pdf.exists() and result.pdf.stat().st_size > 0
    assert result.png.exists() and result.png.stat().st_size > 0
    assert result.pdf.name == "trends_figure_synthetic.pdf"
    assert result.png.name == "trends_figure_synthetic.png"


def test_build_writes_the_legend_numbers(synthetic_dir: Path, tmp_path: Path) -> None:
    """The summary records what the top-N cap hid, for each theme."""
    result = plot.build(synthetic_dir, tmp_path / "figures", tag="synthetic")
    text = result.summary.read_text()
    for theme in plot.style.PANEL_A_THEMES:
        assert theme in text
    # Four blocks, not five: virtual staining went to Panel B only.
    assert len(result.tails) == len(plot.style.PANEL_A_THEMES) == 4
    assert "virtual_staining" not in {tail.theme for tail in result.tails}
    for tail in result.tails:
        assert tail.shown_papers + tail.remainder_papers == tail.total_papers


def test_untagged_build_uses_the_plain_stem(minimal_dir: Path, tmp_path: Path) -> None:
    """Without a tag the outputs take the names the figure spec asks for."""
    result = plot.build(minimal_dir, tmp_path / "figures")
    assert result.pdf.name == "trends_figure.pdf"
    assert result.png.name == "trends_figure.png"


def test_cli_runs(synthetic_dir: Path, tmp_path: Path) -> None:
    """The command line entry point works with the documented arguments."""
    destination = tmp_path / "figures"
    exit_code = plot.main(
        ["--input", str(synthetic_dir), "--output", str(destination), "--tag", "synthetic"]
    )
    assert exit_code == 0
    assert (destination / "trends_figure_synthetic.png").exists()


# --------------------------------------------------------------------------
# Malformed input must fail loudly
# --------------------------------------------------------------------------


def test_missing_directory_raises(tmp_path: Path) -> None:
    with pytest.raises(io.SchemaError, match="input directory does not exist"):
        io.load_figure_data(tmp_path / "nowhere")


def test_missing_table_raises(minimal_dir: Path) -> None:
    (minimal_dir / io.THEME_YEAR_COUNTS).unlink()
    with pytest.raises(io.SchemaError, match="required input table is missing"):
        io.load_figure_data(minimal_dir)


def test_missing_column_raises(tmp_path: Path) -> None:
    shutil.copy(
        FIXTURES / "plot_combination_counts_malformed.csv", tmp_path / io.COMBINATION_COUNTS
    )
    shutil.copy(
        FIXTURES / "plot_theme_year_counts_minimal.csv", tmp_path / io.THEME_YEAR_COUNTS
    )
    with pytest.raises(io.SchemaError, match="missing required column"):
        io.load_figure_data(tmp_path)


def test_non_numeric_count_raises(minimal_dir: Path) -> None:
    path = minimal_dir / io.COMBINATION_COUNTS
    path.write_text(path.read_text().replace(",12,1\n", ",many,1\n"))
    with pytest.raises(io.SchemaError, match="must be integer"):
        io.load_figure_data(minimal_dir)


def test_unknown_theme_raises(minimal_dir: Path) -> None:
    path = minimal_dir / io.COMBINATION_COUNTS
    path.write_text(path.read_text().replace("digital_twins", "digital_twinz"))
    with pytest.raises(io.SchemaError, match="unknown value"):
        io.load_figure_data(minimal_dir)


def test_unknown_modality_raises(minimal_dir: Path) -> None:
    path = minimal_dir / io.COMBINATION_COUNTS
    path.write_text(path.read_text().replace("ct+pet", "ct+spect"))
    with pytest.raises(io.SchemaError, match="unknown modality"):
        io.load_figure_data(minimal_dir)


def test_negative_count_raises(minimal_dir: Path) -> None:
    path = minimal_dir / io.COMBINATION_COUNTS
    path.write_text(path.read_text().replace(",1,12,1\n", ",1,-12,1\n"))
    with pytest.raises(io.SchemaError, match="must be >= 0"):
        io.load_figure_data(minimal_dir)


def test_duplicate_combination_row_raises(minimal_dir: Path) -> None:
    path = minimal_dir / io.COMBINATION_COUNTS
    path.write_text(path.read_text() + "digital_twins,other,1,3,2\n")
    with pytest.raises(io.SchemaError, match="repeated"):
        io.load_figure_data(minimal_dir)


def test_two_partial_years_raise(minimal_dir: Path) -> None:
    path = minimal_dir / io.THEME_YEAR_COUNTS
    path.write_text(path.read_text().replace("foundation_models,all,2025,19,0", "foundation_models,all,2025,19,1"))
    with pytest.raises(io.SchemaError, match="more than one year is flagged partial"):
        io.load_figure_data(minimal_dir)


def test_empty_table_raises(minimal_dir: Path) -> None:
    (minimal_dir / io.COMBINATION_COUNTS).write_text(
        "theme,modality_set,n_modalities,n_papers,rank_in_theme\n"
    )
    with pytest.raises(io.SchemaError, match="no rows"):
        io.load_figure_data(minimal_dir)


def test_bad_top_n_raises(minimal_dir: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="top_n must be at least 1"):
        plot.build(minimal_dir, tmp_path / "figures", top_n=0)


# --------------------------------------------------------------------------
# A theme with no papers
# --------------------------------------------------------------------------


def test_theme_with_no_papers_still_lays_out(minimal_dir: Path, tmp_path: Path) -> None:
    """Digital Twins may come back empty. The block must draw, not crash."""
    for name in (io.COMBINATION_COUNTS, io.THEME_YEAR_COUNTS):
        path = minimal_dir / name
        rows = [
            line
            for line in path.read_text().splitlines()
            if not line.startswith("digital_twins")
        ]
        path.write_text("\n".join(rows) + "\n")

    result = plot.build(minimal_dir, tmp_path / "figures", tag="empty-theme")
    assert result.png.exists() and result.png.stat().st_size > 0
    assert result.pdf.exists() and result.pdf.stat().st_size > 0

    empty = [tail for tail in result.tails if tail.theme == "digital_twins"]
    assert len(empty) == 1
    assert empty[0].total_papers == 0
    assert empty[0].shown_sets == 0
    assert empty[0].remainder_share == 0.0
    assert empty[0].draws_remainder is False


def test_every_theme_empty_still_lays_out(minimal_dir: Path, tmp_path: Path) -> None:
    """The degenerate case: one theme, one combination, one year."""
    (minimal_dir / io.COMBINATION_COUNTS).write_text(
        "theme,modality_set,n_modalities,n_papers,rank_in_theme\n"
        "foundation_models,other,1,1,1\n"
    )
    (minimal_dir / io.THEME_YEAR_COUNTS).write_text(
        "theme,domain,year,n_papers,partial_year\n" "foundation_models,all,2026,1,1\n"
    )
    result = plot.build(minimal_dir, tmp_path / "figures", tag="degenerate")
    assert result.png.exists()


def test_cap_larger_than_the_data_draws_no_remainder_column(
    minimal_dir: Path, tmp_path: Path
) -> None:
    """A cap above the number of combinations leaves only undrawable sets for the remainder.

    A set containing ``other`` has no row in the matrix, so it always joins the
    remainder; nothing else does once the cap exceeds the combination count.
    """
    result = plot.build(minimal_dir, tmp_path / "figures", top_n=50)
    combinations = pd.read_csv(minimal_dir / "combination_counts.csv", comment="#")
    for tail in result.tails:
        block = combinations.loc[combinations["theme"] == tail.theme]
        undrawable = block.loc[block["modality_set"].str.split("+").map(lambda k: "other" in k)]
        assert tail.remainder_sets == len(undrawable)
        assert tail.remainder_papers == int(undrawable["n_papers"].sum())
        assert tail.draws_remainder is (len(undrawable) > 0)


def test_the_matrix_has_no_other_row_and_never_draws_an_other_set(measured_dir: Path) -> None:
    """Author's ruling, 2026-09-29: Other is not a row of Panel A."""
    assert "other" not in panel_a.MATRIX_ROWS
    assert len(panel_a.MATRIX_ROWS) == len(style.MODALITY_ORDER) - 1
    combinations = pd.read_csv(measured_dir / "combination_counts.csv", comment="#")
    for theme in style.PANEL_A_THEMES:
        drawn = panel_a._block_frame(combinations, theme, panel_a.DEFAULT_TOP_N)
        assert not drawn["modality_set"].astype(str).str.contains("other").any(), theme


def test_default_cap_matches_the_specification() -> None:
    """The spec asks for twelve combination columns and then a remainder column."""
    assert panel_a.DEFAULT_TOP_N == 12


# --------------------------------------------------------------------------
# Panel A bar scale
#
# The scale is selectable because the choice between "one shared count axis"
# and "each theme against its own denominator" should be made by looking at the
# real tables. Both are honest; the tests below hold both to that standard.
# --------------------------------------------------------------------------


def test_default_scale_is_share() -> None:
    """A plain rebuild must produce the Panel A the author chose.

    Measured on the real corpus, a shared count axis is set by the multimodal
    remainder bar and both small themes draw as hairlines. See DECISIONS.md,
    2026-09-02. Flipping this constant back would silently ship the other panel.
    """
    assert panel_a.DEFAULT_BAR_SCALE == "share"
    assert panel_a.BAR_SCALES == ("count", "share")


def test_share_scale_builds(synthetic_dir: Path, tmp_path: Path) -> None:
    """The share scale draws end to end and records itself in the result."""
    result = plot.build(synthetic_dir, tmp_path, tag="share", scale="share")
    assert result.pdf.exists() and result.png.exists()
    assert result.scale == "share"


def test_share_scale_does_not_change_the_tail_numbers(
    synthetic_dir: Path, tmp_path: Path
) -> None:
    """The scale is a drawing choice; it must not touch what the cap hid."""
    counted = plot.build(synthetic_dir, tmp_path, tag="c", scale="count")
    shared = plot.build(synthetic_dir, tmp_path, tag="s", scale="share")
    assert [t.total_papers for t in counted.tails] == [t.total_papers for t in shared.tails]
    assert [t.remainder_papers for t in counted.tails] == [
        t.remainder_papers for t in shared.tails
    ]


def test_summary_names_the_scale(synthetic_dir: Path, tmp_path: Path) -> None:
    """A reader of the summary must be able to tell which axis was drawn."""
    result = plot.build(synthetic_dir, tmp_path, tag="s", scale="share")
    assert "share" in result.summary.read_text()
    counted = plot.build(synthetic_dir, tmp_path, tag="c", scale="count")
    assert "count" in counted.summary.read_text()


def test_unknown_scale_raises(minimal_dir: Path, tmp_path: Path) -> None:
    """A typo must stop the run rather than silently drawing counts."""
    with pytest.raises(ValueError, match="scale must be one of"):
        plot.build(minimal_dir, tmp_path, scale="log")


def test_share_bars_are_fractions_of_their_own_theme(
    synthetic_dir: Path, tmp_path: Path
) -> None:
    """Each block's bars must sum to one: the remainder column carries the rest."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = io.load_figure_data(synthetic_dir)
    figure, tails, _ = plot.build_figure(data, scale="share")
    # The four bar axes are the group that shares a bottom edge and height and
    # runs bottom-up from zero; the matrix axes share a row of their own and are
    # drawn with an inverted y axis, and Panel B is alone in its group.
    groups: dict[tuple[float, float], list] = {}
    for ax in figure.axes:
        box = ax.get_position()
        groups.setdefault((round(box.y0, 4), round(box.height, 4)), []).append(ax)
    bar_axes = next(
        group
        for group in groups.values()
        if len(group) == len(tails) and group[0].get_ylim()[0] == 0
    )
    for ax, tail in zip(bar_axes, tails):
        drawn = sum(patch.get_height() for patch in ax.patches)
        if tail.total_papers == 0:
            expected = 0.0
        elif tail.draws_remainder:
            expected = 1.0
        else:
            expected = tail.shown_papers / tail.total_papers
        assert drawn <= 1.0 + 1e-9
        assert abs(drawn - expected) < 1e-9
    plt.close(figure)


# --------------------------------------------------------------------------
# Panel B: two stacked plots
#
# Panel B is split because the measured themes differ by two orders of
# magnitude. The split earns its keep only if the reader cannot mistake the
# lower plot for a continuation of the upper, and only if the two features the
# review's argument rests on survive the drawing: pathology's seven consecutive
# zero years, and the fact that radiology's 13, 9, 21 is a noisy series and not
# a story. These tests are written against the measured numbers.
# --------------------------------------------------------------------------


def _panel(directory: Path):
    """Build the figure once and return the figure and its Panel B record."""
    import matplotlib
    matplotlib.use("Agg")

    data = io.load_figure_data(directory)
    figure, _, panel = plot.build_figure(data)
    return figure, panel


def test_measured_fixture_holds_the_real_clinical_series(measured_dir: Path) -> None:
    """The fixture is the series the author measured, not an approximation of it."""
    frame = io.load_figure_data(measured_dir).theme_years
    clinical = frame.loc[frame["theme"] == "clinical_fda"].sort_values(["domain", "year"])
    radiology = clinical.loc[clinical["domain"] == "radiology", "n_papers"].tolist()
    pathology = clinical.loc[clinical["domain"] == "pathology", "n_papers"].tolist()
    # These are the partitioned series: `radiology` now means radiologic and NOT
    # pathologic, so the three cross-specialty papers that used to be counted on
    # both lines are on neither. The radiology tail moved from 13, 9, 21 to
    # 13, 8, 19 when the partition landed on 2026-09-02.
    assert radiology == [0, 0, 1, 2, 1, 3, 2, 6, 5, 13, 8, 19]
    assert pathology == [0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 4, 6]
    assert sum(radiology) == 60 and sum(pathology) == 13
    cross = clinical.loc[clinical["domain"] == "both", "n_papers"]
    assert cross.sum() == 3


def test_the_domain_rows_partition_every_theme(measured_dir: Path) -> None:
    """radiology + pathology + both + none == all, per theme and year.

    This is the property the legend has to explain: the two split lines of a
    theme do NOT sum to it, because cross-specialty and no-domain papers are
    counted apart. A drawing that assumed otherwise would overstate every
    domain, so the shape is pinned here rather than trusted.
    """
    frame = io.load_figure_data(measured_dir).theme_years
    wide = frame.pivot_table(
        index=["theme", "year"], columns="domain", values="n_papers", aggfunc="sum"
    ).fillna(0)
    split = wide[["radiology", "pathology", "both", "none"]].sum(axis=1)
    assert (split == wide["all"]).all(), "the domain rows must partition the theme"
    # And the property that makes the legend necessary.
    pairs = wide[["radiology", "pathology"]].sum(axis=1)
    assert (pairs < wide["all"]).any(), "some theme must lose papers to both/none"


def test_virtual_staining_is_drawn_undivided_because_it_is_pathologic(
    measured_dir: Path,
) -> None:
    """Nearly every paper is pathologic, so a three-way split would say nothing.

    The totals are read from the table rather than written here: the theme was
    65 papers at themes v8 and 76 at v7, and a literal would have made this test
    assert a superseded corpus instead of the property it is named for.
    """
    frame = io.load_figure_data(measured_dir).theme_years
    theme = frame.loc[frame["theme"] == "virtual_staining"]
    totals = theme.groupby("domain")["n_papers"].sum()
    assert totals["all"] > 0
    assert totals["pathology"] / totals["all"] > 0.9, (
        "the theme is drawn undivided because it is overwhelmingly pathologic"
    )
    assert totals["radiology"] == 0 and totals["both"] == 0
    series = theme.loc[theme["domain"] == "all"].sort_values("year")["n_papers"].tolist()
    pathology_series = (
        theme.loc[theme["domain"] == "pathology"].sort_values("year")["n_papers"].tolist()
    )
    # The v7 row was 76 papers reading [0, 0, 0, 0, 2, 3, 2, 4, 6, 13, 24, 22]; the
    # v8 repair removed the biomarker-status papers, moving the shape as well as
    # the total. This test is named for the undivided-drawing property, so it
    # asserts that property rather than a snapshot of one corpus: the pathology
    # series tracks the whole theme year by year, differing only where the single
    # non-pathologic paper falls.
    assert sum(series) > 0
    assert all(p <= a for p, a in zip(pathology_series, series))
    assert sum(series) - sum(pathology_series) <= 1, (
        "at most one paper in the theme is not pathologic"
    )
    assert ("virtual_staining", "all") in panel_b.LOWER_SERIES


def test_panel_b_draws_two_plots(measured_dir: Path) -> None:
    """The specification asks for two stacked plots, not one."""
    import matplotlib.pyplot as plt

    figure, panel = _panel(measured_dir)
    assert panel.upper is not None and panel.lower is not None
    upper, lower = panel.upper.get_position(), panel.lower.get_position()
    assert upper.y0 > lower.y1, "the plots must not overlap"
    assert abs(upper.x0 - lower.x0) < 1e-9 and abs(upper.width - lower.width) < 1e-9
    plt.close(figure)


def test_panel_b_puts_each_series_in_the_plot_the_spec_names(measured_dir: Path) -> None:
    """Foundation and multimodal above; digital twins and both clinical lines below."""
    frame = io.load_figure_data(measured_dir).theme_years
    upper, lower = panel_b._partition(frame)
    assert upper == [
        ("foundation_models", "radiology"),
        ("foundation_models", "pathology"),
        ("foundation_models", "both"),
        ("multimodal_integration", "radiology"),
        ("multimodal_integration", "pathology"),
        ("multimodal_integration", "both"),
    ]
    assert lower == [
        ("digital_twins", "all"),
        ("virtual_staining", "all"),
        ("agentic_ai", "all"),
        ("clinical_fda", "radiology"),
        ("clinical_fda", "pathology"),
    ]
    assert len(upper) + len(lower) == len(panel_b._SERIES_ORDER)


def test_a_series_the_spec_does_not_name_is_not_drawn(measured_dir: Path) -> None:
    """The table carries every (theme, domain) pair; the figure draws a subset.

    This used to be a fallback that appended any unrecognised pair to the lower
    plot, which on the full table would have added a dozen or more lines nobody
    asked for, silently. It is a filter now.

    The expected pair count is derived, not written down: a theme was added on
    2026-09-02 and another on 2026-09-03, and a literal here would have to be
    edited each time -- which is how a guard quietly stops guarding.
    """
    frame = io.load_figure_data(measured_dir).theme_years
    present = set(map(tuple, frame[["theme", "domain"]].drop_duplicates().to_numpy()))
    expected = len(style.THEME_ORDER) * len(style.DOMAIN_VALUES)
    assert len(present) == expected, "the table carries every combination by design"
    upper, lower = panel_b._partition(frame)
    drawn = set(upper) | set(lower)
    assert len(drawn) == len(panel_b._SERIES_ORDER)
    # The rows deliberately left undrawn, named so the intent is not mistaken
    # for an oversight: every "all" and "none" row, and the clinical theme's
    # three cross-specialty papers, which the spec does not draw.
    assert ("clinical_fda", "both") in present and ("clinical_fda", "both") not in drawn
    assert ("foundation_models", "all") in present
    assert ("foundation_models", "all") not in drawn
    assert not any(domain == "none" for _, domain in drawn)


def test_an_unknown_theme_raises_rather_than_drawing_silently(measured_dir: Path) -> None:
    """A moved canonical key is a bug, not a data variation."""
    path = measured_dir / io.THEME_YEAR_COUNTS
    path.write_text(path.read_text() + "quantum_pathology,all,2024,4,0\n")
    frame = pd.read_csv(path, comment="#")
    with pytest.raises(panel_b.UnknownTheme) as raised:
        panel_b._partition(frame)
    assert "quantum_pathology" in str(raised.value)


def test_the_two_scales_are_far_apart_and_the_ratio_is_reported(measured_dir: Path) -> None:
    """On the measured numbers the lower axis is at least an order finer."""
    import matplotlib.pyplot as plt

    figure, panel = _panel(measured_dir)
    assert panel.scale_ratio is not None and panel.scale_ratio > 10
    upper_span = panel.upper.get_ylim()[1] - panel.upper.get_ylim()[0]
    lower_span = panel.lower.get_ylim()[1] - panel.lower.get_ylim()[0]
    assert abs(panel.scale_ratio - upper_span / lower_span) < 1e-9
    plt.close(figure)


def test_the_lower_plots_whole_range_is_drawn_on_the_upper_plot(measured_dir: Path) -> None:
    """The band and its rule are what stop the reader joining the two axes."""
    import matplotlib.pyplot as plt

    figure, panel = _panel(measured_dir)
    lower_top = panel.lower.get_ylim()[1]
    rules = [
        line
        for line in panel.upper.get_lines()
        if len(line.get_ydata()) and set(map(float, line.get_ydata())) == {lower_top}
    ]
    assert rules, "the upper plot must carry a rule at the lower plot's ceiling"
    plt.close(figure)


def test_both_plots_carry_their_own_y_axis_label(measured_dir: Path) -> None:
    """Each plot is labeled, so the tick numbers cannot be read as one axis."""
    import matplotlib.pyplot as plt

    figure, panel = _panel(measured_dir)
    for ax in panel.axes:
        assert ax.get_ylabel() == "# of papers"
        assert len(ax.get_yticklabels()) > 1
    plt.close(figure)


def test_the_x_axis_is_shared_and_labeled_once(measured_dir: Path) -> None:
    """One x axis under the pair: the lower plot carries it, the upper does not."""
    import matplotlib.pyplot as plt

    figure, panel = _panel(measured_dir)
    assert panel.lower.get_xlabel() == "Publication year"
    assert panel.upper.get_xlabel() == ""
    assert [t.get_text() for t in panel.upper.get_xticklabels()] == [""] * 12
    assert [t.get_text() for t in panel.lower.get_xticklabels()][0] == "2015"
    assert panel.upper.get_xlim() == panel.lower.get_xlim()
    plt.close(figure)


def test_the_zero_run_is_found_but_left_to_the_legend(measured_dir: Path) -> None:
    """Style guide section 6: the artwork names elements, it does not explain them.

    "Pathology: 0 papers in every year from 2015 to 2021" was an explanation, and
    a nine-word one. It moved to the legend on 2026-09-02. The run itself must
    still be *found*, because the run summary reports it and the legend is filled
    from the summary rather than from the picture -- and it must still be
    *drawn*, which the next two tests check.
    """
    import matplotlib.pyplot as plt

    figure, panel = _panel(measured_dir)
    assert panel.zero_run == (2015, 2021)
    drawn = {text.get_text() for text in panel.lower.texts}
    # What is left inside the plot is the end-of-line series labels, which are
    # functional names, not explanations. Nothing else may stand there.
    #
    # Measured against the series the fixture actually carries, not against every
    # series the panel declares: ``_partition`` draws a line only where the table
    # holds rows for it, and this fixture was recorded before ``agentic_ai``
    # existed. A label for a series with no data would be a worse failure than a
    # missing one, so the subset check below still catches it.
    table = io.load_figure_data(measured_dir).theme_years
    present = set(map(tuple, table[["theme", "domain"]].drop_duplicates().to_numpy()))
    expected = {
        style.series_label(theme, domain)
        for theme, domain in panel_b.LOWER_SERIES
        if (theme, domain) in present
    }
    assert drawn == expected
    assert expected <= {
        style.series_label(theme, domain) for theme, domain in panel_b.LOWER_SERIES
    }
    plt.close(figure)


def test_the_zero_line_is_drawn_clear_of_the_bottom_spine(measured_dir: Path) -> None:
    """A zero series drawn on the spine reads as an absent series."""
    import matplotlib.pyplot as plt

    figure, panel = _panel(measured_dir)
    bottom, top = panel.lower.get_ylim()
    assert bottom < 0, "zero must sit above the axis floor"
    assert abs(bottom) > 0.02 * (top - bottom), "the lift must be visible in print"
    plt.close(figure)


def _dash_ratio_of(dashes: tuple) -> tuple[float, ...]:
    """Return a dash pattern normalised so it can be compared across scalings.

    Matplotlib multiplies a dash sequence by the line width before storing it,
    so the pattern read back off a drawn line is not the tuple that was passed
    in. Dividing through by the first segment makes the two comparable.
    """
    pattern = tuple(float(value) for value in dashes[1])
    return tuple(value / pattern[0] for value in pattern) if pattern else ()


def _dash_ratio(line) -> tuple[float, ...]:
    """Return the normalised dash pattern actually drawn on a line."""
    _, pattern = line._dash_pattern
    return _dash_ratio_of((0, tuple(pattern))) if pattern else ()


def test_every_zero_year_is_drawn_as_a_point(measured_dir: Path) -> None:
    """The zeros must read as seven measured years, not a line starting in 2022."""
    import matplotlib.pyplot as plt

    figure, panel = _panel(measured_dir)
    # Identify the line by all three channels. Hue and marker are no longer
    # enough on their own: virtual staining is also drawn as pathology, so the
    # lower plot holds two magenta squares and only the dash tells them apart.
    marker = style.series_marker("clinical_fda", "pathology")
    colour = style.series_color("clinical_fda", "pathology")
    dashes = style.series_dash("clinical_fda", "pathology")
    pathology = [
        line
        for line in panel.lower.get_lines()
        if line.get_marker() == marker
        and line.get_color() == colour
        and line.get_linestyle() != "None"
        and _dash_ratio(line) == pytest.approx(_dash_ratio_of(dashes), rel=1e-6)
    ]
    assert pathology, "the pathology line must be drawn, with its marker"
    drawn = pathology[0]
    x = list(map(int, drawn.get_xdata()))
    y = list(map(float, drawn.get_ydata()))
    assert x[:7] == list(range(2015, 2022))
    assert y[:7] == [0.0] * 7
    plt.close(figure)


def test_counts_are_drawn_per_year_not_cumulatively(measured_dir: Path) -> None:
    """Radiology's 13, 9, 21 must reach the page as 13, 9, 21."""
    import matplotlib.pyplot as plt

    figure, panel = _panel(measured_dir)
    drawn = {
        (int(x), float(y))
        for line in panel.lower.get_lines()
        for x, y in zip(line.get_xdata(), line.get_ydata())
    }
    assert {(2024, 13.0), (2025, 8.0), (2026, 19.0)} <= drawn
    plt.close(figure)


def test_the_partial_year_is_marked_in_both_plots(measured_dir: Path) -> None:
    """The partial-year treatment applies to both plots, not only the upper."""
    import matplotlib.pyplot as plt

    figure, panel = _panel(measured_dir)
    for ax in panel.axes:
        open_markers = [
            line
            for line in ax.get_lines()
            if line.get_markerfacecolor() == "white" and line.get_linestyle() == "None"
        ]
        assert open_markers, "each plot must draw the partial year as an open marker"
        shaded = [
            patch
            for patch in ax.patches
            if getattr(patch, "get_facecolor", None) is not None
        ]
        assert shaded, "each plot must carry the partial-year band"
    plt.close(figure)


def test_the_gap_notes_are_left_to_the_legend(measured_dir: Path) -> None:
    """Author's decision, 2026-09-02: both statements belong in the legend.

    The scale difference must still be carried graphically, so this also checks
    that turning the prose off did not take the range band with it.
    """
    import matplotlib.pyplot as plt

    assert panel_b.SHOW_GAP_NOTES is False
    figure, panel = _panel(measured_dir)
    notes = " ".join(text.get_text() for text in figure.texts)
    assert "change of scale" not in notes
    assert "no information" not in notes
    assert panel.scale_ratio is not None
    assert panel.scale_ratio > panel_b.MIN_RATIO_FOR_BAND, (
        "the range band is what carries the scale difference once the note is gone"
    )
    plt.close(figure)


def test_the_notes_come_back_when_asked(measured_dir: Path, monkeypatch) -> None:
    """The switch is real, so the decision can be reversed without a code edit."""
    import matplotlib.pyplot as plt

    monkeypatch.setattr(panel_b, "SHOW_GAP_NOTES", True)
    figure, _ = _panel(measured_dir)
    notes = " ".join(text.get_text() for text in figure.texts)
    assert "change of scale" in notes
    plt.close(figure)


def test_the_summary_reports_the_split(measured_dir: Path, tmp_path: Path) -> None:
    """Whoever writes the legend needs the ratio and the zero run in text."""
    result = plot.build(measured_dir, tmp_path / "figures", tag="measured")
    text = result.summary.read_text()
    assert "two stacked plots" in text
    assert "finer than the upper plot" in text
    assert "2015-2021 (7 consecutive years at zero)" in text
    assert result.panel.zero_run == (2015, 2021)


def test_a_short_zero_run_is_not_annotated(minimal_dir: Path) -> None:
    """Three years is the floor; a one-year zero is not worth a callout."""
    frame = io.load_figure_data(minimal_dir).theme_years
    assert panel_b._leading_zero_run(frame, "clinical_fda", "pathology") is None


def test_an_all_zero_series_is_not_annotated(minimal_dir: Path) -> None:
    """A series that never rises has nothing to contrast its zeros against."""
    path = minimal_dir / io.THEME_YEAR_COUNTS
    path.write_text(
        path.read_text()
        .replace("clinical_fda,pathology,2024,5,0", "clinical_fda,pathology,2024,0,0")
        .replace("clinical_fda,pathology,2025,9,0", "clinical_fda,pathology,2025,0,0")
        .replace("clinical_fda,pathology,2026,4,1", "clinical_fda,pathology,2026,0,1")
    )
    frame = io.load_figure_data(minimal_dir).theme_years
    assert panel_b._leading_zero_run(frame, "clinical_fda", "pathology") is None


def test_one_plot_takes_the_whole_rectangle(minimal_dir: Path) -> None:
    """With nothing to draw below, the panel must not leave an empty box."""
    import matplotlib.pyplot as plt

    (minimal_dir / io.THEME_YEAR_COUNTS).write_text(
        "theme,domain,year,n_papers,partial_year\n"
        "foundation_models,radiology,2025,19,0\n"
        "foundation_models,radiology,2026,9,1\n"
    )
    figure, panel = _panel(minimal_dir)
    assert panel.lower is None and panel.upper is not None
    assert panel.scale_ratio is None
    assert panel.upper.get_xlabel() == "Publication year"
    box = panel.upper.get_position()
    assert abs(box.height - plot._PANEL_B_RECT[3]) < 1e-9
    plt.close(figure)


# --------------------------------------------------------------------------
# Panel A layout at fifteen modality rows
#
# The modality list has grown twice: eleven rows to thirteen, then thirteen to
# fifteen when `genomics` and `clinical_data` were added. Both growths broke the
# layout silently -- a row label that runs off the page still renders, and a row
# pitch that has collapsed still renders. These tests make the next growth fail
# loudly instead.
# --------------------------------------------------------------------------


def _measure(text: str, fontsize: float) -> float:
    """Return the rendered width of a string, in inches, at the figure's font."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    with plt.rc_context(plot.style.rc_params()):
        figure = plt.figure(figsize=plot.FIGURE_SIZE)
        artist = figure.text(0, 0, text, fontsize=fontsize)
        width = artist.get_window_extent(
            renderer=figure.canvas.get_renderer()
        ).width / figure.dpi
        plt.close(figure)
    return width


def test_the_row_label_gutter_fits_the_longest_modality_label() -> None:
    """A label wider than the gutter is silently clipped, not wrapped."""
    longest = max(
        (plot.style.modality_label(key) for key in plot.style.MODALITY_ORDER),
        key=lambda label: _measure(label, plot.style.FS_TICK),
    )
    needed = _measure(longest, plot.style.FS_TICK) + 2.5 / 72
    gutter = plot._PANEL_A_RECT[0] * plot.FIGURE_SIZE[0]
    assert gutter >= needed, (
        f"{longest!r} needs {needed:.3f} in but the gutter is {gutter:.3f} in; "
        "widen _PANEL_A_RECT's left edge"
    )


def test_the_matrix_row_pitch_stays_legible() -> None:
    """Seven-point labels need room. The pitch is what a new row spends."""
    # The shipped figure draws the dot-colour key, whose strip comes out of the panel.
    panel_height = plot._PANEL_A_RECT[3] * plot.FIGURE_SIZE[1] - panel_a._KEY_STRIP_IN
    body = panel_height * (1 - 0.090 - 0.075)
    pitch_pt = 0.670 * body / len(panel_a.MATRIX_ROWS) * 72
    assert pitch_pt >= 12.0, (
        f"row pitch is {pitch_pt:.1f} pt for "
        f"{len(panel_a.MATRIX_ROWS)} rows; rebalance Panel A or grow the "
        "figure, but do not shrink the type"
    )
    assert pitch_pt >= 1.7 * plot.style.FS_TICK


def test_the_new_data_type_rows_sit_where_the_spec_puts_them() -> None:
    """Pathology, then radiology, then the data types, then other."""
    order = plot.style.MODALITY_ORDER
    assert len(order) == 15
    assert order[-3:] == ("genomics", "clinical_data", "other")
    assert order.index("genomics") > order.index("radiology_report")
    assert plot.style.modality_label("genomics") == "Genomics / Transcriptomics"
    assert plot.style.modality_label("clinical_data") == "Clinical / EHR Data"


def test_the_new_rows_do_not_change_the_domain_rule() -> None:
    """Genomics and EHR data are not imaging, so they carry no domain."""
    for key in ("genomics", "clinical_data", "other"):
        assert key not in plot.style.RADIOLOGY_MODALITIES
        assert key not in plot.style.PATHOLOGY_MODALITIES
    assert len(plot.style.RADIOLOGY_MODALITIES) == 7
    assert len(plot.style.PATHOLOGY_MODALITIES) == 5


def test_other_is_accepted_alongside_named_modalities(minimal_dir: Path) -> None:
    """`other` is additive now; a set naming it beside MRI must load and draw."""
    path = minimal_dir / io.COMBINATION_COUNTS
    path.write_text(path.read_text() + "digital_twins,genomics+mri+other,3,2,2\n")
    data = io.load_figure_data(minimal_dir)
    assert "genomics+mri+other" in set(data.combinations["modality_set"])


# --------------------------------------------------------------------------
# Panel A: the remainder column
#
# Twelve columns plus one remainder column per theme. The remainder is what
# makes the panel honest: every paper in a theme is drawn, so the bars sum to
# the theme total. These tests hold the three properties that make it readable
# as an aggregate rather than as a thirteenth combination -- it carries no dots,
# it stands apart from the columns, and it is drawn in a different fill -- and
# the one property that makes it correct.
# --------------------------------------------------------------------------


def _bar_axes(figure, n_blocks: int):
    """Return Panel A's four bar axes, left to right."""
    groups: dict[tuple[float, float], list] = {}
    for ax in figure.axes:
        box = ax.get_position()
        groups.setdefault((round(box.y0, 4), round(box.height, 4)), []).append(ax)
    group = next(
        candidate
        for candidate in groups.values()
        if len(candidate) == n_blocks and candidate[0].get_ylim()[0] == 0
    )
    return sorted(group, key=lambda ax: ax.get_position().x0)


def _matrix_axes(figure, n_blocks: int):
    """Return Panel A's four matrix axes, left to right."""
    groups: dict[tuple[float, float], list] = {}
    for ax in figure.axes:
        box = ax.get_position()
        groups.setdefault((round(box.y0, 4), round(box.height, 4)), []).append(ax)
    group = next(
        candidate
        for candidate in groups.values()
        if len(candidate) == n_blocks and candidate[0].get_ylim()[0] > candidate[0].get_ylim()[1]
    )
    return sorted(group, key=lambda ax: ax.get_position().x0)


def test_the_bars_sum_to_the_theme_total(synthetic_dir: Path, tmp_path: Path) -> None:
    """With the remainder column drawn, no paper is left off the panel."""
    import matplotlib.pyplot as plt

    data = io.load_figure_data(synthetic_dir)
    figure, tails, _ = plot.build_figure(data, scale="count")
    for ax, tail in zip(_bar_axes(figure, len(tails)), tails):
        drawn = sum(patch.get_height() for patch in ax.patches)
        assert abs(drawn - tail.total_papers) < 1e-6
    plt.close(figure)


def test_the_share_bars_sum_to_the_whole_theme(
    synthetic_dir: Path, tmp_path: Path
) -> None:
    """The same guarantee on the shipped scale: every paper is on the panel.

    Share bars are stored as fractions of the theme and formatted as percentages
    at the axis, so the sum to check is 1.0, not 100.
    """
    import matplotlib.pyplot as plt

    data = io.load_figure_data(synthetic_dir)
    figure, tails, _ = plot.build_figure(data, scale="share")
    for ax, _tail in zip(_bar_axes(figure, len(tails)), tails):
        drawn = sum(patch.get_height() for patch in ax.patches)
        assert abs(drawn - 1.0) < 0.005
    plt.close(figure)


def test_a_theme_with_a_long_tail_draws_a_remainder_column(synthetic_dir: Path) -> None:
    """The tail is a column, not a footnote, whenever there is a tail."""
    data = io.load_figure_data(synthetic_dir)
    tails = {
        tail.theme: tail
        for tail in [
            panel_a._tail_summary(data.combinations, theme, panel_a.DEFAULT_TOP_N)
            for theme in style.THEME_ORDER
        ]
    }
    long_tailed = [tail for tail in tails.values() if tail.total_sets > panel_a.DEFAULT_TOP_N]
    assert long_tailed, "the synthetic corpus must exercise the remainder path"
    for tail in long_tailed:
        assert tail.draws_remainder
        assert tail.shown_sets == panel_a.DEFAULT_TOP_N
        assert tail.shown_papers + tail.remainder_papers == tail.total_papers
        assert tail.remainder_sets == tail.total_sets - tail.shown_sets


def test_the_remainder_column_carries_no_dots(synthetic_dir: Path) -> None:
    """A dot there would say the remainder is one more combination. It is not."""
    import matplotlib.pyplot as plt

    data = io.load_figure_data(synthetic_dir)
    figure, tails, _ = plot.build_figure(data)
    for ax, tail in zip(_matrix_axes(figure, len(tails)), tails):
        if not tail.draws_remainder:
            continue
        remainder_x = panel_a._positions(tail.shown_sets, True)[-1]
        drawn_x = [
            float(x)
            for collection in ax.collections
            for x, _ in collection.get_offsets()
        ]
        assert drawn_x, "the combination columns must still carry their dots"
        assert max(drawn_x) <= tail.shown_sets - 1 + 1e-9
        assert remainder_x - max(drawn_x) > 1.0
    plt.close(figure)


def test_the_remainder_column_is_labeled_where_its_dots_would_be(
    synthetic_dir: Path,
) -> None:
    """The label sits in the empty matrix column, turned on end to fit."""
    import matplotlib.pyplot as plt

    data = io.load_figure_data(synthetic_dir)
    figure, tails, _ = plot.build_figure(data)
    for ax, tail in zip(_matrix_axes(figure, len(tails)), tails):
        labels = [text for text in ax.texts if text.get_text() == panel_a.REMAINDER_LABEL]
        assert bool(labels) == tail.draws_remainder
        if labels:
            assert labels[0].get_rotation() == 90.0
    plt.close(figure)


def test_the_number_of_sets_in_the_remainder_is_printed_beneath_it(
    synthetic_dir: Path, tmp_path: Path
) -> None:
    """The reader must be able to see how many combinations the bar stands for."""
    import matplotlib.pyplot as plt

    data = io.load_figure_data(synthetic_dir)
    figure, tails, _ = plot.build_figure(data)
    printed = {text.get_text() for text in figure.texts}
    for tail in tails:
        if tail.draws_remainder:
            assert f"+{tail.remainder_sets} sets" in printed
    plt.close(figure)


def test_the_remainder_bar_is_drawn_as_a_different_kind_of_bar(
    synthetic_dir: Path,
) -> None:
    """Hollow and hatched, so it never reads as one more combination."""
    import matplotlib.pyplot as plt

    data = io.load_figure_data(synthetic_dir)
    for scale in panel_a.BAR_SCALES:
        figure, tails, _ = plot.build_figure(data, scale=scale)
        for ax, tail in zip(_bar_axes(figure, len(tails)), tails):
            hatched = [patch for patch in ax.patches if patch.get_hatch()]
            assert len(hatched) == (1 if tail.draws_remainder else 0)
            if hatched:
                expected = (
                    tail.remainder_papers
                    if scale == "count"
                    else tail.remainder_papers / tail.total_papers
                )
                assert abs(hatched[0].get_height() - expected) < 0.005
                # Author's decision of 2026-09-02: the remainder column is
                # hatched in the bars' own ink, NOT in the style guide's pale
                # section 4 hatch, which is specified for masked and inactive
                # elements. In the multimodal block this is the tallest bar in
                # the block; drawn pale it read as a rounding error, which is
                # exactly what DECISIONS.md forbids.
                assert style.HATCH_LINE == style.BAR_FILL
                ground = mcolors.to_rgb(style.HATCH_GROUND)
                assert hatched[0].get_facecolor()[:3] == pytest.approx(ground)
                assert mcolors.to_rgb(hatched[0].get_edgecolor()[:3]) == pytest.approx(
                    mcolors.to_rgb(style.HATCH_LINE)
                )
        plt.close(figure)


def test_the_block_note_is_the_theme_total_and_nothing_else(
    synthetic_dir: Path, tmp_path: Path
) -> None:
    """Nothing is hidden, so no note may say so -- and none may explain the cap.

    The note under each block is now the functional label ``n = N papers`` alone.
    "top 12 of 139 combinations" was explanatory prose and moved to the legend on
    2026-09-02, per section 6 of the style guide. How the columns divide the
    theme is still visible in the drawing, through the remainder column and its
    "+N sets" caption, which this file tests elsewhere.
    """
    import matplotlib.pyplot as plt

    data = io.load_figure_data(synthetic_dir)
    figure, tails, _ = plot.build_figure(data)
    notes = " ".join(text.get_text() for text in figure.texts)
    assert "rarer combinations" not in notes
    assert "top " not in notes and "combinations shown" not in notes
    for tail in tails:
        if tail.total_papers:
            assert f"n = {tail.total_papers:,} papers" in notes
    plt.close(figure)


def test_the_summary_reports_the_remainder(synthetic_dir: Path, tmp_path: Path) -> None:
    """Whoever writes the legend reads the numbers here, not off the picture."""
    result = plot.build(synthetic_dir, tmp_path / "figures", tag="remainder")
    text = result.summary.read_text()
    assert "remainder" in text
    assert "top 12 modality combinations per theme" in text


# --------------------------------------------------------------------------
# Panel A: thirteen columns per block
#
# Column width is to the horizontal what row pitch is to the vertical: it is
# what a new column spends, and it fails silently. At thirteen columns per block
# the columns are 0.10 in wide; at twenty-one they would be 0.06 in, and the
# dots would collapse to their own floor while the figure still rendered and
# still looked finished.
# --------------------------------------------------------------------------


def test_the_columns_stay_wide_enough_to_carry_a_dot() -> None:
    """The cap is bounded by column width, not by taste."""
    slots = sum(
        panel_a.block_slots(panel_a.DEFAULT_TOP_N, True) for _ in plot.style.PANEL_A_THEMES
    )
    width = panel_a.column_width_in(plot._PANEL_A_RECT[2], plot.FIGURE_SIZE[0], slots)
    assert width >= panel_a.MIN_COLUMN_WIDTH_IN, (
        f"{panel_a.DEFAULT_TOP_N} columns plus a remainder give {width:.3f} in per "
        f"column, below the {panel_a.MIN_COLUMN_WIDTH_IN} in floor; widen Panel A, "
        "widen the figure, or lower the cap -- do not shrink the dots"
    )


def test_the_dots_are_not_pinned_to_their_own_floor() -> None:
    """A dot clamped at the floor means the column width has already failed."""
    slots = sum(
        panel_a.block_slots(panel_a.DEFAULT_TOP_N, True) for _ in plot.style.PANEL_A_THEMES
    )
    width = panel_a.column_width_in(plot._PANEL_A_RECT[2], plot.FIGURE_SIZE[0], slots)
    panel_height = plot._PANEL_A_RECT[3] * plot.FIGURE_SIZE[1]
    body = panel_height * (1 - 0.090 - 0.075)
    row_h = 0.670 * body / len(plot.style.MODALITY_ORDER)
    diameter = panel_a._dot_size(width, row_h) ** 0.5
    assert diameter > 2.6, f"dot diameter is at its floor ({diameter:.2f} pt)"


def test_a_cap_of_twenty_would_fail_the_column_width_floor() -> None:
    """The rejected alternative is rejected by measurement, not by memory."""
    slots = sum(panel_a.block_slots(20, True) for _ in plot.style.PANEL_A_THEMES)
    width = panel_a.column_width_in(plot._PANEL_A_RECT[2], plot.FIGURE_SIZE[0], slots)
    assert width < panel_a.MIN_COLUMN_WIDTH_IN


def test_bar_labels_stand_on_end_when_the_column_is_too_narrow(
    four_digit_dir: Path,
) -> None:
    """Rotate the label rather than shrink the type below what prints."""
    import matplotlib.pyplot as plt

    slots = sum(
        panel_a.block_slots(panel_a.DEFAULT_TOP_N, True) for _ in plot.style.PANEL_A_THEMES
    )
    width = panel_a.column_width_in(plot._PANEL_A_RECT[2], plot.FIGURE_SIZE[0], slots)
    assert panel_a._value_font_size(width, "1234") < panel_a._MIN_LEGIBLE_VALUE_FS
    assert panel_a._rotated_font_size(width) >= panel_a._MIN_LEGIBLE_VALUE_FS

    data = io.load_figure_data(four_digit_dir)
    figure, tails, _ = plot.build_figure(data)
    for ax in _bar_axes(figure, len(tails)):
        for text in ax.texts:
            assert text.get_rotation() == 90.0
            assert text.get_fontsize() >= panel_a._MIN_LEGIBLE_VALUE_FS
    plt.close(figure)


def test_a_rotated_label_stays_inside_the_bar_axes(synthetic_dir: Path) -> None:
    """A label standing on end must not run off the top of its own axes."""
    import matplotlib.pyplot as plt

    data = io.load_figure_data(synthetic_dir)
    figure, tails, _ = plot.build_figure(data)
    renderer = figure.canvas.get_renderer()
    for ax in _bar_axes(figure, len(tails)):
        ceiling = ax.get_window_extent(renderer=renderer).y1
        for text in ax.texts:
            assert text.get_window_extent(renderer=renderer).y1 <= ceiling + 1.0
    plt.close(figure)


# --------------------------------------------------------------------------
# Nothing may be drawn off the page
#
# Silent clipping is this figure's characteristic failure: a label that runs
# past the paper still renders, and the figure still looks finished. It has
# happened twice, both times when the panel grew -- once to a row label in the
# left gutter, once to the remainder column's caption at the right edge. This
# test watches every piece of type on the figure, not only the two that failed.
# --------------------------------------------------------------------------


def _texts_outside_the_page(figure) -> list[str]:
    """Return the text of every artist whose box leaves the canvas."""
    # Axis labels take their final position only when the figure is drawn.
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    page = figure.get_window_extent(renderer=renderer)
    offenders = []
    artists = list(figure.texts)
    # A tick locator emits ticks beyond the axes' view interval; matplotlib holds
    # the label objects but never draws them, and their boxes sit wherever the
    # off-view tick would have been. Measuring those reports overflows that do
    # not exist on the page, so they are collected here and skipped below. Only
    # ticks that are actually drawn are held to the canvas.
    unrendered = set()
    for ax in figure.axes:
        artists.extend(ax.texts)
        for axis, (low, high) in (
            (ax.xaxis, sorted(ax.get_xlim())),
            (ax.yaxis, sorted(ax.get_ylim())),
        ):
            locations = axis.get_ticklocs()
            labels = axis.get_ticklabels()
            artists.extend(labels)
            for location, label in zip(locations, labels):
                if not low <= location <= high:
                    unrendered.add(label)
        if ax.get_title():
            artists.append(ax.title)
        for label in (ax.xaxis.label, ax.yaxis.label):
            if label.get_text():
                artists.append(label)
    for artist in artists:
        if not artist.get_text().strip():
            continue
        if artist in unrendered:
            continue
        box = artist.get_window_extent(renderer=renderer)
        # A half point of slack: anti-aliasing puts a glyph's box a hair wide.
        if (
            box.x0 < page.x0 - 0.5
            or box.x1 > page.x1 + 0.5
            or box.y0 < page.y0 - 0.5
            or box.y1 > page.y1 + 0.5
        ):
            offenders.append(f"{artist.get_text()!r} at {box.bounds}")
    return offenders


@pytest.mark.parametrize("scale", panel_a.BAR_SCALES)
def test_no_label_runs_off_the_page(four_digit_dir: Path, scale: str) -> None:
    """Every label must be on the paper, at full size, in both scales."""
    import matplotlib.pyplot as plt

    data = io.load_figure_data(four_digit_dir)
    with plt.rc_context(plot.style.rc_params()):
        figure, _, _ = plot.build_figure(data, scale=scale)
        offenders = _texts_outside_the_page(figure)
        plt.close(figure)
    assert not offenders, "text drawn off the page: " + "; ".join(offenders)


def test_no_label_runs_off_the_page_on_the_synthetic_corpus(synthetic_dir: Path) -> None:
    """The same guard, over a corpus with a block that has no remainder column."""
    import matplotlib.pyplot as plt

    data = io.load_figure_data(synthetic_dir)
    with plt.rc_context(plot.style.rc_params()):
        figure, _, _ = plot.build_figure(data)
        offenders = _texts_outside_the_page(figure)
        plt.close(figure)
    assert not offenders, "text drawn off the page: " + "; ".join(offenders)


# --------------------------------------------------------------------------
# Style guide conformance
#
# The figure follows ``../ink_style_guide.md``. Three of its rules are the kind
# that decay silently -- a font substitution nobody sees, a hue that creeps back
# in as decoration, an explanatory sentence that gets re-added "just this once"
# -- so each is pinned here rather than trusted to review.
# --------------------------------------------------------------------------


def test_every_ibm_plex_face_resolves_to_the_vendored_file() -> None:
    """Section 2: the faces are IBM Plex, and not a fallback wearing its name.

    ``findfont`` never fails: handed a family it does not have, it returns
    DejaVu Sans and logs a warning at a level nobody reads, and the whole figure
    renders in the wrong face while looking finished. So the test compares the
    resolved path, not the family name it asked for.
    """
    from matplotlib import font_manager

    directory = style.font_dir()
    for (family, weight, slant), filename in style.FONT_FILES.items():
        resolved = Path(
            font_manager.findfont(
                font_manager.FontProperties(family=family, weight=weight, style=slant)
            )
        ).resolve()
        assert resolved == (directory / filename).resolve(), (
            f"{family} {weight} {slant} resolved to {resolved.name}, not {filename}; "
            "matplotlib has substituted a face the style guide names"
        )
        assert "Plex" in resolved.name


def test_a_missing_face_raises_rather_than_falling_back(tmp_path: Path, monkeypatch) -> None:
    """Section 2 is explicit: do not substitute silently. So: raise, loudly."""
    incomplete = tmp_path / "assets" / "fonts"
    incomplete.mkdir(parents=True)
    (incomplete / "IBMPlexSans-Regular.ttf").write_bytes(b"")
    monkeypatch.setattr(style, "font_dir", lambda: incomplete)
    with pytest.raises(style.FontsUnavailable) as raised:
        style.register_fonts()
    assert "IBMPlexSerif-Bold.ttf" in str(raised.value)


def test_the_font_directory_is_found_from_the_package_not_the_cwd(
    tmp_path: Path, monkeypatch
) -> None:
    """A build launched from anywhere must find the same vendored faces."""
    monkeypatch.chdir(tmp_path)
    assert style.font_dir().is_dir()
    assert (style.font_dir() / "IBMPlexSerif-Bold.ttf").is_file()


def test_the_figure_is_drawn_in_ibm_plex(synthetic_dir: Path) -> None:
    """Serif for the panel letters and theme titles, sans for everything else."""
    import matplotlib.pyplot as plt

    data = io.load_figure_data(synthetic_dir)
    with plt.rc_context(plot.style.rc_params()):
        figure, _, _ = plot.build_figure(data)
        letters = [text for text in figure.texts if text.get_text() in {"A", "B"}]
        assert len(letters) == 2
        for letter in letters:
            assert letter.get_fontfamily() == ["serif"]
            assert letter.get_fontweight() == "bold"
            assert letter.get_color() == style.INK
        titles = [ax.title for ax in figure.axes if ax.get_title()]
        assert titles, "each Panel A block carries its theme title"
        for title in titles:
            assert title.get_fontfamily() == ["serif"]
            assert title.get_fontweight() == "bold"
        assert plt.rcParams["font.sans-serif"][0] == style.SANS
        assert plt.rcParams["font.serif"][0] == style.SERIF
        plt.close(figure)


def test_the_panel_letter_is_the_largest_type_on_the_page() -> None:
    """Section 2's hierarchy, in the order the guide sets it."""
    sizes = (
        style.FS_PANEL_LETTER,
        style.FS_THEME_TITLE,
        style.FS_AXIS_LABEL,
        style.FS_TICK,
        style.FS_NOTE,
    )
    assert list(sizes) == sorted(sizes, reverse=True)
    assert style.FS_PANEL_LETTER > 1.4 * style.FS_THEME_TITLE
    # Nothing may fall below the floors this project measured and tested.
    assert style.FS_BAR_VALUE >= panel_a._MIN_LEGIBLE_VALUE_FS
    assert style.FS_TICK >= 7.0


def test_axis_titles_are_italic_and_subtle(measured_dir: Path) -> None:
    """Section 2's "column headers / axis-style labels" row: italic, #5C6068."""
    import matplotlib.pyplot as plt

    figure, panel = _panel(measured_dir)
    labels = [ax.yaxis.label for ax in panel.axes] + [panel.lower.xaxis.label]
    for label in labels:
        assert label.get_style() == "italic"
        assert label.get_color() == style.SUBTLE
    plt.close(figure)


def test_panel_a_dots_carry_their_rows_modality_colour(minimal_dir: Path) -> None:
    """Section 3: colour identifies a data modality, and only that.

    The fixed assignments are the project's, not this figure's, so the test
    checks the drawn dot against the modality table rather than against itself.
    """
    import matplotlib.pyplot as plt

    data = io.load_figure_data(minimal_dir)
    with plt.rc_context(plot.style.rc_params()):
        figure, _, _ = plot.build_figure(data)
        row_of = {key: index for index, key in enumerate(style.MODALITY_ORDER)}
        seen = 0
        for ax in _matrix_axes(figure, len(style.PANEL_A_THEMES)):
            for collection in ax.collections:
                offsets = collection.get_offsets()
                colours = collection.get_facecolor()
                if len(colours) < 2:
                    continue  # the single-coloured absent-dot grid
                for (_, row), colour in zip(offsets, colours):
                    expected = style.modality_color(style.MODALITY_ORDER[int(round(row))])
                    assert tuple(colour[:3]) == pytest.approx(
                        mcolors.to_rgb(expected), abs=0.01
                    )
                    seen += 1
        assert seen, "no present dot was drawn, so nothing was checked"
        assert row_of["genomics"] < row_of["other"]
        plt.close(figure)


def test_panel_a_bars_carry_no_modality_colour(synthetic_dir: Path) -> None:
    """A bar is a combination, not a modality, so it takes the structural ink."""
    import matplotlib.pyplot as plt

    data = io.load_figure_data(synthetic_dir)
    hues = {mcolors.to_rgb(colour) for colour in style.MODALITY_COLORS.values()}
    with plt.rc_context(plot.style.rc_params()):
        figure, tails, _ = plot.build_figure(data)
        for ax in _bar_axes(figure, len(tails)):
            for patch in ax.patches:
                face = tuple(patch.get_facecolor()[:3])
                assert not any(
                    face == pytest.approx(hue, abs=0.01) for hue in hues
                ), "no bar may be tinted by modality or by theme"
                if not patch.get_hatch():
                    assert face == pytest.approx(mcolors.to_rgb(style.BAR_FILL), abs=0.01)
        plt.close(figure)


def test_panel_b_colour_marks_the_domain_and_only_the_domain() -> None:
    """Section 3, under the 2026-09-02 specification.

    Colour identifies the clinical domain a theme's papers were pursued in --
    which is semantic -- and carries nothing else. Two blue lines in the upper
    plot are radiology work in two different themes, so the test asserts that
    the theme has no influence on the hue at all.
    """
    keys = panel_b.UPPER_SERIES + panel_b.LOWER_SERIES
    by_domain: dict[str, set[str]] = {}
    for theme, domain in keys:
        if (theme, domain) in style.SERIES_DOMAIN_OVERRIDES:
            continue
        by_domain.setdefault(domain, set()).add(style.series_color(theme, domain))
    for domain, colours in by_domain.items():
        assert len(colours) == 1, f"{domain} must have one colour, got {colours}"

    # Virtual staining is drawn undivided but is not domain-less: 75 of its 76
    # papers are pathologic, so it takes the pathology hue rather than the ink
    # that a genuinely mixed undivided series gets. Drawing it in ink would have
    # put it in the same colour as digital twins, which it crosses.
    assert style.series_color("virtual_staining", "all") == style.DIGITAL_PATHOLOGY_DEEP
    assert style.series_color("digital_twins", "all") == style.INK
    # And the override drives hue and marker together, so they cannot disagree.
    assert style.series_marker("virtual_staining", "all") == style.DOMAIN_MARKERS["pathology"]
    assert style.series_marker("digital_twins", "all") == style.DOMAIN_MARKERS["all"]
    assert style.domain_color("radiology") == style.RADIOLOGY_IMAGING
    # The deep pathology variant: every mark in Panel B is a thin stroke or 7 pt
    # type, which is what the specification assigns the deep variant to.
    assert style.domain_color("pathology") == style.DIGITAL_PATHOLOGY_DEEP
    # Cross-specialty takes the guide's structural/integrative grey, which it
    # reserves for fusion modules and joint models.
    assert style.domain_color("both") == style.STRUCTURAL
    # An undivided series makes no domain claim and takes ink.
    assert style.domain_color("all") == style.INK


def test_the_three_channels_carry_one_dimension_each() -> None:
    """Dash = theme. Hue = domain. Marker = domain.

    The marker was a second *theme* cue until 2026-09-02, which left hue as the
    only thing separating the domains, so greyscale lost the domain entirely.
    Marker now doubles the domain instead, and dash carries the theme alone.
    """
    # Dash is the theme channel: unique per theme, and blind to the domain.
    for domain in ("radiology", "pathology", "both"):
        dashes = {style.series_dash(theme, domain) for theme in style.THEME_ORDER}
        assert len(dashes) == len(style.THEME_ORDER), "each theme needs its own dash"
    for theme in style.THEME_ORDER:
        seen = {style.series_dash(theme, d) for d in ("all", "radiology", "pathology", "both")}
        assert len(seen) == 1, "the domain must not affect the dash"

    # Marker is a domain channel: unique per domain, and blind to the theme
    # except where an override deliberately restates a known domain.
    for theme in ("foundation_models", "multimodal_integration", "clinical_fda"):
        markers = {style.series_marker(theme, d) for d in ("radiology", "pathology", "both")}
        assert len(markers) == 3, "each domain needs its own marker"
    for domain in ("radiology", "pathology", "both"):
        seen = {style.series_marker(theme, domain) for theme in style.THEME_ORDER}
        assert len(seen) == 1, "the theme must not affect the marker"

    # Hue and marker are the same statement, so they can never contradict.
    for theme, domain in panel_b.UPPER_SERIES + panel_b.LOWER_SERIES:
        shown = style.appearance_domain(theme, domain)
        assert style.series_color(theme, domain) == style.domain_color(shown)
        assert style.series_marker(theme, domain) == style.DOMAIN_MARKERS[shown]


def test_the_confusable_marker_pair_never_shares_a_plot() -> None:
    """Triangle and diamond are the one pair that could be mistaken. Measured.

    Rendering each marker at its drawn size and measuring the ink inside its
    bounding box gives, for the 2.9 pt filled markers: circle 0.782, square
    1.000, triangle 0.521, diamond 0.515. Triangle and diamond differ by 0.006 --
    they are effectively the same silhouette at 1.02 mm on the page.

    They are safe only because they never appear together: the triangle is
    cross-specialty, drawn in the upper plot alone, and the diamond is the
    no-domain marker, drawn in the lower plot alone. If a future series brought
    them into one plot the figure would lose a distinction in greyscale, so the
    separation is asserted rather than left to luck.

    Within each plot as drawn, the closest pair is circle against square, 0.218
    apart in ink fill -- a 22-point difference plus a round-versus-flat-sided
    silhouette, which reads.
    """
    confusable = {style.DOMAIN_MARKERS["both"], style.DOMAIN_MARKERS["all"]}
    for plot_series in (panel_b.UPPER_SERIES, panel_b.LOWER_SERIES):
        used = {style.series_marker(theme, domain) for theme, domain in plot_series}
        assert not confusable <= used, (
            f"the triangle and diamond markers are 0.006 apart in ink fill and "
            f"must not share a plot; this one draws {sorted(used)}"
        )


def test_two_series_may_share_a_marker_and_the_dash_tells_them_apart() -> None:
    """The marker states a domain, so series making the same claim draw alike.

    One pair still does: virtual staining and clinical pathology are both deep-pink
    squares, separated by dash and by their end labels. That is the scheme
    working, not a collision -- hue and marker answer "which side of the clinic",
    the dash answers "which theme", and the label names it outright.

    **Digital twins and agentic AI used to be the second such pair, and no longer
    are.** The author asked on 2026-09-03 for the two to be distinguishable at a
    glance, which reverses a decision this docstring previously recorded: giving
    a domain-less series its own shape had been measured and declined, on the
    grounds that no unused marker separated cleanly from diamond, circle and
    square at once, and that the star's limbs fell under the guide's minimum
    stroke. Two things resolve it. The style guide's structural/integrative row
    names "fusion modules, joint models, **agents**", so agentic AI has a
    semantic hue of its own rather than a borrowed one -- the earlier analysis
    treated this as a free choice when the guide had already made it. And the
    marker question narrows once hue is doing work too: "X" measures 0.706 ink
    against the diamond's 0.523, a 0.183 separation, with a silhouette no round
    or flat-sided marker resembles, and it is a filled glyph rather than thin
    limbs.

    What this test protects is the rule that a marker means a display domain and
    nothing else -- agentic AI has one, it is not an invented shape for a theme.
    If it fails because a shape was attached to a theme directly, that is a
    different decision and belongs in docs/DECISIONS.md.
    """
    for plot_series in (panel_b.UPPER_SERIES, panel_b.LOWER_SERIES):
        for first in plot_series:
            for second in plot_series:
                if first == second:
                    continue
                same_look = (
                    style.series_color(*first) == style.series_color(*second)
                    and style.series_marker(*first) == style.series_marker(*second)
                )
                if not same_look:
                    continue
                # Then they must be making the same domain claim ...
                assert style.appearance_domain(*first) == style.appearance_domain(*second)
                # ... and the dash and the label must separate them.
                assert style.series_dash(*first) != style.series_dash(*second)
                assert style.series_label(*first) != style.series_label(*second)

    domainless = [pair for pair in panel_b.LOWER_SERIES if pair[1] == "all"
                  and pair not in style.SERIES_DOMAIN_OVERRIDES]
    assert {("digital_twins", "all")} == set(domainless), (
        "agentic AI took a display domain of its own on 2026-09-03"
    )
    for pair in domainless:
        assert style.series_color(*pair) == style.INK
        assert style.series_marker(*pair) == style.DOMAIN_MARKERS["all"]


def test_every_drawn_series_is_distinguishable_from_every_other() -> None:
    """Section 7. Ten lines, so this is the test that has to hold the panel up.

    The standard is greyscale, not colour: **within one plot, the dash-and-marker
    pair alone must separate every series from every other**, with no hue at all.
    Dash carries the theme and marker carries the domain, so the pair identifies
    the series completely and a greyscale print loses nothing.

    This is stronger than what the panel could assert before 2026-09-02, when
    marker was a second theme cue and the three domain lines of one theme were
    the same stroke in three near-identical greys.
    """
    for plot_series in (panel_b.UPPER_SERIES, panel_b.LOWER_SERIES):
        signatures = {
            (
                style.series_color(theme, domain),
                style.series_dash(theme, domain),
                style.series_marker(theme, domain),
            )
            for theme, domain in plot_series
        }
        assert len(signatures) == len(plot_series), "two series would draw alike"
        labels = {style.series_label(theme, domain) for theme, domain in plot_series}
        assert len(labels) == len(plot_series), "every line needs its own end label"
        # The greyscale test: dash and marker alone, no hue, must separate every
        # series. If this fails the figure does not survive a monochrome print.
        strokes = {
            (style.series_dash(theme, domain), style.series_marker(theme, domain))
            for theme, domain in plot_series
        }
        assert len(strokes) == len(plot_series), (
            "two series are identical in greyscale: dash and marker must "
            "separate every series in this plot without any help from hue"
        )


def test_no_explanatory_annotation_stands_in_the_artwork(
    measured_dir: Path, four_digit_dir: Path
) -> None:
    """Section 6: only functional labels of four words or fewer may stay.

    The three sentences removed on 2026-09-02 are named individually, because
    each was added for a real reason and each will be proposed again.
    """
    import matplotlib.pyplot as plt

    data = io.load_figure_data(measured_dir)
    with plt.rc_context(plot.style.rc_params()):
        figure, _, _ = plot.build_figure(data)
        everything = " ".join(
            text.get_text()
            for text in list(figure.texts) + [t for ax in figure.axes for t in ax.texts]
        )
        for gone in (
            "0 papers in every",
            "fits below this line",
            "whole lower plot",
            "combinations shown",
        ):
            assert gone not in everything, f"{gone!r} is an explanation; it belongs in the legend"
        assert "top " not in everything
        plt.close(figure)

        # The functional labels that were kept. Drawn from a corpus with enough
        # combinations to force a remainder column, which the measured fixture
        # has not got.
        figure, tails, _ = plot.build_figure(io.load_figure_data(four_digit_dir))
        kept = " ".join(
            text.get_text()
            for text in list(figure.texts) + [t for ax in figure.axes for t in ax.texts]
        )
        assert panel_a.REMAINDER_LABEL in kept
        assert f"+{tails[0].remainder_sets} sets" in kept
        assert "partial" in kept
        assert f"n = {tails[0].total_papers:,} papers" in kept
        plt.close(figure)


def test_the_svg_references_fonts_by_name_rather_than_outlining_them(
    synthetic_dir: Path, tmp_path: Path
) -> None:
    """Section 8. An outlined SVG cannot be restyled by the journal's artist."""
    assert style.rc_params()["svg.fonttype"] == "none"
    result = plot.build(synthetic_dir, tmp_path / "figures", tag="svg")
    body = result.svg.read_text(encoding="utf-8")
    assert "IBM Plex" in body, "the SVG must name the families it was drawn in"
    assert result.pdf.exists() and result.png.exists()


def test_the_agentic_line_starts_in_2024(measured_dir: Path) -> None:
    """Its earlier matches do not mean what its label means.

    Measured: 24 of 27 papers from 2025 on are strictly agentic (89%), against
    1 of 8 before 2025 (12%). The author set the cut at 2024 so the rise stays
    visible. The papers remain in the theme total and in Panel A; only the drawn
    line starts late. See panel_b.SERIES_START_YEAR.
    """
    frame = io.load_figure_data(measured_dir).theme_years
    drawn = panel_b._series_frame(frame, "agentic_ai", "all")
    assert not drawn.empty, "the series must still be drawn, just not from 2015"
    assert int(drawn["year"].min()) == 2024

    whole = frame.loc[
        (frame["theme"] == "agentic_ai") & (frame["domain"] == "all")
    ]
    assert int(whole["year"].min()) == 2015, (
        "the underlying table must keep every year; only the drawing is cut"
    )


def test_only_the_agentic_series_is_cut(measured_dir: Path) -> None:
    """A start year is an exception that must be argued for, not a habit."""
    frame = io.load_figure_data(measured_dir).theme_years
    assert set(panel_b.SERIES_START_YEAR) == {("agentic_ai", "all")}
    for theme, domain in panel_b._SERIES_ORDER:
        if (theme, domain) == ("agentic_ai", "all"):
            continue
        drawn = panel_b._series_frame(frame, theme, domain)
        if not drawn.empty:
            assert int(drawn["year"].min()) == 2015, f"{theme}/{domain} was truncated"


def test_a_column_needs_at_least_two_papers(measured_dir: Path) -> None:
    """One paper is an anecdote; twelve of them are not a distribution.

    Panel A became primary-research-only on 2026-09-08, which took digital twins
    to 20 papers across 13 modality sets. Nine of its twelve drawn columns then
    held exactly one paper each, and the block read as a distribution. Singletons
    now join the remainder, which is drawn, so nothing is lost.
    """
    data = io.load_figure_data(measured_dir)
    for theme in style.PANEL_A_THEMES:
        block = panel_a._block_frame(data.combinations, theme, panel_a.DEFAULT_TOP_N)
        if not len(block):
            continue
        subset = data.combinations.loc[data.combinations["theme"] == theme]
        qualifying = subset.loc[subset["n_papers"] >= panel_a.MIN_PAPERS_PER_COLUMN]
        if len(qualifying) >= panel_a.DEFAULT_TOP_N:
            # Combinations compete for the columns, so singletons stay out.
            assert block["n_papers"].min() >= panel_a.MIN_PAPERS_PER_COLUMN
        else:
            # Too small for the minimum to remove noise: it would remove the
            # multi-modality combinations first, because those are the rarest.
            assert len(block) >= len(qualifying)


def test_a_small_theme_keeps_its_multimodal_columns(measured_dir: Path) -> None:
    """The failure the author caught on 2026-09-09.

    Digital twins holds 20 papers over 13 sets, and only three sets hold two or
    more papers -- all three single-modality. Applying the two-paper minimum drew
    a block that appeared to contain no multimodal work at all, while six of its
    twenty papers use two or more modalities and one uses four.
    """
    data = io.load_figure_data(measured_dir)
    block = panel_a._block_frame(data.combinations, "digital_twins", panel_a.DEFAULT_TOP_N)
    multi = block.loc[block["n_modalities"] >= 2]
    assert len(multi) >= 4, "a small theme's multi-modality sets must survive the cap"
    assert int(block["n_modalities"].max()) >= 4, "including its richest combination"


def test_ties_are_broken_toward_the_richer_combination(measured_dir: Path) -> None:
    """Among sets holding equally many papers, draw the more informative one."""
    data = io.load_figure_data(measured_dir)
    block = panel_a._block_frame(data.combinations, "digital_twins", panel_a.DEFAULT_TOP_N)
    for count, group in block.groupby("n_papers"):
        modalities = group["n_modalities"].tolist()
        assert modalities == sorted(modalities, reverse=True), (
            f"sets holding {count} papers must be ordered richest first"
        )


def test_the_bars_still_sum_to_the_theme_after_the_minimum(measured_dir: Path) -> None:
    """The minimum moves papers into the remainder; it must not drop them."""
    data = io.load_figure_data(measured_dir)
    for theme in style.PANEL_A_THEMES:
        tail = panel_a._tail_summary(data.combinations, theme, panel_a.DEFAULT_TOP_N)
        subset = data.combinations.loc[data.combinations["theme"] == theme]
        assert tail.total_papers == int(subset["n_papers"].sum())
        drawn = panel_a._block_frame(data.combinations, theme, panel_a.DEFAULT_TOP_N)
        assert int(drawn["n_papers"].sum()) + tail.remainder_papers == tail.total_papers


def test_a_block_is_wide_enough_for_its_own_caption(measured_dir: Path) -> None:
    """A narrow block must not print its caption into its neighbour.

    Panel A's block width follows its column count, while the caption's width
    follows the digits in the theme total. On 2026-09-08 digital twins fell to
    three drawn columns and its "n = 20 papers" overran the multimodal block's
    "+230 sets". Blocks are now widened to hold their captions.
    """
    data = io.load_figure_data(measured_dir)
    summaries = [
        panel_a._tail_summary(data.combinations, theme, panel_a.DEFAULT_TOP_N)
        for theme in style.PANEL_A_THEMES
    ]
    base = [
        panel_a.block_slots(
            len(panel_a._block_frame(data.combinations, theme, panel_a.DEFAULT_TOP_N)),
            summary.draws_remainder,
        )
        for theme, summary in zip(style.PANEL_A_THEMES, summaries)
    ]
    rect_width, fig_w = 0.786, 7.5
    slots = panel_a._slots_with_captions(base, summaries, rect_width, fig_w)
    column_w = panel_a.column_width_in(rect_width, fig_w, sum(slots))
    for summary, block_slots_, base_slots_ in zip(summaries, slots, base):
        assert block_slots_ >= base_slots_, "a block may be widened, never narrowed"
        assert block_slots_ * column_w >= panel_a._caption_width_in(summary) - 1e-9


def test_no_two_block_captions_overlap(measured_dir: Path) -> None:
    """The real guard: measured text boxes, not approximate glyph arithmetic.

    Widening blocks to fit their captions was not sufficient, because the theme
    total is centred under the block while the remainder's set count sits at the
    right-hand edge, so the two collide on a narrow block however wide it is
    made. They are drawn on separate lines now. This test measures what was
    actually rendered, which is what the width arithmetic could not do.
    """
    import matplotlib.pyplot as plt

    data = io.load_figure_data(measured_dir)
    with plt.rc_context(style.rc_params()):
        figure, _, _ = plot.build_figure(data)
        figure.canvas.draw()
        renderer = figure.canvas.get_renderer()
        boxes = [
            (text.get_text(), text.get_window_extent(renderer))
            for text in figure.texts
            if text.get_text().startswith(("n = ", "+")) or text.get_text() == "no papers"
        ]
        assert boxes, "the block captions must be on the figure"
        for i, (label_a, box_a) in enumerate(boxes):
            for label_b, box_b in boxes[i + 1 :]:
                overlaps = not (
                    box_a.x1 <= box_b.x0
                    or box_b.x1 <= box_a.x0
                    or box_a.y1 <= box_b.y0
                    or box_b.y1 <= box_a.y0
                )
                assert not overlaps, f"{label_a!r} overlaps {label_b!r}"
        plt.close(figure)


def test_the_caption_has_one_definition(measured_dir: Path) -> None:
    """The width calculation and the drawn text must not drift apart."""
    data = io.load_figure_data(measured_dir)
    summary = panel_a._tail_summary(
        data.combinations, "digital_twins", panel_a.DEFAULT_TOP_N
    )
    assert panel_a.block_note_text(summary) == f"n = {summary.total_papers:,} papers"


def test_the_figure_refuses_stale_labels(measured_dir: Path, tmp_path: Path) -> None:
    """A figure is harder to un-publish than a number.

    On 2026-09-08 a corpus run finished, the dictionaries were edited underneath
    it, and a figure was built and reported from labels no configuration on disk
    could reproduce. Nothing in the output said so.
    """
    import json
    import shutil

    staged = tmp_path / "processed"
    shutil.copytree(measured_dir, staged)
    manifest = {
        "config": {
            "themes": {"path": "config/themes.yaml", "version": 1, "sha256": "0" * 64},
            "modalities": {
                "path": "config/modalities.yaml", "version": 1, "sha256": "0" * 64,
            },
        }
    }
    (staged / "run_manifest.json").write_text(json.dumps(manifest))

    with pytest.raises(plot.StaleInputs):
        plot.build(staged, tmp_path / "figures", tag="stale")

    result = plot.build(staged, tmp_path / "figures", tag="stale", stale_ok=True)
    assert result.pdf.exists(), "--stale-ok must still draw, for a deliberate look back"


def test_a_directory_without_a_manifest_still_draws(synthetic_dir: Path, tmp_path: Path) -> None:
    """The synthetic tables have no run manifest and must not be blocked by one."""
    result = plot.build(synthetic_dir, tmp_path / "figures", tag="synthetic")
    assert result.pdf.exists()


def test_panel_a_draws_a_one_line_key_to_its_dot_colours(measured_dir: Path, tmp_path: Path) -> None:
    """Author's request, 2026-09-29: the four modality hues, named, in one row on top."""
    import matplotlib.pyplot as plt

    result = plot.build(measured_dir, tmp_path / "figures")
    figure, _, _ = plot.build_figure(result.data)
    legends = figure.legends
    assert len(legends) == 1
    key = legends[0]
    assert [t.get_text() for t in key.get_texts()] == [label for label, _ in style.MODALITY_GROUPS]
    assert key._ncols == len(style.MODALITY_GROUPS)
    # Every hue a present dot can take is named in the key, and nothing else is.
    used = {style.modality_color(k) for k in panel_a.MATRIX_ROWS}
    assert used == {color for _, color in style.MODALITY_GROUPS}
    # It sits above every theme title.
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    key_bottom = key.get_window_extent(renderer).y0
    for ax in figure.axes:
        title = ax.title
        if title.get_text():
            assert title.get_window_extent(renderer).y1 < key_bottom, title.get_text()
    plt.close(figure)


def test_a_bracket_arrow_joins_the_range_band_to_the_lower_plot(
    measured_dir: Path, tmp_path: Path
) -> None:
    """Author's request, 2026-09-29: white ground, a [-shaped arrow in the left margin."""
    import matplotlib.colors as mc
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch

    result = plot.build(measured_dir, tmp_path / "figures")
    figure, _, panel = plot.build_figure(result.data)
    assert mc.to_rgba(panel.lower.get_facecolor()) == mc.to_rgba("white")
    arrows = [a for a in figure.artists if isinstance(a, FancyArrowPatch)]
    assert len(arrows) == 1
    arrow = arrows[0]
    assert mc.to_rgba(arrow.get_edgecolor()) == mc.to_rgba(panel_b.RANGE_ARROW)
    assert arrow.get_linewidth() == pytest.approx(panel.lower.spines["left"].get_linewidth())
    # Green by the author's deliberate exception (DECISIONS 2026-09-29), but still
    # not a modality hue exactly, so no mark reads as a data series.
    assert panel_b.RANGE_ARROW not in set(style.MODALITY_COLORS.values())
    # The band's dashed rule is repeated at the top of the lower plot, where the
    # arrow lands, at the same value.
    lower_top = panel.lower.get_ylim()[1]
    rules = [
        line for line in panel.lower.get_lines()
        if list(line.get_ydata()) == [lower_top, lower_top]
        and mcolors.to_rgba(line.get_color()) == mcolors.to_rgba(panel_b.RANGE_RULE)
    ]
    assert len(rules) == 1 and rules[0].get_linestyle() == "--"

    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    box = arrow.get_window_extent(renderer)
    upper = panel.upper.get_window_extent(renderer)
    lower = panel.lower.get_window_extent(renderer)
    # A bracket: left of both plots, from the band's top down to the lower plot's top.
    assert box.x0 < upper.x0
    # The head lands just inside the lower plot, clear of its tick labels.
    assert upper.x0 < box.x1 < upper.x0 + 12
    lower_top = panel.lower.get_ylim()[1]
    band_top_px = panel.upper.transData.transform((0, lower_top))[1]
    assert box.y1 == pytest.approx(band_top_px, abs=2)
    assert box.y0 == pytest.approx(lower.y1, abs=4)
    # It crosses no tick label or axis title: the upright runs left of every label
    # in its height, and each arm clears every label it passes over.
    upright_x = box.x0
    arm_ys = (box.y1, box.y0)
    for ax in panel.axes:
        low, high = ax.get_ylim()
        drawn = [
            label for label, value in zip(ax.get_yticklabels(), ax.get_yticks())
            if low <= value <= high           # matplotlib lays out, but never draws, the rest
        ]
        for text in drawn + [ax.yaxis.label]:
            if not (text.get_text() and text.get_visible()):
                continue
            label = text.get_window_extent(renderer)
            if label.y1 > box.y0 and label.y0 < box.y1:
                assert label.x0 > upright_x + 2, text.get_text()
            if label.x1 > upright_x:
                for y in arm_ys:
                    assert not (label.y0 < y < label.y1), text.get_text()
    plt.close(figure)
