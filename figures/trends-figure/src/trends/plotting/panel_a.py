"""Panel A: which modality combinations each theme uses.

An inverted UpSet plot. The membership matrix sits on top, one row per modality,
and the paper counts hang below it as bars. Four theme blocks stand side by side
and share one modality row axis, labelled once on the left, and one bar scale, so
bar heights are comparable across themes.

Each block draws its twelve commonest modality combinations and then one
separated column, hatched and labelled "all other combinations", holding every
remaining paper in the theme. The bars therefore sum to the theme total and the
panel hides nothing. The remainder column carries **no dots**: it is not a
combination, it is the rest of the distribution, and the number of distinct sets
inside it is printed beneath it.

Layout choices worth knowing:

* **One bar scale for all four blocks.** A per-block scale would let a
  twenty-paper bar in a small theme look like a three-hundred-paper bar in a
  large one. The cost is that a sparse block draws as hairlines, so every bar
  carries its count in small type above it, and every block prints its own
  total, so a flat block reads as a small literature rather than a drawing error.
* **Two bar scales are selectable** via ``scale``, and both are honest:
  ``"count"`` (the default) draws papers on one shared axis, so blocks are
  comparable but a small theme draws flat; ``"share"`` draws each combination as
  a percentage of its own theme, so all four blocks are legible but cross-theme
  volume is no longer in Panel A. Under ``"share"``, Panel A answers "what does
  each theme use" and Panel B answers "how big is each theme". The choice should
  be made by looking at the real tables, not in the abstract. With the remainder
  column drawn, a block's bars sum to its theme total, so under ``"share"`` they
  sum to 100% by construction.
* **Bar value labels turn vertical when the column is too narrow to hold them.**
  Thirteen columns per block leave about 7.3 pt of column width, and a four-digit
  count needs about 14 pt lying down. Rotating the label keeps the type at its
  designed size; shrinking it to fit would have taken it to about 3 pt. The
  headroom above the tallest bar is then sized from the longest rotated label, so
  a label never runs off the top of the bar axes.

Rejected alternatives
---------------------

**A break-marked ("broken") bar axis, to lift a small block into view: rejected.**
On a bar chart the length of the bar *is* the quantity, measured from zero. Cutting
a break into the axis severs that encoding and makes a forty-paper bar read as
comparable to a fifteen-hundred-paper one — the reader sees two bars of similar
length and believes two similar quantities. It is the textbook way to mislead with
a bar chart, and no gain in legibility is worth it. If a block is too small to
read, the honest fixes are the ones above: print its total, or switch the panel to
``scale="share"`` where every block is measured against its own denominator. This
is recorded because the idea is a natural one and will be proposed again.

Log and square-root bar axes are rejected for the same reason: both break the
proportionality between bar length and count.

**A cap of twenty columns and no remainder bar: rejected.** It still hid 28.1% of
the multimodal-integration papers, and eighty narrow columns across four blocks
put the column width below what a legible dot needs. See
:data:`MIN_COLUMN_WIDTH_IN`, which is what fails if the cap is raised that far.

**Dropping the single-modality columns and drawing co-occurrences only: rejected.**
It changes what the panel means. That multimodal integration's largest columns are
single modalities is the finding; a panel that cannot draw it is answering a
different question.

* **Block width follows column count.** Every column is the same width in every
  block, so a theme with fewer combinations gets a narrower block rather than
  wider columns. Bars stay comparable by area, not just by height.
* **Alternating row bands** carry the eye across four blocks and fifteen rows,
  which a grid of dots alone does not.
* **The size of the remainder is printed under each block**, not only in the legend.

Colour
------
Colour in this panel is semantic and nothing else, per ``../ink_style_guide.md``
sections 1 and 3. A present dot takes its row's fixed modality hue -- radiology
blue, pathology pink, clinical-text green, molecular orange, structural grey --
so a colour in the matrix always answers "what kind of data is this". Absent
dots stay a light neutral, and the connector that joins a column is structural,
so it is drawn in line grey rather than in any hue.

**The bars carry no modality colour.** A bar is a *combination* of modalities,
often several at once, and there is no one hue that could honestly stand for it;
tinting it by theme would be decoration, which the guide forbids. They are drawn
in the guide's secondary-output ink. The remainder column is set apart by the
guide's hatch specification -- 45 degrees, pale ground, grey lines, hairline
border -- which is also what the guide asks for instead of inventing a hue.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.ticker import PercentFormatter

from . import style

#: Number of combination columns drawn per theme, before the remainder column.
#: See ``docs/figure-spec.md`` and the 2026-09-02 entry in ``docs/DECISIONS.md``.
DEFAULT_TOP_N = 12

#: Bar scales Panel A can draw. See the module docstring for why these two and
#: no others: both preserve length-from-zero as the encoding of quantity.
BAR_SCALES: Final[tuple[str, ...]] = ("count", "share")

#: The scale used unless the caller asks otherwise. "share" is the shipped default:
#: measured on the real corpus, a shared count axis is set by the multimodal remainder
#: bar (2,149 papers), and both small themes then draw as hairlines indistinguishable
#: from the axis line -- including their own remainder bars, which are a third of those
#: themes. See docs/DECISIONS.md, 2026-09-02. Exact counts live in the run summary.
DEFAULT_BAR_SCALE: Final[str] = "share"

#: Label drawn down the remainder column, inside the matrix, where its dots
#: would be if it were a combination.
REMAINDER_LABEL: Final[str] = "all other combinations"

#: Gap between the last combination column and the remainder column, in column
#: widths. The remainder is not a combination and must not read as one more.
_REMAINDER_GAP: Final[float] = 0.6

#: Horizontal space between theme blocks, in inches.
BLOCK_GAP_IN: Final[float] = 0.16

#: Least number of column slots a block occupies, so an empty block still has width.
_MIN_BLOCK_COLUMNS = 2

#: Narrowest column that still carries a legible dot. Below about this width the
#: dot diameter hits its own floor in :func:`_dot_size` and the matrix stops
#: reading as a grid. Thirteen columns per block sit at 0.102 in; twenty-one
#: columns would sit at 0.064 in, which is what rules out raising the cap to
#: twenty. ``tests/test_plot.py`` fails if the drawn width falls below this.
MIN_COLUMN_WIDTH_IN: Final[float] = 0.085


@dataclass(frozen=True)
class TailSummary:
    """How one theme's block divides between drawn columns and the remainder.

    Nothing is hidden: ``remainder_papers`` are drawn, in the remainder column,
    and ``shown_papers + remainder_papers == total_papers``.

    Attributes:
        theme: Theme key.
        shown_sets: Combinations drawn as their own column.
        remainder_sets: Combinations collected into the remainder column.
        shown_papers: Papers in the drawn combinations.
        remainder_papers: Papers in the remainder column.
        total_papers: Papers carrying the theme label.
    """

    theme: str
    shown_sets: int
    remainder_sets: int
    shown_papers: int
    remainder_papers: int
    total_papers: int

    @property
    def remainder_share(self) -> float:
        """Share of the theme's papers in the remainder column, 0 to 1."""
        if self.total_papers == 0:
            return 0.0
        return self.remainder_papers / self.total_papers

    @property
    def total_sets(self) -> int:
        """Distinct modality combinations observed in the theme."""
        return self.shown_sets + self.remainder_sets

    @property
    def draws_remainder(self) -> bool:
        """Whether this block draws a remainder column at all."""
        return self.remainder_sets > 0


