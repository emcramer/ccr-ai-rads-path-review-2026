# combined-figure

One four-panel figure built from the two sibling projects, so they cost **one** manuscript
float instead of two. The manuscript is capped at five figures and tables combined
(`CCR_reviews/Editor_instructions.md` §4); this returns a slot.

| Panel | Source project | Called there |
|---|---|---|
| **A** | `../trends-figure` | Panel A — modality combinations by theme |
| **B** | `../trends-figure` | Panel B — theme volume over time |
| **C** | `../clinical-operations` | Panel A — cumulative oncology AI authorizations |
| **D** | `../clinical-operations` | Panel B — authorization pathway |

**Two panels changed letter.** Both source projects still build their own two-panel figures
and their docs still say "Panel A" and "Panel B". The map above is printed at the top of
every summary sheet for that reason.

## What this project contains

No drawing code and no data. Every mark comes from a panel function in `trends.plotting` or
`clinops.plotting`, and every number comes from those projects' own `data/processed/`
directories, read through their own validators. This project contributes exactly two things:
the geometry that says where the four panels go, and the letters that renumber them.

That is deliberate — see `docs/DECISIONS.md`. A merged figure that reimplemented either
panel would be a third thing to keep in step with two pipelines, and the first divergence
would be silent. As built, a change to either sibling reaches this figure on the next build,
because there is nothing in between. Neither sibling was modified.

## Setup and build

Both siblings must be installed **editable**, or at least with `assets/fonts` still above
the installed `style.py`: importing `trends.plotting.style` registers the vendored IBM Plex
faces at import time and raises `FontsUnavailable` rather than letting matplotlib silently
substitute DejaVu Sans.

The virtual environment belongs **outside** the repository: the whole tree is OneDrive-synced
and a venv inside it pushes tens of thousands of files into cloud sync. Reproducibility rests
on the pinned `requirements.txt`, not on the environment's location.

```bash
cd figures/combined-figure
python3 -m venv ~/.venvs/ccr-combined
~/.venvs/ccr-combined/bin/pip install -r requirements.txt -e . -e ../trends-figure -e ../clinical-operations
~/.venvs/ccr-combined/bin/python -m combined.plot --output figures/
~/.venvs/ccr-combined/bin/python -m pytest -q
```

By default it reads `../trends-figure/data/processed` and
`../clinical-operations/data/processed`, resolved **relative to this package rather than to
the working directory**, so the build gives the same figure from any cwd. Override with
`--trends-input` and `--clinops-input`. `--tag` suffixes the stem, so a build from stand-in
fixtures cannot be mistaken for one from the real tables.

### Outputs

- `figures/combined_figure.pdf` — vector, the version that goes to the journal
- `figures/combined_figure.png` — 300 dpi, for drafts and slides
- `figures/combined_figure.svg` — text as text, for the journal's illustrator
- `figures/combined_figure_summary.txt` — the number sheet the legend is refilled from

The summary is the two projects' own summary sheets concatenated verbatim under a header,
so every number still traces to the pipeline that computed it. **Refill the legend from that
file, never by reading the picture.**

## Why the canvas is 14.6 × 10.0 in

Stacked at native geometry the four panels need 14.6 in of panel height against about 9.5 in
on a printed page, and none of the three tall panels can move sideways: each needs
6.8–7.0 in of width, and those widths are tested floors in their own projects. Fitting a
page would mean reversing two decisions argued at length in the sibling DECISIONS logs.

AACR redraws every figure from the author's sketch and the five-float limit counts **items,
not area**, so the canvas is wide and nothing is cut. Full reasoning, and the two rejected
alternatives, in `docs/DECISIONS.md`.

**One consequence for the proof:** at 14.6 in this wants a full landscape page.
`\includegraphics[width=\textwidth]` on a portrait page sets the type below legibility. The
LaTeX float in `docs/figure-legend.md` uses `figure*` and `[p]` for that reason.

## Two guards on every build

Both raise rather than warn, because a figure that is wrong in a way nobody notices is the
failure mode all three of these projects keep designing against.

- **`LabelOverflow` on a label off the canvas** — reuses `clinops.plot.measure_margin`.
  Currently 0.050 in of clearance, which is the panel letters at the top edge, exactly as in
  both source figures.
- **`LabelOverflow` on a label across the column gutter** — `combined.plot.measure_gutter`,
  new here. Trends Panel B labels its lines directly, in a gutter that grows sideways into
  Panel C as series names get longer; that collision is near no paper edge, so the first
  guard cannot see it and neither source suite can either. Currently 0.355 in.

## Before calling a revision done

Run the `../AGENTS.md` checklist against the PNG — greyscale, CVD simulation, no new hues,
no overlaps or clipping, serif panel letters actually serif. The test suite covers the
composition (four panels, four letters, no overlaps, no gutter crossings, the 4.85 in
invariant, the panel-letter map); it does not cover what the panels draw, because their own
suites do that exhaustively.

## Known issue in a source project

`../clinical-operations/docs/figure-legend.md` and its README are **stale against their own
data** — 145/9 devices, a 16-fold gap, a 3/3/3 split, a 30 March 2026 snapshot. The current
tables say 193/8, 24-fold, 2/3/3, and 27 March 2026. `docs/figure-legend.md` here is refilled
from the current summary and flags it; the source project needs the same fix on its own
account.
