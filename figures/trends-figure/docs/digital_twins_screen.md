# Digital twins: hand screen of all 64 rule-labeled papers, under two standards

**Date.** 2026-09-02. **Screener.** Agent, reading title and abstract only; no full
texts were fetched. **Input.** The 64 papers with `theme_digital_twins == 1` in
`data/processed/paper_labels.csv`. **Output.**
`data/processed/validation/digital_twins_screen.csv`, one row per PMID carrying both
verdicts, a class, a reason for each verdict, and the pattern that fired.

Every one of the 64 was read and given a reason a co-author can disagree with by name.

**The figure uses the inclusive standard: 56 of 64 papers.** The strict standard is
kept because it answers a different and also publishable question, and because the
gap between the two numbers is itself a finding.

---

## The two standards

### Inclusive — what the figure measures

The author's statement of purpose:

> "This figure is meant to track trends of *interest* in the literature, not
> successful construction of a digital twin."
>
> "I want to include papers that discuss digital twins in any capacity (proposing a
> digital twin framework or a building block for one, etc.)"

The screening question is therefore: **does this paper genuinely engage with the
digital-twin concept?** A review naming digital twins among its future directions
engages. A paper calling its risk calculator a digital-twin framework engages. A
paper in which the letters happen to spell the phrase does not.

**The operational line I applied**, because "a building block for one" has no natural
stopping point if read broadly: *the paper must invoke the digital-twin idea itself,
in the twin vocabulary, not merely supply something a twin would need.* Read the other
way — every longitudinal imaging paper is a building block for a twin — the theme
would swallow a large fraction of the corpus and stop meaning anything. This line is
what separates the two phantom papers below, and it is the one place the new standard
could drift. It should be stated in the codebook if the author agrees with it.

### Strict — what the manuscript claims

From `CCR_reviews/main.tex`, the glossary entry:

> **Digital twin** — A patient-specific mechanistic, data-driven, or hybrid model
> that simulates future states or intervention effects, updates as new measurements
> are taken, and reports uncertainty with a defined clinical action.

And the operative sentence opening the Digital Twins section:

> Following the National Academies framing, a clinical digital twin (DT) is
> patient-specific, is initialized from multimodal patient data, and is built on
> mechanistic, data-driven, or hybrid computation; it simulates future states or
> intervention effects, updates as new measurements arrive, and reports uncertainty
> attached to a defined clinical action. Continuous updating separates a DT from the
> prognostic models described in other sections.

With the exclusion, currently commented out in the same section, that did most of the
work in the strict screen:

> The main risk in this literature is definitional drift: static prognostic models,
> 3D anatomical reconstructions, synthetic patients, and virtual cohorts are
> components of a DT, not instances of one.

`.claude/RULES.md` §5 cites this definition as `main.tex:88-95`. **Those line numbers
have drifted**: the glossary entry is now at lines 131–134 and the section definition
at line 241. The text is unchanged; only the pointer is stale.

**These standards do not compete.** The strict one asks what the field has built; the
inclusive one asks what the field is talking about. The figure asks the second.

---

## Counts

| Verdict | Inclusive | Strict |
|---|---|---|
| `keep` | **56** (88%) | 18 (28%) |
| `borderline` | — | 6 (9%) |
| `undecidable` | — | 1 (2%) |
| `drop` | **8** (12%) | 39 (61%) |

Every strict keep, borderline, and undecidable is an inclusive keep. Of the 39 strict
drops, 31 become keeps and 8 remain drops.

### By class

The class column in the CSV lets any subset be pulled out.

| Class | n | Inclusive | Strict |
|---|---|---|---|
| `builds_or_reviews` | 18 | keep | keep |
| `closing_gesture` | 21 | keep | drop |
| `boundary` | 6 | keep | borderline |
| `rebadged_predictor` | 5 | keep | drop |
| `device_or_clinician_twin` | 4 | keep | drop |
| `phantom_or_virtual_cohort` | 2 | 1 keep, 1 drop | drop |
| `scope_unclear` | 1 | keep | undecidable |
| `term_collision` | 7 | drop | drop |

### By year

