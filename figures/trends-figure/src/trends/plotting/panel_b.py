"""Panel B: theme volume over time, drawn as two stacked plots.

Measured theme sizes differ by two orders of magnitude — Multimodal Integration
about 5,320 papers against Clinical/FDA's 93 — so one linear axis draws the small
themes as flat lines on the floor. The panel is therefore split, per
``docs/figure-spec.md``:

* **upper plot** — ``foundation_models`` and ``multimodal_integration``, each
  split into three clinical-domain lines;
* **lower plot** — ``digital_twins``, ``virtual_staining``, ``agentic_ai``, and
  the two ``clinical_fda`` domain lines.

The two plots share one x axis, labelled once under the lower plot. Each carries
its own linear y axis. Per-year counts throughout: nothing here is cumulative and
nothing is logarithmic.

Making the scale change unmistakable
------------------------------------
A stacked pair invites the one misreading that would ruin the panel: taking the
lower plot as a continuation of the upper, and so reading a 24-paper year as
though it were comparable to a 1,100-paper year. Four devices work against that,
and they are deliberately redundant, because any one of them can be lost when the
journal redraws the figure:

1. **A real gap** between the two plots, with the note that sits in it. They do
   not share a frame, a spine, or a y axis.
2. **Both y axes are labelled and ticked**, so the tick numbers themselves —
   0-1,200 above, 0-25 below — contradict any reading of one continuous axis.
3. **The lower plot's whole range is drawn on the upper plot**, as a tinted band
   from zero up to the lower plot's ceiling, capped by a dashed rule. The reader
   sees the entire lower plot as a sliver at the foot of the upper one, which is
   what it is. Below :data:`MIN_RATIO_FOR_BAND` the band would cover a third of
   the upper plot and teach nothing, so it is not drawn. The band's caption moved
   to the legend on 2026-09-02; the band and rule are structure and stay.
4. **The ratio is printed**, computed from the axes actually drawn, in the gap
   between the plots.

What must survive the drawing
-----------------------------
* **Pathology is exactly zero for a run of consecutive years.** A zero series
  drawn on the axis floor reads as an absent series. So the lower plot's y limit
  starts slightly below zero, lifting the zero line clear of the spine, and every
  year of the run carries its marker, so the zeros read as measured points rather
  than as a line that starts when the first paper appears. The run used to be
  named on the figure as well, with a curved leader dropped onto the zero line;
  that sentence moved to the legend on 2026-09-02, under the style guide's rule
  that the artwork carries no explanatory prose. :func:`_leading_zero_run` still
  finds the span, and the run summary still prints it, so whoever writes the
  legend reads it from the numbers rather than off the picture.
* **Small counts are noisy.** The lower plot magnifies a 93-paper theme, so its
  shape — clinical radiology's 13, 9, 21 across 2024-2026 — invites a story that
  the numbers cannot carry. That warning, and the change-of-scale note, are made
  in the figure legend rather than on the figure: see :data:`SHOW_GAP_NOTES`. The
  scale difference is still carried graphically, by two labelled axes, the gap
  between the plots, and the range band on the upper plot.

The final year is partial. Its segment is drawn dotted and its point as an open
marker, in both plots, and the year sits inside a shaded band marked "partial".
No trend statement may rest on it.

Colour
------
Colour marks the **clinical domain**, which is a modality statement and so is
semantic under ``../ink_style_guide.md``: radiology blue, pathology the deep
pathology tint, cross-specialty the guide's structural grey. Theme is carried by
the dash pattern, so two blue lines in the upper plot are radiology work in two
different themes. Marker doubles the domain rather than the theme, so a
monochrome print keeps both dimensions: dash says which theme, marker says which
side.

A series drawn undivided makes no domain claim and takes ink -- digital twins and
agentic AI -- unless its papers state one anyway, as virtual staining's do. Two
series may therefore share a hue and a marker, and two do in each plot; the dash
and the end label separate them. See ``style.DOMAIN_MARKERS`` for the
measurement behind that, and for why a fifth shape was not invented for the
second domain-less series.

Every series keeps its own dash and its own label at the end of the line, so
nothing here depends on colour being seen, and the panel survives greyscale.
"""

