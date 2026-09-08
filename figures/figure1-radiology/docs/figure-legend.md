# Figure legend

CCR house form: bold title, bold panel letter written `**A,** ...`, definitions and caveats in
the legend rather than in the artwork. The pathology row's legend (**B,**) is written by its
authors and joins this one.

---

**Figure 1. The AI pipeline in oncologic radiology and pathology.**
**A,** Radiology. Input data are the six imaging modalities, drawn as real images with their
geometry named beneath (projection, quasi-3D, volumetric, real-time, tracer uptake), plus
the paired non-image data a model may take alongside them: report text and EHR, and
molecular profiles. Preprocessing begins with DICOM parsing, series selection, and
de-identification, and with scanner or site harmonization such as ComBat; then intensity
standardization (window and level for CT, which has absolute Hounsfield units; z-score or
N4 bias-field correction for MRI, which has none; SUV conversion for PET), geometry
(resampling of anisotropic voxels to 1 mm, orientation into three planes or 2.5D stacks of
adjacent slices, and optional maximum-intensity projection), registration (longitudinal,
inter-modality, or atlas; rigid or deformable), and segmentation to an anatomy crop and a
lesion volume of interest. Models are shown as three generations: pre-defined features,
where handcrafted radiomics (first-order, shape, texture families such as GLCM, GLRLM, GLSZM,
and NGTDM, and wavelet or Laplacian-of-Gaussian filters, per IBSI) feed a classical learner
such as LASSO, random forest, or Cox regression, illustrated by a real liver volume, its
Hounsfield histogram, and its 32-bin grey-level co-occurrence matrix; supervised deep
learning (CNN, U-Net encoder-decoder, vision transformer); and self-supervised pretraining,
foundation models, and vision-language models. A task head (linear, Cox, segmentation
decoder, or text decoder) attaches to one backbone and decides which clinical task it
serves. Clinical tasks are ordered along the care pathway, from screening and triage through
detection, segmentation, diagnosis, radiogenomics, and treatment planning to response
assessment, prognosis, and report generation. Segmentation appears twice by design, as ROI
extraction in preprocessing and as an endpoint in clinical tasks; the dashed link marks
this inversion. Colour marks data modality only: blue for radiology-derived marks, green for
clinical text, orange for molecular data and PET signal.

Panels are rendered from openly licensed imaging data (CC BY 4.0 or CC0): TotalSegmentator
(Zenodo 10047292), AMOS22 (Zenodo 7262581), FDG-PET-CT-Lesions v2 (TCIA,
doi:10.7937/gkr0-xv29), CMMD (TCIA, doi:10.7937/tcia.eqde-4b16), B-mode-and-CEUS-Liver (TCIA,
doi:10.7937/TCIA.2021.v4z7-tc39), and a chest radiograph by Mikael Häggström (Wikimedia
Commons, CC0). The response thumbnail shows one timepoint only.

---

## Notes for the authors

- About 400 words for panel A alone. If it must come down, cut the parenthetical feature
  families and the modality-specific intensity examples first; keep the two-segmentations
  sentence, the colour sentence, and the data credits.
- The data credits are required by TCIA's terms. The full citation list is in
  `assets/README.md` under "Required citations" and belongs in the
  reference list.
- The artwork keeps the original's short notes and its credit lines at the author's
  instruction (see `DECISIONS.md`, structure entry); this legend repeats their content so the
  journal's redraw can drop them from the figure without losing anything.

## Claims this legend makes, and where each comes from

| Claim | Source |
|---|---|
| Which panel is which image, and its licence | `figures/figure1_radiology_summary.txt` |
| Histogram and GLCM are computed from the real liver VOI | `assets/README.md`, panels 03_features |
| The response thumbnail is a single timepoint | same file, "Still missing" |
