# Figure 1, radiology row — from acquisition to clinical task

Builds the radiology row of the manuscript's Figure 1: a four-column pipeline schematic
running input data, preprocessing, models, clinical tasks. It is Panel A of a two-row
figure whose pathology row is authored separately.

Status: **built and checked.** `docs/DECISIONS.md` records what was settled and why,
`docs/figure-spec.md` the geometry and type ladder, `docs/figure-legend.md` the CCR-style
legend.

## Layout

```
figure1-radiology/
├── build.py           the whole figure, one script; writes to figures/
├── assets/panels/     48 panels rendered from openly licensed imaging data (30 are used)
├── assets/icons/      37 hand-authored 24x24 line icons
├── assets/README.md   panel-by-panel provenance, licences, required citations
├── docs/              spec, legend, decision log
└── figures/           PDF, PNG at 300 dpi, SVG, and the summary of legend numbers
```

`assets/` is the build input and is never written to by `build.py`. Regenerating the panels
is a separate job (`assets/render_panels.py`) that reads multi-GB source volumes not kept
here; `assets/README.md` names the sources.

## Setup

```bash
python3 -m venv ~/.venvs/ccr-figure1
~/.venvs/ccr-figure1/bin/pip install -r requirements.txt -e ../trends-figure
```

The editable install of `../trends-figure` is required, not optional: `build.py` imports
`trends.plotting.style` and re-declares no palette or type token, which is what
`../AGENTS.md` asks for. `cairosvg` is new relative to the sibling figures and binds to the
system Cairo library, so a machine without `libcairo` fails at import.

## Build

```bash
~/.venvs/ccr-figure1/bin/python build.py --output figures/
```

Writes `figures/figure1_radiology.{pdf,png,svg}` and `figure1_radiology_summary.txt`. Every
number quoted in the legend comes from that summary file.

## Style

Radiology blue `#0072B2` and its deep variant are the only hues; molecular orange `#E69F00`
appears where PET signal is shown, since PET is the molecular modality on the fixed
assignment. Everything structural is ink or grey. Colour is never the only cue: each panel
also carries an icon and a text label, and the figure was checked in greyscale.

The figure is a remake of a 31 Aug 2026 HTML build that used the Inter face and cream
chips. `docs/DECISIONS.md` lists what changed under the Ink style and what was kept from
the original at the author's instruction.

## Credits

Every panel derives from a CC BY 4.0 or CC0 source: TotalSegmentator, AMOS22,
FDG-PET-CT-Lesions (autoPET), CMMD, the TCIA liver ultrasound collection, and one Wikimedia
Commons chest radiograph. The per-panel list with licences is in
`figures/figure1_radiology_summary.txt`; the full citations TCIA's terms require are in
`assets/README.md` under "Required citations" and belong in the manuscript's reference list.
