# Decisions — combined figure

What has been settled and why. Per `../../AGENTS.md`, a deliberate deviation from the style
guide is allowed but must be commented in place, dated, attributed, and logged here. Never
"correct" a documented deviation back to spec without reading the comment first.

---

## 2026-09-09 — This project composes, it does not redraw

The manuscript is capped at five figures and tables combined
(`CCR_reviews/Editor_instructions.md` §4), and the trends figure and the clinical-operations
figure were spending two of them. Merging them into one float returns a slot.

The merge is done by **calling the two projects' existing panel functions into one figure**,
not by reimplementing them. Both projects already expose the right seam: every
`panel_*.draw()` takes an externally-supplied `Figure` plus a rect in figure fractions,
creates its own axes inside it, and never touches `plt`, `figsize`, or `savefig`. So this
project holds no drawing code and no data. It contributes the geometry and the panel
letters, and nothing else.

**Rejected: copy the panel code into a third project and tune it there.** It would have made
a third thing to keep in step with two pipelines, and the first divergence would have been
silent — a published number that no longer matched the table it came from. As built, a
change to either sibling reaches this figure on the next build, because there is nothing in
between.

Neither sibling was modified. Both still build their own two-panel figures under their own
filenames and their own test suites still pass.

## 2026-09-09 — A wide canvas rather than a printed page

Stacked at native geometry the four panels need 4.92 + 4.18 + 4.05 + 1.45 = 14.6 in of panel
height, against about 9.5 in on a printed page. None of the three tall panels can move
sideways to recover it, because each needs 6.8–7.0 in of width and those widths are floors:

- Trends Panel A's thirteen columns per block sit at 0.102 in against
  `trends.plotting.panel_a.MIN_COLUMN_WIDTH_IN` of 0.085, and its fifteen-row pitch of
  13.2 pt is pinned by `test_the_matrix_row_pitch_stays_legible`. Its own DECISIONS log
  records that a *fifth* theme block was refused for breaching that same floor.
- Clinops Panel A places its nine device labels in **data** coordinates while their text has
  a fixed physical width, so its 4.85 in plot width is an invariant its own suite tests in
  two places.

So a page-fit merge would mean reversing two decisions argued at length in the sibling
DECISIONS logs: trends Panel B's direct end-of-line labels, and the clinops device gutter
whose entire point is that with n = 8 the devices are namable and naming them is the
argument.

**Adopted: 14.6 × 10.0 in, nothing cut.** AACR redraws every figure from the author's
sketch (`Editor_instructions.md` §4) and the five-float limit counts **items, not area**, so
canvas size costs nothing here. Author's decision.

The consequence to watch: at 14.6 in the figure wants a full landscape page in the proof.
`\includegraphics[width=\textwidth]` on a portrait page sets the type below legibility. That
is a proof concern rather than a print one, but a referee reads the proof. Noted in
`figure-legend.md`.

**Rejected: move trends Panel A to Supplementary and page-fit the rest.** It would also have
freed the float, and more cheaply, but it takes the modality-combination panel out of the
main text, which is the most novel of the four.

## 2026-09-09 — The right column grows into its slack; letters B and D stagger

First geometry placed both source figures at their exact native rects — clinops translated
by (7.80, 2.05) — which put letter C on letter A's line at 9.95 in and, for free, letter D
on letter B's line at 4.81 against 4.79 in. `clinops.plot.LANDSCAPE` argues for exactly that
alignment: a reader scans for the letters first.

Rendered, it was wrong. Clinops is an 8 in figure in a 10 in column, and at native heights
the surplus lands as a 2.4 in block of white below Panel D — the whole bottom-right corner
of the figure empty, which reads as an unfinished figure rather than as a margin.

