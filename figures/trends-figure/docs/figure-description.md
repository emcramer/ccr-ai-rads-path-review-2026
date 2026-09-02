# Figure description — working document, not for the journal

The full account of the two-panel trends figure: what it shows, every number in it, and
every limitation those numbers carry. **This is not the figure legend.** The legend the
journal prints is `figure-legend.md`, which is a few sentences; this file is where its
claims come from and where anything cut from it is recorded.

Filled from the corpus run of 2026-09-02.
Every number below comes from `data/processed/run_manifest.json`,
`data/processed/classification_report.txt`, or `figures/trends_figure_summary.txt`,
which `plot.py` writes beside the figure on every build, or from `docs/validation.md`.
Do not retype numbers from the picture. No placeholders remain. Dictionaries are at
version 6; the run manifest records their hashes.

Written to the manuscript's conventions: American spelling, serial commas, no promotional
language, and no claim the data cannot carry.

---

## Legend

**Figure [figure number]. Data modalities and publication volume in AI research on
radiology and pathology, 2015–2026.**
**A,** Modality combinations used by each research theme. Rows are the fifteen data
modalities, grouped as pathology, radiology, the non-imaging data types (genomics or
transcriptomics, and clinical or EHR data), and other. Genomics and clinical data are not
imaging and do not contribute to the radiology-versus-pathology split in **B**: a paper
using MRI and genomics is radiologic, not both. A paper may carry Other alongside named
modalities as well as alone, so the column `mri+other` means MRI plus some data type
outside the named rows, not MRI alone. The twelve left-hand columns of each block are the
theme's twelve commonest modality combinations, in descending order; a filled dot marks a
modality present in that combination, and dots in one column are joined by a vertical
line. The thirteenth column, set apart by a dotted rule and drawn hollow and hatched,
holds every remaining paper in the theme. It carries no dots, because it is not a
combination, and the number of distinct combinations it collects is printed beneath it.
The bars therefore sum to the theme total, and no paper in a theme is left out of its
block. Within a block, each paper falls in exactly one column. Bar height is the
percentage of that theme's own papers, so the four blocks are comparable in composition
but not in volume; volume is in **B**, and each block prints its own total beneath it. The
remainder column holds 388 papers in 127 combinations for foundation models, 31.6% of the
theme; 2,116 papers in 305 combinations for multimodal integration, 45.5%; 19 papers in 19
combinations for digital twins, 33.9%; and 15 papers in 15 combinations for clinical
applications and FDA approval, 16.1%. The twelve largest columns of the multimodal
integration block are mostly single modalities, and its remainder column is its largest
bar: the multimodality of that literature is dispersed across hundreds of small
combinations rather than concentrated in a few large ones.
**B,** Papers per year, drawn as two stacked plots that share one x axis and carry
separate linear y axes. Ten series are drawn. The upper plot holds foundation models and
multimodal integration, each divided by clinical domain; the lower plot holds digital twins,
virtual staining, and the two clinical-applications domain lines. The series differ in size by
two orders of magnitude — 2,835 papers for multimodal integration in radiology against 13 for
clinical applications in pathology — and on a single axis the small ones draw as flat lines on
the floor. **The two y axes are not the same scale.** The lower plot's axis is about 26 times
finer than the upper plot's, and the dashed rule near the foot of the upper plot marks the
lower plot's entire range. Counts are per year throughout, neither cumulative nor logarithmic.

**Color and marker denote clinical domain; dash pattern denotes theme.** Radiology is
`#0072B2` with a circle, pathology `#8F4B73` with a square, cross-specialty `#4B4B4B` with a
triangle, and the two undivided series carry a diamond. Domain is therefore legible in
grayscale, where hue is lost but marker shape survives; a test asserts that dash and marker
alone separate every series within a plot, with no color at all.

**Domain is derived from the modality labels**: radiology where a paper carries a radiologic
modality and no pathologic one, pathology for the reverse, cross-specialty where it carries
both. Mammography and radiography count as radiologic, per the modality grouping in **A**.
The four domain values partition each theme exactly, so `radiology + pathology +
cross-specialty + none` equals the theme total — but the drawn lines do not, because papers
with no domain are drawn nowhere. That omission is 257 of foundation models' 1,226 papers and
721 of multimodal integration's 4,654: papers whose only labels are genomics, clinical data,
or Other.

Clinical applications is divided into radiology (60 papers) and pathology (13); its three
cross-specialty papers and 17 no-domain papers are drawn on neither line. Digital twins and
virtual staining are drawn undivided — the first is too small to divide three ways at 56
papers, the second is 75 of 76 pathologic and so has nothing to divide. Virtual staining is
nonetheless drawn in the pathology hue and marker, because that is a true statement about its
papers and because ink would have put it in the same stroke as digital twins, which it crosses
in 2024 and 2025.

