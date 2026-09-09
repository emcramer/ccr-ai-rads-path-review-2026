# Figure specification

The deliverable is one two-panel figure for the CCR review manuscript. This file fixes the
figure's content and the schema of the tables it is drawn from, so the plotting code and
the classification code can be written independently.

Source sketch: `figure_mockup.jpg`.

AACR redraws figures from author sketches. Deliver a clear, complete, unfussy figure with a
full legend. Do not over-polish.

---

## The two panels draw on different populations

Author's ruling, 2026-09-08: **Panel A shows primary research; Panel B shows engagement.**

| | Panel A | Panel B |
|---|---|---|
| Reviews, perspectives, editorials, comments, letters, meta-analyses | **excluded** | **included** |
| Papers belonging to neither radiology nor pathology | excluded | excluded |
| Books, no PMID, no parsable year, outside the date window | excluded | excluded |

The reason is that the panels answer different questions. Panel A asks what data primary
research actually uses, so a review that discusses a modality without using one would corrupt
it. Panel B asks how attention to each theme moves over time, and a review naming a theme as a
future direction is evidence of attention — which is what the author's digital-twins ruling of
2026-09-02 already established.

**Consequences that must be stated wherever numbers appear.** The two panels have different
denominators, and no number from one may be quoted against the other. Panel A's per-theme `n =`
is the primary-research count; Panel B's series are the engagement counts and are larger. The
legend must say so plainly, and `figures/trends_figure_summary.txt` reports both.

The `paper_labels.csv` table carries every retained record with an `is_primary_research` flag,
so both views derive from one labelled table rather than from two pipelines that could drift.

## Panel A — which modality combinations each theme uses

An UpSet-style plot, one block per theme, blocks side by side in this order:
Foundation Models, Multimodal Integration, Digital Twins, Clinical Applications/FDA Approval.

Within a block:

- **Matrix (upper region).** Rows are the fifteen modalities, in a fixed order used by every
  block. Each column is one *combination* of modalities observed together in a paper. A
  filled dot marks a modality present in that combination; dots in the same column are
  joined by a vertical line. Absent modalities are drawn as light grey dots, so the row
  grid stays readable.
- **Bars (lower region).** One bar per column, height equal to the number of papers whose
  modality set equals that combination. Axis label: "# of papers".
- **Column order.** Descending paper count within each theme.
- **Column cap.** Show the top **12** combinations per theme, then one final column, set
  apart from the rest, labeled "all other combinations" and carrying every remaining paper
  in that theme. The bars therefore sum to the theme's total and **nothing is hidden**: the
  tail is drawn as a quantity rather than described in a footnote. The remainder column has
  no dots in the matrix — it is not one combination — and the number of distinct sets it
  represents prints beneath it.
- Blocks share one modality row axis, labeled once on the left. A thin vertical rule
  separates blocks; theme names sit above them.

Papers are multi-label: one paper may appear in more than one theme block. Within a block a
paper appears in exactly one column, the column for its exact modality set.

## Panel B — theme volume over time

**Two stacked line plots sharing one x-axis**, not one plot. Theme sizes differ by two orders
of magnitude, and on a single linear axis the small themes are flat lines on the floor.

### Which series are drawn

Foundation models and multimodal integration are each **split by clinical domain**, because
the review's question is where each theme is being pursued, not only how large it is.

| Plot | Series |
|---|---|
| Upper | foundation models × {radiology, pathology, cross-specialty} |
| Upper | multimodal integration × {radiology, pathology, cross-specialty} |
| Lower | digital twins (all) |
| Lower | virtual staining (all) |
| Lower | agentic AI (all) |
| Lower | clinical applications / FDA approval × {radiology, pathology} |

**Domain** comes from the modality labels, by the rule in the Input schema below:
`radiology` if the paper carries any radiologic modality and no pathologic one, `pathology`
for the reverse, and **cross-specialty** where it carries both — a paper pairing, say,
radiography with H&E. Cross-specialty is the integrative case the review argues about, so it
is drawn rather than folded into either side.

Papers whose only labels are non-imaging — genomics, clinical data, or `other` — have no
domain and appear on **no** split line. They are 257 of foundation models' 1,226 papers and
721 of multimodal integration's 4,654, so the split lines do not sum to the theme total and
the legend must say so.

Digital twins, virtual staining, and agentic AI are drawn undivided: digital twins is too
small to split three ways, virtual staining is pathologic by definition, and agentic AI is
both small and deliberately cross-cutting — an agent that reads reports, images, and records
is not usefully assigned to one specialty.

### How the series are distinguished

Per `figures/ink_style_guide.md`, colour is semantic and marks the **domain**:

| Domain | Colour |
|---|---|
| Radiology | `#0072B2` |
| Pathology | `#CC79A7` (deep `#8F4B73` for thin strokes and labels) |
| Cross-specialty | `#4B4B4B`, the guide's structural/integrative grey |
| No domain split (digital twins) | ink neutrals |

**Theme is carried by dash pattern and marker**, not by hue, so two blue lines in the upper
plot are radiology work in two different themes. Every line keeps a direct end label; colour
is never the only cue.

### Axes and marks

- Each plot has its own linear y axis, labelled. The scale difference must be unmistakable:
  the range band on the upper plot marks the lower plot's whole range.
