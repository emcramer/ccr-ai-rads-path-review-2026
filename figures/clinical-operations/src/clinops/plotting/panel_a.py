"""Panel A: cumulative oncology AI authorizations, on a log y axis.

One plot, three series: radiology cancer detection (66 devices), radiation
therapy planning (79), and digital pathology (9). X is the decision year, y is
the running total of authorizations through that year.

Why the axis is logarithmic
---------------------------
The comparison the panel exists to make is 145 radiology authorizations against
pathology's nine, a sixteen-fold gap. On a linear axis pathology is a flat line
on the floor: the reader can see that it is small and can see nothing else about
it -- not that it started in 1995, not that it sat still for twenty-six years,
not that it more than doubled in one year. A log axis draws both slopes at once,
and it is the *shape* of the pathology series, not only its size, that the review
argues about. Panel B then states the gap as a number, so nothing rests on
reading a ratio off a log axis by eye.

The zero problem
----------------
A log axis cannot draw a zero, and the honest options are few. This panel takes
the third of the three set out in ``docs/figure-spec.md``:

1. A broken axis across 1996-2015. **Rejected**: the twenty-six years in which
   pathology sat at two devices is the finding, and a break mark deletes it.
2. Clipping the x range to 2016, radiology's first year. **Rejected**: it puts
   the two 1995 Pap screeners off the page, and a figure that drops two of the
   nine devices it is about cannot be published.
3. **Adopted:** the x axis runs 1995 to 2026 continuously, with no break in
   either axis, and each series is drawn only from the first year its cumulative
   count reaches one. The years before that carry no mark at all.

**Explicitly rejected, and do not "fix" it back:** drawing the pre-authorization
years as a flat line along the axis floor. It reads as "this series was at the
floor value" when the series was at zero -- exactly the misreading a log axis
invites, and the one this project keeps guarding against. The absence of a line
is the honest mark for the absence of a device. The y floor sits at
:data:`Y_FLOOR`, below the smallest drawable value, so no series is drawn on top
of the bottom spine either.

That every line begins at its own first authorization is a statement about the
drawing rather than a label of an element, so it belongs in the figure legend and
not in the artwork. :func:`draw` returns the years involved, and the run summary
prints them, so whoever writes the legend reads them off the numbers rather than
off the picture.

The nine pathology devices
--------------------------
With n = 9 the devices are namable, and naming them is the argument: the whole
regulatory history of AI in cancer pathology fits in a list a reader gets through
in ten seconds. Each device is labelled with its year and its name -- four words
or fewer, no explanatory text, per the style guide's content rules.

Two label placements, chosen by how far the device sits from the gutter:

* Devices within :data:`LEADER_MAX_SPAN` years of the last year are labelled in
  the **right-hand gutter**, stacked, each with a hairline leader to its point on
  the line. Chronological order equals cumulative order, so the stack is in the
  same order as the points and no two leaders cross.
* Earlier devices -- the 1995 pair, thirty years from the gutter -- are labelled
  **inline**, just below their own point, in the empty band beneath the pathology
  plateau. A leader from 1995 to the gutter would cross the whole plot, which is
  why the gutter is not used for everything.

Where several devices share one point, as the four 2025 authorizations do, their
labels fan from that point. That is the drawing telling the truth: four devices
in one year is what the step is.

Colour
------
Hue marks the clinical domain and nothing else, so the two radiology series
**share a hue** and are separated by dash pattern, by marker, and by a direct
label. Pathology takes the deep pathology tint, which is what the style guide
assigns to thin strokes and small type. Nothing in this panel depends on colour
being seen: three dashes, three markers and three labels carry it in greyscale.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.ticker import FixedLocator, FuncFormatter, NullFormatter
from trends.plotting import style

from . import (
    CATEGORY_ORDER,
    category_color,
    category_dash,
    category_marker,
    device_label,
    series_label,
)

#: Lower y limit. Below one, so a series sitting at its first authorization is
#: drawn clear of the bottom spine rather than on top of it, and above zero,
#: which a log axis has no place for at all.
Y_FLOOR: Final[float] = 0.8

#: Headroom above the tallest series, as a multiple of its value. The gutter
#: labels for the two radiology series sit at the top of the panel and need room
#: to stack without being pushed off the axes.
Y_HEADROOM: Final[float] = 1.75

#: Labelled y ticks. Chosen rather than left to a locator: a log locator either
#: labels every decade (three labels on this range, too few to read a value off)
#: or every minor tick (thirty labels, unreadable at 7.5 pt).
Y_TICKS: Final[tuple[int, ...]] = (1, 2, 5, 10, 20, 50, 100)

#: Unlabelled minor ticks, so the log spacing is visible between the labels.
Y_MINOR_TICKS: Final[tuple[int, ...]] = (
    3, 4, 6, 7, 8, 9, 30, 40, 60, 70, 80, 90,
)

#: X tick step, in years. Thirty-two years cannot all carry a label at 7.5 pt:
#: at the drawn width a year is 0.16 in and "2026" needs 0.25 in.
X_TICK_STEP: Final[int] = 5

#: The last year always carries a tick, because it is the snapshot boundary and
#: a reader must be able to see where the data stop. A regular tick closer than
#: this to it is dropped instead of colliding with it.
X_TICK_MIN_GAP: Final[int] = 3

#: Line weight and marker size. The style guide's minimum stroke is 1.0; these
#: are the sibling figure's line-plot values, so the two figures print alike.
LINE_WIDTH: Final[float] = 1.3
MARKER_SIZE: Final[float] = 2.9
OPEN_MARKER_SIZE: Final[float] = 3.4

#: A device whose year is further than this from the last year is labelled
#: inline rather than in the gutter. Set so the 1995 pair goes inline -- a
#: leader from 1995 to the gutter would cross the entire plot and every
#: radiology line in it -- and everything from 2021 on goes to the gutter.
LEADER_MAX_SPAN: Final[int] = 10

#: Most pathology devices this panel will label individually. Nine fit; the
#: annotation is designed around n being small enough to name. A snapshot with
#: more than this must redesign the annotation rather than shed labels, so the
#: build raises instead of dropping a device silently.
MAX_ANNOTATED_DEVICES: Final[int] = 12

#: Gutter label anchor, in years to the right of the last year. Wide enough
#: that a gutter label never reads as a label of the last year's own marker,
#: which sits at the plot edge: at 0.7 the pathology open marker and the "2025
#: Galen Second Read" label were a hair apart.
_GUTTER_OFFSET: Final[float] = 1.0

#: Gap in years between the year an inline label's band becomes clear and where
#: its text starts. Small: the leader carries the distance, the gap only keeps
#: the text off the leader's elbow.
_INLINE_LABEL_GAP: Final[float] = 0.65

#: Where a leader starts and ends, in years either side of the plot edge.
_LEADER_START: Final[float] = 0.12
_LEADER_END: Final[float] = 0.58

#: Least displacement, in label heights, before a leader is drawn at all. A
#: label sitting on its own anchor needs no line pointing at itself.
_LEADER_MIN_SHIFT: Final[float] = 0.2

#: Colour of the small grey notes ("2026 partial"). The guide's subtle neutral.
NOTE_INK: Final[str] = style.SUBTLE


@dataclass(frozen=True)
class GutterLabel:
    """One label waiting to be placed in the right-hand gutter.

    Attributes:
        y_anchor: Where the thing being labelled sits, in log10 units.
        x_anchor: The year it sits at, where its leader starts.
        text: The label, hand-wrapped.
        colour: Line and text colour; a label is drawn in its series' own hue.
        size: Type size, in points. Series labels are the sibling figure's
            series size and device labels the smaller note size, so nine device
            names and two series names share one gutter without either being
            shrunk to fit the other.
    """

    y_anchor: float
    x_anchor: float
    text: str
    colour: str
    size: float


class TooManyDevices(ValueError):
    """More pathology devices than the panel's annotation was designed for.

    Raised rather than dropping labels: which nine devices exist is the panel's
    content, and a figure that quietly stops naming some of them is a figure
    that has stopped making its argument.
    """


@dataclass(frozen=True)
class PanelA:
    """What one Panel A build drew.

    Attributes:
        ax: The axes drawn on.
        first_years: First year each category reaches a cumulative count of one,
            which is where its line begins.
        undrawn_years: Years inside the x range that each category spent at
            zero, and so is *not* drawn for. The legend is written from this.
        totals: Final cumulative count per category.
        y_limits: The drawn y limits, floor first.
        partial_year: The last year, when the snapshot does not cover all of it.
        devices: The pathology devices annotated, in decision-date order.
    """

    ax: Axes
    first_years: dict[str, int | None]
    undrawn_years: dict[str, tuple[int, int] | None]
    totals: dict[str, int]
    y_limits: tuple[float, float]
    partial_year: int | None
    devices: pd.DataFrame


def x_ticks(years: list[int]) -> list[int]:
    """Return the labelled x ticks: a regular grid, plus the last year.

    The last year is the snapshot boundary, so it always carries a label. A grid
    tick within :data:`X_TICK_MIN_GAP` years of it is dropped rather than
    printed on top of it.
    """
    first, last = years[0], years[-1]
    grid = [year for year in range(first, last + 1) if (year - first) % X_TICK_STEP == 0]
    kept = [year for year in grid if last - year >= X_TICK_MIN_GAP]
    return kept + [last]


def _series_frame(cumulative: pd.DataFrame, category: str) -> pd.DataFrame:
    """Return one category's rows, sorted by year, from its first authorization.

    Rows before the first authorization are dropped rather than drawn, because
    their cumulative count is zero and a log axis has no zero. See the module
    docstring for the two alternatives that were rejected.
    """
    frame = cumulative.loc[cumulative["category"] == category].sort_values("year")
    reached = frame.loc[frame["cumulative_count"] >= 1]
    if reached.empty:
        return reached
    return frame.loc[frame["year"] >= int(reached["year"].iloc[0])]


def _undrawn_run(cumulative: pd.DataFrame, category: str) -> tuple[int, int] | None:
    """Return the span of leading years a category is not drawn for, if any."""
    frame = cumulative.loc[cumulative["category"] == category].sort_values("year")
    reached = frame.loc[frame["cumulative_count"] >= 1]
    if reached.empty or int(reached["year"].iloc[0]) == int(frame["year"].iloc[0]):
        return None
    return int(frame["year"].iloc[0]), int(reached["year"].iloc[0]) - 1


def _stack(
    labels: list[GutterLabel],
    y_limits: tuple[float, float],
    line_height: float,
) -> list[tuple[float, GutterLabel]]:
    """Stack gutter labels so none overlaps its neighbour or leaves the axes.

    The same two-pass arithmetic as the sibling figure's
    ``trends.plotting.panel_b._separate``, in log space: the first pass pushes
    each label up clear of the one below it, and the second, run only if the
    stack has overflowed the top, pushes it back down. A label's height depends
    on how many lines it wraps to, so a two-line label reserves twice the room.

    Args:
        labels: The labels to place, in any order. Their ``y_anchor`` is in
            **log10 units**, which is where the stacking must be done: the axis
            is logarithmic, so equal spacing on the page is equal spacing in the
            exponent.
        y_limits: Axis limits, in log10 units, the labels must stay inside.
        line_height: Height of one line of label text, in log10 units.

    Returns:
        ``(y_label, label)`` pairs, sorted ascending, where ``y_label`` is where
        the label was placed and ``label.y_anchor`` where its series or device
        actually sits.
    """
    if not labels:
        return []
    ordered = sorted(labels, key=lambda item: item.y_anchor)
    anchors = [item.y_anchor for item in ordered]
    padding = 0.5 * line_height
    heights = [
        line_height * (item.text.count("\n") + 1) * item.size / style.FS_NOTE
        for item in ordered
    ]
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

    return [(placed[index], ordered[index]) for index in range(len(placed))]


def _pathology_devices(authorizations: pd.DataFrame) -> pd.DataFrame:
    """Return the pathology-domain authorizations, in decision-date order.

    Raises:
        TooManyDevices: If there are more than :data:`MAX_ANNOTATED_DEVICES`.
    """
    devices = authorizations.loc[authorizations["domain"] == "pathology"].sort_values(
        ["decision_date", "submission_number"]
    )
    if len(devices) > MAX_ANNOTATED_DEVICES:
        raise TooManyDevices(
            f"{len(devices)} pathology authorizations, and Panel A labels each one "
            f"individually; the annotation was designed for at most "
            f"{MAX_ANNOTATED_DEVICES}. Redesign the annotation -- naming the devices "
            "is the panel's argument -- rather than raising this constant."
        )
    return devices.reset_index(drop=True)


def _log(value: float) -> float:
    """Return log10 of a positive value, for the label stacking arithmetic."""
    from math import log10

    return log10(value)


def draw(
    figure: Figure,
    cumulative: pd.DataFrame,
    authorizations: pd.DataFrame,
    rect: tuple[float, float, float, float],
    *,
    partial_year: int | None = None,
    title_x: float = 0.0,
) -> PanelA:
    """Draw Panel A into ``rect``.

    Args:
        figure: The figure to draw into.
        cumulative: Validated ``cumulative_by_year.csv``.
        authorizations: Validated ``authorizations.csv``; only its pathology rows
            are drawn, as the nine device labels.
        rect: ``(left, bottom, width, height)`` in figure fractions, covering the
            plot only. The caller reserves the y-label gutter to its left and the
            device-label gutter to its right.
        partial_year: The last year, when the snapshot does not cover all of it.
            Drawn as a shaded band, a dotted final segment and an open final
            marker, exactly as the sibling trends figure draws its partial year.
        title_x: Where the panel title sits, in axes fractions. Negative values
            put it left of the plot, over the y-label gutter, so it can line up
            with the panel letter instead of being indented by however wide that
            gutter happens to be. The caller owns the geometry, so the caller
            owns this number.

    Returns:
        A :class:`PanelA` recording what was drawn, including the years each
        series is *not* drawn for, which the run summary prints.

    Raises:
        TooManyDevices: If the snapshot holds more pathology authorizations than
            the annotation was designed for.
    """
    left, bottom, width, height = rect
    ax = figure.add_axes(rect)

    years = sorted(int(year) for year in cumulative["year"].unique())
    first_year, last_year = years[0], years[-1]
    peak = float(cumulative["cumulative_count"].max())
    y_top = max(peak * Y_HEADROOM, 10.0)

    if partial_year is not None:
        ax.axvspan(
            partial_year - 0.5, last_year + 0.6, color=style.PARTIAL_BAND, linewidth=0, zorder=0
        )

    ax.set_yscale("log")
    ax.set_xlim(first_year - 0.6, last_year + 0.6)
    ax.set_ylim(Y_FLOOR, y_top)
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color="#E8E8E8", linewidth=0.5)

    first_years: dict[str, int | None] = {}
    undrawn: dict[str, tuple[int, int] | None] = {}
    totals: dict[str, int] = {}
    entries: list[GutterLabel] = []

    for category in CATEGORY_ORDER:
        frame = _series_frame(cumulative, category)
        undrawn[category] = _undrawn_run(cumulative, category)
        rows = cumulative.loc[cumulative["category"] == category].sort_values("year")
        totals[category] = int(rows["cumulative_count"].iloc[-1]) if len(rows) else 0
        if frame.empty:
            first_years[category] = None
            continue
        x = frame["year"].to_numpy()
        y = frame["cumulative_count"].to_numpy(dtype=float)
        first_years[category] = int(x[0])
        colour = category_color(category)
        complete = x <= (partial_year - 1 if partial_year is not None else last_year)

        ax.plot(
            x[complete],
            y[complete],
            color=colour,
            linestyle=category_dash(category),
            linewidth=LINE_WIDTH,
            marker=category_marker(category),
            markersize=MARKER_SIZE,
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
                marker=category_marker(category),
                markersize=OPEN_MARKER_SIZE,
                markerfacecolor="white",
                markeredgecolor=colour,
                markeredgewidth=0.8,
                zorder=4,
            )
        if category != "pathology":
            # The pathology line is labelled inline instead, in the empty band
            # above its plateau: its end sits among the device labels, and a
            # third label in that stack would push them apart for nothing.
            entries.append(
                GutterLabel(
                    y_anchor=_log(float(y[-1])),
                    x_anchor=float(x[-1]),
                    text=series_label(category),
                    colour=colour,
                    size=style.FS_SERIES_LABEL,
                )
            )

    _label_pathology_line(ax, cumulative, first_year)

    devices = _pathology_devices(authorizations)
    entries.extend(_device_entries(ax, cumulative, devices, last_year))

    _draw_gutter(figure, ax, entries, (Y_FLOOR, y_top), height, last_year)
    _draw_axes(ax, years)

    if partial_year is not None:
        # Above the plot, not inside it: inside, it collides with whichever
        # series happens to end high.
        ax.annotate(
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

    ax.set_title(
        "Cumulative Oncology AI Authorizations",
        fontsize=style.FS_THEME_TITLE,
        fontfamily="serif",
        fontweight="bold",
        color=style.INK,
        pad=8.0,
        loc="left",
    )
    ax.title.set_x(title_x)
    return PanelA(
        ax=ax,
        first_years=first_years,
        undrawn_years=undrawn,
        totals=totals,
        y_limits=(Y_FLOOR, y_top),
        partial_year=partial_year,
        devices=devices,
    )


def _label_pathology_line(ax: Axes, cumulative: pd.DataFrame, first_year: int) -> None:
    """Label the pathology line inline, above its own plateau.

    The plateau runs flat for twenty-six years across an otherwise empty half of
    the plot, so the line can carry its name directly instead of spending a slot
    in the gutter stack, where it would sit among its own device labels.
    """
    frame = _series_frame(cumulative, "pathology")
    if frame.empty:
        return
    ax.annotate(
        series_label("pathology"),
        xy=(first_year + 0.4, float(frame["cumulative_count"].iloc[0])),
        xytext=(0, 4.0),
        textcoords="offset points",
        ha="left",
        va="bottom",
        fontsize=style.FS_SERIES_LABEL,
        color=category_color("pathology"),
    )


def _device_entries(
    ax: Axes,
    cumulative: pd.DataFrame,
    devices: pd.DataFrame,
    last_year: int,
) -> list[GutterLabel]:
    """Label the early devices inline and return gutter entries for the rest.

    A device is anchored to the point its own line actually draws -- its year's
    cumulative count -- not to its index. Where several devices share a year, as
    the four 2025 authorizations do, they share the anchor and their labels fan
    from it, which is what four devices in one year looks like.
    """
    colour = category_color("pathology")
    pathology = cumulative.loc[cumulative["category"] == "pathology"].set_index("year")
    entries: list[GutterLabel] = []
    inline: list[tuple[int, float, str]] = []

    for _, row in devices.iterrows():
        year = int(row["year"])
        anchor = float(pathology.loc[year, "cumulative_count"])
        text = device_label(str(row["submission_number"]), str(row["device"]), year)
        if last_year - year > LEADER_MAX_SPAN:
            inline.append((year, anchor, text))
        else:
            entries.append(
                GutterLabel(
                    y_anchor=_log(anchor),
                    x_anchor=float(year),
                    text=text,
                    colour=colour,
                    size=style.FS_NOTE,
                )
            )

    if inline:
        # Below the plateau, in the band between it and the axis floor. That band
        # is only empty where every other series is either absent or already
        # above the plateau, so the start year is measured rather than assumed:
        # radiology's cancer-detection line begins at 1 in 1998 and climbs
        # through this band until it clears the plateau around 2001, and text
        # placed at 1995 would sit on top of it. The band's clear year moves
        # whenever the data moves, so computing it is what keeps this correct.
        anchor_year = min(year for year, _, _ in inline)
        plateau = max(anchor for _, anchor, _ in inline)
        others = cumulative.loc[
            (cumulative["category"] != "pathology")
            & (cumulative["year"] >= anchor_year)
            & (cumulative["cumulative_count"] > 0)
            & (cumulative["cumulative_count"] <= plateau)
        ]
        clear_year = int(others["year"].max()) + 1 if not others.empty else anchor_year
        label_x = clear_year + _INLINE_LABEL_GAP

        for index, (year, anchor, text) in enumerate(inline):
            # Stacked downward in chronological order, with a hairline leader
            # each, because two devices share the one 1995 point.
            y_label = anchor * (0.72 ** (index + 1))
            ax.plot(
                [year + 0.1, label_x - 0.35],
                [anchor, y_label],
                color=colour,
                linewidth=0.5,
                zorder=2,
            )
            ax.annotate(
                text,
                xy=(label_x, y_label),
                ha="left",
                va="center",
                fontsize=style.FS_NOTE,
                color=colour,
                linespacing=1.25,
            )
    return entries


def _draw_gutter(
    figure: Figure,
    ax: Axes,
    entries: list[GutterLabel],
    y_limits: tuple[float, float],
    axes_height: float,
    last_year: int,
) -> None:
    """Stack the gutter labels beside the plot and draw their leaders.

    Label heights are known in points, so they are converted into log10 units --
    the axis' own units -- before the stacking arithmetic runs, the same
    conversion the sibling figure makes for its linear axes.
    """
    if not entries:
        return
    axes_height_pt = axes_height * figure.get_figheight() * 72.0
    span = _log(y_limits[1]) - _log(y_limits[0])
    log_per_point = span / axes_height_pt
    line_height = 1.3 * style.FS_NOTE * log_per_point
    limits = (_log(y_limits[0]), _log(y_limits[1]))

    for y_label, label in _stack(entries, limits, line_height):
        shifted = abs(y_label - label.y_anchor) > line_height * _LEADER_MIN_SHIFT
        if shifted or label.x_anchor < last_year:
            ax.plot(
                [label.x_anchor + _LEADER_START, last_year + _LEADER_END],
                [10.0**label.y_anchor, 10.0**y_label],
                color=label.colour,
                linewidth=0.5,
                clip_on=False,
                zorder=2,
            )
        ax.annotate(
            label.text,
            xy=(last_year + _GUTTER_OFFSET, 10.0**y_label),
            ha="left",
            va="center",
            fontsize=label.size,
            color=label.colour,
            linespacing=1.25,
            annotation_clip=False,
        )


def _draw_axes(ax: Axes, years: list[int]) -> None:
    """Set the ticks, the axis titles, and the spines."""
    ax.xaxis.set_major_locator(FixedLocator(x_ticks(years)))
    ax.set_xticklabels([str(year) for year in x_ticks(years)], fontsize=style.FS_TICK)
    ax.xaxis.set_minor_locator(FixedLocator(years))

    ax.yaxis.set_major_locator(FixedLocator(list(Y_TICKS)))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}"))
    ax.yaxis.set_minor_locator(FixedLocator(list(Y_MINOR_TICKS)))
    ax.yaxis.set_minor_formatter(NullFormatter())

    ax.tick_params(axis="both", which="major", labelsize=style.FS_TICK, pad=2.0,
                   colors=style.SUBTLE)
    ax.tick_params(axis="both", which="minor", length=1.2, colors=style.SUBTLE)
    ax.set_xlabel("Decision year", fontsize=style.FS_AXIS_LABEL, style="italic",
                  color=style.SUBTLE)
    # "log scale" is said in words. A reader must not have to infer the
    # transform from the spacing of the ticks.
    ax.set_ylabel(
        "Cumulative authorizations (log scale)",
        fontsize=style.FS_AXIS_LABEL,
        style="italic",
        color=style.SUBTLE,
    )
    for name in ("top", "right"):
        ax.spines[name].set_visible(False)