#: A combination must hold at least this many papers to be drawn as its own
#: column. Below it, the combination joins the remainder.
#:
#: Added 2026-09-08, when Panel A became primary-research-only and digital twins
#: fell to 20 papers across 13 modality sets. At the twelve-column cap, nine of
#: its twelve columns held exactly one paper, so the block drew as a row of
#: near-equal bars -- which reads as a distribution when it is a list of
#: individual papers. One paper is an anecdote; the eye should not be invited to
#: compare twelve of them. The papers are not lost: they move into the remainder
#: column, which is drawn, so the bars still sum to the theme total.
#:
#: This binds only on small themes. Foundation models' twelfth column holds 19
#: papers and multimodal integration's holds 97, so neither is affected.
MIN_PAPERS_PER_COLUMN: Final[int] = 2


def _block_frame(combinations: pd.DataFrame, theme: str, top_n: int) -> pd.DataFrame:
    """Return the rows drawn as their own column, in descending paper count.

    Applies both the column cap and :data:`MIN_PAPERS_PER_COLUMN`; whatever is
    excluded by either is carried by the remainder column, never dropped.
    """
    subset = combinations.loc[combinations["theme"] == theme]
    if subset.empty:
        return subset
    # Ties are broken toward the more informative column. Among combinations
    # holding the same number of papers, a four-modality set says more about a
    # theme than a one-modality set, and in a small theme every combination holds
    # one paper, so the tie-break decides the whole block.
    ordered = subset.sort_values(
        ["n_papers", "n_modalities", "modality_set"], ascending=[False, False, True]
    )
    qualifying = ordered.loc[ordered["n_papers"] >= MIN_PAPERS_PER_COLUMN]
    # The minimum binds only where combinations compete for the columns. In a
    # theme too small to fill the block with qualifying combinations, enforcing it
    # would not remove noise -- it would remove nearly everything, and it removes
    # the multi-modality combinations first, because those are rarest. Digital
    # twins is the case: 20 papers, 13 sets, and only three sets holding two or
    # more papers -- all three single-modality. Applying the minimum drew a
    # digital-twins block that appeared to contain no multimodal work at all,
    # while six of its twenty papers use two or more modalities and one uses four.
    # The author caught that on 2026-09-09.
    if len(qualifying) >= top_n:
        ordered = qualifying
    return ordered.head(top_n).reset_index(drop=True)


