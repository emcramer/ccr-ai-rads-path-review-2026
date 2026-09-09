# Category definitions

What each label in the figure means, what it deliberately excludes, how accurate it was
measured to be, and how it characteristically fails.

Written for a co-author deciding whether to trust a number. The operational definition of
every category is its pattern list in `config/themes.yaml` or `config/modalities.yaml`
together with that category's `notes` block; this file states the same thing in prose.
Where the two disagree, **the patterns are what ran** — this file describes them, it does
not govern them.

Dictionary state described here: `themes.yaml` **v12**, `modalities.yaml` **v13**.
Hashes for both are in `config/VERSIONS.json`.

---

## Two things that apply to every category

**1. Classification is lexical.** A label records what a title and abstract *say*, not what
a paper demonstrably *did*. Hand-coding of every validation disagreement found that **43% of
all false positives were mentions rather than uses** — a pathology paper saying "confirmed by
CT" gets a `ct` label. The error is **one-directional**: 36 such false positives, zero false
negatives. **Every count in the figure is therefore an upper bound on genuine use**, and the
direction of the bias is known. It concentrates where a term names an idea rather than an
instrument: 10 of 15 false positives for `digital_twins`, against 2 of 5 for `ct`.

**2. Nothing was classified by reading full texts.** The corpus is titles and abstracts as
returned by PubMed. A method described only in a paper's Methods section is invisible.

### How to read the precision figures below

Each entry names the version measured, the denominator, and who measured it. Two sources
appear:

- **Blind validation** — an independent agent labelled a stratified sample without seeing
  the patterns. The stronger evidence.
- **Author read** — I read the matched records myself, usually the whole population for
  small categories. Weaker, because I knew what the patterns were.

Where a category was never separately measured, it says so. **No entry implies a
measurement that does not exist.**

---

# Themes

A paper may carry several themes, or none. Most of the corpus carries none; the themes are
specific currents within it, not a partition of it.

## `foundation_models` — Foundation Models

**Definition.** The paper uses, evaluates, or reviews a large pretrained general-purpose
model — a vision or language foundation model, a large language model, or a named
pathology/radiology foundation model such as UNI, CONCH, Virchow, Prov-GigaPath, CT-FM or
Merlin.

**Deliberately excluded.** Self-supervised learning, zero-shot and few-shot evaluation.
These are training and evaluation techniques, not foundation models: a small CNN pretrained
self-supervised is not one. Dropping `self-supervised` alone took precision from 59% to 89%.
Bare "foundation" is never matched — it fires on funding bodies.

**Precision.** **89%** at v3, blind validation round two, up from **59% (27 of 46)** at v2.
The denominator of the 89% was not reported to me.

**Failure mode.** Reviews that discuss foundation models without using one.

## `multimodal_integration` — Multimodal Integration

**Definition.** The paper's model **requires two or more distinct data types during
training**. That covers two cases: combining data types in one model (imaging with genomics,
pathology with clinical variables, image with text), and **predicting one modality from
another** — IHC from H&E, spatial transcriptomics from histology, mutation status from CT,
synthetic CT from MRI.

**The second case was added by author ruling on 2026-09-08** (quoted above). Before it, a
paper predicting IHC from H&E qualified only if it happened to use the word "multimodal".

**Deliberately excluded.**
- **A clinical outcome is not a modality.** Predicting survival, recurrence or treatment
  response from CT needs imaging plus an outcome label. The patterns defend against this by
  *whitelisting* modality targets rather than blacklisting outcomes, so an outcome cannot
  fill the target slot. Measured: 8.2% of newly added papers contain outcome-prediction
  language against an 11.2% corpus base rate — the additions are *less* outcome-heavy than
  the corpus.
- **A segmentation or registration target is not a modality.** Predicting a mask from an
  image is one modality. Measured: 0.6% of additions against a 1.3% base rate.
- **Intra-modality fusion.** Several MRI sequences, or several CT phases, is not multimodal
  however the authors describe it. The cross-modality patterns are built on families that
  mirror the figure's own rows, so "crossing a family" means crossing a Panel A row — which
  is why H&E-to-IHC counts and T1-plus-T2 does not.
- "Multimodal therapy" in its oncology sense, and model-internal `feature fusion`.