from __future__ import annotations

from dataclasses import dataclass

import matplotlib
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import FancyArrowPatch
from matplotlib.path import Path

from . import style

#: Series drawn in the upper plot, in drawing order. Both large themes are split
#: by clinical domain, per the 2026-09-02 specification: the review's question is
#: *where* each theme is being pursued, not only how large it is. Cross-specialty
#: (stored as ``both``) is small -- 39 foundation-model papers and 276 multimodal
#: ones -- but it is the integrative case the review argues about, so it is drawn
#: rather than folded into either side.
#:
#: Papers whose only labels are non-imaging carry no domain and appear on no
#: line here, so these six do not sum to the two theme totals. The legend says so.
UPPER_SERIES: tuple[tuple[str, str], ...] = (
    ("foundation_models", "radiology"),
    ("foundation_models", "pathology"),
    ("foundation_models", "both"),
    ("multimodal_integration", "radiology"),
    ("multimodal_integration", "pathology"),
    ("multimodal_integration", "both"),
)

#: Series drawn in the lower plot, in drawing order. Three of the five are drawn
#: undivided: digital twins is too small to split three ways, virtual staining is
#: pathologic by definition, and agentic AI is both small and deliberately
#: cross-cutting -- an agent that reads reports, images and records is not
#: usefully assigned to one specialty.
#:
#: Order matters where lines sit on zero together, because the last one drawn
#: puts its marker on top. Agentic AI is zero until the mid-twenties and the
#: clinical pathology line is zero through 2021, so the two runs overlap for
#: seven years. Agentic AI is drawn between them rather than last: the clinical
#: markers stay on top, because the pathology zero run is the panel's point, and
#: the diamond still shows around the square, which the square would not do
#: around a circle. The two shapes are the same area at 2.9 pt but the diamond's
#: box is 1.41 times wider, so its points clear the square's edges whichever is
#: drawn first, and both zero runs read as measured years.
LOWER_SERIES: tuple[tuple[str, str], ...] = (
    ("digital_twins", "all"),
    ("virtual_staining", "all"),
    ("agentic_ai", "all"),
    ("clinical_fda", "radiology"),
    ("clinical_fda", "pathology"),
)

_SERIES_ORDER: tuple[tuple[str, str], ...] = UPPER_SERIES + LOWER_SERIES

#: Gap between the two plots, in inches. It has to read as a deliberate break in
#: the axis rather than as a margin, which is now its whole job: the notes that
#: used to sit here moved to the legend on 2026-09-02. Sized for the break alone,
#: it is narrower than it was; restoring SHOW_GAP_NOTES needs about 0.34 in again,
#: or the two lines will collide with the lower plot.
GAP_IN: float = 0.20
GAP_IN_WITH_NOTES: float = 0.34

#: Share of the plotting height, gap excluded, given to the upper plot.
UPPER_SHARE: float = 0.58

#: Fraction of a plot's range left below zero, so a series sitting on zero is
#: drawn clear of the bottom spine instead of on top of it.
_ZERO_LIFT: float = 0.075

#: Shortest run of leading zeros that is named on the figure.
MIN_ZERO_RUN: int = 3

#: Least ratio between the two y scales before the lower plot's range is drawn
#: onto the upper plot. The band exists to show an extreme ratio; below this it
#: covers a third of the upper plot and teaches the reader nothing the two sets
#: of tick numbers do not already say. On the measured corpus the ratio is about
#: forty, so the band is drawn.
MIN_RATIO_FOR_BAND: float = 3.0

#: Print the change-of-scale and small-count notes in the gap between the plots.
#: Off by author's decision of 2026-09-02: both statements belong in the figure
#: legend, which the journal prints beneath the figure. The scale difference is
#: still shown graphically -- two labelled axes, a real gap, and the range band
#: on the upper plot -- so turning the prose off costs the reader nothing that
#: the drawing does not already say. Set True to restore both lines.
SHOW_GAP_NOTES: bool = False