def _tail_summary(combinations: pd.DataFrame, theme: str, top_n: int) -> TailSummary:
    """Count what one theme draws as columns and what its remainder column holds."""
    subset = combinations.loc[combinations["theme"] == theme]
    shown = _block_frame(combinations, theme, top_n)
    total = int(subset["n_papers"].sum())
    shown_papers = int(shown["n_papers"].sum()) if len(shown) else 0
    return TailSummary(
        theme=theme,
        shown_sets=len(shown),
        remainder_sets=len(subset) - len(shown),
        shown_papers=shown_papers,
        remainder_papers=total - shown_papers,
        total_papers=total,
    )


def block_slots(n_columns: int, has_remainder: bool) -> float:
    """Return the column slots one block occupies, remainder and gap included."""
    used = n_columns + (1.0 + _REMAINDER_GAP if has_remainder else 0.0)
    return max(used, float(_MIN_BLOCK_COLUMNS))


def block_note_text(summary: "TailSummary") -> str:
    """Return the caption printed under one block. One definition, two callers."""
    return (
        "no papers"
        if summary.total_papers == 0
        else f"n = {summary.total_papers:,} papers"
    )


def _caption_width_in(summary: "TailSummary") -> float:
    """Return the width a block's captions need, in inches.

    A block prints two: the theme total, centred under the block, and the
    remainder's set count, sitting under the remainder column at the right-hand
    edge. Sizing the block to the wider of the two is not enough -- they are
    drawn at different anchors and collide with each other before either
    overruns the block. The requirement is therefore the sum of both, plus a
    gap, which is what the first version of this function got wrong: it counted
    only the theme total, and digital twins still printed "n = 20 papers" across
    "+10 sets" and into the neighbouring block's "+230 sets".
    """
    note = _label_width_em(block_note_text(summary)) * style.FS_NOTE / 72.0
    sets = (
        _label_width_em(f"+{summary.remainder_sets} sets") * style.FS_NOTE / 72.0
        if summary.draws_remainder
        else 0.0
    )
    return max(note, sets) + _CAPTION_GAP_IN