**Adopted: grow the right column into its own slack.** Panel C 4.05 → 5.20 in tall, Panel D
1.45 → 1.90 in and moved down. **Only heights change.** Panel C's *width* is the invariant,
for the data-coordinate reason above; its height is free, and more of it spreads those eight
device labels further apart than the source figure manages. Panel D's two bars simply get
thicker. Canvas narrowed 15.0 → 14.6 in, set from the furthest label (Panel C's "Detection
and assessment (radiology)" at 14.38 in) plus about 0.2 in.

**The cost, accepted deliberately:** letter D no longer sits on letter B's line. The
alignment argument is kept where it counts — A and C are both at 9.95 in, the line a reader
enters the figure on. Below that the two columns hold different numbers of panels at
different heights, so B at 4.79 in and D at 3.66 in are staggered. Both were rendered and
compared: the staggered pair reads as two columns, the aligned pair read as an unfinished
corner. Author's decision. `tests/test_plot.py::test_the_top_two_letters_share_a_line` pins
the half that is load-bearing.

## 2026-09-09 — Panel D keeps the horizontal-bar form

`clinops.plot.LANDSCAPE` turns that panel upright, because it puts it in a 3.30 × 3.55 in
slot where horizontal bars would waste the height and crush radiology's two thin segments.
Here the slot is wide and short, as in the portrait, so the portrait's own orientation is
right. `vertical=False`, which is the default.

## 2026-09-09 — A gutter guard, because the paper-edge guard cannot see this failure

`clinops.plot.measure_margin` measures every label against the paper edge. On a two-column
canvas the likelier failure is a left-column label running into the right column, which is
not near any paper edge: trends Panel B labels its lines directly, in a gutter whose width
depends on how long the series names happen to be, and a longer name grows that gutter
sideways into Panel C, where it renders on top of it and nothing complains.

So `combined.plot.measure_gutter` measures every label that *starts* left of the column
boundary against that boundary, and the build raises `LabelOverflow` on a crossing exactly
as it does on an overflow. Currently 0.355 in of clearance. Neither source suite can see
this failure, which is why it is tested here.

## 2026-09-09 — The staleness guard is re-implemented, not reused

`trends.plot` refuses to draw from labels the current configuration would not produce, but
through a private helper that resolves its configuration as `Path("config")` — relative to
the working directory, which is the trends project only when the build runs from inside it.
From here it would silently find nothing.

`combined.plot._refuse_if_stale` calls the public
`trends.classify.check_freshness(directory, config_dir)` with an absolute path instead. That
keeps the guard and drops the assumption, without reaching into the sibling's private
function and without quietly going without. The clinical-operations project has no
equivalent ledger, so nothing is checked on that side.

## 2026-09-09 — The summary sheet is the two sheets, concatenated

`figures/combined_figure_summary.txt` calls `trends.plot.summary_text` and
`clinops.plot.summary_text` unchanged and prints both under a header. **Nothing is
recomputed here**, because a number recomputed in a third place is a number that can
disagree with the table it came from.

The header adds two things the siblings cannot write on their own:

1. **The panel-letter map.** Two panels changed letter, and the source projects' docs still
   use the old ones.
2. **The three-populations warning.** A is primary research, B is all article types, C and D
   are devices. Each source figure already warned about the two denominators inside it;
   putting papers and devices under one figure number makes that warning load-bearing,
   because a single figure number is an invitation to cross-quote.

## Open — the clinical-operations legend is stale against its own data

Not this project's to fix, but it will bite whoever writes the merged legend from it.
`../clinical-operations/docs/figure-legend.md` says 145 radiology and 9 pathology devices, a
16-fold gap, a 3/3/3 pathology split, and a 30 March 2026 snapshot. The current tables say
**193 and 8**, **24-fold**, **2/3/3**, and 27 March 2026, and the two radiology categories
have been renamed to "Detection and assessment" and "Treatment planning". Its own README
quotes the old numbers too.

`docs/figure-legend.md` here is refilled from the current summary and flags the discrepancy
at the top. The source project needs the same treatment on its own account.
