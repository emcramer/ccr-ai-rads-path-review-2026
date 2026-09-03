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
) -> PanelB:
    """Draw Panel B into ``rect`` as two normalized stacked bars.

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

    Returns:
        A :class:`PanelB` recording every segment drawn and every total printed.
    """
    left, bottom, width, height = rect
    ax = figure.add_axes(rect)
    axes_width_in = width * figure.get_figwidth()

    counts = _domain_counts(pathways)
    # Radiology on top: it is the larger field and the reading order of the
    # finding is "radiology does this, pathology does that".
    positions = {domain: index for index, domain in enumerate(reversed(DOMAIN_ORDER))}

    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(-_Y_PAD, len(DOMAIN_ORDER) - 1 + _Y_PAD)
    ax.set_axisbelow(True)
    ax.xaxis.grid(True, color="#E8E8E8", linewidth=0.5)

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
                ax.barh(
                    y,
                    share,
                    left=cursor,
                    height=BAR_HEIGHT,
                    facecolor=style.HATCH_GROUND,
                    edgecolor=deep,
                    hatch=hatch,
                    linewidth=_BORDER_WIDTH,
                    zorder=2,
                )
            else:
                ax.barh(
                    y,
                    share,
                    left=cursor,
                    height=BAR_HEIGHT,
                    facecolor=fill,
                    edgecolor=fill,
                    linewidth=_BORDER_WIDTH,
                    zorder=2,
                )
            inside = share * axes_width_in >= MIN_INSIDE_LABEL_IN and count > 0
            if count:
                _label_segment(
                    ax,
                    x=cursor + share / 2,
                    y=y,
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

    ax.set_yticks([positions[domain] for domain in DOMAIN_ORDER])
    ax.set_yticklabels(
        [domain_label(domain) for domain in DOMAIN_ORDER],
        fontsize=style.FS_TICK,
        color=style.SUBTLE,
    )
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))
    ax.tick_params(axis="both", labelsize=style.FS_TICK, pad=2.0, colors=style.SUBTLE)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel(
        "% of a field's authorizations",
        fontsize=style.FS_AXIS_LABEL,
        style="italic",
        color=style.SUBTLE,
    )
    for name in ("top", "right", "left"):
        ax.spines[name].set_visible(False)

    _draw_key(ax)
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


def _label_segment(
    ax: Axes,
    *,
    x: float,
    y: float,
    count: int,
    inside: bool,
    ink: str,
    leader_ink: str,
) -> None:
    """Print one segment's count, inside it if it fits and above it if not."""
    if inside:
        ax.text(
            x,
            y,
            f"{count:,}",
            ha="center",
            va="center",
            fontsize=style.FS_BAR_VALUE,
            color=ink,
            zorder=4,
        )
        return
    ax.plot(
        [x, x],
        [y + BAR_HEIGHT / 2, y + _SLIVER_RISE],
        color=leader_ink,
        linewidth=_LEADER_WIDTH,
        zorder=3,
    )
    ax.text(
        x,
        y + _SLIVER_RISE + 0.02,
        f"{count:,}",
        ha="center",
        va="bottom",
        fontsize=style.FS_BAR_VALUE,
        color=style.INK,
        zorder=4,
    )


def _draw_key(ax: Axes) -> None:
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
    legend = ax.legend(
        handles=handles,
        loc="upper left",
        bbox_to_anchor=(0.0, -0.34),
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