#: Clear space beside a block's captions, in inches.
_CAPTION_GAP_IN: Final[float] = 0.05

#: Vertical drop from the remainder's "+N sets" line to the theme-total line,
#: in figure fraction. One line of note type plus a little air.
_CAPTION_LINE_DROP: Final[float] = 0.011


def _slots_with_captions(
    base_slots: list[float],
    summaries: list["TailSummary"],
    rect_width: float,
    figure_width_in: float,
) -> list[float]:
    """Widen any block too narrow to hold its own caption.

    A block's width follows its column count, so a theme with few drawn columns
    draws a narrow block -- and its caption, whose width follows the number of
    digits in the theme total rather than the block, then overruns into the
    neighbouring block. That happened on 2026-09-08, when Panel A became
    primary-research-only and digital twins fell to three drawn columns while
    still printing "n = 20 papers".

    Column width depends on the total slot count, which this function changes, so
    it iterates to a fixed point. Three passes are ample: each pass can only
    widen a block, and widening shrinks every column, so the sequence converges
    from below. Widths are treated as a floor, never a cap -- a block is never
    made narrower than its columns need.
    """
    slots = list(base_slots)
    for _ in range(3):
        column_w = column_width_in(rect_width, figure_width_in, sum(slots))
        if column_w <= 0:
            return slots
        for index, summary in enumerate(summaries):
            needed = _caption_width_in(summary) / column_w
            slots[index] = max(slots[index], base_slots[index], needed)
    return slots


def column_width_in(rect_width: float, figure_width_in: float, total_slots: float) -> float:
    """Return the drawn width of one column, in inches.

    Args:
        rect_width: Panel A's width as a fraction of the figure.
        figure_width_in: Figure width in inches.
        total_slots: Column slots summed over every block.

    Returns:
        The width one column gets once the between-block gaps are taken out.
    """
    n_gaps = len(style.PANEL_A_THEMES) - 1
    usable = rect_width * figure_width_in - BLOCK_GAP_IN * n_gaps
    return usable / total_slots if total_slots else 0.0


#: Approximate advance widths, in ems, for the glyphs a bar label can contain.
#: A percent sign is nearly twice the width of a digit, so counting characters
#: rather than widths sizes share labels too large and lets them collide.
_GLYPH_EM: Final[dict[str, float]] = {"%": 0.95, ".": 0.32, ",": 0.32}
_DIGIT_EM: Final[float] = 0.62

#: Below this, a bar label stops being readable in print. A share label that
#: would need a decimal place to be informative is rounded instead of shrunk:
#: precision the reader cannot see is not precision. Below it lying down, the
#: label is stood on end rather than shrunk further.
_MIN_LEGIBLE_VALUE_FS: Final[float] = 5.0


def _label_width_em(label: str) -> float:
    """Return the approximate width of a bar label, in ems."""
    return sum(_GLYPH_EM.get(char, _DIGIT_EM) for char in label) or _DIGIT_EM


def _value_font_size(column_width_in: float, longest_label: str) -> float:
    """Return a type size at which a bar's label fits inside its column width.

    Real counts may run to four or five digits, and share labels carry a percent
    sign. Rather than let the labels collide, the type shrinks with the widest
    label drawn, down to a floor below which nothing would be readable anyway.
    """
    fitted = (column_width_in * 72.0 * 0.92) / _label_width_em(longest_label)
    return max(4.4, min(style.FS_BAR_VALUE, fitted))


def _rotated_font_size(column_width_in: float) -> float:
    """Return a type size for a bar label stood on end in a narrow column."""
    return max(4.4, min(style.FS_BAR_VALUE, column_width_in * 72.0 * 0.85))


def _dot_size(column_width_in: float, row_height_in: float) -> float:
    """Return a scatter marker area, in points squared, that fits the cell."""
    diameter_pt = 0.46 * min(column_width_in, row_height_in) * 72.0
    diameter_pt = max(2.6, min(diameter_pt, 6.4))
    return diameter_pt**2


