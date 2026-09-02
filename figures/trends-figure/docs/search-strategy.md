# Search strategy

How the paper pool for the trends figure was defined, what it contains, how precise it
is, and what it misses.

**Retrieval date: 2026-09-01.** Every count below was measured against live PubMed on
that date through the E-utilities REST API. Nothing here is estimated unless it says so.
PubMed grows and re-indexes continuously, so a rerun will return more records; a rerun
that returns *fewer* means the query broke.

Files this document explains: `config/corpus.yaml`, `config/themes.yaml`,
`config/modalities.yaml`.

**Dictionary version 6** (2026-09-02) for both `themes.yaml` and `modalities.yaml`; see §5,
"Version 6". `modalities.yaml` jumps 4 → 6 because it had no v5 change; the two files are
kept on one number so a manifest pair identifies one dictionary state. Earlier versions
follow. Version 2 (2026-09-01)
is described below it. From v3 onward the version bumps on **any** content change, not
only on changes judged significant — an unversioned edit makes every older manifest and
report uninterpretable, which happened once between two v2 runs.

**Dictionary version 2** (2026-09-01). `themes.yaml` and `modalities.yaml` were revised
after the first production run; see §5, "Version 2". The corpus query is unchanged and
`corpus.yaml` stays at version 1. The production run returned **44,625** records against
the 44,617 measured here on the same day — PubMed indexed 8 more between the two calls,
which is the expected direction of drift.

---

## 1. Scope

One corpus, retrieved once: **artificial-intelligence methods applied to pathology or
radiology imaging in cancer, 2015-01-01 to 2026-09-01.** Themes and modalities are then
assigned to each record by matching a term dictionary against title and abstract. No
theme or modality is retrieved by its own PubMed query, so every subset shares one
denominator and Panel A's co-occurrence sets are well defined. That choice is recorded in
`docs/DECISIONS.md`.

## 2. Retrieval parameters

| Parameter | Value |
|---|---|
| Database | `pubmed` |
| Date range | 2015/01/01 – 2026/09/01, applied as `mindate`/`maxdate` with `datetype=pdat` |
| Rate | ≤ 3 requests/second (no API key) |
| Identification | `tool=ccr-trends-figure`, `email=ericscrum@gmail.com` on every call |
| Batch size | 500 |

The date range is **not** written into the query string. It lives in the `date_range`
block of `config/corpus.yaml` and is applied by the retrieval client as `mindate`/
`maxdate`. Filtering in both places would filter twice and the two copies would drift.

**Verified equivalence.** An inline `("2015/01/01"[dp] : "2026/09/01"[dp])` filter and the
`mindate`/`maxdate` parameters return the identical count, 44,617. Either route
reproduces the corpus.

PubMed's resolved expansion of the query is stored as `QueryTranslation` in each run
manifest under `data/raw/`. It is not transcribed here; read it from the manifest.

## 3. The corpus query

Three blocks joined by `AND`: **METHOD**, **DOMAIN**, **CANCER**. The exact string is in
`config/corpus.yaml` under `query:`; it is reproduced there rather than here so there is
one copy, not two.

### Why MeSH in some places and text words in others

MeSH is used where a curated term exists and its tree does real work:

- **`"Artificial Intelligence"[mh]`** — explodes to Machine Learning, Deep Learning,
  Neural Networks (and Convolutional, Graph, and Recurrent beneath it), Natural Language
  Processing, and Generative Artificial Intelligence. One term replaces a dozen.
- **`"Radiomics"[mh]`** — a recent descriptor, 4,540 records in all of PubMed.
- **`"Diagnostic Imaging"[mh]`** — explodes to MRI, X-Ray Computed Tomography, Emission
  Computed Tomography, Ultrasonography, Microscopy, and Radiomics.
- **`"Image Processing, Computer-Assisted"[mh]`**, **`"Radiology"[mh]`**,
  **`"Pathology"[mh]`**, **`"Neoplasms"[mh]`**.

Text words carry the rest, for two reasons.

**First, MeSH indexing lags, and the lag falls hardest on exactly the years the figure is
about.** Share of corpus records that are MEDLINE-indexed, measured by year:

| Year | Corpus | MEDLINE-indexed | Share |
|---|---|---|---|
| 2019 | 2,313 | 1,989 | 86% |
| 2022 | 5,593 | 3,953 | 71% |
| 2024 | 7,668 | 5,737 | 75% |
| 2025 | 9,960 | 7,184 | 72% |
| 2026 | 7,299 | 4,355 | 60% |

A MeSH-only query would understate 2026 by roughly 40%, drawing a decline that is an
artifact of indexing. The `[tiab]` terms are what keep the recent years honest.

**Second, no MeSH term exists for much of this vocabulary.** There is no descriptor for
foundation models, whole-slide imaging, digital pathology, pathomics, spatial
transcriptomics, spatial proteomics, or vision transformers. Those must be text words.

`"Pathology"[mh]` is the *discipline* descriptor. It is not the `/pathology` subheading,
which is attached to disease terms and would admit essentially every disease-mechanism
paper in oncology. Verified: PubMed translates `"Pathology"[mh]` to `"Pathology"[MeSH
Terms]` with no subheading expansion.

### Block sizes, dated 2015-01-01 to 2026-09-01

| Set | Records |
|---|---|
| METHOD alone | 520,490 |
| DOMAIN alone | 1,967,066 |
| CANCER alone | 2,701,594 |
| METHOD ∩ DOMAIN | 121,074 |
| METHOD ∩ CANCER | 90,151 |
| **METHOD ∩ DOMAIN ∩ CANCER — the corpus** | **44,617** |

### One term was measured and removed from the query

A draft DOMAIN block containing bare `"histolog*"[tiab]` returned 44,922. That term
admitted **1,434** papers no other pathology term admitted. Reading 16 of them gave
roughly **40% precision**: most were clinical or genomic machine-learning papers carrying
"histologically confirmed" or "histologic subtype", with no tissue image anywhere. It was
replaced by ten explicit phrases (`"histological image*"`, `"histologic section*"`, and so
on), which add 127 records at far higher precision.

`"pathologist*"[tiab]` was tested the same way and **kept**: it admits 357 papers no other
term admits, and 11 of 12 read were genuine pathology-AI papers.

## 4. What the corpus contains

**Total: 44,617 records.**

| Year | Records | | Year | Records |
|---|---|---|---|---|
| 2015 | 484 | | 2021 | 4,544 |
| 2016 | 546 | | 2022 | 5,593 |
| 2017 | 835 | | 2023 | 6,323 |
| 2018 | 1,366 | | 2024 | 7,668 |
| 2019 | 2,313 | | 2025 | 9,960 |
| 2020 | 3,367 | | 2026 | 7,299 *(partial, through 09-01)* |

Publication types and languages within the corpus:

| | Records |
|---|---|
| Has an abstract | 43,790 (98.1%) |
| English | 44,059 (98.7%) |
| Review | 5,970 |
| Editorial | 467 |
| Comment | 381 |
| Case Reports | 170 |
| **Retracted Publication** | **168** |

