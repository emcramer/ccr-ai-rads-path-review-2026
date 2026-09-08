# Figure specification: Figure 1, radiology row

One landscape panel, lettered A, for the CCR review manuscript's Figure 1. It shows the
radiology AI pipeline as four columns read left to right: what the data are, what is done to
them before modelling, what kinds of model consume them, and which clinical tasks those
models serve. The pathology row, panel B, is drawn by the other authors to the same column
structure so the two rows stack in register.

Style is not settled here. The collaborator's `figures/ink_style_guide.md` is normative and
`figures/AGENTS.md` operational; `build.py` imports `trends.plotting.style` from the clone
and redeclares no colour or type token.

AACR redraws figures from author sketches. Deliver a clear, complete, unfussy figure with a
full legend. Do not over-polish.

## Column 1, Input Data

Six modality thumbnails in a 2 by 3 grid, each a real image with a radiology-blue hairline
border (`#0072B2`), a bold label, and a deep-blue sub-label naming the data's geometry:
radiography (2D projection), mammography (2D, DBT), ultrasound (real-time video), CT (3D,
structural), MRI (3D, T1/T2/DWI), PET (molecular, SUV). Below them the original's two
bordered strips, kept: "Dimensionality" (2D projection, quasi-3D DBT, 3D volumetric, 2D plus
time, 4D) and "Paired non-image data" (report text, DICOM metadata, clinical and staging,
molecular). Strip bodies are wrapped by measured text width at build time.

## Column 2, Preprocessing

Two neutral chips at the top, as in the original, for the steps every pipeline starts with:
DICOM parse, series selection, de-identify; and scanner or site harmonization (ComBat). Then
three blocks of real before-and-after thumbnails, each group captioned under a rule:

| Block | Thumbnails | Caption |
|---|---|---|
| Intensity standardization | one CT slice at full range, lung, and mediastinal window; one MRI raw and z-scored | CT: window / level, full range, lung, mediastinum; MRI: z-score, N4, PET: SUV |
| Geometry | anisotropic MRI native and resampled; axial, coronal, sagittal planes; single slice and 60 mm MIP | resampling 3.0 mm to 1 mm isotropic; orientation and 2.5D, 3 planes, adjacent slices; MIP (optional), slice to 60 mm slab |
| Registration and Segmentation to ROI / VOI | CT checkerboard before and after, PET/CT fused; CT input, organ overlay, binary mask | longitudinal, inter-modality, atlas, rigid / deformable; anatomy crop, then lesion VOI, also a clinical task |

Every thumbnail has a rule-grey hairline border. Colour inside a thumbnail is limited to
radiology blue for anything derived from the image (segmentation overlay, contours) and
molecular orange for PET signal.

## Column 3, Models

Three numbered generations, each with a badge to the left of its title, then a task head:

1. Pre-defined features: the real liver VOI, its HU histogram in bar ink, and its 32-bin GLCM
   in greyscale, captioned; then the original's two chips as white cards, "IBSI: first-order,
   shape, texture (GLCM, GLRLM, GLSZM, NGTDM), wavelet / LoG" and "selection + classical ML
   (LASSO, RF, Cox)", joined by an arrow.
2. Supervised deep learning: CNN, U-Net, ViT icons.
3. Self-supervised and foundation: SSL pretraining, foundation model, vision-language icons.

The task head keeps the original's row: head icon, "Task head", the chip "linear, Cox,
segmentation decoder, text decoder", and the note "one backbone, many tasks; the head decides
which".

## Column 4, Clinical Tasks

Ten rows on the original's 38 px boxes and 43 px pitch, ordered along the care pathway, with
a thin structural arrow running down the left as the time axis and the note "along the care
pathway" under the subtitle. Four rows carry a real thumbnail (screening: mammogram;
detection: lesion contour on CT; segmentation: organ overlay; response: tumour burden on the
PET MIP), six carry an icon in a neutral box.
Labels: Screening / future risk; Triage / workflow; Detection / localization; Segmentation /
quantification; Diagnosis / characterization; Radiogenomics / molecular; Treatment planning;
Response / longitudinal; Prognosis / survival; Report generation, VQA.

## The dashed link

Segmentation appears twice on purpose: as ROI extraction in preprocessing and as an endpoint
in clinical tasks. A dashed line (dashed means a conceptual connection in the style guide)
runs from the preprocessing segmentation block into the frame's bottom padding and up to the
segmentation task row, with the original's italic note beneath its horizontal run. The
legend repeats the explanation.

## Inputs

`build.py` reads only `assets/panels/*.png` (48 rendered panels; 30 are
used, listed with their source and licence in `figures/figure1_radiology_summary.txt`),
`assets/icons/*.svg` (37 icons), and the collaborator's approved icons.
It performs no rendering from source volumes; that is `assets/render_panels.py`.

## Geometry

The original's geometry scaled from its 1400 px canvas, one pixel being 7.5/1400 in: section
title above the frame, frame with 14/17/44 px padding, header row, four dashed column boxes
580 px tall, credit lines under the frame. 7.5 in wide, about 4.35 in tall, aspect 1.72
against the original PDF page's 1.74. Column widths 239, 489, 353, 202 px with 16 px gaps;
the original's 518 and 173 px for the second and fourth column were traded by 29 px so the
two-line task labels fit at 5.8 pt. Type sits on the collaborator's ladder: panel letter
12.6 pt, title 10.3, column subtitles 8.6, block titles 7.0, card labels 6.8, modality labels
6.0, task labels 5.8, icon labels 5.8, captions, chips, and sub-labels 5.6, credits 5.5.
Nothing below 5.5 pt. Text that must fit a fixed width is measured in the vendored face at
build time, and the build fails on any overflow of a label, a strip, or a column box. Panels
are embedded at 600 px per inch of print size; icons at 600 px.
