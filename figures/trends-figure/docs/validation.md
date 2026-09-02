# Classifier validation

How accurate the rule-based classifier is, measured twice against independently
labeled samples, and what the figure legend may therefore claim.

**Three rounds.** Round one measured `config/*.yaml` **v2** (seed 20260902,
200 papers) and found seven defects, all fixed. Round two measured **v3** on a
**fresh sample with a fresh seed** (20260903, 200 papers), because the v3
patterns were written after reading round one's papers: that sample had been
fitted to and could no longer measure the dictionary. Round three measures
**themes v5 / modalities v4** (seed 20260904) as a **targeted** draw — 106
papers across only the categories a v4/v5 change touched, none of them read in
an earlier round.

**Read improvements between rounds carefully.** They are partly the fixes and
partly a fresh draw. Where a change is large and the mechanism is identified —
foundation models in round two — the fix is the explanation. Where a change is
small and the intervals overlap, the sample moved and nothing else can be
concluded.

**Round three measures precision only.** Every one of its strata is
rule-positive, so it contains no paper the rules called negative and recall is
not estimable from it. Round two's recall figures stand as the most recent
estimates.

**The digital-twins row is judged against a different question from every other
row.** The author's standard, approved 2026-09-02: *this row tracks trends of
interest in the literature, not successful construction of a digital twin.* The
operational line is that **the paper must invoke the digital-twin idea itself,
in the twin vocabulary, and not merely supply something a twin would need**. A
review naming digital twins among its future directions is a true positive. A
finite-element tumour simulation that never uses twin vocabulary is a true
negative. Round two scored that row against the wrong question — "does this
paper build a digital twin" — and its 40% is void. Round three re-measures it.

---

## For the author: the 50-abstract audit

**File.** `data/processed/validation/round2-v5/audit_sheet.csv`. Fifty rows,
built from the **current** labels (themes v5, modalities v4).

**Two earlier sheets are superseded and must be discarded.** The round-one sheet
was never sent. The round-two sheet was sent and then went stale within the hour
when the dictionaries moved to v4 and v5, so some of its `rule_*` columns are
wrong. The current sheet shares 37 of its 50 rows with that one, so work already
done on those rows carries over; the abstracts and the agent's labels never
changed. The superseded sheets are kept at `round1/` and `round2/` for the
record.

Open it in Excel, Numbers, or a text
editor; it is plain CSV with a `#` provenance header that spreadsheet readers
will show as seven leading rows. Delete them if they get in the way — nothing
downstream needs them.

**Time.** Budget an hour. The rows differ in cost: the twenty-five `random`
rows take under a minute each, because most need only a nod; the twenty-five
`disagreement` rows take two or three minutes each, because each asks you to
settle a specific split between two labelers.

**Do this.** For each row, read `title` and `abstract`, then fill four columns:

| Column | What to put in it |
|---|---|
| `author_themes` | The themes the paper belongs to, as keys joined by `+`, or `(none)`. Keys: `foundation_models`, `multimodal_integration`, `digital_twins`, `clinical_fda`. |
| `author_modalities` | The modalities the paper **uses**, same format. Keys are the fifteen in `docs/figure-spec.md`. |
| `author_verdict` | One word: `rule`, `agent`, `both`, or `neither` — whose labels you agree with. On a `random` row where both already agree, `both`. |
| `author_note` | One line, only where it is not obvious. Especially where you think both labelers are wrong. |

The fastest way to fill the first two columns is to copy `rule_modalities` or
`agent_modalities` across and edit it, rather than typing the keys out.

**Read the abstract before the two label columns.** They are in the file
because the disagreement rows are unreadable without them, not because they are
a starting point. Anchoring is the failure mode this whole exercise is built to
avoid.

**Three definitions decide most of the hard rows.** They are the project's, not
the labelers':

- **`clinical_fda` means regulatory clearance, not clinical deployment.** A
  paper counts when it reports that an AI device holds, or is being assessed
  for, FDA clearance, CE marking, 510(k), or an equivalent. A paper that merely
  argues AI should reach the clinic does not. Approval of a *drug* or an *assay*
  does not count. (`docs/DECISIONS.md`, 2026-09-01.) The agent labeled against
  this narrow definition in both rounds, not against the row's display label
  "Clinical Applications / FDA Approval", which invites an order-of-magnitude
  over-call. This is worth confirming rather than assuming: the theme is the
  best-performing one in both rounds, which is what you would expect from a
  narrow definition applied consistently, and not what you would see if the
  labeler had read the display label instead.
- **A modality counts when the paper uses that data, not when it names it.**
  "Patients had limited access to CT" is not a CT paper. `pathology_report` and
  `radiology_report` are **text** modalities: the paper must process the report,
  not cite it.
- **A theme counts when the paper is about it, not when it mentions it.** A
  review whose last sentence says the field is "advancing toward digital twins"
  is not a digital-twins paper.

Where you cannot decide, write `uncertain` in `author_verdict` and say why. A
recorded doubt is data; a coin flip is noise.

**Two columns you can ignore unless curious.** `agent_uncertain` marks the 95
of 200 papers where the agent's call was a judgment another careful reader could
reverse; `agent_note` says what the judgment was.