Pathology in the clinical theme is exactly zero in every year from 2015 through 2021, drawn as
seven plotted points on the zero line rather than as a line beginning in 2022; where two lines
both sit at zero, only the upper of the two is visible. Lines are labeled at their right-hand
ends.

The lower plot magnifies themes of 93 and 56 papers, and their year-to-year movement is
largely sampling noise. Clinical radiology runs 13, 9, and 21 papers across 2024, 2025,
and 2026, and a difference of a few papers between adjacent years carries no information.
No statement in the text rests on such a change.

Papers were retrieved from PubMed on 2026-09-01 with the query in `config/corpus.yaml`,
and themes and modalities were assigned by matching a versioned term dictionary against
each title and abstract. The search returned 44,625 records; 8 book records and 84 records
whose publication year fell outside 2015–2026 were excluded, leaving 44,533 papers
analyzed. Classification is multi-label: one paper may carry several themes and several
modalities, so the theme totals sum to more than the corpus and a paper may appear in more
than one block of **A**. Theme totals are 1,226 papers for foundation models, 4,654 for
multimodal integration, 56 for digital twins, and 93 for clinical applications and FDA
approval; 38,827 papers carry no theme label.

Classifier accuracy was measured against stratified samples of abstracts labeled by a
language model and calibrated by an author audit; it is not a hand-labeled gold standard,
and no single accuracy figure describes the classifier, because precision differs by more
than threefold across categories. Per-category precision, with the counts it rests on, is
reported in `docs/validation.md`. The imaging rows are the most reliable: CT, MRI, PET,
ultrasound, and mammography ran 85-96% precision and 94-98% recall. Among themes, clinical
applications and FDA approval ran 92% precision and 96% recall, and foundation models 89%
after revision. Two rows are materially weaker and are described below.

The clinical or EHR data row counts papers that state they combined clinical variables
with imaging. It over-counts papers that merely report clinical variables alongside a
model, and under-counts papers that combine them without saying so, so it is not a precise
count of multimodal clinical-imaging models.

The genomics or transcriptomics row counts data used as model input. A paper that predicts
a molecular label from an image is not counted as using genomic data, because the molecular
data there is the prediction target. That rule removes the recognizable form of the problem
but not all of it: a paper predicting a molecular subtype from histology, which also names
the sequencing behind its ground-truth labels, still matches. Validation put precision in
the genomics and H&E cell at about 45% before the rule and measured that a looser rule would
discard genuine papers faster than it removed spurious ones. **That cell is the least
reliable in A and should not be read as comparable to the imaging rows.**

The Other row combines two different assignments. A pattern match is a positive finding: the
paper uses a data type outside the fifteen named rows, such as endoscopy, dermoscopy,
dosimetry, mass spectrometry, or ECG. The remainder are a fallback, meaning no named
modality could be identified from the title and abstract, so the modality is **not
determined** rather than Other. Validation scored the two apart: the pattern route was
correct in 21 of 23 sampled papers (91%, 95% CI 73-98%), the fallback route in 18 of 24
(75%, 55-88%), the errors being papers whose modality a reader could name and the dictionary
could not. The two should not be summed into a single count of papers using an unlisted
data type.

**The four themes do not all measure the same kind of thing.** Foundation models, multimodal
integration, and clinical applications count what a paper does. Digital twins counts
engagement with an idea: a paper is included if it invokes the digital-twin concept in that
vocabulary, whether it builds one, proposes a framework, or names the concept as a future
direction. That is deliberate, because the figure tracks interest in the literature rather
than successful construction. A hand screen read all 56 papers: 18 describe a
patient-specific model meeting the definition used in this review, and 3 update as new
measurements arrive. Readers should not take the digital-twins count as a count of built
twins.

Modality marks record what a title and abstract indicate, so they over-attribute rather than
under-attribute: hand-coding of every disagreement in the validation samples found that 43%
of false positives were papers mentioning a modality they did not use, with no cases in the
opposite direction. Every count in A is therefore an upper bound on genuine use, and the
bias is largest in rows whose term names an idea rather than an instrument.

2026 is partial. It covers papers indexed through 2026-09-01 and is shaded in both plots
of **B**, drawn with a dotted final segment and an open marker. It is not evidence of a
decline, and no trend statement in the text rests on it. PET and CT co-occur often because
most oncologic PET is acquired as PET/CT; that overlap is real and is not suppressed.

---

## Notes for the authors, not for the journal

- **The figure follows `figures/ink_style_guide.md` as of 2026-09-02.** Colour is semantic:
  Panel A's dots take their row's modality colour, and the only colour in Panel B marks the
  clinical theme's radiology and pathology series, which are modality-domain series. Themes
  are distinguished by ink tone, dash, and marker instead. Type is IBM Plex Serif for panel
  letters and block titles, IBM Plex Sans elsewhere; the faces are vendored at
  `assets/fonts/` and the build raises rather than substituting silently.
