"""Panel B: how the two fields get authorized.

Two horizontal bars, one per clinical domain, each divided into the three FDA
marketing pathways in the order 510(k), De Novo, PMA. Bars are normalized to
100 % of their own domain.

The finding: **radiology iterates inside established device categories and
pathology keeps having to create new ones.** 140 of radiology's 145
authorizations are 510(k)s, cleared against a predicate device that already
exists; pathology's nine split three, three and three, evenly across all three
routes. An even split across all three pathways is what a field with almost no
predicates to clear against looks like.

Why the bars are normalized
---------------------------
145 against 9 on a shared count axis draws pathology as a stub about a
sixteenth the length of the radiology bar, and the composition -- which is the
whole claim -- becomes unreadable inside it. Normalizing costs the reader the
sense of scale, so the scale is put back in type rather than left out: every
segment prints its own count, and every bar prints ``n = …`` at its end. Panel
A carries the volume comparison on its own axis.

Colour and texture
------------------
Hue marks the **clinical domain**, which is a data-modality statement and so is
semantic under ``../../ink_style_guide.md``: radiology blue, pathology pink,
both fixed project-wide. Bars are areas, so they take the border hues; hatch
lines and segment counts are thin strokes and small type, so they take the deep
variants, exactly as the guide's own parenthetical directs.

**The marketing pathway gets no hue at all.** It is not a modality, and the
guide is explicit that anything which is not a modality does not get a colour --
reach for hatching, dashes and weight first. So pathway is carried by fill
texture: 510(k) solid, De Novo diagonal hatch, PMA cross hatch, with a key
beneath the panel drawn in neutral ink so the key itself claims no domain. The
panel therefore survives greyscale with both dimensions intact: position and hue
say which field, texture says which route, and every segment carries its count
in type besides.

Slivers
-------
Radiology's De Novo and PMA segments are 1.4 % and 2.1 % of their bar. Type does
not fit inside a sliver that narrow at any size this project permits, so those
counts are printed above the bar with hairline leaders instead of being shrunk
until they fit. Whether a segment is wide enough is **measured**, in inches,
against :data:`MIN_INSIDE_LABEL_IN`, rather than assumed from the data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from matplotlib.ticker import PercentFormatter
from trends.plotting import style

from . import (
    CATEGORY_DOMAIN,
    DOMAIN_ORDER,
    PATHWAY_ORDER,
    domain_color,
    domain_label,
    pathway_hatch,
    pathway_label,
)

#: Height of one bar, in axis units, where the bars sit one unit apart.
BAR_HEIGHT: Final[float] = 0.44

#: Padding above and below the outermost bars, in axis units.
_Y_PAD: Final[float] = 0.62

#: Narrowest segment that will hold its count inside itself, in inches. A
#: five-point digit is about 0.05 in wide and needs air either side; below this
#: the count goes above the bar on a leader instead of being shrunk to fit.
MIN_INSIDE_LABEL_IN: Final[float] = 0.17

#: Vertical offset of a sliver's count above the bar, in axis units.
_SLIVER_RISE: Final[float] = 0.42

#: Hairline weight for the segment borders and the sliver leaders. The style
#: guide's minimum stroke is 1.0 for structural strokes; these are hairlines on
#: a filled area, where the sibling figure also draws 0.5-0.8.
_BORDER_WIDTH: Final[float] = 0.8
_LEADER_WIDTH: Final[float] = 0.5


@dataclass(frozen=True)
class Segment:
    """One drawn segment of one bar.

    Attributes:
        domain: Clinical domain the bar belongs to.
        pathway: Marketing pathway the segment stands for.
        count: Authorizations in the segment.
        share: Share of the domain's authorizations, 0 to 1.
        inside: Whether the count was drawn inside the segment. ``False`` means
            the segment was too narrow to hold type and the count was placed
            above the bar on a leader.
    """

    domain: str
    pathway: str
    count: int
    share: float
    inside: bool


@dataclass(frozen=True)
class PanelB:
    """What one Panel B build drew.

    Attributes:
        ax: The axes drawn on.
        segments: Every segment drawn, bar by bar.
        totals: Authorizations per domain, the ``n = …`` printed on each bar.
    """

    ax: Axes
    segments: list[Segment]
    totals: dict[str, int]

    def share(self, domain: str, pathway: str) -> float:
        """Return one segment's share of its domain, 0 to 1."""
        for segment in self.segments:
            if segment.domain == domain and segment.pathway == pathway:
                return segment.share
        return 0.0