**One column was relabelled, and not blind.** Every label in the sheet is the
original blind round-two label except `theme_digital_twins`, which was
relabelled against the v5 inclusive standard after the v3 scoring was already
known. That was done so the sheet would not ask you to adjudicate twelve
disagreements that are artifacts of the superseded rubric. The blind
measurement of the new standard is round three, below.

**Never average the two halves.** `audit_stratum` marks which half a row came
from. The `random` half estimates how often you and the agent agree at all; the
`disagreement` half is deliberately enriched for conflict and would drag any
pooled percentage down by construction. Report them apart.

When the sheet comes back, the other two comparisons — rules against your
labels, agent against your labels — are computed by the same functions with the
labelers swapped (`agreement_table(joined, keys, system_prefix="agent_",
reference_prefix="author_")`). There is no CLI subcommand for it yet, because
there is nothing to run it on; the agreement section below is missing two of its
three tables until then.

---

## The design

Four themes ranging from 64 papers to 4,921, and fifteen modalities from 226 to
12,566. A simple random sample of 200 would carry roughly 0.3 digital-twin
papers and 0.4 clinical/FDA papers. So both samples are stratified, on the same
plan.

A paper joins the **first** stratum it qualifies for and no other, so the strata
partition the corpus and the weights are well defined. Rarity sets the order.

| Stratum | Definition | Round 2 population | Sampled | Weight | (Round 1 population) |
|---|---|---|---|---|---|
| `digital_twins` | rule label `digital_twins` | 64 | 25 | 2.6 | 64 |
| `clinical_fda` | rule label `clinical_fda` | 94 | 25 | 3.8 | 94 |
| `rare_modality` | any of spatial proteomics, spatial transcriptomics, pathology report, radiology report, radiography | 1,876 | 20 | 93.8 | 1,885 |
| `foundation_models` | rule label `foundation_models` | 882 | 40 | 22.1 | 1,165 |
| `multimodal_integration` | rule label `multimodal_integration` | 4,385 | 40 | 109.6 | 5,174 |
| `no_theme` | none of the above | 37,232 | 50 | 744.6 | 36,151 |
| **Total** | | **44,533** | **200** | | 44,533 |

The `no_theme` stratum is the one that makes recall measurable. A sample drawn
only from papers the rules already labeled can measure precision and can never
find a false negative.

**Blind labeling.** In both rounds the agent read `blind_sheet.csv`, which
carries the item number, the PMID, the title, and the abstract. No rule label,
no stratum, no weight, and the row order shuffled from the same seed so that
position carries nothing either. The labels were written out in full and only
then joined to the rule labels. `tests/test_validate.py` asserts that the blind
sheet has exactly those five columns.

Two papers in the round-two sample have no abstract; both are notices — a
retraction and a correction — labeled from the title and flagged.

---

## Agreement: rounds one and two (v2 and v3)

The rules are the system under test; the agent's labels are the reference.
**TP** = both said yes, **FP** = rules only, **FN** = agent only. Counts are
papers in the 200-paper sample. Intervals are 95% Wilson score intervals; they
cover sampling error only, not the risk that the reference labels are wrong.

### Themes

| Theme | TP | FP | FN | Precision (95% CI) | Recall (95% CI) | v2 precision |
|---|---|---|---|---|---|---|
| Foundation Models | 41 | 5 | 0 | **89% (77–95%)** | 100% (91–100%) | 59% |
| Multimodal Integration | 43 | 21 | 24 | 67% (55–77%) | 64% (52–75%) | 64% |
| Digital Twins | 10 | 15 | 0 | **40% (23–59%)** | 100% (72–100%) | 68% |
| Clinical Applications / FDA | 24 | 1 | 0 | **96% (80–99%)** | 100% (86–100%) | 92% |

Three recall figures of 100% are weaker than they look. The two small themes
were sampled at 25 of 64 and 25 of 94, and the search for false negatives ran
over only 50 no-theme papers standing for 37,232. **No false negative was found;
that is not the same as none existing.**

### Modalities

| Modality | TP | FP | FN | Precision (95% CI) | Recall (95% CI) | v2 prec. / rec. |
|---|---|---|---|---|---|---|
| H&E / Histology | 37 | 5 | 10 | 88% (75–95%) | 79% (65–88%) | 86% / 79% |
| IHC | 3 | 3 | 2 | 50% (19–81%) † | 60% (23–88%) † | 57% / 100% |
| Spatial Proteomics | 2 | 1 | 0 | 67% (21–94%) † | 100% (34–100%) † | 25% / 33% |
| Spatial Transcriptomics | 5 | 0 | 1 | 100% (57–100%) † | 83% (44–97%) † | 100% / 100% |
| Pathology Report | 2 | 0 | 2 | 100% (34–100%) † | 50% (15–85%) † | 100% / 100% |
| MRI | 44 | 2 | 1 | 96% (85–99%) | 98% (88–100%) | 92% / 96% |
| CT | 39 | 5 | 0 | 89% (76–95%) | 100% (91–100%) | 88% / 98% |
| PET | 13 | 0 | 0 | 100% (77–100%) | 100% (77–100%) | 96% / 96% |
| Ultrasound | 11 | 2 | 1 | 85% (58–96%) | 92% (65–99%) | 85% / 94% |
| Mammography | 9 | 1 | 0 | 90% (60–98%) † | 100% (70–100%) † | 94% / 100% |
| Radiography (X-ray) | 7 | 1 | 1 | 88% (53–98%) † | 88% (53–98%) † | 100% / 100% |
| Radiology Report | 5 | 0 | 3 | 100% (57–100%) † | 62% (31–86%) † | 100% / 50% |
| Genomics / Transcriptomics | 21 | 7 | 1 | **75% (57–87%)** | 95% (78–99%) | 93% / 76% |
| Clinical / EHR Data | 29 | 6 | 18 | 83% (67–92%) | **62% (47–74%)** | 89% / 41% |
| Other (composite) | 39 | 8 | 11 | 83% (70–91%) | 78% (65–87%) | 86% / 73% |