**The invariant.** A paper cannot carry this theme with fewer than two modality rows; the
classifier enforces that, and it is the only mechanism that separates a genuine multimodal
paper from one that merely says "multimodal". Pattern-level tightening was attempted against
the five language families the author identified and **measured to be counter-productive** —
every family is commoner in the genuinely multimodal population than in the broken one, from
1.1× for architecture fusion to 12.5× for radiomics-plus-nomogram wording. Those families are
ubiquitous features of radiology papers, not markers of the defect. After the v13 recall fix,
**1,253 of 3,886 primary-research papers (32%) still fall below two rows and lose the theme**.

**Precision.** **55% (95% CI 34–74)** at v5, blind validation round three — the last
independent measurement. Since then v6 rewrote the intra-modality exclusion and v11 added
cross-modality prediction. A read of 20 of the 459 newly added papers gave roughly 17–18
genuine. **The row has not been re-validated blind since v5**, so treat 55% as a floor that
two rounds of repair are expected to have raised, not as the current figure.

**Correctness check.** Nearly all virtual-staining papers should be multimodal under the
ruling, since predicting spatial signal from H&E requires both. Measured **12 of 65 before,
61 of 65 after**. An earlier draft of the patterns reached only 37 of 65; that shortfall is
what exposed a family-design bug in which H&E and IHC were treated as one family.

**Failure mode.** Multi-sequence MRI work described as "multi-modal", and papers where a
spurious "from" links a modality to an unrelated noun.

## `digital_twins` — Digital Twins

**Definition.** The paper engages with the digital-twin idea in any capacity — proposing a
framework, building a component, reviewing the concept, or naming it as future work.

**This row's scope was set by the author, not derived.** The measured alternative was a
strict standard counting only papers that build something meeting the manuscript's criteria;
a hand screen of all 64 candidates found only 18 of those, against 21 reviews or
future-work mentions and 5 self-described frameworks. The author ruled that the row tracks
**trends of interest, not successful construction**. So this line measures **discussion**,
and 18 of its 56 papers build anything.

**Deliberately excluded.** Papers that supply something a twin would need but never invoke
the idea — patient-specific growth simulations, virtual patient phantoms, in-silico imaging
trials. The operational line the author approved: *the paper must invoke the digital-twin
idea in the twin vocabulary*. Without it, "a building block for one" has no stopping point.

**Precision.** **56 of 56** read across three validation rounds (95% CI 94–100) at v5. The
validator noted this is **near-tautological**: the row is one pattern matching a vocabulary,
and the standard is genuine use of that vocabulary. The honest claim is that the *lexical
collisions are gone*, not that the row is accurate in a deeper sense.

**Failure mode.** Mention-versus-use is at its worst here — 10 of 15 false positives in an
earlier round. That is intrinsic: the row is a measure of discussion.

## `clinical_fda` — Clinical Applications / FDA Approval

**Definition.** The paper concerns **regulatory clearance** of an AI device — FDA clearance
or approval, CE marking, 510(k), UKCA, MHRA/PMDA/NMPA authorisation, or software as a
medical device.

**Deliberately excluded.** The author ruled this row **regulatory only**. A measured
alternative that also counted clinical-deployment language (clinical implementation,
prospective validation, routine practice) was about **twenty times larger** — roughly 3,290
papers against 130 — and was rejected. That vocabulary is preserved as a commented block in
`themes.yaml` in case the decision is revisited. Bare "FDA" is never matched: it appears in
discussion sections of papers that cleared nothing. Drug and radiotracer approvals are
excluded explicitly.

**Precision.** **95.7% (89 of 93)** on a whole-population author read at the v2 narrowing;
blind validation later reported **92% precision, 96% recall**. v4 removed "following" from
the possession verbs; **not re-measured after v4**.

**Failure mode.** Drug or biomarker approvals discussed inside a genuine AI imaging paper.

## `virtual_staining` — Virtual Staining

**Definition.** The paper predicts a **spatially resolved molecular or protein-level
readout** from a routine H&E slide — virtual IHC, virtual multiplex immunofluorescence, or
spatial transcriptomics predicted from whole-slide images.

**This row's scope was set by the author, not derived.** Two independent reads of the same
76 papers disagreed by seven, and the gap was one class: papers predicting a **biomarker
status or score** — HER2, PD-L1, Ki-67, BAP1 — from H&E. The author ruled that **a HER2
status is not spatial proteomics**; the model must produce a spatial map. That ruling removed
11 papers and took precision from 82.9% to 96.9%.

**Deliberately excluded.** Biomarker status and score prediction, per the ruling above. The
**reverse direction** — virtual H&E generated *from* autofluorescence, photoacoustic or
label-free imaging — which is the largest adjacent literature at 77 candidates, 72 of them
correctly excluded. Stain normalisation and colour transfer. Virtual *special* stains
(trichrome, PAS, Jones silver), which are histochemical rather than molecular; the corpus
holds exactly one such paper, so that exclusion costs one paper.