def _relative_luminance(colour: str) -> float:
    """Return the WCAG relative luminance of a ``#rrggbb`` colour."""
    red, green, blue = (int(colour[index : index + 2], 16) / 255 for index in (1, 3, 5))
    channels = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in (red, green, blue)
    ]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _readable_ink(fill: str) -> str:
    """Return whichever of white and the guide's ink reads better on ``fill``.

    Measured as a WCAG contrast ratio rather than chosen by eye, because the two
    domain hues sit either side of the crossover: on radiology blue white scores
    5.2 against ink's 3.6, and on pathology pink ink scores 6.1 against white's
    3.1. Picking white for both -- the obvious thing to do, since both fills
    look "dark" -- would have put 5.5 pt white type on the pink bar at a
    contrast no print process recovers.
    """
    background = _relative_luminance(fill)
    on_white = 1.05 / (background + 0.05)
    on_ink = (background + 0.05) / (_relative_luminance(style.INK) + 0.05)
    return "#FFFFFF" if on_white >= on_ink else style.INK


def _domain_counts(pathways: pd.DataFrame) -> dict[str, dict[str, int]]:
    """Return counts per domain and pathway, aggregated over categories.

    The two radiology categories are summed here, because the pathway claim is a
    claim about the domain: radiology as a field clears its devices against
    predicates. The per-category table is not lost -- the run summary prints it,
    so a legend can quote it without anyone reading it off the picture.
    """
    counts: dict[str, dict[str, int]] = {
        domain: {pathway: 0 for pathway in PATHWAY_ORDER} for domain in DOMAIN_ORDER
    }
    for _, row in pathways.iterrows():
        domain = CATEGORY_DOMAIN[str(row["category"])]
        counts[domain][str(row["pathway"])] += int(row["count"])
    return counts