**† fewer than ten papers on one side. Read the fraction and the interval, not
the percentage.** Spatial proteomics rests on three rule-positive papers and
pathology report on two. Those rows say almost nothing, and the honest response
is to say so. The intervals make the point without argument: IHC's precision is
50%, and the data are equally consistent with 19% and with 81%.

### The two routes to `other`, scored apart

`other` reaches a paper two ways and they mean opposite things. A **pattern**
match is a positive claim: this paper uses a data type outside the fifteen named
rows. The **fallback** is an admission: no named modality was found. In the
corpus the split is 4,470 by pattern against 5,020 by fallback, so a pooled
figure is half a claim and half an absence of one, and means nothing.

| Route | Claim | Correct | 95% CI |
|---|---|---|---|
| pattern | uses a data type outside the named rows | 21 of 23 | 91% (73–98%) |
| fallback | no named modality could be identified | 18 of 24 | 75% (55–88%) |

The pattern route is trustworthy. The fallback is right three times in four:
in six of the 24 papers the agent could name a modality that the rules could
not — usually a review that says "digital pathology" or "pathology reports"
without any phrase the dictionary covers. **In the figure, `other`-by-fallback
should be read as "not determined", and the two routes should not be summed into
one bar without saying what the sum contains.**

### Whole-label-set agreement

All nineteen labels identical, per stratum. A strict test: one modality apart
and the paper counts as a mismatch.

| Stratum | Round 2 | Round 1 |
|---|---|---|
| `clinical_fda` | 16 of 25 (64%) | 13 of 25 (52%) |
| `foundation_models` | 20 of 40 (50%) | 11 of 40 (28%) |
| `multimodal_integration` | 18 of 40 (45%) | 8 of 40 (20%) |
| `no_theme` | 29 of 50 (58%) | 35 of 50 (70%) |
| `rare_modality` | 8 of 20 (40%) | 5 of 20 (25%) |
| `digital_twins` | 6 of 25 (24%) | 8 of 25 (32%) |
| **Overall** | **97 of 200** | 80 of 200 |

Total individual label disagreements fell from 175 to 158.

---

## Did each round-two fix work? (v2 -> v3)

Seven changes shipped in v3. Each is checkable, and each is checked.

**1. `self-supervised` dropped from foundation models — worked, and it was the
single largest defect in the dictionary.** In round one that one pattern caused
12 of the theme's 19 false positives. In round two **not one false positive
comes from self-supervised learning**, and theme precision rose from 59% (27 of
46) to **89% (41 of 46)**. The intervals do not overlap. The corpus count fell
1,529 → 1,226 as predicted.

**2. `zero-shot` and `few-shot` also dropped — no measurable cost, on a small
test.** This went beyond the reported defect and was flagged for testing. Four
papers in the round-two sample use those phrases. All four are genuine
foundation-model papers, and **all four were still caught by other patterns**
(the LLM, GPT and named-model patterns). Theme recall is 41 of 41, 100%
(91–100%). Four papers is a thin test; what can be said is that no cost was
found and the interval bounds the cost at under 9% of the theme.

**3. `LMM` and `PRISM` removed — collisions gone.** Neither alternation appears
in any round-two hit, and none of the five remaining foundation-model false
positives is an acronym collision. The broadened
`large (language|vision|multi-modal(ity)?) models?` did its job: no recall loss
appeared.

**4. `imaging mass spectrometry` moved to `other`, `secondary ion mass
spectrometry` added — half-tested, and a new collision appeared.** The bad
pattern is gone and caused no false positives. The added pattern could not be
tested: no such paper was drawn. Meanwhile the row acquired a **new, exactly
analogous collision**: `\bMIBI\b` fired on **"99mTc-MIBI scintigraphy"**
(PMID 35182328) — sestamibi, a nuclear-medicine tracer, not multiplexed ion beam
imaging. That is one false positive on a base of three.

**5. Fusion patterns constrained and a context-aware multiparametric-MRI
exclusion added — no measurable improvement.** Multimodal precision moved from
64% to 67% and recall from 69% to 64%; every interval overlaps. The corpus count
fell 5,794 → 4,921 as designed, but **11 of the 21 remaining false positives are
still intra-modality or architectural fusion**. Two mechanisms defeat the new
exclusion:

- It requires the literal phrasing "multimodal MRI". PMID 42096391 writes
  "Multi-modal deep learning methods, which integrate features from multiple
  magnetic resonance imaging (MRI) sequences" — the words are all there, in the
  wrong order, and the exclusion does not fire.
- It cannot fire when MRI is never named. PMID 40932804 is titled "…for
  Multi-Modal Brain Tissue and Tumor Extraction" and says only "different
  imaging modalities".

Two further families are untouched: `intermediate fusion` of DCE-MRI phases
(PMID 38637240), which the v3 term-of-art list explicitly admits, and
"multimodal" in senses that are not data at all — a storage platform's
"multi-modal pathology data" (PMID 37350884), a cognitive-neuroscience paper's
"multimodal systems, such as working memory" (PMID 25848923).

**6. `clinical_data` broadened — recall bought at a measured price.** Recall
rose from 41% (17 of 41) to **62% (29 of 47)**, the largest recall gain in the
dictionary. Precision fell from 89% to 83%, a little more than the 96% → 94%
that was predicted. **Four of the six false positives come from the three new
v3 patterns**: `clinical (model|score|signature)` on a comparator model,
`radiomics? nomogram` on a bare nomogram — including one that fired on a
**retraction notice** whose only text is the retracted title (PMID 38188730) —
and `clinicopathologic\w*\s+(data|variable|parameter)` on parameters used for
correlation rather than as inputs. The trade is real and, at this size,
reasonable. The corpus count rose 3,825 → 6,248, which is a 63% increase for a
21-point recall gain; that ratio deserves a look before the figure is final.

**7. `TCGA` qualified — worked cleanly.** Ten round-two papers name TCGA. In the
four where TCGA supplies *slides only*, genomics is correctly **off** in all
four. In the five where real molecular data is used, it is correctly **on**.
Agreement on TCGA papers is 9 of 10, and the single miss is a definitional case,
not a leak.

**But genomics precision fell, 93% → 75%, for an unrelated reason.** Of the
seven false positives, four are papers that *predict* a molecular label from an
image — EGFR status from histology, MGMT methylation from MRI, mutations from
whole-slide images. The agent counts `genomics` when molecular data is generated
or used, and not when a mutation is merely the outcome being predicted; the
rules count `mutation status` and `methylation` either way. That is a definition
the project should settle, not a defect. Two more are `radiogenomic` firing where
no genomic data exists, and one is bare `genomic` matching **"genomic
instability"** (PMID 41667716) — a biological concept, not a data type.

---

## Why they disagree (round two)

Every one of the 158 disagreements was read and coded into exactly one cause,
in `data/processed/validation/round2/disagreement_causes.csv`. The coding is a
judgment, recorded per line so a reader can disagree with a specific one.

| Cause | FP | FN | Total | Share |
|---|---|---|---|---|
| `rule_gap` — the paper does it in words no pattern covers | 6 | 73 | 79 | 50.0% |
| `mention_not_use` — the term is there, the paper does not do it | 36 | 0 | 36 | 22.8% |
| `term_defect` — the pattern matched something lexically different | 23 | 0 | 23 | 14.6% |
| `definition_boundary` — both readings defensible | 17 | 2 | 19 | 12.0% |
| `agent_error` — the reference label was wrong | 1 | 0 | 1 | 0.6% |

**The mention-versus-use number.** It was predicted to be the dominant axis of
disagreement and to bias the rules toward over-calling uniformly. Measured:

- **43% of all false positives (36 of 83)** are mention-not-use. It is the
  largest single cause of over-calling, ahead of term defects at 28%.
- **It is perfectly one-directional: 36 false positives, 0 false negatives.**
  The prediction of a uniform over-calling bias is confirmed exactly.
- **It is not the largest cause of disagreement overall.** Recall gaps are, at
  50%. The rules miss more than they over-call, because most of the vocabulary
  is deliberately narrow.
- **22.8% of all disagreement is mention-versus-use, and no edit to a term list
  can remove it.** Distinguishing "we used CT" from "CT was unavailable"
  requires reading the sentence's argument role, which regex cannot do.

It concentrates where the vocabulary is a *concept* rather than a *thing*:
10 of the 15 digital-twin false positives and 9 of the 21 multimodal ones, against
2 of 5 for CT and 1 for mammography. A term naming a data type is mostly used by
papers that use that data. A term naming an idea is used by every paper that
would like to.

Term defects concentrate differently — 11 of 23 in multimodal integration,
where "fusion" and "multimodal" are terms of art in two unrelated senses.

**The digital-twins number moved the wrong way, and it is not a regression.**
Precision fell from 68% (17 of 25) to 40% (10 of 25) on a category whose patterns
did not change. Three of the fifteen false positives are genuine new term
defects, all from `(?i)\bdigital (patient|tumou?r|avatar)`:

- **"DGMate (DiGital tuMor pArameTErs)"** — a CamelCase acronym (PMID 31780575).
- **"digital tumour-associated stroma (Digi-TAS) score"** (PMID 36705810).
- **"digital patient files"**, in a hospital-accounting paper about smartphone
  wound photography (PMID 32935138).

