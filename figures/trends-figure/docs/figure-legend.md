# Figure legend

For the manuscript. The full account of the figure, every number in it, and every
limitation those numbers carry is in `figure-description.md`.

---

**Figure [N]. Data modalities and publication volume in AI research on radiology and
pathology, 2015–2026.**
**A,** Modality combinations used by papers in each of four research themes. Rows are the
fifteen data modalities, colored by modality group; a filled dot marks a modality present in
a combination, and joined dots mark modalities used together. Bar height is that
combination's share of the theme's own papers, and the hatched column holds all remaining
combinations, so the bars sum to the theme total. **B,** Papers per year, in two plots with
separate linear y axes: the lower axis is about 26 times finer than the upper, and the dashed
rule marks the lower plot's full range. Foundation models and multimodal integration are each
divided by clinical domain — radiology, pathology, or cross-specialty for papers using both —
as is clinical applications. Color and marker denote domain; dash pattern denotes theme.
Papers using no imaging or report data carry no domain and appear on no divided line, so the
divided lines do not sum to their theme. Pathology in the clinical theme is exactly zero in
every year from 2015 through 2021.

Papers were retrieved from PubMed on 1 September 2026 and labelled by matching a versioned
term dictionary against each title and abstract (n = 44,533). Labelling is multi-label, so
theme totals exceed the corpus, and a mark records the data an abstract reports, making every
count an upper bound on demonstrated use. Two themes count intent rather than achievement:
digital twins counts papers engaging with the concept, of which 18 of 56 describe a
patient-specific model; virtual staining counts models predicting spatially resolved
molecular signal from H&E slides, and excludes prediction of a biomarker status. 2026 is
partial, covering papers indexed through 1 September, and is shaded.

---

## Notes for the authors

- About 296 words, up from 221 when Panel B carried five lines rather than ten. If it must
  come down, cut the virtual-staining clause and the "color and marker denote domain"
  sentence — the first is recoverable from the theme's name, the second by looking at the
  figure. Do not cut the multi-label sentence, the upper-bound sentence, or the sentence
  about papers with no domain: those three are what keep the counts honest.
- Three caveats rest on this legend alone, having been removed from the artwork: the change
  of scale between the plots, the pathology zero run, and that counts below about 100 papers
  a year move by a few papers between adjacent years without meaning. That third one is not
  in the text above and should be added if the body text does not carry it.
- Any accuracy figure quoted in a methods section must be per-category. Precision ranges from
  about 45% to 97% across categories, and no single number describes this classifier. See
  `validation.md`.
- Every number here is written by `plot.py` into `figures/trends_figure_summary.txt` on each
  build. Refill from that file rather than reading the picture — the scale ratio alone has
  moved three times as the data changed.
