# Figure specification

The deliverable is one two-panel figure for the CCR review manuscript. This file fixes the
figure's content and the schema of the tables it is drawn from, so the plotting code and
the classification code can be written independently.

Source sketch: `figure_mockup.jpg`.

AACR redraws figures from author sketches. Deliver a clear, complete, unfussy figure with a
full legend. Do not over-polish.

---

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

**Two stacked line plots sharing one x-axis**, not one plot. Measured theme sizes differ by
two orders of magnitude — Multimodal Integration 5,794 papers against Clinical/FDA's 94 —
and on a single linear axis the small themes are flat lines on the floor.

- **Upper plot:** `foundation_models`, `multimodal_integration`.
- **Lower plot:** `digital_twins`, and the two `clinical_fda` domain lines.
- Each plot carries its own y-axis label and its own linear scale. The difference in scale
  must be unmistakable; a reader must not read the lower plot as a continuation of the upper.
- X axis: publication year, shared, labeled once.
- Lines are labeled at their ends rather than in a legend box.
- Per-year counts throughout. Not cumulative, not logarithmic.

The Clinical Applications/FDA Approval theme is split into radiology and pathology, drawn
with the same colour and different dash patterns, per the sketch's "(Rads vs. Path)" note.

Two features of the real clinical series must survive the drawing:

- **Pathology is exactly zero for seven consecutive years** (2015-2021; 2022 holds one
  paper). That is the review's argument. It must read as a visible zero, not as a line that
  begins when the first paper appears.
- **Radiology runs 13, 9, 21 across 2024-2026.** The dip is sampling noise in a 94-paper
  theme. The legend must say that single-digit yearly changes here carry no information.

The final year is partial (retrieval date 2026-09-01). Draw it in both plots, distinguish it
— dashed segment or open marker — and say in the legend that it is partial. Do not describe
a trend using the partial year.

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
| `domain` | string | `all`, or `radiology`/`pathology` for the clinical theme split |
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