def _positions(n_columns: int, has_remainder: bool) -> list[float]:
    """Return the x position of every bar and matrix column in a block."""
    positions = [float(index) for index in range(n_columns)]
    if has_remainder:
        positions.append(n_columns + _REMAINDER_GAP)
    return positions


def draw(
    figure: Figure,
    combinations: pd.DataFrame,
    rect: tuple[float, float, float, float],
    top_n: int = DEFAULT_TOP_N,
    scale: str = DEFAULT_BAR_SCALE,
) -> list[TailSummary]:
    """Draw Panel A into ``rect`` and return how each block divides.

    Args:
        figure: The figure to draw into.
        combinations: Validated ``combination_counts.csv``.
        rect: ``(left, bottom, width, height)`` in figure fractions. ``left`` is
            where the matrix begins; the caller reserves the row-label gutter to
            its left.
        top_n: Combination columns drawn per theme, before the remainder column.
        scale: ``"count"`` to draw papers on one shared axis, or ``"share"`` to
            draw each combination as a percentage of its own theme. See the
            module docstring.

    Returns:
        One :class:`TailSummary` per theme, in figure block order.

    Raises:
        ValueError: If ``scale`` is not one of :data:`BAR_SCALES`.
    """
    if scale not in BAR_SCALES:
        raise ValueError(f"scale must be one of {BAR_SCALES}, got {scale!r}")
    left, bottom, width, height = rect
    fig_w, fig_h = figure.get_figwidth(), figure.get_figheight()

    # Vertical budget inside the panel, as fractions of the panel's own height.
    # The matrix takes the larger share, and the title reserve is only as deep as
    # a two-line theme title needs, because the row pitch is what the panel lives
    # or dies by: at fifteen modality rows the pitch is 13.2 pt, against 13.6 pt
    # at thirteen rows under the old 0.115/0.615 split. Holding the pitch cost the
    # bars 14% of their height and cost the page nothing. Restoring the old split
    # would drop the pitch to 11.8 pt; holding 13.6 pt instead would need three
    # quarters of an inch more page.
    title_h = 0.090 * height
    note_h = 0.075 * height
    body_h = height - title_h - note_h
    matrix_h = 0.670 * body_h
    gap_h = 0.045 * body_h
    bars_h = body_h - matrix_h - gap_h

    matrix_bottom = bottom + note_h + bars_h + gap_h
    bars_bottom = bottom + note_h
    bars_h_in = bars_h * fig_h

    # Horizontal budget: equal column width everywhere, blocks separated by a gap.
    # PANEL_A_THEMES, not THEME_ORDER: virtual staining was added to Panel B
    # only, because a fifth block breaches MIN_COLUMN_WIDTH_IN. See the note on
    # the constant in ``style``.
    blocks = [(theme, _block_frame(combinations, theme, top_n)) for theme in style.PANEL_A_THEMES]
    summaries = [_tail_summary(combinations, theme, top_n) for theme in style.PANEL_A_THEMES]
    base_slots = [
        block_slots(len(frame), summary.draws_remainder)
        for (_, frame), summary in zip(blocks, summaries)
    ]
    slots = _slots_with_captions(base_slots, summaries, width, fig_w)
    gap_w = BLOCK_GAP_IN / fig_w
    column_w = column_width_in(width, fig_w, sum(slots)) / fig_w

    n_rows = len(style.MODALITY_ORDER)
    row_h_in = (matrix_h * fig_h) / n_rows
    column_w_in = column_w * fig_w
    dot_area = _dot_size(column_w_in, row_h_in)

    # Bar heights, on whichever scale was asked for. Under "share" each block is
    # divided by its own theme total -- every paper carrying the theme label --
    # and because the remainder column carries everything the columns do not, the
    # bars within a block sum to exactly one.
    block_values: list[np.ndarray] = []
    for (theme, frame), summary in zip(blocks, summaries):
        raw = list(frame["n_papers"].to_numpy(dtype=float)) if len(frame) else []
        if summary.draws_remainder:
            raw.append(float(summary.remainder_papers))
        values = np.asarray(raw, dtype=float)
        total = summary.total_papers
        block_values.append(values / total if scale == "share" and total else values)

    peak = max((float(values.max()) for values in block_values if values.size), default=0.0)

    def _labels(decimals: int) -> list[list[str]]:
        if scale == "share":
            return [[f"{value:.{decimals}%}" for value in values] for values in block_values]
        return [[f"{int(value):d}" for value in values] for values in block_values]

    def _widest(labels: list[list[str]]) -> str:
        return max(
            (label for block in labels for label in block), key=_label_width_em, default="0"
        )

    if scale == "share":
        # One decimal only when every share would otherwise round to the same
        # integer, which happens when no combination holds much of its theme --
        # and then only if the wider label still prints legibly. Rounding is the
        # better loss: a decimal place nobody can read is not worth 4.4 pt type.
        decimals = 0 if peak >= 0.10 else 1
        block_labels = _labels(decimals)
        if decimals == 1 and _value_font_size(column_w_in, _widest(block_labels)) < _MIN_LEGIBLE_VALUE_FS:
            block_labels = _labels(0)
    else:
        block_labels = _labels(0)

    widest = _widest(block_labels)
    flat_fs = _value_font_size(column_w_in, widest)
    rotate_values = flat_fs < _MIN_LEGIBLE_VALUE_FS
    value_fs = _rotated_font_size(column_w_in) if rotate_values else flat_fs

    # Headroom above the tallest bar. A label lying down needs a sliver; a label
    # standing on end needs its whole length, or it runs off the top of the axes.
    if rotate_values:
        label_in = _label_width_em(widest) * value_fs / 72.0 + 0.035
        headroom = min(0.40, label_in / bars_h_in) if bars_h_in else 0.16
    else:
        headroom = 0.16
    y_top = peak / (1.0 - headroom) if peak else 1.0
    if scale == "share":
        y_top = min(1.0, y_top)

    x_cursor = left
    for index, (theme, frame) in enumerate(blocks):
        summary = summaries[index]
        block_w = column_w * slots[index]
        positions = _positions(len(frame), summary.draws_remainder)

        matrix_ax = figure.add_axes((x_cursor, matrix_bottom, block_w, matrix_h))
        bars_ax = figure.add_axes((x_cursor, bars_bottom, block_w, bars_h))
        _draw_matrix(
            matrix_ax,
            frame,
            slots[index],
            positions,
            dot_area,
            show_row_labels=index == 0,
            has_remainder=summary.draws_remainder,
        )
        _draw_bars(
            bars_ax,
            block_values[index],
            block_labels[index],
            slots[index],
            positions,
            y_top,
            show_axis=index == 0,
            value_fs=value_fs,
            rotate_values=rotate_values,
            scale=scale,
            has_remainder=summary.draws_remainder,
        )

        matrix_ax.set_title(
            style.theme_label(theme),
            fontsize=style.FS_THEME_TITLE,
            fontfamily="serif",
            fontweight="bold",
            color=style.INK,
            pad=4.0,
            linespacing=1.15,
        )

        def _x_of(position: float) -> float:
            """Figure-fraction x of a column centre in this block."""
            return x_cursor + (position + 0.5) / slots[index] * block_w

        note_center = _x_of((len(frame) - 1) / 2 if len(frame) else (slots[index] - 1) / 2)
        _draw_block_note(figure, summary, note_center, bars_bottom, top_n)
        if summary.draws_remainder:
            figure.text(
                _x_of(positions[-1]),
                bars_bottom - 0.012,
                f"+{summary.remainder_sets} sets",
                ha="center",
                va="top",
                fontsize=style.FS_NOTE,
                color=style.SUBTLE,
            )

        if index < len(blocks) - 1:
            rule_x = x_cursor + block_w + gap_w / 2
            figure.add_artist(
                Line2D(
                    [rule_x, rule_x],
                    [bars_bottom, matrix_bottom + matrix_h],
                    transform=figure.transFigure,
                    color=style.RULE,
                    linewidth=0.5,
                    linestyle=(0, (2.5, 2)),
                )
            )
        x_cursor += block_w + gap_w

    return summaries