The other twelve are the same class round one found: ten papers whose closing
sentence gestures at digital twins, and two where the authors' own usage is
figurative — 75 Monte Carlo phantom variants called "digital twins"
(PMID 41936288), and a digital twin of a **robot** (PMID 41829684). The
difference between rounds is which 25 of the 64 papers were drawn, plus a
labeler applying the "closing clause does not count" rule more consistently the
second time. The intervals (48–83% and 23–59%) barely overlap, so the two rounds
are not comfortably reconciled; the safe reading is that **roughly half of the
64-paper digital-twins row is not digital-twins literature**, and the exact
fraction is not pinned down by 50 papers across two draws.

---

## Round three: the targeted re-measurement

Seven more changes shipped as **modalities v4** and **themes v5**. A full
200-paper draw would have been disproportionate, so round three samples only the
categories a change touched: 106 papers, six rule-positive strata, seed
20260904, none of them read in rounds one or two. Every paper was judged on all
five affected categories, because being told which category a paper was drawn
for would have revealed its rule label.

| Stratum | Population | Sampled | Weight |
|---|---|---|---|
| `digital_twins` | 20 | 20 | 1.0 |
| `spatial_proteomics` | 320 | 14 | 22.9 |
| `genomics` ∩ `he_histology` | 853 | 20 | 42.6 |
| `genomics` alone | 2,729 | 12 | 227.4 |
| `multimodal_integration` | 3,198 | 20 | 159.9 |
| `clinical_data` | 4,533 | 20 | 226.7 |

### Precision, and the trajectory across the three rounds

| Category | v2 (round 1) | v3 (round 2) | v5/v4 (round 3) | 95% CI |
|---|---|---|---|---|
| Digital Twins | 68% (17/25) † | 40% (10/25) † | **100% (20/20)** | 84–100% |
| Genomics ∩ histology | — | — | **45% (9/20)** | 26–66% |
| Genomics alone | 93% (25/27) | 81% (21/26) | **58% (7/12)** | 32–81% |
| Multimodal Integration | 64% (44/69) | 67% (43/64) | **55% (11/20)** | 34–74% |
| Clinical / EHR Data | 89% (17/19) | 83% (29/35) | **85% (17/20)** | 64–95% |
| Spatial Proteomics | 25% (1/4) | 100% (2/2) | **93% (13/14)** | 69–99% |

**† measured against the wrong question.** Rounds one and two judged the
digital-twins row against "does this paper build a digital twin". The author's
standard is "does the literature engage with the idea". Those two numbers should
be struck, not compared.

**The genomics rows are not comparable across rounds either.** Round three
deliberately over-samples the genomics ∩ histology co-occurrence, which is the
hardest case. Its 45% is a measurement of that co-occurrence, not of the row.

### Did each change work?

**`genomics` restricted to input use — the residue is not a curiosity.** The
change was known to leave one residue: a paper that predicts a molecular label
from an image, and mentions the sequencing behind its ground-truth labels,
survives the rule. Measured: **9 of the 18 genomics false positives are exactly
that case**, and they concentrate where predicted. In the genomics ∩ histology
stratum, **8 of 11 false positives are residue** and precision is 45% (26–66%).
Applied to that stratum's 853 papers, roughly **half the genomics + H&E pairing
is spurious** — 300 to 630 papers, on the interval. That pairing is precisely
the imaging-plus-molecular combination Panel A is read for, so this is not
cosmetic. The remaining nine false positives are ordinary mention-not-use: bare
`genomic` in "genomic variation is a motivation", `radiogenomic` where no
molecular data exists, `multi-omics` in a future-work clause.

The `(?!\s+instabilit)` guard added in v4 works: "genomic instability" no longer
fires.

**`MIBI` removed — the collision is gone.** Re-scoring the round-two sample
against v5 turns spatial proteomics from 2/3 into 2/2, and round three measures
the row properly for the first time: **13 of 14, 93% (69–99%)**. The single
false positive is a different sense of the term — TRANSPIRE (PMID 32401031)
analyses *subcellular* protein localisation by fractionation mass spectrometry
and calls it "spatial proteomics". No tissue is imaged. That is a boundary the
project may want to state rather than a defect.

**`following` dropped from the possession verbs — the false positive is gone.**
Re-scoring round two against v5, `clinical_fda` goes from 24/25 to **24/24,
100% (86–100%)**. "Following regulatory approval, 123 LDCT examinations…" no
longer fires.

**`clinical risk factors` tightened — precision held.** 85% (64–95%) in round
three against 83% in round two. The corpus row fell 6,248 → 6,127. No change is
demonstrable at this sample size, which is the honest reading.

**The multiparametric-MRI exclusion was rewritten, and it is structurally
narrow.** Multimodal precision is 55% (34–74%) against round two's 67%; the
intervals overlap and no change is demonstrable. The mechanism is measurable and
worth stating exactly. The v4 exclusion requires the abstract to name **both** a
T1-family and a T2-family sequence:

- 3,452 corpus records match `multi-modal` or `cross-modal`.
- Only **245 of them (7.1%) name both a T1 and a T2 sequence**. On the other
  92.9% the exclusion cannot fire at all.