#: Largest yearly count in the lower plot for which the small-count note is
#: still true. It is a claim about the data, so it is drawn only when the data
#: support it: at a few hundred papers a year, a difference of a few papers is
#: no longer what the warning is about. Unused while SHOW_GAP_NOTES is False.
NOISE_NOTE_MAX_PEAK: float = 50.0

#: Tint of the band on the upper plot that marks the lower plot's whole range,
#: and the colour of its dashed rules and of the bracket arrow joining the plots.
#:
#: A DELIBERATE EXCEPTION to the style guide's rule that hue is only for data
#: types. Green is the project's "Clinical text / EHR" hue, and a structural
#: element in it could be read as clinical-text data. The author chose it anyway
#: on 2026-09-29: the earlier slate blue (#E7EEF4 band, #7B8B99 rule, #4F6F8F
#: arrow) had too little contrast against the grey partial-year band and the
#: grey series, and Panel B draws no clinical-text series for it to be confused
#: with. The band is the author's pale mint; the rules and arrow are a deeper
#: green, because the mint vanishes as a thin stroke on white. Do not "correct"
#: this back without reading the 2026-09-29 entry in docs/DECISIONS.md.
RANGE_BAND: str = "#9FFCDF"
RANGE_RULE: str = "#47624F"
RANGE_ARROW: str = "#47624F"

#: How far left of the plots' y axis the bracket's upright runs, in points.
#: Measured: the widest tick label in the bracket's height ("0" on the upper
#: plot) starts 8.5 pt left of the axis, so 15 pt clears it by about 6 pt.
_BRACKET_OFFSET_PT: float = 15.0

#: How far inside the lower plot's y axis the arrowhead's tip lands, in points.
_BRACKET_HEAD_INSET_PT: float = 6.0

#: Colour of the small grey notes ("2026 partial", and the gap notes when they
#: are switched back on). The style guide's subtle neutral.
NOTE_INK: str = style.SUBTLE


@dataclass(frozen=True)
class PanelB:
    """What one Panel B build drew.

    Attributes:
        upper: The upper plot's axes, or ``None`` if no upper series was present.
        lower: The lower plot's axes, or ``None`` if no lower series was present.
        scale_ratio: How many times finer the lower plot's y axis is than the
            upper's, or ``None`` when only one plot was drawn.
        zero_run: ``(first_year, last_year)`` of the pathology line's leading run
            of zero years, or ``None`` when there is no run worth naming.
    """

    upper: Axes | None
    lower: Axes | None
    scale_ratio: float | None
    zero_run: tuple[int, int] | None

    @property
    def axes(self) -> tuple[Axes, ...]:
        """The axes drawn, upper first."""
        return tuple(ax for ax in (self.upper, self.lower) if ax is not None)


class UnknownTheme(ValueError):
    """``theme_year_counts.csv`` names a theme the figure has no place for."""