- **Three explanatory annotations were removed from the artwork** under §6 of the guide and
  now rest on the legend alone: the pathology zero-run callout, the sentence explaining the
  dashed range rule, and the "top 12 of N combinations" line under each block. If the legend
  is cut further, the zero-run statement should move to the body text rather than disappear.
- **The remainder column deliberately departs from §4.** The guide assigns its pale hatch to
  "masked, hidden, or inactive" elements; the remainder column is none of those, and in the
  multimodal block it is the tallest bar. It is hatched in the bars' own ink instead. The
  reasoning is recorded beside the constants in `style.py` and asserted by a test, so
  restoring the pale spec fails rather than passes silently.
- **Type was not scaled literally from the guide.** The guide's sizes are units on a canvas
  about 1355 wide; this figure is 540 pt wide, so literal scaling would put body text near
  5 pt and the guide's own floor near 3.8 pt, below print legibility and below the floors
  this project measured and tested. The guide's hierarchy and ratios are preserved instead.

- **Fill any number from the summary file, not from the figure.** `plot.py` writes
  `figures/trends_figure_summary.txt` on every run, holding the corpus size, the theme
  totals, and the remainder counts per theme. Its Panel B block also holds the two numbers
  the split needs: how many times finer the lower y axis is, and the span of the pathology
  zero run.
- **`share` is now the code's default**, so a plain rebuild produces the shipped figure.
  `--panel-a-scale count` still draws the other version: bars in papers on one axis shared
  by all four themes, which renders digital twins and the clinical theme as hairlines. Under
  `count`, two sentences change: bar height becomes the number of papers on one scale shared
  by every block, and the sentence about composition against volume comes out. The run
  summary records which scale drew the file, so a PDF cannot be traced to the wrong one.
- **`docs/figure-spec.md` has been corrected to match the measured data**: pathology zero
  for seven years, 2015–2021, and clinical clinical radiology 13, 8, 19 across 2024–2026. Where the
  two ever disagree again, the legend follows the data and the spec is the stale copy.
- **The count of clinical papers on neither Panel B line is 17, not 16.** All 94 clinical
  papers carry at least one modality label. Seventeen carry no radiologic and no
  pathologic one: 16 are labeled only Other, and 1 is labeled genomics and Other.
  Three further papers use both domains and count in both lines.
- **The accuracy paragraph is filled from `docs/validation.md`** and deliberately reports
  per-category rates rather than one number: precision ranges from about 45% to 96% across
  categories, and the validation strata are not proportional to the corpus, so a weighted
  corpus-wide figure is not available. That was tested, not assumed — weighting the strata
  back to corpus scale reproduced known counts with a median error of 19% and a worst case
  of +106%. **Do not publish a single headline accuracy figure for this classifier.**
- **The small-count warning and the change-of-scale note are no longer on the figure.**
  Both moved to the legend by the author's decision of 2026-09-02, and the gap between the
  plots was tightened accordingly. `panel_b.SHOW_GAP_NOTES = True` restores both lines and
  widens the gap again to fit them. The scale difference is still carried graphically, by
  two labelled axes, the break between the plots, and the range band on the upper plot.
- **Check the scale-ratio figure against the run before quoting it.** It is computed from
  the axes actually drawn, so it moves when the data move; on the current corpus it is 43.
  If it ever falls below `panel_b.MIN_RATIO_FOR_BAND`, the figure stops drawing the range
  band on the upper plot, and any sentence about the dashed rule must come out with it.
- **Nothing in Panel A is hidden any more.** The old top-eight cap left 48.7% of the
  multimodal integration papers off the panel. Twelve columns and a remainder column leave
  none off, and the remainder is drawn at its true height: for that theme it is the tallest
  bar in the block. Do not describe it as a rounding error, and do not let a redraw shrink
  it into one.
- **A break-marked bar axis was considered and rejected.** The reasoning is recorded at the
  top of `src/trends/plotting/panel_a.py`, under "Rejected alternatives", next to the code
  that would have to change: on a bar chart the length of the bar is the quantity, measured
  from zero, and a break makes a small bar read as comparable to a large one.
- **Panel A's type has a floor and so does its geometry.** Row labels are sized to
  "Genomics / Transcriptomics" at 1.41 in, and columns to 0.10 in, which is what holds the
  dots legible at thirteen columns per block. Both are tested: `tests/test_plot.py` fails
  if a row label outgrows the gutter, if the row pitch drops below 12 pt, if a column drops
  below `panel_a.MIN_COLUMN_WIDTH_IN`, or if any label on the figure runs off the page.
  Raising the column cap to twenty fails the third of those.
- Journal limits: figures and tables together must not exceed five, and this figure must be
  mentioned in the body text. See `.claude/RULES.md`.

Rebuild command:

```
~/.venvs/ccr-trends/bin/python -m trends.plot --input data/processed --output figures/
```