- Of those 245, 161 are blocked by a context token and **84 are excluded** — 2.4%
  of the candidates.

So the rewrite catches papers that spell out their sequences and misses the
commonest false positive, which does not. PMID 42135350 is the type specimen:
"Brain tumor segmentation from **multi-modal MRI scans**", four BraTS sequences,
no sequence named, no other data type — exactly the paper the exclusion was
built for, and it is untouched.

**A latent defect in the same exclusion, small today.** Its context list carries
two acronyms that are not protected against case-insensitive matching: `SPECT`
matches "retro**spect**ive" and "re**spect**ively", and `CT\b` matches the "-ct"
ending of "predi**ct**", "subje**ct**", "aspe**ct**". Corpus-wide, `(?i)SPECT`
matches 51% of records and `(?i)CT\b` matches 64%, against 0.4% and 25% for the
case-sensitive forms. Today the cost is small — 24 of the 161 blocked records
contain such a match and only 2 are blocked solely by them — because the
sequence-pair requirement is the binding constraint. It matters because the
moment anyone loosens that requirement, the exclusion will silently stop firing.
This is the same class of defect the project has measured repeatedly for CT,
PET and IHC; it has reappeared inside an exclusion's context list, where nobody
was looking.

**`early/late/intermediate fusion` removed — no measurable effect.** No round-three
false positive comes from a fusion term. The remaining thirteen are
`multi-modal` and `multi-omics` matching prose: a "multimodal human-machine
interface" (voice and augmented reality), "the multimodality of the acquired
images" as an opening flourish, "multimodality imaging" describing a diagnostic
workup, grayscale-plus-Doppler ultrasound, and future-work clauses.

### Digital twins: a census, not a sample

The v5 row is 56 papers and the three rounds have now read **all 56** under the
inclusive standard — 20 blind in round three, 22 relabelled from round two, 14
from round one.

**56 of 56 invoke the digital-twin idea in twin vocabulary. Precision 100%
(94–100%).** On the 20 papers read blind, with no knowledge of the rule label,
20 of 20 (84–100%).

This confirms the hand screen's "56 keep" independently. It should be read for
what it is: the v5 row is defined by one pattern matching the twin vocabulary,
and the standard is defined as genuine use of that vocabulary, so the two are
close to tautological. The only way they could diverge is on **non-twin uses of
the words**, and v5 removed exactly those by dropping
`digital (patient|tumou?r|avatar)`. Round two found three such papers and all
three are now correctly out: "DGMate (**DiGital tuMor** pArameTErs)",
"**digital tumour**-associated stroma", and "**digital patient** files" in a
hospital-accounting study.

**Recall was probed too, and it is clean.** "virtual twin", "in-silico twin" and
"computational twin" match **zero** corpus records, confirming the v2 removal
decision. "patient avatar", "digital avatar" and "virtual human" match five
records between them; all five were read and none is a digital-twin paper — they
are 3D anatomical renderings and digital-anatomy reviews. No genuine twin paper
is being missed by the single shipped pattern.

Two papers are worth flagging to the author as boundary cases the standard does
not settle: PMID 41829684 uses twin vocabulary for a twin of **a robot**, and
PMID 38438436 for a twin of **a pathologist**. Both invoke the idea in the
vocabulary, so both count under the operational line; neither is a patient twin.

---

## What the legend may claim

Defensible, in this form:

> Labels were assigned by regex matching against title and abstract
> (`config/themes.yaml` v5, `config/modalities.yaml` v4). Accuracy was measured
> on stratified samples of abstracts labeled blind by a language model and
> calibrated against an author audit of 50 of them. Against those labels the
> rules reached 100% precision for the clinical/FDA theme (24 of 24 papers),
> 89% for foundation models (41 of 46), 85–100% for CT, MRI, PET, ultrasound and
> mammography, 93% for spatial proteomics (13 of 14), and 55% for multimodal
> integration (11 of 20), whose false positives are papers using "multimodal" in
> a sense other than combining data types. Every one of the 56 papers in the
> digital-twins row was read: all 56 invoke the digital-twin idea, which is what
> that row is defined to track. These are per-category rates on stratified
> samples, not a corpus-wide accuracy, and the reference labels are not a
> hand-labeled gold standard.

**Wording for the `other` row, which the legend must carry.** `other` reaches a
paper two ways and they mean opposite things, so the row cannot be presented as
one quantity:

> The `Other` row combines two different assignments. A pattern match (4,470
> papers) is a positive finding: the paper uses a data type outside the fifteen
> named rows — endoscopy, dermoscopy, dosimetry, mass spectrometry, ECG and the
> like. The remaining 5,041 papers are a **fallback**: no named modality could be
> identified from the title and abstract, so the modality is **not determined**
> rather than "other". Validation scored the two apart: the pattern route was
> correct in 21 of 23 sampled papers (91%, 95% CI 73–98%), the fallback in 18 of
> 24 (75%, 55–88%), the six errors being papers whose modality a reader could
> name and the dictionary could not. Readers should not sum the two into a single
> count of papers using an unlisted data type.

Not defensible, and none of it should appear:

- **A single accuracy number.** There is no such quantity. Precision runs from
  45% to 100% across categories, and the strata are not proportional to the
  corpus, so nothing legitimately averages.
- **"Validated against a gold standard."** The reference is one agent's reading
  of abstracts, checked on 50 by the author. `docs/DECISIONS.md` requires the
  legend to say so.
- **Any rate for IHC, spatial transcriptomics, pathology report, radiography or
  mammography.** Two to ten papers each. Say the rows exist and that the sample
  could not measure them.
- **A recall claim for the two small themes.** Zero false negatives found in a
  50-paper window onto 37,232 unlabeled papers bounds the false-negative rate
  loosely and no more. Round three measures precision only.
- **Corpus-wide projections from the weights.** See below.
- **Any improvement claim for multimodal integration.** Precision has moved
  within its interval across three rounds and nothing has been demonstrated.
- **The digital-twins precision figure as evidence the row is well built.** It is
  100% because the row's single pattern and the standard both key on the same
  vocabulary. It shows the pattern implements the standard; it does not show the
  standard is the right one. That is the author's call.

Two consequences belong in the manuscript rather than the legend. **Roughly half
the genomics + H&E co-occurrence is spurious** — 300 to 630 of those 853 papers —
because a paper predicting a molecular label from a slide still counts as using
genomics. And **`clinical_data` under-counts by about a third** even after the
v3 broadening.

---

## The weighted projections, and why they are not the headline

Each stratum has a known population and a known sample size, so a sampled paper
stands for between 2.6 and 745 corpus papers, and the strata partition the
corpus. Weighted precision and recall are therefore unbiased estimates of
corpus-wide values, and they sit in `agreement_themes.csv` and
`agreement_modalities.csv` as `est_precision` and `est_recall`. **Their variance
is severe, and round one proved it.**

The same weights, applied to the rule labels alone, estimate a quantity already
known exactly: how many corpus papers carry each label. In round one the median
absolute error of that estimate was 19% and the worst was **+106%** (PET,
3,325 papers estimated at 6,856). The four themes came out near-exact, because
the theme strata *are* the theme populations; the modalities, which cut across
strata, did not.

**Read the raw sample counts and their intervals. The weighted estimates are a
sanity check, not a result.**

---

## What I would change now

`config/*.yaml` has one owner, per `docs/DECISIONS.md` (2026-09-01), so this is
a recommendation. In descending order of measured return against **v5/v4**, and
all needing re-measurement after the change:

1. **Qualify `mutation (status|profil|burden)`, `methylation`, `(gene signature|
   genetic alteration)` and the TCGA pattern so that a *predicted* molecular
   label does not count as using genomic data.** This is the largest measured
   defect in the current dictionaries: 9 of 18 genomics false positives, and it
   inflates the genomics + H&E co-occurrence — the very pairing Panel A is read
   for — by roughly half of its 853 papers. The construction that would work is
   the one already used elsewhere: require an input verb near the molecular
   noun ("sequencing was performed", "RNA-seq data were used") and exclude the
   prediction frame ("predict ... from", "inferred from", "directly from H&E").
2. **Rewrite the multiparametric-MRI exclusion to fire without sequence names.**
   It currently reaches 2.4% of multimodal candidates because 93% of them never
   name a T1 and a T2 sequence. Keying on "multi-modal/multi-parametric" within
   a few words of "MRI/magnetic resonance", with the same no-other-data-type
   guard, would cover the common wording; the sequence-pair test can stay as a
   second route.
3. **Protect `SPECT` and `CT\b` in that exclusion's context list against
   case-insensitive matching.** They match "retrospective" and the "-ct" ending
   of ordinary words. The cost is small today only because the sequence-pair
   requirement is the binding constraint; fix it before recommendation 2 removes
   that constraint and the exclusion silently stops firing.
4. **Decide whether subcellular "spatial proteomics" belongs in the imaging
   row.** Organelle-fractionation mass spectrometry uses the same phrase for a
   different thing and supplies the row's only false positive.
5. **Constrain `multi[- ]?modal` against the non-data senses.** "Multimodal
   human-machine interface", "multimodality imaging" describing a workup, and
   "the multimodality of the acquired images" account for most of what remains.
   A negative lookahead on `interface|human-machine|analgesi` and a requirement
   that a second data type be named would address them.
6. **Consider dropping bare `genomic`.** Four round-three false positives are
   the bare adjective in prose that uses no genomic data.

What I would *not* change: the mention-versus-use problem. It was 43% of all
round-two false positives and no term list fixes it. The only remedies are
reading the full text or accepting a model call at classification time, and
`docs/DECISIONS.md` rules the second out.

Two questions for the author rather than the dictionary owner:

- The digital-twins row now counts papers that **invoke** the idea, including in
  a closing sentence. That is the approved standard. The manuscript should say
  so explicitly, because a reader will otherwise take 56 papers to mean 56
  digital-twin studies.
- Two papers in the row apply twin vocabulary to a **robot** and to a
  **pathologist** rather than to a patient. Both satisfy the operational line.
  If the row is meant to be patient twins, the line needs one more clause.

---

## Reproducing this