def _partition(theme_years: pd.DataFrame) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Select the series each plot draws, and ignore every other row.

    This is a **filter**, not a fallback. ``theme_year_counts.csv`` carries every
    (theme, domain) combination by design -- five themes times five domains,
    300 rows on the current corpus -- because the table is the record and the
    figure decides what to draw. An earlier version of this function appended
    any unrecognised (theme, domain) pair to the lower plot, which on that table
    would have drawn about nineteen lines nobody asked for, silently.

    A row the specification does not name is therefore skipped. Skipping is safe
    because the rows are a partition and the drawn subset is chosen deliberately:
    the clinical theme has a ``both`` row of three papers that the spec does not
    draw, and every theme has ``none`` and ``all`` rows that no line uses.

    The one thing that is *not* skipped is an unknown theme. That means the
    canonical key list has moved and this module has not caught up, which is a
    bug rather than a data variation, so it raises.

    Raises:
        UnknownTheme: If a theme outside :data:`style.THEME_ORDER` is present.
    """
    themes = set(theme_years["theme"].astype(str))
    unknown = sorted(themes - set(style.THEME_ORDER))
    if unknown:
        raise UnknownTheme(
            f"theme_year_counts.csv names theme(s) the figure does not know: "
            f"{', '.join(unknown)}. Add them to style.THEME_ORDER and decide "
            "which plot they belong in, in UPPER_SERIES or LOWER_SERIES."
        )
    present = set(map(tuple, theme_years[["theme", "domain"]].drop_duplicates().to_numpy()))
    upper = [pair for pair in UPPER_SERIES if pair in present]
    lower = [pair for pair in LOWER_SERIES if pair in present]
    return upper, lower


#: Years before which a series is not drawn, because its earlier matches do not
#: mean what its label means. Only ``agentic_ai`` qualifies, and the reason is
#: measured rather than stylistic: 24 of its 27 papers from 2025 onward are
#: strictly agentic (89%), against 1 of 8 before 2025 (12%). "Agent" acquired its
#: current sense around 2025; earlier hits are reinforcement-learning agents, or
#: models whose authors simply called them agents. No vocabulary separates those,
#: because they use the word correctly for their own era. The author set the cut
#: at 2024 on 2026-09-03 -- one year earlier than the precision data alone would
#: suggest, which keeps the rise visible rather than starting the line at its
#: peak. The omitted papers stay in the theme total and in Panel A; only the
#: drawn line starts late, and the legend says so.
SERIES_START_YEAR: dict[tuple[str, str], int] = {
    ("agentic_ai", "all"): 2024,
}


def _series_frame(theme_years: pd.DataFrame, theme: str, domain: str) -> pd.DataFrame:
    """Return one series' rows, sorted by year and cut to its drawable span.

    A series listed in :data:`SERIES_START_YEAR` is truncated at the left. This
    hides no paper from the figure's totals -- it declines to draw years whose
    counts would be read as meaning something the labels do not support.
    """
    frame = theme_years.loc[
        (theme_years["theme"] == theme) & (theme_years["domain"] == domain)
    ].sort_values("year")
    start = SERIES_START_YEAR.get((theme, domain))
    if start is not None:
        frame = frame.loc[frame["year"] >= start]
    return frame


def _peak(theme_years: pd.DataFrame, series: list[tuple[str, str]]) -> float:
    """Return the largest yearly count across a set of series, at least one."""
    values = [
        float(frame["n_papers"].max())
        for theme, domain in series
        if not (frame := _series_frame(theme_years, theme, domain)).empty
    ]
    return max(values) if values else 1.0


def _leading_zero_run(theme_years: pd.DataFrame, theme: str, domain: str) -> tuple[int, int] | None:
    """Return the span of a series' leading run of zero years, if it has one.

    Returns ``None`` unless the run starts at the series' first year, is at least
    :data:`MIN_ZERO_RUN` years long, and is followed by a non-zero year — a series
    that is zero throughout has nothing to contrast against and is not annotated.
    """
    frame = _series_frame(theme_years, theme, domain)
    if frame.empty:
        return None
    counts = frame["n_papers"].to_numpy()
    years = frame["year"].to_numpy()
    non_zero = np.flatnonzero(counts > 0)
    if non_zero.size == 0 or non_zero[0] < MIN_ZERO_RUN:
        return None
    return int(years[0]), int(years[non_zero[0] - 1])


def _separate(
    labels: list[tuple[float, str, str]],
    y_limits: tuple[float, float],
    line_height: float,
) -> list[tuple[float, float, str, str]]:
    """Stack end labels so none overlaps its neighbour and none leaves the axes.

    Two passes. The first pushes each label up clear of the one below it; the
    second, run only if the stack has overflowed the top, pushes it back down.
    A label's height depends on how many lines it wraps to, so a two-line label
    reserves twice the room of a one-line label.

    Args:
        labels: ``(y, text, colour)`` triples, in any order.
        y_limits: The axis limits the labels must stay inside.
        line_height: Height of one line of label text, in data units.

    Returns:
        ``(y_label, y_data, text, colour)`` quadruples, sorted ascending, where
        ``y_data`` is where the series actually ended and ``y_label`` is where
        its label was placed.
    """
    if not labels:
        return []
    ordered = sorted(labels, key=lambda item: item[0])
    anchors = [item[0] for item in ordered]
    # Half a line of air between neighbours, so two stacked labels do not abut.
    padding = 0.5 * line_height
    heights = [line_height * (item[1].count("\n") + 1) for item in ordered]
    placed = list(anchors)
    low, high = y_limits

    for index in range(1, len(placed)):
        needed = (heights[index - 1] + heights[index]) / 2 + padding
        placed[index] = max(placed[index], placed[index - 1] + needed)

    placed[-1] = min(placed[-1], high - heights[-1] / 2)
    for index in range(len(placed) - 2, -1, -1):
        needed = (heights[index] + heights[index + 1]) / 2 + padding
        placed[index] = min(placed[index], placed[index + 1] - needed)
    placed[0] = max(placed[0], low + heights[0] / 2)

    return [
        (placed[index], anchors[index], ordered[index][1], ordered[index][2])
        for index in range(len(placed))
    ]


def _draw_plot(
    figure: Figure,
    ax: Axes,
    theme_years: pd.DataFrame,
    series: list[tuple[str, str]],
    *,
    years: list[int],
    partial_year: int | None,
    y_top: float,
    y_bottom: float,
    axes_height: float,
    show_x_labels: bool,
) -> None:
    """Draw one of the two plots: its lines, its axes, and its end labels.

    Args:
        figure: The figure being drawn into, for the point-to-data conversion.
        ax: The axes to draw on.
        theme_years: Validated ``theme_year_counts.csv``.
        series: The ``(theme, domain)`` pairs this plot carries, in drawing order.
        years: Every year in the table, ascending.
        partial_year: The year flagged partial, or ``None``.
        y_top: Upper y limit, chosen by the caller so that both plots' limits are
            known before either is drawn.
        y_bottom: Lower y limit, slightly below zero so a zero series is visible.
        axes_height: This plot's height as a fraction of the figure, used to turn
            label heights in points into data units.
        show_x_labels: Whether this plot carries the shared x axis' tick labels
            and its title. Only the bottom plot does.
    """
    first_year, last_year = years[0], years[-1]

    if partial_year is not None:
        ax.axvspan(
            partial_year - 0.5,
            last_year + 0.5,
            color=style.PARTIAL_BAND,
            linewidth=0,
            zorder=0,
        )

    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color="#E8E8E8", linewidth=0.5)
    ax.set_xlim(first_year - 0.4, last_year + 0.5)
    ax.set_ylim(y_bottom, y_top)

    label_entries: list[tuple[float, str, str]] = []
    for theme, domain in series:
        frame = _series_frame(theme_years, theme, domain)
        if frame.empty:
            continue
        x = frame["year"].to_numpy()
        y = frame["n_papers"].to_numpy()
        colour = style.series_color(theme, domain)
        dashes = style.series_dash(theme, domain)
        marker = style.series_marker(theme, domain)

        complete = x <= (partial_year - 1 if partial_year is not None else last_year)
        ax.plot(
            x[complete],
            y[complete],
            color=colour,
            linestyle=dashes,
            linewidth=1.3,
            marker=marker,
            markersize=2.9,
            markeredgewidth=0.0,
            zorder=3,
        )
        if partial_year is not None and complete.sum() >= 1 and (~complete).any():
            bridge = slice(int(complete.sum()) - 1, int(complete.sum()) + 1)
            ax.plot(
                x[bridge],
                y[bridge],
                color=colour,
                linestyle=(0, (1.2, 1.2)),
                linewidth=1.1,
                zorder=3,
            )
            ax.plot(
                x[~complete],
                y[~complete],
                color=colour,
                linestyle="none",
                marker=marker,
                markersize=3.4,
                markerfacecolor="white",
                markeredgecolor=colour,
                markeredgewidth=0.8,
                zorder=4,
            )
        label_entries.append(
            (
                float(y[-1]),
                style.series_label(theme, domain),
                style.series_text_color(theme, domain),
            )
        )

    ax.set_xticks(years)
    if show_x_labels:
        ax.set_xticklabels([str(year) for year in years], fontsize=style.FS_TICK)
        ax.set_xlabel(
            "Publication year",
            fontsize=style.FS_AXIS_LABEL,
            style="italic",
            color=style.SUBTLE,
        )
    else:
        ax.set_xticklabels([])
    ax.tick_params(axis="both", labelsize=style.FS_TICK, pad=2.0, colors=style.SUBTLE)
    ax.set_ylabel(
        "# of papers",
        fontsize=style.FS_AXIS_LABEL,
        style="italic",
        color=style.SUBTLE,
    )
    for name in ("top", "right"):
        ax.spines[name].set_visible(False)

    # Label heights are known in points; convert them into data units so the
    # stacking arithmetic can be done on the y axis.
    axes_height_pt = axes_height * figure.get_figheight() * 72.0
    data_per_point = (y_top - y_bottom) / axes_height_pt
    line_height = 1.3 * style.FS_SERIES_LABEL * data_per_point

    for y_label, y_data, text, colour in _separate(label_entries, (y_bottom, y_top), line_height):
        if abs(y_label - y_data) > line_height * 0.2:
            ax.plot(
                [last_year + 0.14, last_year + 0.52],
                [y_data, y_label],
                color=colour,
                linewidth=0.5,
                clip_on=False,
                zorder=2,
            )
        ax.annotate(
            text,
            xy=(last_year + 0.6, y_label),
            xycoords=("data", "data"),
            ha="left",
            va="center",
            fontsize=style.FS_SERIES_LABEL,
            color=colour,
            linespacing=1.25,
            annotation_clip=False,
        )


def _mark_lower_range(ax: Axes, lower_top: float) -> None:
    """Draw the lower plot's whole range onto the upper plot.

    The band runs from zero to the lower plot's ceiling. On the real numbers it is
    a sliver a couple of points high, which is the honest picture: that sliver is
    the entire lower plot.

    The band and its dashed rule are structural and stay. The sentence that used
    to sit beside the rule -- "the whole lower plot fits below this line" -- was
    removed on 2026-09-02: it explained the drawing rather than naming an
    element, which the style guide keeps out of the artwork and puts in the
    legend. What it said is now a clause of the legend's Panel B sentence.
    """
    ax.axhspan(0.0, lower_top, color=RANGE_BAND, linewidth=0, zorder=0.5)
    ax.axhline(lower_top, color=RANGE_RULE, linewidth=0.7, linestyle=(0, (2.6, 1.6)), zorder=1)


def _point_band_to_lower_plot(
    figure: Figure, upper_ax: Axes, lower_ax: Axes, lower_top: float
) -> None:
    """Draw a ``[``-shaped arrow in the left margin, from the band to the lower plot.

    The band and the lower plot are the same range of papers at two scales, and
    the reader has to see that. Author's request, 2026-09-29, after a straight
    arrow down the middle and a tint carried into the lower plot were both tried.

    Both arms sit at the same value, ``lower_top``: the top arm leaves the upper
    plot where the band's dashed rule meets the axis, and the bottom arm points
    into the top of the lower plot, its head just inside the axis. So the bracket says "this line is that line".
    The arms cannot sit at mid-height: the upper plot's "0" tick label covers the
    band's middle, and the lower plot's axis title covers its middle.

    The arrow is in the band's own slate blue, not the radiology hue, so it
    reads as belonging to the band rather than to a series. Logged in
    ``docs/DECISIONS.md``.
    """
    # The same dashed rule the band carries, at the same value, where the arrow
    # lands: the two rules are one line drawn at two scales. It sits on the axes'
    # top edge, so it is not clipped there, or half its width would vanish.
    lower_ax.axhline(
        lower_top, color=RANGE_RULE, linewidth=0.7, linestyle=(0, (2.6, 1.6)),
        zorder=1, clip_on=False,
    )
    to_figure = figure.transFigure.inverted()
    x_spine = upper_ax.get_xlim()[0]
    top = to_figure.transform(upper_ax.transData.transform((x_spine, lower_top)))
    bottom = to_figure.transform(lower_ax.transData.transform((x_spine, lower_top)))
    points = 1.0 / 72.0 / figure.get_figwidth()
    x_bracket = top[0] - _BRACKET_OFFSET_PT * points
    # The head sits just inside the lower plot, not on its axis: on the axis its
    # lower edge would touch the top tick label. The plot's top-left corner is
    # empty on this data, since every lower series starts near zero.
    x_head = bottom[0] + _BRACKET_HEAD_INSET_PT * points
    path = Path(
        [
            (top[0], top[1]),
            (x_bracket, top[1]),
            (x_bracket, bottom[1]),
            (x_head, bottom[1]),
        ]
    )
    figure.add_artist(
        FancyArrowPatch(
            path=path,
            transform=figure.transFigure,
            arrowstyle="-|>,head_length=0.5,head_width=0.25",
            mutation_scale=10,
            color=RANGE_ARROW,
            # The axis-line weight, so the bracket reads as structure, like the
            # spines, rather than as one more series. Author's request, 2026-09-29.
            linewidth=matplotlib.rcParams["axes.linewidth"],
            joinstyle="miter",
            capstyle="butt",
            shrinkA=0,
            shrinkB=0,
            zorder=6,
        )
    )


# The pathology zero run used to be named on the figure, with a curved leader
# dropped onto the zero line: "Pathology: 0 papers in every year from 2015 to
# 2021". It was removed on 2026-09-02. It is an explanation, not a label of an
# element, and the style guide keeps explanations in the legend; at nine words
# it was also far past the four-word limit for anything that may stand in the
# artwork. What the drawing still does is show the run: every zero year carries
# its own marker, and the lower plot's floor sits below zero so the run reads as
# seven measured points rather than as a line that starts in 2022. The sentence
# naming the years now lives in the figure legend, and :func:`_leading_zero_run`
# still computes the span, which is reported in the run summary.


def _draw_gap_notes(
    figure: Figure,
    left: float,
    y: float,
    ratio: float,
    lower_peak: float,
) -> None:
    """Print, in the gap between the plots, why the two plots are not one plot."""
    if not SHOW_GAP_NOTES:
        return
    ratio_text = f"{ratio:,.0f}×" if ratio >= 10 else f"{ratio:.1f}×"
    lines = [
        "Note the change of scale: the lower plot's y axis is "
        f"{ratio_text} finer than the upper plot's.",
    ]
    if lower_peak <= NOISE_NOTE_MAX_PEAK:
        lines.append(
            f"The lower plot's largest year is {lower_peak:,.0f} papers. A "
            "difference of a few papers between adjacent years carries no "
            "information."
        )
    figure.text(
        left,
        y,
        "\n".join(lines),
        ha="left",
        va="bottom",
        fontsize=style.FS_NOTE,
        color=NOTE_INK,
        linespacing=1.35,
    )


def draw(
    figure: Figure,
    theme_years: pd.DataFrame,
    rect: tuple[float, float, float, float],
) -> PanelB:
    """Draw Panel B into ``rect`` as two stacked plots sharing one x axis.

    Args:
        figure: The figure to draw into.
        theme_years: Validated ``theme_year_counts.csv``.
        rect: ``(left, bottom, width, height)`` in figure fractions, covering both
            plots and the gap between them. The caller reserves room to the right
            for the end-of-line labels and below for the shared x axis.

    Returns:
        A :class:`PanelB` naming the axes drawn, the ratio between their scales,
        and the zero run that was annotated.
    """
    left, bottom, width, height = rect
    fig_h = figure.get_figheight()

    years = sorted(theme_years["year"].unique().tolist())
    last_year = years[-1]
    partial_years = theme_years.loc[theme_years["partial_year"] == 1, "year"].unique()
    partial_year = int(partial_years[0]) if len(partial_years) else None

    upper_series, lower_series = _partition(theme_years)
    zero_run = _leading_zero_run(theme_years, "clinical_fda", "pathology")
    # The lower plot's headroom. It used to open to 1.34 to make room for the
    # zero-run note; the note moved to the legend on 2026-09-02 and the headroom
    # follows it down, closing the dead band left above the lines.
    #
    # This moves a published number. The headroom sets the lower plot's y limit,
    # the y limit sets the ratio between the two scales, and that ratio is quoted
    # in the figure legend and in the description. Whoever changes it must read
    # the new value out of ``figures/trends_figure_summary.txt`` and carry it into
    # both documents -- never off the picture. Author's decision, 2026-09-02.
    lower_headroom = 1.12

    upper_ax: Axes | None = None
    lower_ax: Axes | None = None
    ratio: float | None = None

    if upper_series and lower_series:
        gap_in = GAP_IN_WITH_NOTES if SHOW_GAP_NOTES else GAP_IN
        gap = min(gap_in / fig_h, 0.4 * height)
        plots_h = height - gap
        upper_h = UPPER_SHARE * plots_h
        lower_h = plots_h - upper_h

        upper_peak = _peak(theme_years, upper_series)
        lower_peak = _peak(theme_years, lower_series)
        upper_top, upper_bottom = upper_peak * 1.10, -_ZERO_LIFT * upper_peak
        lower_top, lower_bottom = lower_peak * lower_headroom, -_ZERO_LIFT * lower_peak

        lower_ax = figure.add_axes((left, bottom, width, lower_h))
        upper_ax = figure.add_axes((left, bottom + lower_h + gap, width, upper_h))

        _draw_plot(
            figure,
            lower_ax,
            theme_years,
            lower_series,
            years=years,
            partial_year=partial_year,
            y_top=lower_top,
            y_bottom=lower_bottom,
            axes_height=lower_h,
            show_x_labels=True,
        )
        _draw_plot(
            figure,
            upper_ax,
            theme_years,
            upper_series,
            years=years,
            partial_year=partial_year,
            y_top=upper_top,
            y_bottom=upper_bottom,
            axes_height=upper_h,
            show_x_labels=False,
        )
        ratio = (upper_top - upper_bottom) / (lower_top - lower_bottom)
        if ratio >= MIN_RATIO_FOR_BAND:
            _mark_lower_range(upper_ax, lower_top)
            _point_band_to_lower_plot(figure, upper_ax, lower_ax, lower_top)
        _draw_gap_notes(figure, left, bottom + lower_h + 0.055 * gap, ratio, lower_peak)
        annotate_on = upper_ax
    else:
        # Only one plot has anything to draw. It takes the whole rectangle rather
        # than leaving an empty box beside it.
        series = upper_series or lower_series
        peak = _peak(theme_years, series)
        headroom = lower_headroom if series is lower_series else 1.10
        ax = figure.add_axes(rect)
        _draw_plot(
            figure,
            ax,
            theme_years,
            series,
            years=years,
            partial_year=partial_year,
            y_top=peak * headroom,
            y_bottom=-_ZERO_LIFT * peak,
            axes_height=height,
            show_x_labels=True,
        )
        if series is lower_series:
            lower_ax = ax
        else:
            upper_ax = ax
        annotate_on = ax

    if partial_year is not None:
        # Above the top plot, not inside it: inside, it collides with whichever
        # series happens to end high, and this figure cannot know which will.
        annotate_on.annotate(
            f"{partial_year} partial",
            xy=(partial_year, 1.0),
            xycoords=("data", "axes fraction"),
            xytext=(0, 2.0),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=style.FS_NOTE,
            color=NOTE_INK,
            annotation_clip=False,
        )

    return PanelB(upper=upper_ax, lower=lower_ax, scale_ratio=ratio, zero_run=zero_run)