No publication-type filter is applied. Reviews are 13% of the corpus and they are real
signal for a trends figure — a review of foundation models in pathology *is* evidence of
the theme's activity. Retractions, editorials, and comments are a different matter and are
listed under open decisions in §9.

### A trap in year-by-year retrieval

Retrieving the corpus one year at a time and summing gives **50,298**, which overshoots
the true total of 44,617 by 12.7%. `[dp]` matches more than one date field, so a record
with distinct electronic and print dates satisfies two year windows. Deduplicating PMIDs
across the year queries returns exactly 44,617.

Two consequences for the retrieval code:

1. Deduplicate by PMID.
2. Take each record's year from the parsed record by one documented rule, never from the
   year window that returned it. `data/processed/paper_labels.csv` has a `year_source`
   column for exactly this.

### Corpus precision

**40 records sampled at random and read (titles, plus abstracts where the title was
ambiguous).**

- **38 of 40 (95%)** are genuinely artificial intelligence applied to imaging in cancer.
- The two failures: a retracted paper on music-therapy emotion mapping, and a psychiatry
  paper predicting executive cognition from brain connectivity.
- Applying the stricter reading — imaging that is specifically **radiology or pathology** —
  gives roughly **34–35 of 40 (86%)**. The difference is endoscopy, dermoscopy, optical
  coherence tomography, and clinical photography. Those are correctly retained in the
  corpus and land in the `other` modality; they are not errors, but they are not
  radiology or pathology either.

## 5. Term dictionaries

### Matcher contract

Both dictionaries use one matcher, and the classifier must implement it exactly:

- **`kind: phrase`** — case-insensitive, whitespace-tolerant, word-bounded literal.
- **`kind: regex`** — Python `re`, applied **case-sensitively**. Write `(?i)` at position 0
  of the pattern to opt into case-insensitivity.

Two notes the implementer needs:

1. **Case sensitivity is load-bearing.** `PET`, `CT`, `IHC`, and `WSI` are only usable as
   bare acronyms when matched case-sensitively. See §6.
2. **Python accepts `(?i)` only at position 0** of a pattern. `(?i)foo|(?i)bar` raises
   `re.PatternError`. Every pattern in these files carries at most one, at the front.

Matched against `title + " \n " + abstract`. A record matches a category if **any**
include pattern hits and **no** exclude pattern hits. Excludes are record-level and blunt;
they are used sparingly and each one is justified in its category's `notes`.

Three categories need an AND that the schema's OR-of-includes cannot express
(`pathology_report`, `radiology_report`, and one `he_histology` pattern). These use a
single regex of anchored lookaheads — `(?i)^(?=[\s\S]*A)(?=[\s\S]*B)` — which is a plain
Python regex and needs no change to the matcher.

### Validation sample

A random sample of **3,000 of the 44,617** corpus records (seed 42) was downloaded with
titles and abstracts; 2,939 had an abstract. Most counts in §5–§6 are measured on that
sample by running the shipped YAML through the reference matcher. Corpus estimates scale
by 14.87 and are marked as estimates.

**Small categories are measured over their whole population instead.** A sample of 3,000
puts only a handful of records in a category the size of `clinical_fda` or `digital_twins`,
which is too few to estimate precision from. For `clinical_fda` the entire regulatory
candidate set was downloaded — every corpus record containing any of `FDA`, `Food and Drug
Administration`, `CE mark*`, `regulatory`, `510(k)`, `premarket`, `medical device*`,
`cleared`, `clearance`, `MHRA`, `NMPA`, `PMDA`, `UKCA` or `market(ing) authorization` in
title or abstract, which is **834 records** — and the shipped patterns were run over all of
them. The 93 matches were then read individually. Counts and precision for that category
are exact, not estimated.

### Theme counts

| Theme | Sample (n=3,000) | % | Est. corpus |
|---|---|---|---|
| `foundation_models` | 89 | 2.97% | ~1,320 |
| `multimodal_integration` | 291 | 9.70% | ~4,330 |
| `digital_twins` | 5 | 0.17% | ~74 |
| `clinical_fda` | 5 | 0.17% | **93 (exact, see below)** |
| *no theme* | 2,630 | 87.67% | — |

`clinical_fda` was not estimated from the sample. Because the category is small,
it was measured over its whole population: every corpus record containing any
regulatory vocabulary was downloaded (834 records) and the patterns were run over
all of them. **93 records match, and all 93 were read.** The sample-scaled estimate
(~74) agrees within Poisson error but the exact figure is the one to quote.

That 88% of the corpus carries no theme is expected and correct. The corpus is the
denominator; the themes are four specific currents within it.

### Modality counts

| Modality | Sample (n=3,000) | % | Est. corpus |
|---|---|---|---|
| `he_histology` | 438 | 14.60% | ~6,510 |
| `ihc` | 146 | 4.87% | ~2,170 |
| `spatial_proteomics` | 15 | 0.50% | ~223 |
| `spatial_transcriptomics` | 29 | 0.97% | ~431 |
| `pathology_report` | 10 | 0.33% | 222 (exact) |
| `mri` | 865 | 28.83% | ~12,870 |
| `ct` | 823 | 27.43% | ~12,240 |
| `pet` | 224 | 7.47% | ~3,330 |
| `ultrasound` | 286 | 9.53% | ~4,250 |
| `mammography` | 131 | 4.37% | ~1,950 |
| `xray` | 37 | 1.23% | ~550 |
| `radiology_report` | 27 | 0.90% | ~402 |
| `genomics` | 261 | 8.70% | ~3,880 |
| `clinical_data` | 382 | 12.73% | ~5,680 |
| `other` | 671 | 22.37% | ~9,980 |

Counts are **version 3** (2026-09-02).

`other` splits into two routes: **294** records match one of its include patterns
(the additive route — the paper uses a data type outside the named rows) and **383**
reach it only by the fallback route, having matched no named modality at all.

Modalities per paper (v2, counting `other`): 1 → 2,038, 2 → 732, 3 → 183, 4 → 43,
5 → 3, 6 → 1. No paper has zero, because `other` is a fallback.

### Measured co-occurrences

These drive Panel A's columns, so they are reported rather than engineered away.

| Pair | Both | Share of first | Share of second |
|---|---|---|---|
| `pet` & `ct` | 173 | **77.2%** | 21.0% |
| `he_histology` & `ihc` | 58 | 13.2% | 39.7% |
| `he_histology` & `spatial_transcriptomics` | 12 | 2.7% | 41.4% |
| `mri` & `ct` | 113 | 13.1% | 13.7% |
| `spatial_transcriptomics` & `spatial_proteomics` | 2 | 6.9% | 10.5% |
| `radiology_report` & `pathology_report` | 1 | 3.7% | 10.0% |
| `mammography` & `xray` | 2 | 1.5% | 5.4% |
| `mammography` & `mri` | 23 | 17.6% | 2.7% |
| `xray` & `ct` | 20 | 54.1% | 2.4% |