```bash
# Refresh an already-labeled sample after the dictionaries move (v3 -> v5)
~/.venvs/ccr-trends/bin/python -m trends.validate score \
    --sample data/processed/validation/round2/sample.csv \
    --agent  data/processed/validation/round2-v5/agent_labels.csv \
    --labels data/processed/paper_labels.csv \
    --output data/processed/validation/round2-v5/

# 1. Draw the sample and the blind sheet (seed 20260903 for round two)
~/.venvs/ccr-trends/bin/python -m trends.validate sample \
    --output data/processed/validation/round2/

# 2. Label blind_sheet.csv into agent_labels.csv, reading nothing else

# 3. Score, including the two `other` routes and the cause coding
~/.venvs/ccr-trends/bin/python -m trends.validate score \
    --sample data/processed/validation/round2/sample.csv \
    --agent  data/processed/validation/round2/agent_labels.csv \
    --causes data/processed/validation/round2/disagreement_causes.csv \
    --output data/processed/validation/round2/

# 4. Build the author's sheet
~/.venvs/ccr-trends/bin/python -m trends.validate audit \
    --joined data/processed/validation/round2/joined_labels.csv \
    --output data/processed/validation/round2/

# Tests
~/.venvs/ccr-trends/bin/python -m pytest tests/test_validate.py -q
```

Round one is preserved unchanged under `data/processed/validation/round1/` and
is reproducible with `--seed 20260902`, though it was drawn against the v2
labels, which the reclassification has overwritten.

| File (per round directory) | What it is |
|---|---|
| `sample.csv` | The 200 papers, their stratum, population, sample size, weight, and rule labels. Header records the seed. |
| `blind_sheet.csv` | What the labeler read: item, PMID, title, abstract. Nothing else. |
| `agent_labels.csv` | The agent's labels, plus `uncertain`, `other_datatype`, and `note`. |
| `joined_labels.csv` | Both labelers side by side, with weights and the `other` route. |
| `agreement_themes.csv`, `agreement_modalities.csv` | Confusion counts, precision, recall, F1, Wilson intervals, weighted estimates. |
| `disagreements.csv` | One row per paper and category where the two labelers split, with the direction. |
| `disagreement_causes.csv` | The hand coding: one cause per disagreement (round two only). |
| `cause_summary.csv`, `other_routes.csv` | The two round-two tables above. |
| `agreement_report.txt` | Everything above, as printed. |
| `audit_sheet.csv` | The author's fifty rows. |
| `agreement_round3.csv`, `agreement_report.txt` | Round three's per-category precision, in its own directory. |

Four directories: `round1/` (v2), `round2/` (v3), `round2-v5/` (the same sample
and labels re-scored against v5/v4, and the current audit sheet), and `round3/`
(the targeted draw).

`other_datatype` is separate from `mod_other` on purpose. `mod_other` is the
composite the classifier assigns by either route; `other_datatype` is only the
positive half of it. Without the second column the two routes cannot be scored
apart.

---

## Limitations, stated plainly

**The reference labels are not ground truth.** They are one agent's reading of
200 abstracts against the definitions in `config/*.yaml` and
`docs/classification.md`. Ninety-five of the 200 carry a recorded judgment call.
The author's audit of 50 bounds how far these labels drift from the author's
judgment; until it is done, every figure here is agreement with a machine, not
accuracy.

**The labeler is the same across rounds and may have drifted.** The
digital-twins fall is partly a stricter application of the same rule. A second
labeler, or a re-label of round one's papers under round two's rubric, would
separate drift from sampling; neither was done.

**The sample is stratified, not random.** Every number is a per-category rate.
Nothing here averages to a corpus-wide accuracy, and round one demonstrated that
the weighted projections that would try carry errors up to a factor of two.

**Six categories rest on ten papers or fewer.** IHC, spatial proteomics, spatial
transcriptomics, pathology report, radiography, and mammography have no usable
rate, which is what the intervals in the table say.

**Recall is measured through a narrow window.** Fifty papers stand for 37,232
that the rules gave no theme. A false-negative class affecting 1% of that
stratum — 372 papers — would more likely than not have gone unseen: 0.99^50 =
61%.

**Round two is not independent of round one in one respect.** Fifteen papers
appear in both samples, and the labeler had seen them. They are 7.5% of the
sample and were labeled consistently.

**Abstract-only.** Both labelers read the title and abstract, as the classifier
does. A paper whose full text makes its modality plain and whose abstract does
not is miscounted by both, and this design cannot detect that.

**One agent, one pass per round.** Nothing here measures the agent's own
consistency.

**Round three measures precision and not recall.** Every stratum is
rule-positive by construction. A category could have lost recall to a v4 or v5
change without this round seeing it. The one exception is digital twins, where
the whole row was read and the near-miss vocabulary was searched corpus-wide.

**The digital-twins column of the audit sheet was relabelled, not blind.** It
was relabelled under the v5 standard after the v3 scoring was known, so the
22-of-22 agreement on the round-two papers is not an independent measurement.
The 20 papers of round three are.

**The genomics residue estimate rests on twenty papers.** "Roughly half the
genomics + H&E co-occurrence is spurious" is 9 of 20 with a 26–66% interval on
precision. The direction is solid and the magnitude is not.