| Year | Row total | Inclusive keep | Strict keep |
|---|---|---|---|
| 2019 | 2 | 1 | 0 |
| 2020 | 2 | 0 | 0 |
| 2021 | 2 | 1 | 0 |
| 2022 | 3 | 3 | 1 |
| 2023 | 2 | 0 | 0 |
| 2024 | 4 | 4 | 1 |
| 2025 | 15 | 15 | 7 |
| 2026 (through 1 Sep) | 34 | 32 | 9 |
| **Total** | **64** | **56** | **18** |

---

## What the inclusive standard drops, and why

Only eight papers. Seven are lexical accidents; one is phantom vocabulary that
predates and does not invoke the concept.

### Term collision — 7 papers

The characters match; the idea is absent. None of these authors is discussing digital
twins in any capacity.

- **PMID 31780575** — "DGMate (**DiG**ital t**u**Mor p**A**rame**T**Ers)", a CamelCase
  acronym for a LASSO prognostic score.
- **PMID 36705810** — "digital tumour-associated stroma (Digi-TAS) score."
- **PMID 32935138** — "digital patient files," meaning the hospital's electronic
  records, in an orthopedic *accounting* study.
- **PMID 34206336** — "digital tumor signatures," the authors' own coinage for
  autoencoder latent codes.
- **PMID 37673751** — the "digital avatars" are the *surgeons*, meeting in a virtual
  reality room; the concept under discussion is the metaverse.
- **PMID 41370219** — "patient avatar" is the 3D total-body photograph used as a
  display surface for heatmaps.
- **PMID 42172162** — the authors explicitly disclaim the twin sense: the closed-loop
  terminology "is used in a computational, representation-space sense only."
  "Twin-GRU" names a network component.

### Phantom vocabulary without the concept — 1 paper

- **PMID 32294626** — "digital patient simulations" means voxelized Monte Carlo
  anthropomorphic phantoms for CBCT scatter correction. The authors never use "twin"
  and never invoke the idea; "digital patient" is ordinary dosimetry vocabulary that
  predates the digital-twin literature. Dropped. Note this record is moot in any case:
  it was caught by `\bdigital (patient|tumou?r|avatar)`, removed in v4.

**The other phantom paper is kept.** **PMID 41936288** writes that "each patient was
represented by 75 digital twins with distinct tumoral washout dynamics." That is the
authors reaching for the twin vocabulary to name a per-patient simulated cohort — the
virtual-cohort building block, in their own words. Under the author's standard this is
engagement, and the split between these two papers is exactly the operational line
above: 41936288 invokes the idea, 32294626 only shares a word with it.

### On the four device and clinician twins — kept, and I agree

- **PMID 38438436** — a digital twin *of the pathologist*. vPatho is built and
  critically evaluated as one. This is a deliberate, unusual, and fully conscious
  application of the concept, and it belongs in a figure about interest in the idea.
- **PMID 41829684** — a digital twin of the biopsy robot; **PMID 42533186** — of the
  robotic ultrasound platform; **PMID 42403543** — of magnetic nanorobots for path
  optimization.

The three device twins are the engineering sense of the term, from which the clinical
sense descends. I would keep them, with one reservation the author should weigh: if
the figure's block is read as *clinical* digital twins, three papers modeling machines
rather than patients slightly inflate it. They are 5% of the inclusive count and are
tagged `device_or_clinician_twin` so they can be removed with one filter. My
recommendation is to keep them and say nothing; my second choice is to drop the three
device twins (giving 53) and keep the pathologist twin, which is about a person.

---

## The finding that survives from the strict screen

Under the manuscript's own criteria, **18 of 64 papers build or substantively review
something that meets them.** Under the inclusive standard, **56 of 64 engage with the
concept.** The manuscript can say both, and the sentence is stronger than either
number alone:

> Fifty-six papers in this corpus engage with the digital-twin concept; eighteen
> describe a patient-specific model that simulates future states or intervention
> effects, and far fewer update as measurements arrive.

The evidence for the second half is preserved in `verdict_strict` and `reason_strict`,
and rests on three classes.