def draw(
    figure: Figure,
    pathways: pd.DataFrame,
    rect: tuple[float, float, float, float],
    *,
    title_x: float = 0.0,
    vertical: bool = False,
) -> PanelB:
    """Draw Panel B into ``rect`` as two normalized stacked bars.

    The bars run horizontally by default and vertically when ``vertical`` is
    set. This is not a style preference: it follows the shape of the space the
    caller gives it. Beneath Panel A the panel is wide and short, and rows fit
    that; beside Panel A it is narrow and tall, and rows leave most of the
    height empty while squeezing the two thin radiology segments into a few
    hundredths of an inch. Columns use the height that is there, which makes
    those segments taller rather than the panel emptier.

    One code path draws both. The stacked direction is called *along* and the
    categorical direction *across*, and only their mapping onto x and y
    changes -- so a fix to segment labelling or sliver leaders cannot land in
    one orientation and miss the other.

    Args:
        figure: The figure to draw into.
        pathways: Validated ``pathway_by_domain.csv``.
        rect: ``(left, bottom, width, height)`` in figure fractions, covering the
            bars only. The caller reserves room to the left for the domain
            labels, to the right for the ``n = …`` totals, and below for the
            axis title and the pathway key.
        title_x: Where the panel title sits, in axes fractions. Negative values
            put it left of the bars, so it lines up with the panel letter rather
            than with the domain labels. The caller owns the geometry, so the
            caller owns this number.
        vertical: Draw columns rather than rows. Pick it from the aspect ratio
            of ``rect``, not from taste.

    Returns:
        A :class:`PanelB` recording every segment drawn and every total printed.
    """
    left, bottom, width, height = rect
    ax = figure.add_axes(rect)
    # The span a segment's share is measured against: the stacked direction.
    axes_span_in = (
        height * figure.get_figheight() if vertical else width * figure.get_figwidth()
    )

    counts = _domain_counts(pathways)
    # Reading order of the finding is "radiology does this, pathology does
    # that". Rows put radiology on top; columns put it on the left. Both are the
    # position a reader reaches first in that orientation.
    order = DOMAIN_ORDER if vertical else tuple(reversed(DOMAIN_ORDER))
    positions = {domain: index for index, domain in enumerate(order)}

    # The share axis always runs 0 to 1; the categorical axis holds the domains.
    share_limits = (0.0, 1.0)
    category_limits = (-_Y_PAD, len(DOMAIN_ORDER) - 1 + _Y_PAD)
    if vertical:
        ax.set_xlim(*category_limits)
        ax.set_ylim(*share_limits)
    else:
        ax.set_xlim(*share_limits)
        ax.set_ylim(*category_limits)
    ax.set_axisbelow(True)
    # Gridlines run across the share axis, so they read as a percentage scale.
    (ax.yaxis if vertical else ax.xaxis).grid(True, color="#E8E8E8", linewidth=0.5)

    segments: list[Segment] = []
    totals: dict[str, int] = {}

    for domain in DOMAIN_ORDER:
        y = positions[domain]
        total = sum(counts[domain].values())
        totals[domain] = total
        if total == 0:
            continue
        fill = domain_color(domain)
        deep = domain_color(domain, deep=True)
        cursor = 0.0
        for pathway in PATHWAY_ORDER:
            count = counts[domain][pathway]
            share = count / total
            hatch = pathway_hatch(pathway)
            if hatch:
                # White ground, hatch and hairline border in the domain's deep
                # tint. Same treatment as the sibling figure's remainder bar:
                # the segment reads as a different *kind* of fill without a
                # second hue being invented for it.
                _stacked_bar(
                    ax,
                    across=y,
                    share=share,
                    cursor=cursor,
                    vertical=vertical,
                    facecolor=style.HATCH_GROUND,
                    edgecolor=deep,
                    hatch=hatch,
                )
            else:
                _stacked_bar(
                    ax,
                    across=y,
                    share=share,
                    cursor=cursor,
                    vertical=vertical,
                    facecolor=fill,
                    edgecolor=fill,
                    hatch=None,
                )
            inside = share * axes_span_in >= MIN_INSIDE_LABEL_IN and count > 0
            if count:
                _label_segment(
                    ax,
                    along=cursor + share / 2,
                    across=y,
                    vertical=vertical,
                    count=count,
                    inside=inside,
                    ink=_readable_ink(fill) if not hatch else style.INK,
                    leader_ink=deep,
                )
            segments.append(
                Segment(
                    domain=domain, pathway=pathway, count=count, share=share, inside=inside
                )
            )
            cursor += share

        # A row's total sits past the end of the bar, where there is nothing
        # else. A column's would sit above it, on the panel title -- so in that
        # orientation the total joins the category label under the axis
        # instead. Same information, and it stays next to the name it counts.
        if not vertical:
            ax.annotate(
                f"n = {total:,}",
                xy=(1.0, y),
                xytext=(5.0, 0.0),
                textcoords="offset points",
                ha="left",
                va="center",
                fontsize=style.FS_SERIES_LABEL,
                color=style.INK,
                annotation_clip=False,
            )

    category_axis = ax.xaxis if vertical else ax.yaxis
    share_axis = ax.yaxis if vertical else ax.xaxis
    category_axis.set_ticks([positions[domain] for domain in DOMAIN_ORDER])
    category_axis.set_ticklabels(
        [
            f"{domain_label(domain)}\nn = {totals.get(domain, 0):,}"
            if vertical
            else domain_label(domain)
            for domain in DOMAIN_ORDER
        ],
        fontsize=style.FS_TICK,
        color=style.SUBTLE,
    )
    share_axis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))
    ax.tick_params(axis="both", labelsize=style.FS_TICK, pad=2.0, colors=style.SUBTLE)
    # No tick marks on the categorical axis: the labels name the bars, and a
    # tick would imply a scale the axis does not have.
    ax.tick_params(axis="x" if vertical else "y", length=0)
    axis_label = "% of a field's authorizations"
    if vertical:
        ax.set_ylabel(
            axis_label, fontsize=style.FS_AXIS_LABEL, style="italic", color=style.SUBTLE
        )
    else:
        ax.set_xlabel(
            axis_label, fontsize=style.FS_AXIS_LABEL, style="italic", color=style.SUBTLE
        )
    # Keep the spine the bars stand on; drop the rest.
    hidden = ("top", "right", "bottom") if vertical else ("top", "right", "left")
    for name in hidden:
        ax.spines[name].set_visible(False)

    _draw_key(ax, vertical=vertical)
    ax.set_title(
        "Authorization Pathway",
        fontsize=style.FS_THEME_TITLE,
        fontfamily="serif",
        fontweight="bold",
        color=style.INK,
        pad=6.0,
        loc="left",
    )
    ax.title.set_x(title_x)
    return PanelB(ax=ax, segments=segments, totals=totals)