def _draw_matrix(
    ax,
    frame: pd.DataFrame,
    slots: float,
    positions: list[float],
    dot_area: float,
    *,
    show_row_labels: bool,
    has_remainder: bool,
) -> None:
    """Draw one block's membership matrix: banded rows, dots, and connectors.

    The remainder column, if there is one, is left empty of dots and carries its
    label down the space where the dots would be. A dot there would say the
    remainder is one more combination, which is exactly what it is not.
    """
    n_rows = len(style.MODALITY_ORDER)
    row_of = {key: index for index, key in enumerate(style.MODALITY_ORDER)}

    ax.set_xlim(-0.5, slots - 0.5)
    ax.set_ylim(n_rows - 0.5, -0.5)
    for row in range(0, n_rows, 2):
        ax.axhspan(row - 0.5, row + 0.5, color=style.BAND, linewidth=0, zorder=0)

    n_combinations = len(frame)
    absent_x, absent_y = [], []
    for column in range(n_combinations):
        for row in range(n_rows):
            absent_x.append(positions[column])
            absent_y.append(row)
    if absent_x:
        ax.scatter(absent_x, absent_y, s=dot_area, color=style.INK_LIGHT, linewidths=0, zorder=1)

    for column, raw in enumerate(frame["modality_set"].astype(str) if n_combinations else []):
        rows = sorted(row_of[key] for key in raw.split("+") if key in row_of)
        if not rows:
            continue
        x = positions[column]
        # The connector is structural -- it says "these were used together" and
        # names no modality -- so it is drawn in line grey, not in any hue.
        if len(rows) > 1:
            ax.plot([x, x], [rows[0], rows[-1]], color=style.LINE, linewidth=1.0, zorder=2)
        # A present dot takes its row's modality colour, so colour in this panel
        # only ever identifies a kind of data.
        ax.scatter(
            [x] * len(rows),
            rows,
            s=dot_area,
            color=[style.modality_color(style.MODALITY_ORDER[row]) for row in rows],
            linewidths=0,
            zorder=3,
        )

    if has_remainder:
        x = positions[-1]
        ax.text(
            x,
            (n_rows - 1) / 2,
            REMAINDER_LABEL,
            rotation=90,
            ha="center",
            va="center",
            fontsize=style.FS_NOTE,
            color=style.SUBTLE,
            zorder=3,
        )
        divider = (positions[-2] + x) / 2 if len(positions) > 1 else x - 0.5
        ax.axvline(divider, color=style.RULE, linewidth=0.5, linestyle=(0, (1, 1.6)), zorder=2)

    if not n_combinations:
        ax.text(
            (slots - 1) / 2,
            (n_rows - 1) / 2,
            "no papers",
            ha="center",
            va="center",
            fontsize=style.FS_NOTE,
            style="italic",
            color=style.SUBTLE,
        )

    ax.set_xticks([])
    if show_row_labels:
        ax.set_yticks(range(n_rows))
        ax.set_yticklabels(
            [style.modality_label(key) for key in style.MODALITY_ORDER],
            fontsize=style.FS_TICK,
            color=style.SUBTLE,
        )
        ax.tick_params(axis="y", length=0, pad=2.5)
    else:
        ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def _draw_bars(
    ax,
    values: np.ndarray,
    labels: list[str],
    slots: float,
    positions: list[float],
    y_top: float,
    *,
    show_axis: bool,
    value_fs: float = style.FS_BAR_VALUE,
    rotate_values: bool = False,
    scale: str = DEFAULT_BAR_SCALE,
    has_remainder: bool = False,
) -> None:
    """Draw one block's bars, on the scale shared by every block.

    Every bar carries its own value in type, because under ``scale="count"`` the
    axis is shared across blocks and a sparse theme would otherwise draw as an
    unreadable hairline. The label always states what the bar encodes -- a count
    under ``"count"``, a percentage under ``"share"`` -- so the printed number and
    the bar length can never tell the reader two different things.

    No bar carries a modality colour: a bar is a combination of modalities, not
    one modality, so under the style guide it is structural and takes the
    secondary-output ink. The remainder bar is set apart by hatching instead --
    the guide's 45-degree pattern on a pale ground with a hairline grey border --
    so it reads at a glance as a different kind of quantity: an aggregate, not
    one more combination.
    """
    ax.set_xlim(-0.5, slots - 0.5)
    ax.set_ylim(0, y_top)
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color="#DCDCDC", linewidth=0.55)

    n_bars = values.size
    n_combinations = n_bars - 1 if has_remainder else n_bars
    if n_combinations > 0:
        ax.bar(
            positions[:n_combinations],
            values[:n_combinations],
            width=0.66,
            color=style.BAR_FILL,
            linewidth=0,
            zorder=2,
        )
    if has_remainder and n_bars:
        ax.bar(
            [positions[-1]],
            [values[-1]],
            width=0.66,
            facecolor=style.HATCH_GROUND,
            edgecolor=style.HATCH_LINE,
            hatch=style.HATCH_PATTERN,
            linewidth=0.8,
            zorder=2,
        )
        divider = (positions[-2] + positions[-1]) / 2 if n_bars > 1 else positions[-1] - 0.5
        ax.axvline(divider, color=style.RULE, linewidth=0.5, linestyle=(0, (1, 1.6)), zorder=1)

    for position, value, label in zip(positions, values, labels):
        ax.text(
            position,
            value + y_top * 0.012,
            label,
            ha="center",
            va="bottom",
            rotation=90 if rotate_values else 0,
            fontsize=value_fs,
            color=style.INK,
            zorder=3,
        )

    ax.set_xticks([])
    for name in ("top", "right"):
        ax.spines[name].set_visible(False)
    if show_axis:
        if scale == "share":
            ax.set_ylabel(
                "% of theme's papers",
                fontsize=style.FS_AXIS_LABEL,
                style="italic",
                color=style.SUBTLE,
            )
            ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))
        else:
            ax.set_ylabel(
                "# of papers",
                fontsize=style.FS_AXIS_LABEL,
                style="italic",
                color=style.SUBTLE,
            )
        ax.tick_params(axis="y", labelsize=style.FS_TICK, pad=2.0, colors=style.SUBTLE)
    else:
        ax.set_yticks([])
        ax.spines["left"].set_visible(False)