**PET and CT overlap at 77% of PET papers.** Most oncologic PET is acquired as PET/CT, and
`\bCT\b` correctly fires inside `PET/CT` and `SPECT/CT`. This is not suppressed: the papers
really do use both. `pet+ct` will be one of the largest columns in Panel A and the legend
should say why.

The two spatial modalities overlap at only 2 records, so the disambiguation in §6 works.

### Version 6 — round three: the residue, measured to its limit (2026-09-02)

Round three found that the predicted-molecular-label residue documented in v4 is not a
curiosity but **the dominant defect in the dictionary**, and that it lands on the figure's
most-read cell.

#### 1. The genomics ∩ H&E stratum

Measured by validation: **45% precision (95% CI 26–66%)** in that stratum, with 8 of 11
false positives being the residue. Against ~855 papers that implies **300–630 spurious**.
This is the imaging-plus-molecular pairing the whole additive-`other` rebuild exists to
display, so an inflated count here would make the figure support the review's argument by
construction — the same failure the TCGA fix addressed.

I reconstructed the stratum from the corpus (2,153-record superset; my stratum comes to
**855** against the validator's 853, so the reconstruction is faithful) and built a
prediction-side exclude, as advised: the construction is treated as evidence *against*
genomics rather than merely failing to be evidence for it.

Two routes, both guarded so that a paper naming genomics as a **source** is rescued:

- **Title-scoped.** The title is the text before the first newline, so `^[^\n]*` scopes a
  test to it. Residue papers announce themselves there: "Prediction of homologous
  recombination deficiency from routine histology".
- **Whole-record.** Prediction verb → molecular target → source preposition → image, inside
  one sentence.

| | before | after |
|---|---|---|
| `genomics` (in superset) | 1,182 | 1,092 |
| **`genomics` ∩ `he_histology`** | **855** | **766** (−10%) |

Removal precision is high — 18 of 18 read from the whole-record route, 20 of 22 from the
title route were unambiguous residue. The source guard rescues 10 records, 9 correctly.

**The residue is not fully fixable at abstract level.** A looser detector was built and
rejected on measurement: dropping the sentence boundary and proximity constraints reaches
213 of 855 (25%), but a 20-record read put its removal precision near **70%**. It would
discard roughly 64 genuine papers to remove roughly 150 spurious ones, moving stratum
precision from about 45% to about 50%. That is not a trade worth making. What stays
uncaught is the paper that predicts a molecular label but phrases it across sentences, or
never names the image source in the same breath.

**So the stratum precision must go in the legend as a number.** A stated 45% is publishable;
an unstated one is not.

#### 2. The intra-modality exclusion, widened

Round three measured the v4/v5 form at 55% (34–74%) against 67% before — overlapping
intervals, demonstrating nothing. The mechanism was measured: the sequence-pair test needs
both a T1-family and a T2-family term, but only **245 of 3,452 candidates (7.1%)** name
both, so it fired on 2.4%. The type specimen it missed is PMID 42135350 — "multi-modal MRI
scans" over four BraTS sequences, no other data type, not one sequence named.

It now has two routes: `multi-modal`/`multi-parametric` within 60 characters of MRI (either
order), **or** the original sequence-pair test. PMID 42135350 is caught by the new route and
was not caught before. Exclusion rate on multimodal candidates **1.7% → 5.5%**; theme count
**287 → 276**. All 11 newly excluded records were read; all 11 are intra-modality MRI work.

#### 3. The latent defect — checked before acting

The report named `SPECT` and `CT\b` as unprotected against case-insensitive matching. **As
written in the file they were already anchored** as `\bSPECT\b` and `\bCT\b`, and
case-insensitivity costs **0 and 1** records out of 3,000. The quoted 51% and 64% rates
reproduce exactly only if the leading `\b` is dropped — which is what must have been tested.
That specific defect was not live, and is not live now.

**But a real unbounded token was present and unreported:** `text`, which matches "context"
(169 records) and "texture" (177) — and texture is everywhere in a radiomics corpus. It is
now `\btext\b`. Every acronym in the context list is additionally pinned case-sensitive with
a scoped inline flag, `(?-i:\bCT\b)` and so on, so that widening the exclusion cannot make
the class live later.

#### v6 counts

`foundation_models` 89 · `multimodal_integration` 276 · `digital_twins` 5 · `clinical_fda` 5
per 3,000. `genomics` 230 (~3,420 corpus, from 244) · `he_histology` 438 · `clinical_data`
373 · `other` 673. `genomics` ∩ `he_histology` 38 per 3,000 (~565 corpus).

### Version 5 — the digital-twins standard change (2026-09-02)

The author clarified the theme's purpose: it tracks **trends of interest**, not successful
construction. Papers discussing digital twins in any capacity count. A hand screen of all 64
candidates under the inclusive standard kept 56 and dropped 8, and the 8 are lexical
collisions — the class patterns can fix — so the row stays fully rule-based with no
hand-curation in the pipeline.

**The operational line**, approved by the author and binding on all recall work here:

> The paper must **invoke the digital-twin idea itself, in the twin vocabulary**, not merely
> supply something a twin would need.

Without it, "a building block for one" has no stopping point — every longitudinal imaging
paper is a building block and the theme swallows the corpus.

#### Result: one pattern, and that is the finding

`digital_twins` ships a single include, `(?i)\bdigital[\s-]+twin(s|ning)?\b`, and the
`patient avatars?` pattern is removed. **56 papers**, matching the hand screen's calibration
exactly.

The pattern must **not** be anchored on a modifier. The genuine vocabulary is "digital twin"
plus a modifier, and the modifiers vary without limit — medical, clinical, cognitive,
theranostic, generative, optical, geometric, therapeutic. Every one precedes the head noun,
so the unanchored pattern catches them all.

**The hyphen fix was not cosmetic.** A literal space missed "modeling digital-twin of renal
functions". Tolerating the hyphen took the count 55 → 56 — the whole gap between my
measurement and the screen's expectation.

#### Recall: every ranked candidate yielded zero

| Candidate | Corpus hits | Unique | Verdict |
|---|---|---|---|
| `patient-specific computational model` | 1 | **0** | already captured — the paper says "digital twin" in its title |
| `virtual human twin` | 1 | **0** | glossed three words from the head term |
| `in silico trial` | 4 | 3 | **rejected on the operational line** — virtual *imaging* trials over phantoms |
| `virtual trial` | 3 | 2 | rejected, same reason |
| `virtual cohort` | 1 | 1 | rejected, same reason |
| bare `virtual patient` | 11 | 9 | rejected — phantoms, XCAT models, GAN synthetic data |
| `digital <modifier> twin` | — | **0** | construction does not occur |
| `virtual replica` | **0** | — | as predicted |

The field's own reviewers do treat patient-specific computational models as one literature
with digital twins — the neuro-oncology systematic review writes exactly that in its
inclusion criteria — but in *this corpus* the phrase never appears outside a paper already
captured by the head term.

#### Self-correction

An earlier v5 draft added `digital patient/human model`, `virtual patient model` and
`patient-specific simulation/computational model`, gaining 5 records. All five were then
tested against the operational line and **all five failed** — none contains any twin
vocabulary. They are a biobank's patient model, an image-registration coordinate space, two
3D surgical-planning models and a finite-element tumour-growth simulation: precisely the
"supplies what a twin needs but never invokes it" class the line exists to exclude. Reverted.

#### One open disagreement

The screener counts the "Twin-GRU" paper as a collision because its authors disclaim the twin
sense. It is the only Twin-GRU record in the corpus and its title reads "A **Digital
Twin-Inspired** Closed-Loop Latent Simulation Framework". Under the strict standard it is a
false positive; under "engagement in any capacity" a title framing the work as
digital-twin-inspired is engagement. **It is currently counted.** No pattern separates it from
genuine usage — if the screener's reading governs it must be dropped by PMID.

### Version 4 — round-two validation, and one definitional decision (2026-09-02)

Round two drew a fresh sample with a new seed against v3. It confirmed the v3 repairs —
`foundation_models` precision **59% → 89%** with non-overlapping intervals and no
self-supervised false positives left; the `zero-shot`/`few-shot` removal, which v3 flagged
as untested, cost nothing measurable; the TCGA qualifier worked; `clinical_data` recall
**41% → 62%** for six points of precision. It also found seven further defects.

#### The definitional decision: modalities are INPUTS

`genomics` precision fell to 75%, and four of seven false positives were papers that
*predict* a molecular label from an image — MSI or HER2 from H&E. The author has settled
it: **a paper counts for a modality only if that data type enters the model as input.**
Prediction targets do not count. **Panel A therefore means "what data does this work
consume", and the legend must say so** — it is not "what data does this work relate to".

This is the same class of error as the TCGA defect, and it fails in the same direction:
counting predicted labels re-inflates the imaging-plus-molecular pairing the figure exists
to display.

The exclusion is conjunctive and self-limiting — it fires only when a
predict-molecular-from-image idiom is present *and* no genomics-as-input idiom appears
anywhere in the record. **Measured: removes 17 of 261 records per 3,000. All 17 were read
and all 17 are correct.** `genomics`+`he_histology` falls 47 → 44; the effect is modest
there because most predict-molecular papers are radiology, not histology.

**Known residue, not fixable by terms.** A paper predicting molecular subtype from
histology that also mentions the sequencing used to generate its ground-truth *labels* is
rescued by the input clause and survives. Tightening the rescue clause to drop bare
"sequencing" was tested and changed nothing.

#### The seven changes

| # | Category | Defect | Fix | Measured cost |
|---|---|---|---|---|
| 1 | `genomics` | predicted labels counted as inputs | conjunctive predict-from-image exclude | 261 → 244; 17/17 removals correct |
| 2 | `genomics` | bare `genomic` hit "genomic instability" | negative lookahead | phenotype, not a data type |
| 3 | `spatial_proteomics` | `MIBI` hit 99mTc-MIBI sestamibi (5 of 12 corpus records) | **acronym removed**, not guarded | **zero** — all 5 genuine papers still caught |
| 4 | `multimodal_integration` | intra-modality fusion; v3 exclude did not work | rewritten to key on **sequence names**, not phrase order | fires on 5 per 3,000 vs 2; 5/5 correct |
| 5 | `multimodal_integration` | `early/late/intermediate fusion` architectural | removed | 3 matches, 1 unique — close to free |
| 6 | `digital_twins` | `digital (patient / tumour / avatar)` hit 3 unrelated senses | removed | **zero unique records** |
| 7 | `clinical_fda` | `following` admitted temporal sequence | dropped from possession verbs | — |
| 8 | `clinical_data` | 4 of 6 false positives from the v3 structural patterns | tightened `clinical risk factors` to require a model verb | 75 → 54 hits; unique 14 → 5, precision 10/14 → 4/5 |

On #3, a technetium-prefix lookbehind was built and measured first, but it still admitted
"Ultrasound and MIBI are the most commonly used imaging methods" and "scintigraphy with
iodine-123, MIBI", where no prefix is adjacent. Removing the acronym was then tested
against all five genuine multiplexed-ion-beam papers in the corpus: all five survive via
the spelled-out names. A free removal beats a guard that half works.

On #4, the v3 exclusion required the literal phrase "multimodal MRI", so it missed
"multi-modal deep learning … magnetic resonance imaging sequences" and could not fire when
MRI was never named. It now fires when a T1-family term and a second sequence family (T2,
FLAIR, DWI, ADC, DCE, SWI, PWI, MRCP) both appear and no other data type is named anywhere.

**Still unexercised:** `secondary ion mass spectrometry`, added in v3, matched no validation
paper and only 3 corpus records. Retained on definitional grounds; precision unmeasured.

#### v4 counts

`foundation_models` 89 · `multimodal_integration` 287 · `digital_twins` 5 · `clinical_fda` 5
per 3,000. `genomics` 244 (~3,630 corpus) · `clinical_data` 373 (~5,550) ·
`spatial_proteomics` 15 · `other` 672. `genomics`+`he_histology` 44 (1.47%). Multimodal
papers with exactly one modality: 36.2%.

### Version 3 — corrections from blind validation (2026-09-02)

A 200-paper stratified sample, labeled blind, found real defects. Seven changes followed.
**These were fixes to the defects revealed, not to the specific papers named.** Because the
dictionary changed after that sample was inspected, the sample no longer measures the
revised dictionary; a fresh sample with a new seed will be drawn for the affected
categories, and both rounds reported. Note also that no sample of the corpus can bound
recall against the *literature* — only against the corpus.

| # | Category | Defect | Fix | Measured cost |
|---|---|---|---|---|
| 1 | `foundation_models` | 59% precision (27/46); **12 of 19 false positives from one pattern** | dropped `self-supervised`, `zero-shot`, `few-shot` | 108 → 89 per 3,000 (~1,610 → ~1,320 corpus) |
| 2 | `foundation_models` | `LMM` matched "linear mixed-effects models" | dropped acronym, broadened spelled-out form | **zero** — both genuine papers preserved |
| 3 | `foundation_models` | `PRISM` matched drug-screen compounds | dropped outright | zero genuine hits found in 24 corpus records |
| 4 | `spatial_proteomics` | `imaging mass spectrometry` in wrong row; missed a MIBI paper | moved to `other`; added `secondary ion mass spectrometry` | 19 → 15 per 3,000 |
| 5 | `he_histology` | `patch-level` describes granularity, not data type | dropped | none measurable (438 unchanged) |
| 6 | `multimodal_integration` | fusion patterns fired on network architecture; mpMRI false positives | constrained both fusion patterns; context-aware mpMRI exclude | 358 → 291 per 3,000 |
| 7 | `clinical_data` | **41% recall** (17/41) | bounded-gap fusion patterns + 4 structural patterns | 244 → 382 per 3,000; precision ~96% → **~94%** |
| 8 | `genomics` | bare `TCGA` admitted slide-archive papers | require a molecular noun within 120 characters | 288 → 261; **`genomics`+`he_histology` 68 → 47, −31%** |

#### The TCGA defect, and why it was the worst one

`TCGA` fired on 1,094 corpus papers and was the *only* genomics pattern for 527 of them, of
which **349 (66%) also carried `he_histology`**. Reproduced on the validation sample: 69
TCGA papers, 34 TCGA-only, 24 of those (71%) also histology.

TCGA distributes both whole-slide images and molecular data, so the archive's name cannot
settle which a paper used, in either direction. The failure mode was not an ordinary false
positive: these papers landed in `genomics` + `he_histology`, **precisely the
imaging-plus-molecular pairing the figure was rebuilt to display**. The defect manufactured
evidence for the review's own argument, which is a worse failure than a count error.

The pattern now requires a molecular noun within 120 characters and no intervening sentence
break. Reading all 21 dropped TCGA-only-plus-histology papers: they are slide-archive uses —
pathomics signatures, whole-slide tumour recognition, histologic classification, slide
retrieval, and MSI or HPV prediction *from* histology. The 3 kept are genuinely molecular.
About 1–2 of the 27 total drops look like genuine losses, the clearest being a paper
integrating "gene biomarker signatures" in a phrasing no other pattern catches. **The fix
trades a small amount of real recall to remove a much larger amount of manufactured
co-occurrence.**

#### `clinical_data`: trading precision for recall, deliberately

v2 measured 96% precision but **41% recall** — it under-counted by more than half. The
commonest miss was the radiomics nomogram: "a combined model with clinical characteristics"
fired nothing, because every v2 fusion pattern required "clinical" to follow the fusion verb
immediately. All fusion patterns now allow a bounded gap of up to 45 non-sentence
characters, and four structural patterns were added (`clinicopathological
data/variables/factors`, `clinical model/score/signature`, `radiomics nomogram`, `clinical
risk factors`) — in the radiomics literature a "radiomics nomogram" or a "clinical model"
essentially always denotes clinical variables combined with an imaging signature.

The category grew 244 → 382 per 3,000 (~3,630 → ~5,680 corpus, +57%). Precision on the 92
newly admitted records was 17–18 of 20 read, giving a blended **~94%**, down from ~96%.
Residual failures are papers mentioning clinicopathological factors in a statistical
adjustment or as background framing rather than as model inputs.

#### Net effect on the multimodal theme

| | exactly one modality | two or more |
|---|---|---|
| v1 (imaging and text rows only) | 65.1% | 21.2% |
| v2 (all rows, `other` additive) | 45.3% | 54.7% |
| **v3** | **35.4%** | **64.6%** |

Of multimodal papers carrying a single imaging or text row, **60.4%** now also carry a
non-imaging row, up from 48.5% at v2.

#### What held up

The blind sample also confirmed what was already sound: CT, MRI, PET, ultrasound and
mammography ran 85–96% precision and 94–98% recall, and `clinical_fda` came in at 92%
precision and 96% recall — which vindicates measuring that small category over its whole
population rather than sampling it.

### Version 2 — the additive-`other` correction (2026-09-01)

The first corpus run exposed a **semantic error, not a vocabulary error**. `other` was
assigned only when a paper matched *no* named modality, so a paper using MRI plus genomics
was recorded as "MRI alone" and was indistinguishable from a unimodal MRI study. **61.6% of
the 5,796 multimodal-integration papers carried exactly one named modality**, and 44.8% of
those mentioned genomic, clinical or proteomic data. The figure would have shown the
multimodal theme as overwhelmingly unimodal, which is close to the opposite of the truth.

Three changes fixed it: two new non-imaging rows (`genomics`, `clinical_data`) and making
`other` additive. Measured effect on the multimodal-integration theme:

| | exactly one modality | two or more |
|---|---|---|
| before (imaging and text rows only) | 233 of 358 — **65.1%** | 76 — 21.2% |
| after (all rows, `other` additive) | 162 of 358 — **45.3%** | 196 — 54.7% |

Of the 233 multimodal papers that previously carried exactly one imaging or text row,
**113 (48.5%) now carry a second label**. That independently reproduces the 44.8% figure
from the production run, which is the strongest evidence available that the two new rows
capture the population that was being missed rather than some other population.

The residual 45.3% is not all error. A paper on "multimodal MRI" — several MRI sequences —
legitimately occupies one row, and papers of that kind are a real part of the theme.

`genomics` and `clinical_data` do **not** contribute to the radiology/pathology `domain`
rule. A paper using MRI and genomics is `radiology`, not `both`.

## 6. Precision spot-checks

Every figure below is from titles I read, with the sample size stated. Where a term failed,
it was changed and re-measured; both numbers are given.

| Category / term | n read | Precision | Verdict |
|---|---|---|---|
| **Corpus overall** | 40 | 95% (86% strict) | ship |
| `histolog*` in corpus query | 16 | ~40% | **removed** |
| `pathologist*` in corpus query | 12 | ~92% | kept |
| `foundation_models` | 20 | 20/20 plausible, 18/20 strong | ship |
| `multimodal_integration` | 18 | 16/18 (89%) | ship |
| `digital_twins` | 7 (all) | 5/7 after fix | ship, small |
| — `virtual patient/cohort` | 2 (all) | **0/2** | **removed** |
| `clinical_fda` — regulatory only | **93 (all)** | **95.7%** | ship |
| — bare `regulatory approval` | 16 | 44% | **removed** |
| — deployment reading (rejected) | 14 | ~11/14 as "clinical application" | **not used, §9.1** |
| `he_histology` — before fix | 12 | ~63% | rejected |
| `he_histology` — after fix | 14 | 12–13/14 (~90%) | ship |
| `ihc` | 12 | 11/12 involve IHC data | ship, see §9 |
| `spatial_proteomics` | 20 | 16–17/20 (~82%) | ship |
| — `Vectra` | 1 (all) | **0/1** | **removed** |
| `spatial_transcriptomics` | 20 | ~18/20 (90%) | ship |
| `pathology_report` — before fix | 20 | 10/20 (50%) | rejected |
| `pathology_report` — after fix | 10 (all) | 9/10 (90%) | ship |
| `radiology_report` — before fix | 20 | ~12/20 (60%) | rejected |
| `radiology_report` — after fix | 20 | ~19/20 (95%) | ship |
| — `BI-RADS assessment/category` | 2 (all) | **0/2** | **removed** |
| `ct` — bare `\bCT\b` only | 22 | **22/22 (100%)** | ship |
| `pet` — bare `\bPET\b` only | 16 | **16/16 (100%)** | ship |
| `ultrasound` | 12 | 12/12 | ship |
| `mammography` | 16 | 16/16 | ship |
| `xray` | 18 | ~17/18 (94%) | ship |
| — bare `x-ray` | 13 | ~4/13 (31%) | **removed** |
| — `\bDBT\b` collision check | 7 (all) | 7/7 breast tomosynthesis | ship |
| `genomics` | 20 | 19/20 (95%) | ship |
| — genomics ∩ spatial transcriptomics | 14 (all) | 12/14 (86%) | boundary accepted |
| — bare `transcriptomic` | — | swallows 96.6% of `spatial_transcriptomics` | **removed** |
| — bare `gene expression` | — | raises spatial overlap 14→23 of 29 | **removed** |
| — `\bgenomic` vs "10x Genomics" | 2 (all) | 0/2 | **guarded** |
| — `microarray` vs "tissue microarray" | 18 (all) | 14/18 were tissue | **guarded** |
| `clinical_data` | **49 (two samples)** | **~96%** | ship |
| — bare `clinical data` / `clinical features` | — | 118 and 117 of 3,000, cohort description | **removed** |
| `other` (additive route) | 14 | 14/14 | ship |
| — `(radiotherapy\|radiation) dose` | 26 | 24/26 acquisition dose | **removed** |
| `pathology_report` — full population re-read | **25 of 222** | **24/25 (96%)** | ship, supersedes n=10 |
| — bare `\bUS\b` | 12, then 6 | 9/12; 2/6 when alone | **removed** |

### Dead patterns removed in version 2

The production run reported five patterns that never fired in 44,625 records. Each was
checked against PubMed directly before being touched:

| Pattern | Corpus hits | Action |
|---|---|---|
| `digital_twins` "virtual twin" | 0 | removed |
| `digital_twins` "computational twin" | 0 | removed |
| `digital_twins` "in-silico twin" | 0 | removed |
| `ihc` "immunoperoxidase" | 0 | removed |
| `radiology_report` `radiolog\w* (narrative\|impression section)` | 0 | **repaired, not removed** |

The last one was a near-miss rather than dead weight. "impression section" occurs in 3
corpus records and all three are genuine radiology-report NLP papers, but never adjacent to
"radiolog". It is now two patterns: `radiolog\w* (narrative|impressions?)`, which also
catches "Radiology Impressions", and a standalone `impression section`.

### The acronym traps, resolved

**`PET` vs. `pet`.** Case sensitivity closes it completely. In 3,000 corpus records,
case-sensitive `\bPET\b` matched **213**; lower-case `\bpet\b` matched **1** — and that one
was `"pet-based radiogenomics in oncology"`, a lower-cased title for PET imaging, not an
animal. No polyethylene terephthalate appeared. Of the 133 records that write PET but never
"positron emission tomography", 16 of 16 read were genuine. Bare lower-case `pet` is not
shipped, at a measured cost of one true positive in 3,000. `\bPET\b` does not fire inside
`SPECT`, which is correct.

**`CT`.** Also solved by case sensitivity, and the result is better than expected. 722 of
3,000 records contain case-sensitive `\bCT\b`; **386 never write "computed tomography"**,
and 22 of 22 of those read were computed tomography. No collision with qPCR *Ct*,
chemotherapy, or clinical trial appeared. Case-insensitive matching would be unusable.

**`IHC`.** One real collision: *intrahepatic cholangiocarcinoma*, which some hepatobiliary
papers abbreviate IHC. Of 3,000 records, 36 contain `\bIHC\b`; of the 6 that contain IHC but
no `immunohistochem*` spelling, 1 was the cholangiocarcinoma sense. A narrow exclude fires
only on the literal definition `intrahepatic cholangiocarcinoma (IHC)`.

**`US`.** Unsalvageable, and dropped. 68 of 3,000 records contain `\bUS\b`; of the 21 with
no other ultrasound word, 4 of 6 read were false — "US populations", "US National Science
Foundation", "US English", "US-based trial". The cost of dropping it is near zero, because
papers that use the abbreviation introduce it as "ultrasound (US)" first.

**`foundation`.** Collides with funding bodies. 52 of 3,000 records contain "foundation";
only 22 contain "foundation model". Only the phrase is used, never the bare word.

**`Vectra`.** Removed from `spatial_proteomics`: it collides with the Canfield VECTRA
total-body photography system, and its one match was a dermatology photography paper.

**`digital twin`.** Rare, as expected — 5 records in 3,000, about 74 in the corpus, nearly
all after 2022. Broadening was tested and rejected. "virtual patient/cohort" matched 2
records and **both were false** (a virtual-phantom dosimetry study and an image-guided
neurosurgery system). "in silico patient/cohort/trial" and "patient-specific model" added
nothing the twin terms had not already caught, so their precision could not be measured and
they are not shipped. **The theme is small because the literature is small.** That is the
finding, and it agrees with the manuscript's refusal to let the term drift.

**`FDA approval`.** Bare `FDA` is not used; it appears in discussion sections of papers
that cleared nothing. Requiring `FDA` adjacent to `clear|approv|authoriz` fixes it. In
3,000 records only 4 mention FDA at all and 3 survive the adjacency requirement. Across the
corpus, 125 records contain `"FDA"[tiab]` — that is the entire regulatory population.

**`X-ray`.** Unsalvageable as a bare token, and dropped. On 3,000 corpus records
`(?i)\bx-?ray` matches 39, and of 13 read only about 4 were plain radiography. It
leaks in five directions at once: X-ray radiation and radiotherapy dose ("exposed to
X-ray radiation, 3 x 8 Gy"), X-ray fluorescence, dual-energy X-ray absorptiometry,
the X-ray physics of CT ("CT uses x-ray radiation"), and mammography ("mammography,
a low-dose X-ray technique"). Excluding the crystallography family alone does not fix
it, because radiotherapy dose and mammography are the larger leaks. The `xray` row
names the examination instead — chest X-ray, CXR, radiography/radiographs, plain
film, fluoroscopy — which measured 37 of 3,000 at roughly 17 of 18 precision.

**`radiographic` versus `radiography`.** The adjective is excluded on purpose. In
oncology "radiographic response" and "radiographic progression" are RECIST vocabulary
describing CT or MRI, not plain films. Requiring a terminal *y* or *s* keeps the noun
and drops the adjective.

**Mammography leaking into `xray`.** Mammography is a projection X-ray technique, so
the two rows are split by clinical role rather than physics and are expected to
overlap. The definitional sentence "mammography is an X-ray imaging technique" pulled
mammography papers into `xray`; a targeted exclude removes it, cutting the measured
overlap from 7 records to 2 (5.4% of `xray`). `mammography` is not swallowed: it keeps
131 of its 132 records.

**`DBT`.** Checked case-sensitively for the dialectical-behaviour-therapy collision
and clean: 7 of 7 matches in 3,000 records were digital breast tomosynthesis.

**The spatial-transcriptomics boundary for `genomics`.** Measured, not guessed, because
the author asked for it specifically. Bare `transcriptomic` matched **28 of the 29**
spatial-transcriptomics papers in a 3,000-record sample — 96.6% — which would have made
that row redundant, so it is not used. Bare `gene expression` is not used either: adding it
raised the overlap from 14 to 23 of 29, because it describes the spatial assay itself
("analyse gene expression profiles of tissues while preserving spatial location"). With the
shipped patterns the overlap is 14 of 29, and **all 14 were read: 12 were correct** —
papers genuinely integrating single-cell RNA-seq, bulk RNA-seq, TCGA or multi-omics data
alongside spatial. The two failures were `\bgenomic` matching the vendor name "10x
Genomics", now guarded by a lookbehind, and one paper describing "tissue genomic
architecture". A spatial paper therefore carries `genomics` only when it names non-spatial
molecular data, which is where the line should fall.

**`microarray` versus "tissue microarray".** A clean collision between `genomics` and
`he_histology`: **14 of 18** `microarray` matches were *tissue* microarrays. A lookbehind
guard removes them.

**`clinical_data` — the hardest category in the dictionary, and its honest ceiling.** The
bare noun phrases are unusable: `clinical data` matches 118 of 3,000 records, `clinical
features` 117, `clinicopathologic` 69, almost all describing the cohort rather than the
model's inputs. None is shipped. Every pattern instead requires a record system (EHR/EMR), a
named hybrid model type (clinico-radiomic), or **fusion phrasing** — clinical variables
being combined with, integrated with, or incorporated into an imaging model. Measured over
**49 records read across two independent samples (seeds 7 and 23): 47 genuine, about 96%**.
This is higher than expected, and the reason is structural: the corpus already requires an
AI term, so "combined with clinical data" almost always does mean a model input. The two
failures were a narrative review listing demographic and clinical prognostic factors, and a
paper whose abstract said "routine laboratory tests" while describing current practice; the
word "test" was dropped from the laboratory pattern after that read.

The honest ceiling is lower than 96% in what the number *means*. The category counts papers
that **say** they fused clinical variables with imaging. It will over-count papers that
merely report clinical variables alongside an imaging model, and under-count papers that
fuse them without saying so. It should not be read as a precise count of multimodal
clinical-imaging models, and the figure legend should not claim that it is.

**Acquisition dose versus dose data in `other`.** `(radiotherapy|radiation) dose` was
drafted and removed: **24 of its 26** matches were acquisition dose — "reduce radiation
dose", "low-dose CT", "zero radiation dose imaging" — a scanner setting, not a data type the
model consumes. Only dose-volume, dose-distribution, dose-map, dose-prediction, dosimetry,
DVH and the explicit "radiotherapy dose" are kept. `treatment planning` was also rejected:
132 matches, and it names a clinical process rather than a data type.

**`FDA` and `regulatory approval`, after the narrowing.** See §9.1. Bare `FDA` is
never used. Bare `regulatory approval` measured **44% precise** over 16 reads — nine
of sixteen were aspirational, of the form "further validation and regulatory approval
are needed" — and is not shipped; only a possession-constrained form is. The generic
`FDA` patterns additionally require a software or device noun within 90 characters.
The one systematic residue is approval of a **drug or radiotracer** rather than a
device ([177Lu]Lu-PSMA-617, [68Ga]PSMA-11, contrast agents, checkpoint inhibitors);
two targeted excludes remove four such records with **zero genuine records lost**.

**`spatial transcriptomics` vs. `spatial proteomics`.** Kept apart by naming the assays
rather than the category. The shared platform (GeoMx, which measures both protein and RNA)
is assigned to both deliberately. The genuinely ambiguous umbrella terms — "spatial omics",
"spatial biology", "spatial multi-omics" — are in **neither**, and those papers fall to
`other` unless they name a specific assay. Under-assigning was preferred to guessing.
Measured overlap after this treatment: 2 records.

## 7. Why the domain block filters what it filters

An early check showed the DOMAIN block admitting only 33% of corpus-eligible
`spatial transcriptomic*` papers and 31% of `digital twin*` papers, which looked like a
recall failure. Reading the excluded papers showed it was not.

The excluded spatial-transcriptomics papers were overwhelmingly bulk and single-cell
RNA-seq prognostic-signature bioinformatics — "machine learning identifies a T-cell
signature in lung adenocarcinoma" — that mention spatial transcriptomics in passing and
contain no tissue image. That literature is enormous and would have swamped the classifier.
The excluded digital-twin papers were mental health, dentistry, bone-mechanics simulation,
and pharmacokinetics: digital twins, but not of pathology or radiology imaging.

The block was still widened where the exclusion was wrong: title-level spatial-omics terms,
`imaging mass cytometry`, `multiplex immunofluorescence`, `imaging mass spectrometry`,
`pathology report*`, and the PET terms were added, and the low-precision `histolog*` was
removed.

## 8. What this strategy knowingly misses

Stated plainly, because a reader should not have to discover these.

1. **Non-English papers without an English abstract.** 98.7% of the corpus is English. A
   Chinese- or Japanese-language paper with no English title or abstract cannot match any
   `[tiab]` term and is invisible.
2. **Papers with no abstract** — 827 records (1.9%) — are matched on title alone and will
   be under-labeled for both themes and modalities.
3. **Preprints.** PubMed indexes almost no bioRxiv or arXiv preprints. Much foundation-model
   work in pathology and radiology appears there first, sometimes for a year or more. The
   `foundation_models` line in Panel B lags the real field. `main.tex` names KRONOS, CT-FM,
   RAD-DINO, and Merlin, several of which were preprints; this corpus will not see them
   until they are journal-published.
4. **Resolved 2026-09-01:** mammography and radiography have their own rows, and `other` is
   now additive with 22 include patterns naming the data types outside the named rows —
   radiotherapy dose, endoscopy, dermoscopy, optical coherence tomography, SPECT,
   hyperspectral, mass spectrometry, metabolomics, bulk proteomics, flow cytometry, liquid
   biopsy, microbiome, wearables and ECG/EEG. What still reaches `other` only by fallback is
   any data type nobody named often enough to be worth a pattern.
5. **`clinical_data` measures stated fusion, not actual fusion.** See §6. It counts papers
   that say they combined clinical variables with imaging. That is the best a term
   dictionary can do, and it is not the same quantity as "papers that built a multimodal
   clinical-imaging model".

6. **The modality a paper *uses* versus the modality it *predicts*.** A paper predicting
   HER2 status from H&E images matches both `he_histology` and `ihc`, though its input is
   only H&E. In a 12-record read of `ihc`, 11 involved IHC data but only about 4 used IHC as
   the model input. The dictionary cannot separate input from label, and it does not try.
7. **Named foundation models released after 2026-09-01** are not in the dictionary.
8. **`digital_twins` (~74 papers) and `clinical_fda` (93 papers) are small enough to be
   noisy** across twelve years. Their Panel B lines should be drawn, but no trend statement
   should rest on a single year of either. See §9.1 for the recommended cumulative plot.
9. **Papers that do the thing without using the word.** A paper that fuses CT and pathology
   without ever writing "multimodal" is missed; so is a foundation model described only as
   "a large pretrained network".
10. **The 2026 year is partial**, ending at the retrieval date. Already handled in
   `docs/DECISIONS.md` and `docs/figure-spec.md`.
11. **Retracted papers are retained** — 168 of them. See §9.

## 8a. The "mention, not use" bias — for the figure legend

This is the largest single source of error in the classification, it cannot be fixed by any
term list, and it must be stated in the legend rather than repaired.

The validator hand-coded all 158 disagreements between the rules and blind human labels.
**43% of all false positives are "mention, not use":** the rule fires on a term the paper
genuinely contains, but the paper does not *use* that data type. A pathology paper saying
"confirmed by CT" is the canonical case — the term is really there, and a reader asked
"does this paper use CT?" correctly says no.

Two properties make it worth stating precisely rather than apologising for:

1. **It is perfectly one-directional.** 36 false positives, **zero** false negatives. The
   dictionary over-attributes modalities; it never under-attributes them by this route.
   Every count in Panel A is therefore an upper bound on genuine use, not a point estimate,
   and the direction of the bias is known.
2. **It concentrates where a term names an idea rather than a thing.** 10 of 15
   `digital_twins` false positives are of this kind, against 2 of 5 for `ct`. Concrete
   instruments (CT, MRI, PET, ultrasound, mammography) are named when they are used;
   abstractions ("digital twin", "multimodal") are named when they are discussed.

Nothing in a pattern distinguishes "we acquired CT" from "confirmed by CT" reliably at
abstract level, and attempts to do so trade a large recall loss for a small precision gain.
The honest treatment is disclosure: **the legend should say that a modality mark means the
paper's title or abstract indicates that data type, that this over-attributes rather than
under-attributes, and that the bias is largest for the conceptual rows.**

The `genomics` input-only rule in v4 is not an exception to this. It removes one specific,
recognisable idiom — predicting a molecular label from an image — and does not attempt the
general problem.

### Panel A does not mean the same thing in every theme

As of v5 this must be stated plainly in the legend, because the themes no longer share a
definition of what a mark means.

- **Foundation Models, Multimodal Integration, Clinical Applications / FDA Approval** —
  a modality mark means **the work consumes that data type**. The v4 input-only rule makes
  this explicit: prediction targets do not count.
- **Digital Twins** — the row measures **engagement with an idea, not construction of a
  thing**. The author's standard is deliberate: it tracks trends of *interest* in the
  literature, so a review, a framework proposal, and a paper naming digital twins as future
  work all count equally with a working implementation. Of the 56 papers, a hand screen
  found only 18 build something meeting the manuscript's strict criteria.

**The genomics ∩ H&E cell carries a measured precision that belongs in the legend.**
Validation put it at **45% (95% CI 26–66%)** before v6; the v6 prediction-side exclude cuts
the stratum by 10% and removes the reachable part of the cause, but the residue cannot be
fully removed at abstract level (§5, "Version 6"). The legend should state the measured
precision for this cell rather than let a reader assume it matches the well-behaved imaging
rows, which run 85–96%.

So the mention-versus-use bias is a defect in three themes and **the intended measurement in
the fourth**. A reader who assumes one meaning across the panel will misread the digital-twins
row by a factor of roughly three. The legend must say which rows count data and which counts
discussion.

## 9. Open decisions — for the team, not for me

These are judgment calls that change what the figure says. Items 1 and 3 were put to the
author on 2026-09-01 and are now settled; their resolutions are recorded here because the
measurements behind them are part of the strategy. The rest remain open, with a provisional
choice flagged rather than settled.

1. **SETTLED 2026-09-01 — `clinical_fda` means regulatory clearance only.** The author
   chose the narrow reading. The deployment vocabulary is preserved verbatim as a commented
   block inside `config/themes.yaml` so a reversal does not require rediscovering it.

   **Result: 93 papers, 95.7% precise** (4 residual false positives, all drug or biomarker
   approvals discussed inside genuine AI imaging papers). Per year, and split by domain as
   `docs/figure-spec.md` defines it:

   | | '15 | '16 | '17 | '18 | '19 | '20 | '21 | '22 | '23 | '24 | '25 | '26* |
   |---|---|---|---|---|---|---|---|---|---|---|---|---|
   | radiology | 0 | 0 | 1 | 2 | 1 | 3 | 2 | 6 | 5 | 12 | 8 | 24 |
   | pathology | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 1 | 3 | 10 |
   | no modality | 0 | 1 | 0 | 0 | 0 | 1 | 1 | 2 | 4 | 1 | 1 | 5 |

   \* 2026 is partial, through 09-01.

   **Recommendation: plot this cumulatively, not annually.** The annual radiology series
   runs 12 → 8 → 24 across 2024–2026; that dip is sampling noise, not a decline, and a
   reader will read it as one. The annual pathology series is a flat zero for eight
   consecutive years. Cumulative counts are monotone, remove the spurious wiggle, and state
   the review's argument more plainly:

   | | '15 | '16 | '17 | '18 | '19 | '20 | '21 | '22 | '23 | '24 | '25 | '26* |
   |---|---|---|---|---|---|---|---|---|---|---|---|---|
   | radiology (cum.) | 0 | 0 | 1 | 3 | 4 | 7 | 9 | 15 | 20 | 32 | 40 | 64 |
   | pathology (cum.) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 3 | 6 | 16 |

   **Pathology is exactly zero until 2023.** That is the finding, and cumulative plotting
   shows it without inviting a false reading of the year-to-year noise. If the annual form
   is kept instead, the legend must say the counts are small and that single-year changes
   are not interpretable. Sixteen of the 93 papers carry no modality label at all — they are
   regulatory-landscape reviews — so they appear in neither line; the legend should say so.

2. **Retracted publications.** 168 in the corpus, and one surfaced in a 40-record precision
   read. **Provisional choice: retain, since a retracted paper still counts as published
   activity.** Excluding them costs one line, `NOT "Retracted Publication"[pt]`.
   Editorials (467) and comments (381) are a similar question.

3. **SETTLED 2026-09-01 — mammography and radiography split into two rows.** The author
   chose to split rather than pool, because mammographic screening AI (MASAI, PRAIM) is the
   strongest clinical-trial evidence in the review and would be invisible inside a generic
   X-ray bucket. Measured: `mammography` 131 of 3,000 (~1,950 corpus), `xray` 37 of 3,000
   (~550), overlap 2 records. Both count as radiology for the `domain` rule.

4. **Corpus size.** 44,617 is larger than the "thousands" the brief anticipated. It is the
   denominator, not the plotted quantity, and the themes are 0.2%–12% subsets of it.
   Tightening further would cost recall in the pathology categories, which are already the
   smaller side of the figure. **Provisional choice: keep it.**

5. **`ihc` conflates input and label** (§8.5). If Panel A is meant to show what data the
   model consumed, `ihc` overstates. Fixing it needs a classifier that reads the abstract's
   methods, not a term dictionary.

## 10. Reproducing this

```bash
# Corpus count, exactly as stored in config/corpus.yaml
python3 -c "import yaml;print(yaml.safe_load(open('config/corpus.yaml'))['query'])" > /tmp/q.txt
curl -s -X POST "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi" \
  --data-urlencode "db=pubmed" --data-urlencode "term@/tmp/q.txt" \
  --data-urlencode "retmode=json" --data-urlencode "retmax=0" \
  --data-urlencode "datetype=pdat" --data-urlencode "mindate=2015/01/01" \
  --data-urlencode "maxdate=2026/09/01" \
  --data-urlencode "tool=ccr-trends-figure" --data-urlencode "email=ericscrum@gmail.com"
```

On 2026-09-01 this returned `"count":"44617"` with no warnings.
