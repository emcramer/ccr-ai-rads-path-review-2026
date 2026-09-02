# Figure legend

For the manuscript. The full account of the figure, every number in it, and every
limitation those numbers carry is in `figure-description.md`.

---

**Figure [N]. Data modalities and publication volume in AI research on radiology and
pathology, 2015–2026.**
**A,** Modality combinations used by papers in each of four research themes. Rows are the
fifteen data modalities, colored by modality group; a filled dot marks a modality present in
a combination, and joined dots mark modalities used together. Bar height is that combination's share of the theme's
own papers, and the hatched column holds all remaining combinations, so the bars sum to the
theme total. **B,** Papers per year carrying each theme label, in two plots with separate
linear y axes: the lower axis is about 43 times finer than the upper, and the dashed rule
marks the lower plot's full range. The two clinical lines are not additive, and pathology is
exactly zero in every year from 2015 through 2021.

Papers were retrieved from PubMed on 1 September 2026 and labelled by matching a versioned
term dictionary against each title and abstract (n = 44,533). Labelling is multi-label, so
theme totals exceed the corpus, and a mark records the data an abstract reports, making
every count an upper bound on demonstrated use. The digital-twins theme counts engagement
with the concept rather than construction: of its 56 papers, 18 describe a patient-specific
model. 2026 is partial, covering papers indexed through 1 September, and is shaded.

---

## Notes for the authors

- About 221 words. If it must come down further, cut the last sentence of the first
  paragraph and the digital-twins sentence. Do not cut the multi-label sentence or the
  upper-bound sentence: they are what keep the counts honest.
- Two caveats were cut from the figure itself and now rest on this legend alone — the
  change of scale between the plots, and that counts below about 100 papers a year move by
  a few papers between adjacent years without meaning. If the legend is shortened further,
  the second one should move into the body text rather than disappear.
- Any accuracy figure quoted in a methods section must be per-category. Precision ranges
  from about 45% to 96% across categories, and no single number describes this classifier.
  See `validation.md`.
- Every number here is written by `plot.py` into `figures/trends_figure_summary.txt` on each
  build. Refill from that file rather than reading the picture.
