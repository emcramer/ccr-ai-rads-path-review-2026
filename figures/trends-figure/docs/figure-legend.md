# Figure legend

For the manuscript. The full account of the figure, every number in it, and every
limitation those numbers carry is in `figure-description.md`.

---

**Figure [N]. Data modalities and publication volume in AI research on radiology and
pathology, 2015–2026.**
**A,** Modality combinations used by **primary research** papers in each of four themes. Rows
are the fifteen data modalities, colored by modality group; a filled dot marks a modality
present in a combination, and joined dots mark modalities used together. Bar height is that
combination's share of the theme's own papers; combinations of fewer than two papers join the
hatched column, which holds all remaining combinations, so the bars sum to the theme total.
Multimodal integration is defined by combination, so A draws only its papers carrying two or
more modalities: 2,727 of the theme's 3,897 primary-research papers.
**B,** Papers per year in **all article types**, including reviews and perspectives, so the
panel measures attention rather than practice. Two plots with separate linear y axes: the
lower axis is about 26 times finer than the upper, and the dashed rule marks the lower plot's
full range. Foundation models, multimodal integration, and clinical applications are each
divided by clinical domain — radiology, pathology, or cross-specialty for papers using both.
Color and marker denote domain; dash pattern denotes theme. Papers using no imaging or report
data carry no domain and appear on no divided line. Agentic AI is drawn from 2024 only, because
earlier uses of "agent" in this literature denote reinforcement-learning agents.

Papers were retrieved from PubMed on 1 September 2026 and labelled by matching a versioned term
dictionary against each title and abstract. Of 44,625 records, 1,546 were excluded as books, as
falling outside the 2015–2026 window, or as belonging to neither specialty, leaving **43,079
for B**, of which **36,321 are primary research and form A**. The two panels therefore have
different denominators. A modality is counted when the work required it during training,
whether as input or as prediction target. Labelling is multi-label, and a mark records what an
abstract reports, so every count is an upper bound on demonstrated use. The digital-twins
theme counts engagement with the concept, of which 20 of 52 papers are primary research. 2026 is partial,
covering papers indexed through 1 September, and is shaded.

---

## Notes for the authors

- About 354 words, which is long for a legend and reflects a figure that now carries two
  populations, six themes, and three exclusion rules. If it must come down, cut the agentic-AI
  sentence and the color-and-marker sentence first — the first is recoverable from the
  description, the second by looking at the figure. **Do not cut** the sentence naming the two
  denominators, the multi-label sentence, or the upper-bound sentence.
- **The two panels are not comparable, and no number from one may be quoted against the
  other.** Panel A's per-theme `n =` is the primary-research count; Panel B's series are
  engagement counts and are larger. Both populations are tabulated in
  `figures/trends_figure_summary.txt` and in the classification report.
- **The digital-twins theme is 61.5% secondary literature** — 32 of its 52 papers — against 3.1% for
  virtual staining. That is the widest attention-to-practice gap of any theme, and it is worth
  a sentence in the text on its own.
- Panel A draws four themes; virtual staining and agentic AI appear in Panel B only, because a
  fifth block breaches the tested minimum column width.
- **1,170 primary-research papers carry the multimodal label but only one modality, and are
  held out of A** — 30.0% of that theme. They keep the label and still count in B. The gap is
  not a filter artefact: five language families that looked like the cause (multi-sequence MRI,
  multi-scale or multi-view architecture, contrast phases, multi-centre studies, radiomics
  nomograms) were each measured **more common among genuinely multimodal papers than among the
  single-modality ones**, so none can be used to identify the over-call. Counting the modalities
  is the only test that works. Worth a methods sentence if the text quotes the theme's size.
- Any accuracy figure quoted in a methods section must be per-category. Precision ranges from
  about 45% to 97% across categories, and no single number describes this classifier. Several
  categories were last measured against a superseded dictionary version, and `validation.md`
  says which.
- **Refill every number from `figures/trends_figure_summary.txt`, not from the picture**, and
  check the output is current first:
  `python -m trends.classify --check --output data/processed --config-dir config`. The scale
  ratio alone has moved four times as the data changed.
