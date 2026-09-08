# Decision log

Append-only. One entry per decision that a reader could reasonably question.
Format: date, decision, alternatives considered, reason, who made it.

---

## 2026-09-04 — Remake in matplotlib rather than restyle the HTML

**Decision.** Rebuild the row with matplotlib under `trends.plotting.style`, embedding the
original's rendered panels and rasterized icons, instead of editing the original HTML build.
**Alternatives.** (a) Restyle the HTML and print it to PDF from a browser; (b) hand-author
an SVG as the collaborator did for the multimodal schematic.
**Reason.** (a) needs a browser on the build machine and cannot enforce the font check the
collaborator requires; the fonts would load from Google Fonts or fall back silently. (b)
needs an SVG renderer with the vendored fonts configured for PDF export, which this
machine lacks. Matplotlib is the collaborator's preferred route, registers the vendored IBM
Plex faces and raises if one is missing, and writes PDF, PNG, and SVG with text as text from
one script.
**Consequence.** Icons and panels are raster inside the PDF (600 px per inch of print for
panels, 600 px per icon). The journal redraws figures, so vector icons were not required.
**Who.** Claude, on the user's instruction to match the collaborator's style and rules.

## 2026-09-04 — Width 7.5 in, height grows to 4.18 in

**Decision.** Draw at a full manuscript page width with type on the collaborator's ladder
(smallest 5.5 pt), and let the height grow from the original's 2:1 aspect to 1.8:1.
**Alternatives.** Keep the original's 1400 by 700 px proportions and scale.
**Reason.** Scaling the original to 7.5 in puts its 9 px captions at 3.7 pt, below the 5 pt
floor in `AGENTS.md`. Column widths keep the original's proportions so the pathology row
can still be drawn to the same grid.
**Consequence.** With the pathology row at the same height, Figure 1 is 7.5 by about 8.4 in.
**Who.** Claude.

## 2026-09-04 — Coloured overlays in the panels are snapped to the palette

**Decision.** Saturated pixels in the rendered panels are re-hued: contours and organ
overlays to radiology blue `#0072B2`, PET signal to molecular orange `#E69F00`, the
histogram bars to bar ink `#3D4147`, the GLCM heat map to greyscale.
**Alternatives.** (a) Re-render the panels from the source volumes with palette colours;
(b) leave the panels as delivered.
**Reason.** (a) needs the multi-gigabyte source volumes, which are not in the package. (b)
puts a magma heat map, steel-blue bars, a red lesion contour, and a multi-hue organ map into
a figure whose one colour rule is that hue means modality; the organ map alone used four hues
that the guide assigns to other modalities. Re-hueing keeps brightness, so ramps stay ramps
and organs stay apart by lightness.
**Consequence.** Organ overlays no longer distinguish organs by hue. `render_panels.py`
should adopt the palette when the panels are next re-rendered, and this step then becomes a
no-op.
**Who.** Claude.

## 2026-09-04 — Detection thumbnail uses the CT contour, not the fused box

**Decision.** The detection task thumbnail is the lesion contour on the CT slice
(`h_lesion_ct_axial_seg.png`) rather than the yellow box on the fused PET/CT slice.
**Reason.** The box and the hot-colormap PET signal on the fused slice occupy the same hue
range, so the hue snap cannot separate them: the box would become orange and read as
molecular signal. The CT contour re-hues cleanly to blue.
**Who.** Claude.

## 2026-09-04 — Icons keep the hand-authored set, with the stroke raised

**Decision.** Use the 37 hand-authored icons from the original package for the preprocessing,
model, and task concepts, rasterized with the stroke raised from 0.5 to 1.1 units.
**Alternatives.** Source icons from the Noun Project family the collaborator approved.
**Reason.** The approved set has no icon for CNN, U-Net, ViT, SSL, VLM, task head, or any
of the ten clinical tasks, and the collaborator's rule is to reuse before sourcing and to
flag new icons for team approval. At 0.26 in the original 0.5-unit stroke prints at
0.39 pt, under the guide's minimum stroke; 1.1 units prints at 0.86 pt, near the Noun
Project icons' weight.
**Consequence.** These icons must be flagged to the team for approval. The approved
document and DNA icons were tried for the paired-data cards and dropped: at 0.62 in card
width there is no room for an icon beside a legible label, and the label is the second cue
the guide requires.
**Who.** Claude; team approval pending.

## 2026-09-04 — Explanatory text moved from artwork to legend

**Decision.** Removed from the artwork: the dimensionality strip; the IBSI feature-family
list; the task-head list; "one backbone, many tasks"; the sentence on the dashed link; the
data credits. Kept: labels of four words or fewer, and the note "along the care pathway".
**Reason.** The style guide's content rule: no explanatory annotation inside the artwork,
only short functional labels; the legend absorbs the rest.
**Who.** Claude, applying the collaborator's rule.

## 2026-09-04 — Cream chips become white cards; column boxes become open columns

**Decision.** The original's cream chips (`#F7E8C4`) are neutral white cards with a
`#20242B` hairline; the dashed column boxes are removed and the columns are separated by
flow arrows between their serif subtitles.
**Reason.** Cream is a hue outside the palette. Dashed strokes mean placeholder or
conceptual boundary in the guide, which a column is not.
**Who.** Claude.

## 2026-09-04 — No flow arrows between column subtitles

**Decision.** The four columns carry no arrows or separators between them; left-to-right
order and the legend state the sequence.
**Alternatives.** Arrows in the 0.12 in gaps between subtitles (tried); numbered badges on
the four columns; vertical rules.
**Reason.** At 9 pt the gap arrows drew as stubs pressed against the serif titles. Column
badges would collide with the badges that number the three model generations. A rule in the
gap between the models and tasks columns would sit on the dashed link's vertical run.
**Who.** Claude.

## 2026-09-04 — The original's structure and aspect ratio are kept; only the style changes

**Decision.** The remake keeps the original figure's geometry, scaled from its 1400 px
canvas to 7.5 in: the section title above the frame, the frame and its padding, the header
row, the four dashed column boxes at 580 px height, the two strips in the data column, the
chips and brace captions, the dashed link with its note in the frame's bottom padding, and
the credit lines under the frame. Page aspect 1.73 against the original PDF page's 1.74.
Only fonts, colours, stroke treatment, and the type ladder change.
**Alternatives.** The first remake of the same day, which dropped the column boxes, the
dimensionality strip, the in-figure notes, and the credits to satisfy the style guide's
content rule, and let the height grow.
**Reason.** The author asked that the bounding boxes, aspect ratio, and total structure be
kept, so the pathology row, built in Figma to the same grid, still stacks in register. The
style guide's content rule is therefore relaxed for this figure's short notes and credits,
which is the kind of deliberate, written-down deviation `AGENTS.md` allows.
**Consequence.** Type at the collaborator's ladder needs more room than the original's, so
thumbnails inside the same boxes are 5 to 15 percent smaller than a straight scaling, and
0.16 in moved from the preprocessing column to the clinical-tasks column so the two-line task
labels fit at 6 pt. A build-time check fails if any column's content runs past its box.
Superseded by this entry: the "no flow arrows", "explanatory text moved to legend", and
"column boxes become open columns" entries above, and the height growth in the width entry.
**Who.** The author (Terry), 2026-09-04; implemented by Claude.