**The closing gesture — 21 papers, the single largest class in the row.** A review of
something else names digital twins in a final sentence or a future-directions list.
Five separate reviews (PMIDs 41857437, 41290079, 41787197, 41595166, 41717418) carry a
nearly identical closing list pairing digital twins with federated learning and
explainable AI. PMID 42014628 in *Nature Reviews Cancer* mentions the concept exactly
once, as "the field is advancing toward patient-specific digital twins." These are
real evidence of interest — which is why they are kept for the figure — and they are
not evidence that anything was built.

**Self-identification without the substance — 5 papers.** PMID 41909290 proposes a
"Digital Twin Framework" that is a single-timepoint malignancy probability score with
no patient-level data analyzed. PMID 34305523 titles itself a digital-twin study and
reports Dice and Jaccard scores from an AlexNet segmentation pipeline. PMID 40676342
calls a preoperative kidney mesh for augmented-reality overlay a "geometric digital
twin." These are the drift, documented rather than argued.

**What is actually rare is updating.** Of the 18 strict keeps, only three describe a
model that revises itself as new measurements arrive: PMID 42361838 and PMID 39761649
(daily cone-beam CT re-optimization in radiotherapy) and PMID 42041819 (BrainTwin,
continuous wearable EEG). Independent confirmation comes from inside the row:
PMID 42330729, a scoping review of 64 diagnostic digital twins, finds 97% of models at
conception or operations level and real-time closed-loop feedback rare. The manuscript's
claim that continuous updating is what separates a twin from a prognostic model is
supported by this literature's own systematic reviews.

---

## Confidence

- **High on the inclusive screen.** 56 versus 8 is not a close call anywhere except
  the two phantom papers and the three device twins, all named above. A co-author
  reading these abstracts would reach the same call on at least 59 of the 64.
- **High on the 39 strict drops and on 14 of the 18 strict keeps.**
- **Moderate on the strict boundary.** Six papers sit in a genuine gray zone; the
  strict count is best quoted as "18, or up to 24 on a generous reading."

The inclusive standard is much easier to apply reproducibly, because it asks a
question about the text rather than about the model behind the text. That is a point
in the figure's favor.

---

## The calls I found hardest

Under the inclusive standard the hard set shrinks to five, and the strict-standard
hard set is preserved below it because it supports the second number.

**Inclusive:**

1. **PMID 32294626** — dropped, the only judgment call among the eight drops. If the
   author reads "digital patient" phantoms as a building block, this flips to keep and
   the count becomes 57. The record is moot regardless: its pattern was removed in v4.
2. **PMID 41936288** — kept, the mirror of the above. 75 Monte Carlo variants per
   patient, called twins by their authors.
3. **PMIDs 41829684, 42533186, 42403543** — kept; twins of machines, not patients.
   See the reservation above.
4. **PMID 42172162** — dropped despite "Digital Twin-Inspired" in its title, on the
   strength of the authors' own disclaimer in the abstract. This is the only paper
   where I let a self-identification be overridden, and I did it because the
   overriding statement is the authors'.
5. **PMID 42396189** — was `undecidable` under the strict standard because the
   abstract cannot say how much space digital twins receive. Under the inclusive
   standard that no longer matters and it is a clean keep. The inclusive standard
   dissolves this whole category, which is one of its practical merits.

**Strict** (unchanged, and the reasons remain in `reason_strict`): PMID 40473100 kept
on substance despite a closing-sentence-only mention; PMID 41052882 borderline because
counterfactual individual-treatment-effect estimation satisfies more of the criteria
than any other closing-mention paper; PMID 35310959 borderline as a genuine digital-twin
program that delivers a component; PMID 42472318 the thinnest strict keep; PMID 41909290
dropped despite its title; PMID 35403831 kept on two of six criteria unmet.

---

## Consequence for the figure

**A per-year line is now defensible, with two marks on it.** The inclusive series is:

| 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026* |
|---|---|---|---|---|---|---|---|
| 1 | 0 | 1 | 3 | 0 | 4 | 15 | 32 |

\* through 1 September.

Two things must be said in the legend or the text:

1. **2026 is eight months.** Thirty-two papers in eight months against fifteen in
   twelve is the row's main quantitative claim, and it should be stated as a rate or
   marked partial, not plotted as a completed year. Do not annualize on the figure.
