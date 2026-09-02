# AGENTS.md — instructions for producing figures in this project

**Read this before you draw anything.** Every figure in this manuscript has to read as one
system: same palette, same two type families, same rules about what colour is allowed to
mean. This file tells you how to hit that target. It is written for a coding agent, but a
person can follow it just as well.

If you are using Claude Code, add `@figures/AGENTS.md` to your `CLAUDE.md` so this loads
automatically. Cursor, Codex, Copilot, and Gemini CLI pick up `AGENTS.md` on their own.

## Authority

| File | What it is |
|---|---|
| `figures/ink_style_guide.md` | **Normative.** The "Ink" style — philosophy, palette, type, shapes, accessibility. When this file and that one disagree, that one wins. |
| `figures/AGENTS.md` (this file) | Operational. How to actually apply the guide, with the constants in copy-pasteable form and the traps called out. |
| `figures/trends-figure/src/trends/plotting/style.py` | The guide compiled into Python. The reference implementation for matplotlib figures. |

**Correction to the style guide:** §1 and §8 point at `build_variants.py` and
`figure1_ink_2x2.svg` as the reference implementation. Those files are not in this
repository. Use these instead:

- **matplotlib:** `figures/trends-figure/` (see `src/trends/plotting/`)
- **hand-authored SVG:** `figures/multimodal_integration_figure_inkstyle_horiz.svg`,
  `figures/ai_pathology_workflow.svg`

## The three things you may not change

1. **The modality-to-hue assignments are fixed project-wide.** Radiology is blue,
   pathology is pink, clinical text is green, molecular is orange — in every figure,
   forever. Do not rearrange them to suit one panel's composition.
2. **Colour is semantic, never decorative.** A colour appears only where it identifies a
   data modality. Anything structural — arrows, connectors, rules, bars, boxes — is ink or
   grey. If an element is not a modality, it does not get a hue.
3. **Never introduce a new hue.** If you need another category, reach for ink/grey
   treatments first: solid vs. dashed vs. dotted, hatching, marker shape, weight. Propose a
   new colour to the team rather than adding one yourself.

Corollary worth internalising: colour is never the *sole* cue (guide §7). Every coloured
element also carries an icon, a dash pattern, a marker, or a text label. Every figure must
survive being printed in greyscale.

## Route A — matplotlib figures (preferred)

Do not re-declare the constants. Import them:

```python
from trends.plotting import style
import matplotlib.pyplot as plt

with plt.rc_context(style.rc_params()):
    ...  # style.INK, style.modality_color("mri"), style.FS_AXIS_LABEL, etc.
```

`style.py` registers the vendored IBM Plex faces with matplotlib **at import time** and
raises `FontsUnavailable` if any face is missing or if matplotlib silently substitutes one.
That is deliberate — see "Fonts" below. `rc_params()` sets `pdf.fonttype=42`,
`svg.fonttype="none"`, and `savefig.dpi=300`, which is what the guide's §8 deliverables
rules require.

To build the existing trends figure:

```bash
cd figures/trends-figure
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -e .
.venv/bin/python -m trends.plot --input data/processed --output figures/
```

If your figure lives outside `trends-figure/`, either `pip install -e
../trends-figure` to import `style` directly, or copy the token table below.

## Route B — hand-authored or generated SVG

Copy these tokens verbatim.

### Palette

| Role | Hex | Use |
|---|---|---|
| Ink | `#141414` | Primary text, panel letters, serif headings, dark pills, badges |
| Line | `#33373D` | Arrows, connectors, brackets, structural strokes |
| Subtle | `#5C6068` | Secondary labels, axis titles, tick labels |
| Panel / box border | `#20242B` | Panel border 1.3, neutral box border 1.0 |
| Secondary output fill | `#3D4147` | Intermediate outputs, bars |
| Structural accent | `#4B4B4B` | Fusion modules, joint models, agents, "other" |
| Background | `#FFFFFF` | The only fill. No gradients, no shadows. |

| Modality | Border / accent | Deep (small text, icon tint) |
|---|---|---|
| Radiology imaging | `#0072B2` | `#00517F` |
| Digital pathology | `#CC79A7` | `#8F4B73` |
| Clinical text / EHR | `#009E73` | `#006B4E` |
| Molecular / omics | `#E69F00` | `#9C6C00` |

Okabe–Ito, colourblind-safe (Wong, *Nat Methods* 2011). Use the **deep** variant whenever
the coloured thing is small type — below about 8 pt the border hues read light on white,
and pink and green go pale in greyscale.

Sequential ramps (e.g. embedding tokens): start at the border colour and mix toward white
at 25 / 48 / 70 / 87 %. Blue: `#0072B2 → #338EC1 → #66AAD1 → #99C7E0 → #CCE3F0`.

### Light neutrals

Not in the guide's table — added by the trends figure for work the guide's reference
figure had no equivalent of. Reuse rather than inventing your own greys:

`#E3E3E3` absent-value dots · `#E9E9E9` shading over a partial/incomplete period ·
`#F2F2F2` alternating row bands · `#9A9A9A` separators and axis spines

### Shapes