- Per-year counts throughout. Not cumulative, not logarithmic.
- The final year is partial (retrieval date 2026-09-01): draw it in both plots, distinguish it
  with a dotted segment and an open marker, and shade it. Never describe a trend using it.
- Pathology in the clinical theme is exactly zero from 2015 through 2021. It must read as
  plotted zeros, not as a line that begins when the first paper appears.
- Small themes move by single papers between years, which carries no information. That
  statement lives in the legend, not on the figure.

---

## Input schema — `data/processed/`

Plotting code reads only these three files. It performs no classification and no filtering.

### `paper_labels.csv`
One row per paper in the corpus.

| Column | Type | Meaning |
|---|---|---|
| `pmid` | string | PubMed identifier |
| `year` | integer | Publication year, by the rule documented in the retrieval module |
| `year_source` | string | Which date field the year came from |
| `theme_foundation_models` | 0/1 | Theme labels, one column per theme |
| `theme_multimodal_integration` | 0/1 | |
| `theme_digital_twins` | 0/1 | |
| `theme_clinical_fda` | 0/1 | |
| `mod_<key>` | 0/1 | One column per modality, including `mod_other` |
| `domain` | string | `radiology`, `pathology`, `both`, or `none`, derived from modality labels |
| `is_primary_research` | 0/1 | 0 for reviews, perspectives, editorials, comments, letters, meta-analyses and the like. Panel A reads only the 1s; Panel B reads every row. |

`domain` derivation: `radiology` if any of MRI, CT, PET, ultrasound, mammography,
radiography, radiology report;
`pathology` if any of H&E, IHC, spatial proteomics, spatial transcriptomics, pathology
report; `both` if each side has at least one; `none` if the paper carries no imaging or report
modality at all — including a paper labeled only `genomics`, only `clinical_data`, only
`other`, or any combination of those three. Genomics, clinical data, and `other` take no
side: they are data types, not radiology or pathology examinations.

### `combination_counts.csv`
One row per theme and observed modality combination. Drives Panel A.

| Column | Type | Meaning |
|---|---|---|
| `theme` | string | Theme key |
| `modality_set` | string | Modality keys, sorted, joined by `+`; `other` alone is allowed |
| `n_modalities` | integer | Set size |
| `n_papers` | integer | Papers whose modality set is exactly this |
| `rank_in_theme` | integer | 1 = most papers |

### `theme_year_counts.csv`
Drives Panel B.

| Column | Type | Meaning |
|---|---|---|
| `theme` | string | Theme key |
| `domain` | string | `all` for a whole theme, or one of `radiology`, `pathology`, `both`, `none` for a split. Emitted for every theme; the figure chooses which rows to draw. `both` is displayed as "cross-specialty". |
| `year` | integer | Publication year |
| `n_papers` | integer | Papers with that theme label in that year |
| `partial_year` | 0/1 | 1 for the retrieval year |

---

## Output

- `figures/trends_figure.pdf` — vector, the version that goes to the journal
- `figures/trends_figure.png` — 300 dpi, for drafts and slides
- Both built by one command from `data/processed/`, with no manual steps afterward.

Width: fits a single manuscript page. Draw at a size where 7 pt type is legible; do not
rely on shrinking to hide crowding.

---

## Canonical keys — fixed, used by every file and every module

Themes (`theme` column values, and the `theme_<key>` column suffixes):

| Key | Display label |
|---|---|
| `foundation_models` | Foundation Models |
| `multimodal_integration` | Multimodal Integration |
| `digital_twins` | Digital Twins |
| `clinical_fda` | Clinical Applications / FDA Approval |
| `virtual_staining` | Virtual Staining |
| `agentic_ai` | Agentic AI |

Modalities (`mod_<key>` columns, and the members of `modality_set`), in figure row order:

| Key | Display label | Type |
|---|---|---|
| `he_histology` | H&E / Histology | Imaging |
| `ihc` | IHC | Imaging |
| `spatial_proteomics` | Spatial Proteomics | Imaging |
| `spatial_transcriptomics` | Spatial Transcriptomics | Imaging |
| `pathology_report` | Pathology Report | Text |
| `mri` | MRI | Imaging |
| `ct` | CT | Imaging |
| `pet` | PET | Imaging |
| `ultrasound` | Ultrasound | Imaging |
| `mammography` | Mammography | Imaging |
| `xray` | Radiography (X-ray) | Imaging |
| `radiology_report` | Radiology Report | Text |
| `genomics` | Genomics / Transcriptomics | Molecular |
| `clinical_data` | Clinical / EHR Data | Structured |
| `other` | Other | All other |

Row order groups pathology modalities, then radiology modalities, then the non-imaging data
types, then `other`, so the pathology/radiology split in Panel A is visible without reading
the labels.

`genomics` and `clinical_data` are **not** imaging modalities and do **not** contribute to
the `domain` rule. A paper using MRI and genomics is `radiology`, not `both`. They are drawn
as rows because the pairing of imaging with molecular or clinical data is the multimodal
integration the review argues about, and it is invisible if those data types have no row.

`other` is **additive**: it marks a paper that uses a data type outside the named rows, and
it may appear alongside named modalities. It is also assigned, as before, to a paper that
matches no named modality at all. Both routes are recorded in `pattern_hits.csv`.