2. **The early years are noise.** Six papers total across 2019–2023, with zeros in
   2020 and 2023 that are produced by one or two lexical accidents landing in a year
   that had nothing else. A zero here means "no paper used the phrase," not "no
   interest existed." Consider starting the line at 2022, or drawing 2019–2021 with a
   visual marker for counts below five.

The shape is a real and clean finding: essentially nothing before 2022, then roughly
fourfold growth in 2025 and again on pace in 2026. That is a trend line worth drawing,
which the strict series (0, 0, 0, 1, 0, 1, 7, 9) was not.

---

## Recall: vocabulary the field uses, from having read the 64

This screen removes papers; it cannot recover missed ones, and the inclusive standard
widens what counts as a miss. Terms rejected against the strict standard deserve
re-measurement against this one. In priority order, with the evidence from these 64:

1. **"patient-specific computational model" — highest priority.** PMID 41823607, a
   systematic review of digital twins in neuro-oncology, states its own inclusion
   criteria as "DT development, validation, or **patient-specific computational
   models** in neuro-oncology." The field's own systematic reviewers treat the two as
   one literature. `config/themes.yaml` records this term as drafted and removed
   because it "added no records the twin terms did not already catch" — that was
   measured on the old pattern set and against the strict standard, and it is the
   single term most likely to change the count now.
2. **"virtual human twin" and "digital patient twin".** PMID 41073794 opens: "'Digital
   twins', also called 'digital patient twins' or 'virtual human twins'." These are
   attested synonyms *inside the corpus*. Note that `\bdigital patient twins?\b` is
   already covered by `\bdigital twins?\b`, but **"virtual human twin" is not**, and it
   is distinct from the "virtual twin" / "computational twin" / "in-silico twin"
   variants that fired zero times and were removed in v2. It is a European Commission
   term of art (the Virtual Human Twin initiative), so it will carry EU-funded work
   that US-centric vocabulary misses.
3. **"in silico trial" and "virtual trial".** PMID 41930301 pairs them directly with
   digital twins — "AI-based simulations, such as digital twins and in silico trials."
   The manuscript's own Digital Twins section treats virtual trials and simulated
   control arms as a principal DT application. Under the inclusive standard these are
   squarely in scope; under the strict one they were correctly excluded as virtual
   cohorts.
4. **"virtual patient", "virtual cohort", "virtual population" — re-measure, expect
   little.** These were measured at 0 of 2 and rejected. The precision judgment was
   made against the strict standard and may reverse, but the *base rate* will not: two
   records in three thousand. Worth one measurement, not more.

**Not recommended**, so the recall agent does not spend reads on them:

- **"virtual replica"** — attested twice in these 64 (PMIDs 42000470, 39435342), but
  both times in the same sentence as "digital twin." Expect zero unique yield. This is
  the same failure mode as the two auxiliary patterns just removed in v4, and the
  lesson generalizes: a phrase used to *gloss* "digital twin" will not find papers that
  do not also say "digital twin."
- **Bare "mechanistic model", "quantitative systems pharmacology", "in silico".** These
  would admit pharmacokinetic and finite-element work wholesale. `config/themes.yaml`
  rejects them for the strict standard, and the operational line above rejects them for
  the inclusive one too: supplying a component a twin would need is not discussing
  digital twins. Admitting them would make the theme unmeasurable.
- **Avatar vocabulary.** Both avatar hits in these 64 were false (surgeons in VR; a 3D
  photograph). The word is used in medicine for any rendering of a person.

One structural observation for whoever tests these. The theme's genuine vocabulary is
**"digital twin" plus a modifier**, and the modifiers are wildly various: medical,
clinical, cognitive, theranostic, generative, optical, geometric, therapeutic,
metabolic, and cancer/patient/tumor twins all appear in these 64. The existing
`\bdigital twins?\b` catches every one of them because the modifier precedes the head
noun. Any replacement pattern must preserve that property.

---

## Files

- `data/processed/validation/digital_twins_screen.csv` — 64 rows: `pmid`, `year`,
  `title`, `verdict_strict`, `verdict_inclusive`, `class`, `reason_strict`,
  `reason_inclusive`, `matched_patterns`.
- This document.

Nothing in `config/`, `docs/DECISIONS.md`, `docs/validation.md`, `CODEBOOK.md`, or any
module was modified.
