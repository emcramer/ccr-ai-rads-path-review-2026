# Figure assets - radiology pipeline schematic

Material for the four-column figure: **data -> preprocessing -> models -> clinical tasks**.

```
icons/                     37 hand-authored SVG icons, 24x24, 0.5 px stroke
icon_sheet.html            browse all icons
placement_map.html         WHICH image goes in WHICH slot, and why — start here
panels/                    48 rendered PNGs from real, openly licensed imaging data
panels/contact_sheet.html  browse all panels
render_panels.py           regenerates every panel from the source volumes
fetch_from_remote_zip.py   pulls single files out of a multi-GB remote ZIP by byte range
```

**Icons.** I wrote these by hand - every path coordinate is authored, not taken from a
library, so anything here can be changed on request. Drag the `.svg` files onto the Figma
canvas and they arrive as editable vector networks, not images. Every path uses
`stroke="currentColor"` with no fill (bar a few 0.14 washes), so recoloring is one stroke
property. Stroke is 0.5 px at 24x24 - hairline weight. When you enlarge them in Figma, turn OFF
"scale with object" or the strokes thicken back up and you lose the thinness. All 37 share
one geometric language so a row reads as a set.

**Panels.** Real images, not icons. Every one is rendered from openly licensed patient data
and displayed in radiological convention (patient right on the viewer's left). Licensing and
required citations are below - all sources are CC BY 4.0 or CC0, none are NC.

---

## Content review of the four columns

Flagging where I think the current plan is incomplete or slightly off. Take or leave.

### Column 1 - Data

Your list: X-ray, CT/PET, MRI, ultrasound.

- **Split CT from PET.** Grouping them collapses the one distinction the column exists to
  make. CT is structural, PET is functional/molecular - a tracer signal, not an anatomy
  signal. For an oncology review PET is where response criteria live (PERCIST, Deauville).
  Draw them as separate cells and note PET is virtually always hybrid PET/CT or PET/MR.
- **Mammography / DBT is missing** and it is load-bearing for you. MASAI, the DBT triage
  trial, and the nationwide screening implementation study are all in section R.2. If the
  data column has no mammography cell, R.2 has no visual anchor. Icon provided.
- **Ultrasound is not a still image.** It is operator-acquired real-time video with no
  standardized geometry. That is exactly why its AI story differs from CT/MRI, and one word
  in the caption ("real-time, operator-dependent") earns its place.
- **Consider a dimensionality strip** under the row rather than more cells:
  2D projection (X-ray, mammography) | quasi-3D (DBT) | 3D volumetric (CT, MRI, PET) |
  2D + time (ultrasound, cine MRI) | 4D (DCE-MRI, 4D CT). This is what actually drives the
  preprocessing differences in column 2, so it makes the two columns interlock.
- **Decide whether non-pixel data enters here.** Section MR is image + text + structured
  clinical + molecular. If this figure covers the whole review, column 1 needs a second
  tier (report text, DICOM metadata, labs/staging, genomics). If it is imaging-only, say so
  in the caption so MR does not look unrepresented.

### Column 2 - Preprocessing

Your list: 2D = windowing, pixel value std, registration. 3D = the above + orientation,
spacing/slice thickness, MIP. Then segmentation for ROI.

- **"Windowing" is CT-only and should not be the generic label.** CT has absolute
  Hounsfield units, so window/level is meaningful. MRI has no absolute intensity scale -
  the analogue is intensity normalization (z-score, histogram matching, Nyul-Udupa,
  WhiteStripe) plus N4 bias-field correction. PET's analogue is SUV conversion by injected
  dose and body weight. Ultrasound has neither. Label the box **intensity standardization**
  and list the modality-specific instances underneath. Windowing then becomes one instance
  rather than the rule.
- **Add a DICOM / de-identification step at the front.** Every real pipeline starts with
  series selection, tag parsing, and PHI removal, and reviewers ask about it. Icon provided.
- **Add bias-field correction** explicitly (MRI, N4ITK). It is not covered by "pixel value
  standardization" and is the single most common MRI preprocessing omission.
- **Add scanner/site harmonization.** ComBat on features, or image-domain harmonization.
  This is the reproducibility crux of radiomics and it sits in preprocessing. Related:
  IBSI-compliant discretization and bin width, which straddle preprocessing and feature
  extraction - worth a footnote about which side you put it on.
- **2.5D is missing and is the more common bridge than MIP.** Three orthogonal planes, or
  stacking adjacent slices as channels, is how most work gets 3D context into a 2D
  backbone. MIP is real but narrower (lung nodule detection, breast MRI). Keep MIP as
  optional, add 2.5D beside it.
- **Split registration into its three uses,** because they serve different sections:
  intra-patient longitudinal (same modality across time - this is what R.5 depends on),
  inter-modality (PET/CT, MR/CT), inter-patient/atlas. Rigid vs deformable is a second axis.
- **Anatomy cropping is distinct from ROI segmentation** - body masking, lung masking,
  skull stripping. Worth its own small step, or at least a sub-label.
- **Keep augmentation out.** It is training-time, not preprocessing. Conflating them is a
  common figure error and a reviewer will notice.
- **Draw segmentation twice, deliberately.** It appears in preprocessing (ROI/VOI for
  radiomics) and again in clinical tasks (as an endpoint). That is not a duplication bug,
  it is precisely the inversion your R.1 argues. Connect them with a dashed line and say so
  in the caption - it turns an apparent redundancy into the section's thesis.

### Column 3 - Models

Your list: radiomics (deterministic) -> texture/shape features; then deep features, ViT,
CNN, FM.

- **"Deterministic" is not the right contrast.** Feature *extraction* is deterministic, but
  the model on top (LASSO, random forest, SVM, Cox) is learned. Your own archive file
  already uses the better wording: **pre-defined features** vs **deep features + SSL**. Use
  that. The real axis is handcrafted vs learned representation.
- **Name IBSI and the full feature families.** Texture and shape is a subset. The standard
  set is: first-order/intensity histogram, shape/morphology, texture (GLCM, GLRLM, GLSZM,
  GLDM, NGTDM), and filter-based (wavelet, LoG). Three icons provided for the first three.
- **Structure the column as three generations, matching your own R.0 framing:**
  (1) handcrafted features + classical ML, (2) supervised deep learning (CNN -> ViT),
  (3) self-supervised / foundation models. Right now the list mixes architecture names with
  training paradigms; separating them into two sub-rows (architecture / supervision) says
  more in the same space.
- **U-Net deserves its own cell.** "CNN" does not cover it. Encoder-decoder vs encoder-only
  is what determines which clinical tasks in column 4 are even reachable, so it is a
  load-bearing distinction for the arrows between columns 3 and 4.
- **Add vision-language models** (dual-encoder CLIP-style, and generative decoders). Without
  them, column 4 cannot reach report generation and VQA, which is half of section MR.
- **Add a small "task head" box between models and tasks.** Backbone -> head -> task. This
  is where a Cox proportional-hazards head, a segmentation decoder, or a text decoder
  attaches, and it is the honest explanation of how one backbone serves many tasks. It also
  gives the column 3 -> 4 arrows somewhere to converge instead of an N-to-M tangle.

### Column 4 - Clinical tasks

Your list: segmentation, detection, classification, prognostic, diagnostic, risk.

- **"Diagnostic" and "classification" overlap.** Cleaner to order by the clinical question:
  detection (is there a lesion?) -> characterization (what is it - benign/malignant,
  subtype, molecular) -> prognosis (what happens?) -> prediction (what happens *under this
  treatment*?).
- **Use prognostic vs predictive precisely.** Predictive means treatment-effect-modifying.
  CCR readers use these as terms of art and will read imprecision as sloppiness. Your
  archive already flags "(prognostic)" on the survival bullet, so the instinct is there.
- **Split "risk" in two.** Risk of *developing* cancer (Sybil, opportunistic CT screening -
  a screening task) is a different clinical use from risk of an outcome *given* cancer
  (prognosis). One box for both hides the distinction R.2 and R.4 rest on.
- **Missing from the list, all present in your own sections:**
  - treatment response / longitudinal monitoring (R.5) - pCR, progression vs pseudoprogression
  - radiogenomics / molecular phenotype (R.3) - currently folded into "classification"
  - report generation, VQA, conversational (MR)
  - triage and workflow (MASAI workload reduction - this is the strongest prospective
    evidence you cite, and it is not a diagnostic task at all)
  - treatment planning / RT auto-contouring (the GAP flagged in 02 section R.1)
  All five have icons.
- **Consider ordering column 4 along the care pathway** rather than by technical task type:
  screening -> detection -> diagnosis -> planning -> response -> surveillance/prognosis.
  That makes the last column double as the time axis, which is the thing missing from every
  published figure I surveyed (see `04_pipeline_figure_references.md`). It would be the
  figure's actual contribution rather than a redraw.

---

## Source data - all CC BY 4.0 or CC0

Nothing here is NonCommercial, nothing is behind a data use agreement, and nothing needs a
BioRender licence. Every panel is reproducible by re-running `render_panels.py`.

| Source | Used for | Licence |
|---|---|---|
| **TotalSegmentator dataset** (Zenodo 10047292) | CT + 7 organ masks; segmentation and radiomic-feature panels | CC BY 4.0 |
| **AMOS22** (Zenodo 7262581) | abdominal MRI x2 + organ labels; MRI modality, intensity and resampling panels | CC BY 4.0 |
| **FDG-PET-CT-Lesions / autoPET** (TCIA) | whole-body PET + CT + tumour segmentation; PET, fusion, registration, lesion panels | CC BY 4.0 |
| **CMMD** (TCIA) | mammography, left CC and MLO | CC BY 4.0 |
| **B-mode-and-CEUS-Liver** (TCIA) | liver B-mode ultrasound | CC BY 4.0 |
| **Wikimedia Commons** (Mikael Häggström) | normal PA chest radiograph | CC0 |

### Required citations

- Wasserthal J, et al. *Dataset with segmentations of 117 important anatomical structures in
  1228 CT images.* Zenodo. doi:10.5281/zenodo.10047292 — and the method paper,
  TotalSegmentator, *Radiology: Artificial Intelligence* 2023, which is already in R.1.
- Ji Y, et al. *AMOS: a large-scale abdominal multi-organ benchmark for versatile medical
  image segmentation.* Zenodo. doi:10.5281/zenodo.7262581
- Gatidis S, Kuestner T. *A whole-body FDG-PET/CT dataset with manually annotated tumor
  lesions (FDG-PET-CT-Lesions), Version 2.* The Cancer Imaging Archive, 2022.
  doi:10.7937/gkr0-xv29
- Cui C, Li L, Cai H, et al. *The Chinese Mammography Database (CMMD).* The Cancer Imaging
  Archive, 2021. doi:10.7937/tcia.eqde-4b16
- Eisenbrey J, Lyshchik A, Wessner C. *Ultrasound data of a variety of liver masses.* The
  Cancer Imaging Archive, 2021. doi:10.7937/TCIA.2021.v4z7-tc39
- Chest radiograph: Mikael Häggström, Wikimedia Commons, CC0 (no attribution required, but
  worth giving).

TCIA additionally asks that the collection name and DOI appear in any publication using its
data. Version 2 of autoPET is the defaced release; version 1 is controlled-access, so cite
version 2 specifically.

---

## Panel inventory

### `panels/01_modalities/` — the data column

| File | What it is |
|---|---|
| `xray_chest_pa.png` | normal PA chest radiograph (2D projection) |
| `mammo_L_cranio-caudal.png`, `mammo_L_medio-lateral-oblique.png` | the two standard screening views |
| `ultrasound_liver.png` | liver B-mode, cropped to the DICOM-declared image region so no vendor UI is visible |
| `ct_axial_softtissue.png`, `ct_coronal.png` | whole-body CT |
| `mri_axial.png`, `mri_coronal.png` | abdominal MRI |
| `pet_mip_coronal.png` | whole-body FDG PET coronal MIP, SUVbw 0–5 inverted greyscale — the canonical PET picture |

### `panels/02_preprocessing/` — the preprocessing column

- **`a_window_*`** — one mid-thoracic CT slice at four settings: full range, lung
  (−600/1500), mediastinum (50/350), bone (400/1800). The slice was chosen automatically as
  the one with the most aerated lung inside the body mask, so all four windows genuinely
  differ. This is the pair that makes "intensity standardization" concrete.
- **`b_intensity_*`** — two different MRI scans shown on one global scale (they look
  nothing alike) and after within-body z-scoring (comparable). Caveat: these are two
  different sequences from two patients, so the panel illustrates the *problem* rather than
  a controlled before/after.
- **`c_spacing_*`** — a genuinely anisotropic MRI (1.39 × 1.39 × 3.0 mm) coronal reformat,
  nearest-neighbour so the 3 mm stair-stepping is visible, next to the same volume resampled
  to 1 mm isotropic. Not simulated.
- **`d_plane_*`** — axial, coronal, sagittal from one volume, for the 2.5D box.
- **`e_mip_*`** — single slice vs a 60 mm slab MIP in a lung window.
- **`f_registration_*`** — PET and CT are hardware co-registered, so `AFTER_fused` is real.
  `BEFORE_simulated_offset` applies a known rigid shift, and is labelled as simulated in the
  filename. The CT-vs-CT checkerboards (`*_ctct`) read far more clearly than the PET/CT ones
  because a checkerboard needs two similar-looking images to show broken edges — use those
  for the figure and keep the PET/CT pair as backup.
- **`g_seg_*`** — TotalSegmentator masks for liver, spleen, heart, aorta, two lung lobes and
  a vertebra: input CT, colour overlay, binary mask.
- **`h_lesion_*`** — the autoPET tumour annotation: on PET, on CT, as a detection box on the
  fused slice, and projected onto the whole-body MIP. The case is lesion-positive
  (PETCT_b899150306, 10,764 annotated tumour voxels); most autoPET patients are negative
  controls, so do not swap the patient ID casually.

### `panels/03_features/` — the models column

`roi_liver_crop.png` and `..._masked.png` are the real liver VOI. `glcm_matrix_32bin.png` is
an actual 32-bin grey-level co-occurrence matrix computed from that VOI, not a mock-up, and
`histogram_liver_roi.png` is its real HU distribution (mean 74, SD 27). Using genuinely
computed feature objects rather than decorative ones is worth it here, because the whole
point of the models column is that these are derived quantities.

---

## Regenerating

```bash
python render_panels.py
```

Needs `numpy scipy matplotlib pillow nibabel pydicom` and the source volumes under `data/`.
`fetch_from_remote_zip.py` pulls individual members out of the 23 GB TotalSegmentator and
24 GB AMOS archives over HTTP range requests, so neither has to be downloaded in full:

```bash
python fetch_from_remote_zip.py <zip-url> '<regex>' ./data/out 20
```

## Still missing

- **DBT** — no openly licensed tomosynthesis volume found; the Breast-Cancer-Screening-DBT
  collection on TCIA is the place to look if you want the quasi-3D cell filled.
- **A longitudinal pair** — nothing here is the same patient at two timepoints, so R.5 has
  no real before/after. TCIA collections with follow-up imaging (e.g. RIDER, QIN) would fix
  this and it is the one genuinely missing panel.
- **Bias-field correction** — needs an MRI with visible shading; neither AMOS volume shows it
  strongly enough to be worth a panel.