Cards: white fill, corner radius 2, coloured hairline border 1.4–1.6. Panels: white fill,
`#20242B` border 1.3, radius 10. Terminal outputs: fully rounded pill, solid `#141414`,
white bold text. Arrows: `#33373D`, width 1.6 (1.8–2.0 for major flows), solid triangular
head ~6–7 units, ≥12 units clearance from any box edge. Dashed (`4 3` or `5 4`) means
placeholder / predicted / conceptual boundary.

## Type — and the one trap in it

Families: **IBM Plex Serif** for panel letters and titles, **IBM Plex Sans** for everything
else. Fallbacks `Georgia, serif` and `Arial, sans-serif`, but nothing should ever reach
them.

**The trap:** the style guide's §2 sizes are *SVG user units on a ~1355-unit-wide canvas*,
not points. Scaling them literally to a print-width figure destroys them — a 7.5 in figure
is 540 pt, a factor of 0.40, which puts the guide's body text near 5 pt and its own
9.5-unit floor near 3.8 pt. Both are below print legibility.

So: **preserve the guide's hierarchy and ratios, not its absolute numbers.** Anchor the
bottom of your scale on what is legible at your output size, then step upward by the
guide's own ratios. The trends figure's ladder, for a 7.5 in wide figure:

| Role | Size | Ratio to the step below |
|---|---|---|
| Panel letter | 12.6 pt | 1.47× (guide: 22/15 = 1.47×) |
| Section subtitle / theme title | 8.6 pt | 1.15× (guide: 15/13 = 1.15×) |
| Axis title, tick label | 7.5 pt | 1.29× (guide: 13/10.5 = 1.24×) |
| Small functional label | 5.8 pt | anchor (guide's 10–11 unit row) |
| Bar value | 5.5 pt | floor |

Never let effective text fall below ~9.5 units at the guide's canvas density, or below
about 5 pt in print. Minimum stroke 1.0.

## Fonts

Vendored at `figures/trends-figure/assets/fonts/` — all eight faces (both families ×
regular/bold/italic/bold-italic). IBM Plex 1.1.0, SIL Open Font License 1.1, so
redistributing them here is fine. They are kept in-project rather than installed
system-wide so a figure renders identically on any machine.

**A missing face must fail the build, not fall back.** `style.register_fonts()` checks that
every face is present *and* that matplotlib actually resolves to it rather than
substituting, and raises otherwise. Matplotlib's default is to warn once at a log level
nobody reads and render the whole figure in DejaVu Sans — a figure that is wrong in a way
nobody notices. If you write a new build script, reproduce this check. Do not downgrade it
to a warning.

For SVG, reference fonts by name (`svg.fonttype="none"`); do not outline them. The
journal's illustrator needs the text editable.

## Icons

`figures/icons/` holds the approved set: radiology (X-ray), microscope (pathology), medical
document (clinical text / EHR), DNA (molecular), robot (LLM agent), person (user). Both SVG
source and PNG raster of each.

- Single-weight line icons only. **Reuse these before sourcing anything new.** If a new
  concept genuinely needs an icon, take it from the same family so the stroke weight
  matches, and flag it for team approval.
- Tint modality icons to their **deep** colour from the palette table. Agents and people
  are ink `#141414`.
- Size 28–44 units inside a card, placed left of the label.
- Provenance: the `noun_*` SVGs are from The Noun Project and carry the icon ID in the
  filename. Check the licence on each before the figure set goes anywhere public, and
  budget for an attribution line in the acknowledgements if any is CC BY.

## Content rules

No explanatory annotations inside the artwork. Definitions, trade-offs, and caveats go in
the figure legend; only short functional labels (≤4 words naming what an element *is*) may
appear in-figure. Numbered badges ①②③ for any sequential process, and the legend walks the
numbers in order. No exemplar model names in artwork. Panel titles are short Title Case
noun phrases; everything inside is sentence case.

Every figure ships with a CCR-style legend using bold panel letters (`**A,** …`) that
absorbs the explanatory content you kept out of the artwork.

## Before you call a figure done

- [ ] Rendered at full size and visually inspected — no overlaps, no clipping, every arrow
      head landing on its target
- [ ] Serif headings actually rendered as serif (proof the fonts loaded and nothing
      silently substituted)
- [ ] Converted to greyscale and still readable — every series distinguishable without hue
- [ ] Checked under deuteranopia / protanopia / tritanopia simulation
- [ ] No new hues; modality assignments unchanged
- [ ] SVG **and** PDF exported, fonts referenced not outlined
- [ ] Legend drafted
- [ ] Build script committed alongside the figure, so the next revision is re-renderable

## If you have to deviate

Sometimes the guide is wrong for a specific figure. That is allowed, but it must be
deliberate and it must be written down. The precedent is in `style.py`: the guide's §4
hatch specification (`#F0F0F0` ground, `#BDBDBD` lines) exists for "masked, hidden, or
inactive elements", and applying it literally to Panel A's remainder column — which is 45 %
of a theme and the tallest bar in its block — made the loudest quantity the faintest mark
on the page. The override is implemented, commented in place with the reason, dated, and
attributed to the author's decision.

Do the same: change it, comment *why* in the code next to the change, and add a line to
`figures/trends-figure/docs/DECISIONS.md`. Never make a silent deviation, and never
"correct" a documented one back to spec without reading the comment first.
