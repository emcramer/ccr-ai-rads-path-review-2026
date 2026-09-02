# SYNTHETIC DATA — NOT THE REAL CORPUS

Every number in this directory is invented. The tables exist so the plotting
code could be written and tested before the PubMed retrieval and the classifier
were finished. They describe no real literature.

**Do not quote these numbers. Do not put them in the manuscript. Do not draw a
conclusion from them.** When the real tables land in `data/processed/`, rebuild
the figure from those and compare.

## Provenance

- Generator: `src/trends/plotting/synthetic.py`, seed `20260901`.
- Rebuild with:
  `PYTHONPATH=src python -m trends.plotting.synthetic --output data/processed/synthetic`
- Schema: `docs/figure-spec.md`. The three files match it column for column.

## What the invented corpus contains

- 3,801 papers, 2015–2026, the final year partial by construction
  (62% of a full year's volume).
- Papers are multi-label: one paper may carry several themes.
- Theme totals (papers carrying the label):
  - `foundation_models`: 1,490
  - `multimodal_integration`: 1,593
  - `digital_twins`: 97
  - `clinical_fda`: 1,791

## What it was shaped to stress

- A fat tail of rare modality combinations, so the top-N cap in Panel A has
  something real to hide and the legend must report it.
- `digital_twins` deliberately sparse, so a near-empty block must still draw.
- Heavy CT and PET co-occurrence, as in oncologic PET/CT.
- Imaging paired with genomics and with clinical/EHR data, so the multimodal
  theme cannot draw as overwhelmingly unimodal without the figure showing it.
- `other` used additively, beside named modalities as well as alone.
- A partial final year, so Panel B's partial-year treatment is exercised.

## What it does not stress

- Real term ambiguity, classifier error, or missing publication years.
- A theme with zero papers; that case is covered in `tests/test_plot.py` instead.
- The two-order-of-magnitude gap between theme sizes that Panel B's split scale
  exists for. The invented themes sit within a factor of two of each other, so the
  split draws but its scale callouts stay quiet. The measured magnitudes, and the
  real clinical radiology and pathology series, are in
  `tests/fixtures/plot_theme_year_counts_measured.csv` instead.

## Files

| File | Rows | Contents |
|---|---|---|
| `paper_labels.csv` | 3,801 | one row per invented paper |
| `combination_counts.csv` | 652 | one row per theme and modality set; drives Panel A |
| `theme_year_counts.csv` | 60 | one row per theme, domain, and year; drives Panel B |
| `MANIFEST.txt` | — | seed, timestamp, and row counts for this build |