def _stacked_bar(
    ax: Axes,
    *,
    across: float,
    share: float,
    cursor: float,
    vertical: bool,
    facecolor: str,
    edgecolor: str,
    hatch: str | None,
) -> None:
    """Draw one segment of a stacked bar, in either orientation.

    ``across`` is the bar's position on the categorical axis and ``cursor`` is
    how much of the bar is already drawn. Keeping this in one place is what
    stops the two orientations acquiring different fills or border widths.
    """
    common = dict(
        facecolor=facecolor,
        edgecolor=edgecolor,
        hatch=hatch,
        linewidth=_BORDER_WIDTH,
        zorder=2,
    )
    if vertical:
        ax.bar(across, share, bottom=cursor, width=BAR_HEIGHT, **common)
    else:
        ax.barh(across, share, left=cursor, height=BAR_HEIGHT, **common)


def _label_segment(
    ax: Axes,
    *,
    along: float,
    across: float,
    vertical: bool,
    count: int,
    inside: bool,
    ink: str,
    leader_ink: str,
) -> None:
    """Print one segment's count, inside it if it fits and outside it if not.

    A segment too thin to hold its own number gets a hairline leader out of the
    bar to a number in the margin. The leader leaves along the categorical axis
    -- upward from a row, sideways from a column -- because leaving along the
    stacked axis would put the number over the neighbouring segment.
    """
    if inside:
        ax.text(
            *((across, along) if vertical else (along, across)),
            f"{count:,}",
            ha="center",
            va="center",
            fontsize=style.FS_BAR_VALUE,
            color=ink,
            zorder=4,
        )
        return

    edge = across + BAR_HEIGHT / 2
    tip = across + _SLIVER_RISE
    if vertical:
        ax.plot([edge, tip], [along, along], color=leader_ink,
                linewidth=_LEADER_WIDTH, zorder=3)
        ax.text(
            tip + 0.02, along, f"{count:,}", ha="left", va="center",
            fontsize=style.FS_BAR_VALUE, color=style.INK, zorder=4,
        )
    else:
        ax.plot([along, along], [edge, tip], color=leader_ink,
                linewidth=_LEADER_WIDTH, zorder=3)
        ax.text(
            along, tip + 0.02, f"{count:,}", ha="center", va="bottom",
            fontsize=style.FS_BAR_VALUE, color=style.INK, zorder=4,
        )


def _draw_key(ax: Axes, *, vertical: bool = False) -> None:
    """Draw the three-swatch pathway key beneath the panel.

    In neutral ink, not in either domain's hue: the key states what a texture
    means, and a texture means the same thing on both bars. Tinting the swatches
    would make the key look like a third series.
    """
    handles = [
        Patch(
            facecolor=style.HATCH_GROUND if pathway_hatch(pathway) else style.BAR_FILL,
            edgecolor=style.HATCH_LINE if pathway_hatch(pathway) else style.BAR_FILL,
            hatch=pathway_hatch(pathway),
            linewidth=_BORDER_WIDTH,
            label=pathway_label(pathway),
        )
        for pathway in PATHWAY_ORDER
    ]
    # Below the axes in both orientations. A column panel is far taller than a
    # row panel, and the anchor is in axes fractions, so the same -0.34 would
    # drop the key several inches. The offsets below are each about 0.4 in.
    legend = ax.legend(
        handles=handles,
        loc="upper left",
        bbox_to_anchor=(0.0, -0.10 if vertical else -0.34),
        ncols=len(PATHWAY_ORDER),
        frameon=False,
        fontsize=style.FS_NOTE,
        labelcolor=style.SUBTLE,
        handlelength=1.5,
        handleheight=0.9,
        handletextpad=0.5,
        columnspacing=1.6,
        borderpad=0.0,
        borderaxespad=0.0,
    )
    legend.set_zorder(5)