def _draw_block_note(
    figure: Figure, summary: TailSummary, x_center: float, y_bottom: float, top_n: int
) -> None:
    """Print the theme's size under its block.

    The theme total is printed because the bar scale carries composition rather
    than volume: without its total a reader cannot tell a small literature from
    a drawing error.

    The second line this note used to carry -- "top 12 of 139 combinations" --
    was removed on 2026-09-02 under the style guide's rule that explanatory
    prose belongs in the legend and only short functional labels (four words or
    fewer) may stand in the artwork. Nothing is lost from the drawing: the
    remainder column is still there, still labelled "all other combinations",
    and still prints "+127 sets" beneath itself, so how the columns divide the
    theme is visible without being narrated. ``top_n`` is kept in the signature
    because the run summary and the legend are written from it.
    """
    text = block_note_text(summary)
    # A line below the remainder's "+N sets", not beside it. The two are drawn at
    # different anchors -- this one centred under the block, that one under the
    # remainder column at the right edge -- so on a narrow block they collide
    # however wide the block is made. Digital twins fell to three drawn columns on
    # 2026-09-08 and printed "n = 20 papers" straight through "+10 sets" and into
    # the neighbouring block. Separating the lines removes the collision by
    # construction rather than by arithmetic on approximate glyph widths.
    figure.text(
        x_center,
        y_bottom - 0.012 - _CAPTION_LINE_DROP,
        text,
        ha="center",
        va="top",
        fontsize=style.FS_NOTE,
        color=style.SUBTLE,
        linespacing=1.25,
    )