**Precision.** **96.9% (63 of 65)**, 95% CI 89.5–99.2, at v8. All 65 read. The row is two
literatures that share no papers: virtual-staining vocabulary, **31 of 33**; spatial-omic
prediction from histology, **32 of 32**.

**Failure mode.** None characteristic at the shipped scope. Five of the 65 predict molecular
signal from a label-free rather than an H&E source — the spirit of the definition but not its
letter.

## `agentic_ai` — Agentic AI

**Definition.** The paper uses an AI **agent** — a system that plans, calls tools, or acts
across multiple steps — for pathology or radiology research or practice.

**Deliberately excluded.** A chat interface, and a single-shot LLM query. **Chain-of-thought
prompting is excluded** and this is the load-bearing exclusion: it is the largest reasoning
signal in the corpus at 31 records, but roughly 24 of the 28 it would add are
prompting-strategy benchmarks ("zero-shot, few-shot and chain-of-thought prompting were
tested"). CoT is a prompting technique, not agency. Bare `agent` is never matched — in an
oncology corpus it means a drug: of 629 corpus records containing it, 384 carry a drug or
contrast cue and only 29 a software cue. `agent-based model` is excluded as a simulation
technique. "multi-agent chemotherapy" is guarded out.

**Precision.** **Author read, not blind validation.** 35 papers: **25 of 35 (71%)** strictly
agentic, or **30 of 35 (86%)** counting classical reinforcement-learning agents as agents.
Five MARL papers are counted and flagged rather than silently dropped, because excluding
them would narrow the author's definition on my judgment.

**Failure mode — an era problem, and it matters for the figure.** Precision is strongly
time-dependent: **24 of 27 (89%) in 2025–26, but 1 of 8 (12%) before 2025.** The word "agent"
only acquired its agentic-AI sense around 2025; earlier matches are reinforcement-learning
agents or models whose authors simply called them agents. No vocabulary separates those —
they use the words correctly for their own era. **The pre-2025 tail should not be read as a
trend.**

---

# Modalities

A paper may carry several modality labels. `other` is additive: it can appear alongside named
rows, and is also assigned as a fallback to any paper matching no named row.

**Panel A means "what data the work required during training."** This is an author
ruling of 2026-09-08, and it replaced an earlier and narrower reading:

> "Multimodal should include any models that predict one modality from another. Basically,
> if it requires two modalities during training, then it is a multimodal model/application."

**This is a decision, not a discovery.** The earlier rule counted only data *consumed as
input*, which meant `genomics` excluded papers predicting a molecular label from an image
while `ihc` and the two spatial rows counted them. When that inconsistency was measured and
reported, the author resolved it by **reversing the input-only rule rather than extending
it**. A model predicting IHC from H&E needs both during training, so both rows apply and the
paper is also multimodal.

Two consequences a reader should hold in mind. `genomics` grew by 424 papers, and its overlap
with `he_histology` went from 796 to 964 — **that rise is correct under the new rule**, not a
defect. And `multimodal_integration` gained 459 papers, because cross-modality prediction now
qualifies.

**Modalities are limited to radiology and pathology.** A second ruling of the same date:
*"Endoscopy, dermoscopy, colposcopy, OCT, etc. are not modalities of either specialty."* The
line is imaging read by a radiologist or pathologist, plus the data types a pathology
department generates. The excluded vocabulary was moved, not deleted — see `non_specialty`.

## Pathology rows

### `he_histology` — H&E / Histology
**Definition.** The paper uses stained tissue-section images: H&E, whole-slide images,
digital or computational pathology, pathomics, tissue microarrays, frozen sections.
**Excluded.** Bare `histolog*` and bare `histopatholog*`, which fire on "histologically
confirmed" in radiology papers with no tissue image; a 16-record read of what bare
`histolog*` uniquely admitted was about 40% precise.
**Precision.** ~**90% (12–13 of 14)**, author read at v3. Not separately reported by blind
validation.
**Failure mode.** Reference-standard mentions of histology in imaging papers.

### `ihc` — IHC
**Definition.** The paper's model required immunohistochemistry or immunostaining during
training — whether IHC was an input, or the target it was trained to predict.
**Excluded.** "Intrahepatic cholangiocarcinoma (IHC)", the one measured acronym collision.
**Precision.** A 12-record author read found 11 of 12 genuinely involve IHC data. Of those,
about 4 use IHC as a model input and the rest as the prediction target or reference standard
— **which the 2026-09-08 ruling makes correct rather than an error.**
**History worth knowing.** Until v11 this row's behaviour was inconsistent with `genomics`:
all 11 papers that predicted a biomarker status from H&E carried `ihc` but not `genomics`,
because `genomics` suppressed predicted labels and `ihc` did not. Reporting that
inconsistency is what prompted the ruling, and the ruling resolved it in this row's favour.
**Failure mode.** Mention of IHC as a reference standard in a paper that neither consumes nor
predicts it — the general lexical bias, not a row-specific one.

**Recall added at v13.** A named prediction target now assigns this row: a paper predicting
Ki-67, HER2, PD-L1, ER/PR or p16 from imaging required IHC during training, so `ihc` applies.
The cohort-descriptor sense is guarded per-occurrence — "HER2-positive breast cancer" is an
eligibility criterion, not IHC use.

### `spatial_proteomics` — Spatial Proteomics
**Definition.** Multiplexed protein imaging of tissue — imaging mass cytometry, multiplex
immunofluorescence, MIBI, CODEX, CyCIF, GeoMx, PhenoCycler.
**Excluded.** Imaging mass spectrometry, moved to `other` as lipid/MALDI imaging rather than
spatial proteomics. The bare acronym `MIBI` was removed outright after it collided with
99mTc-MIBI sestamibi scintigraphy in 5 of 12 corpus records; all five genuine
multiplexed-ion-beam papers survive through spelled-out names, so removal cost nothing.
**Precision.** **93% (13 of 14)** at v4, blind validation round three — measurable for the
first time after the MIBI removal.
**Failure mode.** A different sense of "proteomics" entirely.

### `spatial_transcriptomics` — Spatial Transcriptomics
**Definition.** Spatially resolved transcriptomic assays — Visium, Xenium, CosMx, MERFISH,
seqFISH, Slide-seq, Stereo-seq, in-situ sequencing.
**Excluded.** Umbrella terms — "spatial omics", "spatial biology", "spatial multi-omics" —
are in **neither** this row nor `spatial_proteomics`, because they do not say which. Those
papers fall to `other` unless they name an assay. Deliberate under-assignment rather than a
guess.
**Precision.** ~**90% (18 of 20)**, author read at v2.
**Failure mode.** Six of six papers predicting spatial transcriptomics *from* H&E carry this
row although the assay is their target — **correct under the 2026-09-08 training-set ruling**,
since the assay is required to train. Before v11 this was an inconsistency with `genomics`.

### `pathology_report` — Pathology Report
**Definition.** A **text** modality: the paper processes the pathology report itself —
natural-language processing, information extraction, report classification or generation.
**Excluded.** Papers that merely cite a pathology report as the reference standard. An
unconditional "pathology report" pattern measured 50% precise; the shipped pattern requires
report vocabulary **and** a text-processing signal in the same record.
**Precision.** **96% (24 of 25)** on a full-population author read of 222 matches at v3.
**Failure mode.** A radiology-report paper that also mentions pathology reports.

## Radiology rows

### `mri` — MRI
**Definition.** Magnetic resonance imaging, including named sequences (T1/T2-weighted, DWI,
ADC, DCE, FLAIR, MRCP) and multiparametric MRI.
**Excluded.** Bare "MR", which collides with the honorific and with gene abbreviations.
**Precision.** Blind validation reported **85–96% precision and 94–98% recall** for the group
CT, MRI, PET, ultrasound and mammography together; individual figures were not broken out.

### `ct` — CT
**Definition.** Computed tomography, including CECT, NCCT, LDCT, HRCT, cone-beam CT and
Hounsfield units.
**Excluded.** Nothing case-insensitive. Bare `CT` is matched **case-sensitively**, which is
what makes it usable: of 722 matches in 3,000 records, 386 never write "computed tomography",
and 22 of 22 of those read were CT, with no collision with qPCR *Ct*, chemotherapy or
clinical trial. `\bCT\b` also fires inside PET/CT and SPECT/CT, which is intended.
**Precision.** In the 85–96% group above; author read of bare-`CT`-only matches was 22 of 22.

### `pet` — PET
**Definition.** Positron emission tomography, including FDG, SUV metrics and radiotracer
uptake.
**Excluded.** Lower-case "pet". Case-sensitive `\bPET\b` matched 213 records against 1 for
`\bpet\b`, and that one was a lower-cased title for PET imaging, not an animal. `\bPET\b`
does not fire inside SPECT.
**Precision.** In the 85–96% group; author read of PET-only matches was 16 of 16.
**Note.** `pet` and `ct` co-occur in **77% of PET papers**, because oncologic PET is acquired
as PET/CT. That is real, not double-counting.

### `ultrasound` — Ultrasound
**Definition.** Ultrasonography, sonography, echography, elastography, Doppler, and the
endoscopic and automated-breast variants.
**Excluded.** Bare "US", which is unsalvageable: of 68 matches, the ones with no other
ultrasound word were 2 of 6 precise — "US populations", "US National Science Foundation".
Papers using the abbreviation introduce it as "ultrasound (US)" first, so the loss is near
zero.
**Precision.** In the 85–96% group; author read 12 of 12.

### `mammography` — Mammography
**Definition.** Mammography, mammograms, digital breast tomosynthesis, FFDM, CESM.
**Excluded.** Bare "DM", which is diabetes mellitus far more often than digital mammography;
bare "breast imaging", which covers breast MRI and ultrasound.
**Precision.** In the 85–96% group; author read 16 of 16. `DBT` was checked for the
dialectical-behaviour-therapy collision: 7 of 7 were breast tomosynthesis.

### `xray` — Radiography (X-ray)
**Definition.** Plain radiography — chest X-ray, CXR, radiographs, plain film, fluoroscopy,
and named projection studies.
**Excluded.** **Bare "x-ray", which is unsalvageable** at about 4 of 13 precise: it leaks
into radiotherapy dose ("exposed to X-ray radiation, 3 × 8 Gy"), X-ray fluorescence, DXA, the
X-ray physics of CT, and mammography. Also excluded is the **adjective "radiographic"** — in
oncology "radiographic response" and "radiographic progression" are RECIST vocabulary for CT
and MRI, so admitting the adjective would pull CT papers into this row. Only the nouns
"radiography" and "radiographs" are matched.
**Precision.** ~**94% (17 of 18)**, author read at v4.

### `radiology_report` — Radiology Report
**Definition.** A **text** modality, as `pathology_report`: the paper processes the radiology
report — NLP, extraction, classification, generation, report simplification.
**Excluded.** Bare "structured report", generic across medicine. "BI-RADS
assessment/category" was drafted and removed: both matches were papers predicting a BI-RADS
category from images, which is an imaging task.
**Precision.** ~**95% (19 of 20)**, author read at v3.

## Non-imaging data rows

`genomics` and `clinical_data` are **not** imaging modalities and do **not** contribute to
the radiology/pathology `domain` rule. A paper using MRI and genomics is `radiology`, not
`both`. They exist as rows because the pairing of imaging with molecular or clinical data is
the integration the review argues about, and it is invisible if those data types have no row.

### `genomics` — Genomics / Transcriptomics
**Definition.** The paper's model **required** bulk or single-cell molecular data during
training — RNA-seq, whole exome or genome sequencing, methylation, copy number, mutation
profiles, multi-omics, TCGA molecular data. Whether the data was an input or the target the
model was trained to predict does not matter.
**Changed at v11 (2026-09-08).** Two prediction-side exclusions were **removed** on the
author's ruling. They had suppressed the label on **424 papers, 168 of them carrying H&E**,
on the grounds that a predicted molecular label is not consumed data. Under the training-set
rule those papers do use genomic data, so the label belongs. `genomics` goes 3,551 → 3,975,
and `genomics` ∩ `he_histology` goes **796 → 964**.
**Still excluded, and this is a different kind of fix.** The **TCGA qualifier** stands: bare
`TCGA` is not evidence of molecular data, because TCGA distributes whole-slide images
alongside it, and 66% of papers whose only genomics signal was `TCGA` also carried
`he_histology`. The two fixes shipped together in v6 and are easily remembered as one, but
they answer different questions — the prediction-side exclusions answered *"does a predicted
label count as use?"* (a definitional question, now answered yes), while the TCGA qualifier
answers *"does naming an archive establish which data type was used?"* (an evidential
question, still answered no). Also still excluded: bare `transcriptomic`, which swallowed
96.6% of `spatial_transcriptomics` papers; the vendor name "10x Genomics"; and "tissue
microarray" masquerading as a gene microarray.
**Precision.** **75%** overall at v5, blind validation round three; in the
`genomics` ∩ `he_histology` stratum, **45% (95% CI 26–66)**. **Both figures predate v11 and
were measured against the narrower definition** — the papers they counted as false positives
are largely the ones the ruling has since made correct, so the current row should be better
than 75% and the stratum better than 45%. Neither has been re-measured. **Do not quote 45%
for the shipped row.**
**Failure mode.** With the prediction-side exclusions gone, the characteristic failure is the
general lexical one: a paper mentioning a molecular assay it neither uses nor predicts.

**Recall added at v13.** A named prediction target now assigns this row, per the training-set
rule: predicting MSI, a mutation, a molecular subtype or methylation from imaging required the
molecular labels. `MSI` is guarded against **mass-spectrometry imaging** ("MALDI MSI"), a
collision found in a precision read.

### `clinical_data` — Clinical / EHR Data
**Definition.** Structured clinical variables used as a **model input** — electronic health
records, clinico-radiomic models, and clinical variables explicitly combined with, integrated
with, or incorporated into an imaging model.
**Excluded.** The bare noun phrases. "Clinical data" matches 118 of 3,000 records, "clinical
features" 117, "clinicopathologic" 69 — almost all describing the cohort, not the model's
inputs. Every shipped pattern requires a record system, a named hybrid model type, or
**fusion language**.
**Precision.** ~**90%** at v3, blind validation round two, after recall was raised from
**41% to 62%** at a cost of about six points of precision. The v2 form measured ~96%
precision on 49 author-read records but under-counted by more than half.
**Failure mode — a caveat about what the number means.** This row counts papers that **say**
they fused clinical variables with imaging. It over-counts papers that merely report clinical
variables alongside a model, and under-counts papers that fuse them without saying so. It is
not a precise count of multimodal clinical-imaging models.

### `other` — Other
**Definition.** Two routes. **Additive**: the paper uses a named data type outside the other
rows but still within radiology or pathology — SPECT, hyperspectral imaging, confocal and
electron microscopy, mass spectrometry and MALDI, metabolomics, bulk proteomics, flow
cytometry, Raman spectroscopy, liquid biopsy and ctDNA, microbiome. **Fallback**: the paper
matched no named modality at all. Both routes are distinguished in `pattern_hits.csv`.
**Narrowed at v12 (2026-09-08).** Data types outside the two specialties were moved to
`non_specialty` — see that entry. Acquisition dose is still excluded ("low-dose CT" is a
scanner setting, not a data type), as is "treatment planning" as a clinical process.
**Hyperspectral imaging was kept, and that call was mine rather than the author's.** A
24-record read found roughly 15 are tissue-section, specimen or cytology studies —
histopathology nuclei databases, unstained tissue sections, FNA cytology, resected specimens,
tumour-margin assessment on surgical specimens — against about 6 that are intraoperative
surgical-field imaging. The majority are data a pathology department generates or examines,
which places the term inside the author's line. The intraoperative minority is a real
impurity, accepted because dropping the term would cost the larger tissue group.
**Precision.** **14 of 14** on the additive route, author read, measured before the v12
narrowing. The fallback route is definitional and was not separately measured.
**Count.** 1,542 papers on the additive route at v12.

### `non_specialty` — Non-specialty (excluded)
**Not a figure row.** This category exists to **exclude** papers, not to label them.
**Definition.** Data types the author ruled outside radiology and pathology on 2026-09-08:
radiotherapy dosimetry, the endoscopy family (endoscopy, colonoscopy, gastroscopy,
bronchoscopy, cystoscopy), dermoscopy, colposcopy, optical coherence tomography, thermography,
clinical photography, wearables and accelerometry, ECG and EEG.
**Why the vocabulary is kept rather than deleted.** So the exclusion is auditable. A reader
can see exactly what was removed, count it, and re-measure the decision; a silent absence
allows none of that.
**Measured consequence.** 3,163 corpus papers match a term here. **1,339 (3.0% of the corpus)
would fall out of the analysis entirely** — no named modality row and no surviving `other`
term. The rest keep a specialty label and stay.
**The dosimetry case, checked because it is the largest single exclusion.** 900 papers mention
radiotherapy dose, but **791 of them also carry CT or another named row and keep it**, so the
true loss is **107**, not 900. A 26-record read of those 107 found EBRT and proton planning,
auto-contouring for treatment planning, Monte Carlo dose distributions, dosimetrist workflow
surveys and brachytherapy — radiation oncology rather than diagnostic radiology, which is what
the author ruled. The consequence matches the decision.
**Note.** Colposcopy was absent from the dictionary entirely before this round; it is added
here so the ruling is actually enforced rather than nominally accepted.
