# Decision log

Append-only. One entry per decision that a reader could reasonably question.
Format: date, decision, alternatives considered, reason, who/what made it.

---

## 2026-09-03 — Repository layout mirrors trends-figure

**Decision.** Python 3.13, one package (`src/clinops`), configuration in YAML, data in
`data/{raw,interim,processed}`, figures in `figures/`, documentation in `docs/`. Virtual
environment at `~/.venvs/ccr-clinops`, outside the OneDrive tree.
**Alternatives.** A single script; a notebook.
**Reason.** The sibling project `../trends-figure` already established this shape for the same
manuscript, and a reader who has read one project should not have to learn a second layout. The
venv sits outside the project for the reason recorded in that project's log on 2026-09-01: the
directory is OneDrive-synced and a venv inside it would push thousands of files into cloud
sync. Reproducibility rests on the pinned `requirements.txt`.
**Who.** Claude, with the author's approval of the plan.

## 2026-09-03 — Oncology is derived from product code, not device name

**Decision.** Classify a device as cancer-directed from its FDA `Primary Product Code`, using
the regulation definition openFDA returns for that code. Do not classify from the `Device`
name.
**Alternatives.** (a) Text matching on device names; (b) fetching and reading each device's
510(k) summary or De Novo decision summary for its indications for use; (c) an LLM label per
device.
**Reason.** The FDA AI-enabled device list has no indication-for-use field, so the label must
be derived. Device names are brand names — `Transpara`, `ProFound AI`, `AIR Recon DL` — and a
deliberately generous cancer-term regular expression over them matched only 42 of 1,103
radiology and pathology rows (4%), missing every mammography product whose name does not say
"mammo". (b) is the ground truth but means retrieving and parsing roughly 1,100 PDFs, most of
which are scanned; it is the right answer for a dedicated study and out of scope for one
manuscript figure. (c) is not deterministic and cannot be re-run to the same answer by a
reader, which Rule 1 of the task spec forbids.
**Consequence.** The unit of classification is a device *type*, not a device. This is what
makes the rule auditable — there are 47 codes to check rather than 1,103 devices — and it is
also the source of the floor described in the next entry.
**Who.** Claude.

## 2026-09-03 — The conservative rule: indeterminate codes are excluded, and the count is a floor

**Decision.** A product code counts as oncology only when its FDA regulation definition, or its
device-type name, states the cancer indication. Codes with generic definitions are excluded
even though some devices under them are certainly oncologic.
**Alternatives.** (a) A second tier that adjudicates devices under generic codes from their
names, hand-audited on a stratified sample with reported precision and recall — the validation
method `../trends-figure` used for its term dictionaries; (b) counting all radiology AI devices
regardless of indication.
**Reason.** The author chose the conservative rule. It is fully reproducible from public
fields with no judgment calls a reader has to accept on trust, which matters more for a
published figure than a larger number does.
**Consequence.** Roughly 800 devices sit under generic codes and are excluded. QIH alone holds
274 devices under "Automated Radiological Image Processing Software", and among them are
clearly oncologic tools such as `DrAid for Liver Segmentation` and `Neosoma Brain Mets`. The
figure therefore reports a floor, not a count of all oncologic radiology AI. **The legend must
say so, and any sentence in the manuscript quoting these numbers must not present them as
exhaustive.** The exclusions are enumerated in `config/oncology_codes.yaml` under `excluded:`
so a reader who disagrees can find the code they would have counted and read why it was left
out.
**Who.** The author, on 2026-09-03, choosing between the three options above.

## 2026-09-03 — QFM is excluded despite its name

**Decision.** Product code QFM, "Radiological Computer-Assisted Prioritization Software For
Lesions" (39 devices), is classified `not_oncology`.
**Alternatives.** Counting it, which a first pass over code names did.
**Reason.** The code name reads oncologic and is misleading. Reading the 39 devices authorized
under it shows pneumothorax and pulmonary-embolism triage (`Rayvolve PTX-PE`, `qXR-PTX-PE`),
vertebral compression fracture (`CINA-VCF`), aneurysm triage, and trauma triage. One device of
39, `VinDr-Mammo`, is oncologic. "Lesion" in this code means any acute finding, not a suspected
cancer.
**Consequence.** This single exclusion moves the radiology count by 39, from 184 to 145. It is
the reason the classification procedure requires reading the devices under a code and not only
its definition, and that requirement is now written into `config/oncology_codes.yaml`.
**Who.** Claude, during planning, after inspecting the device list per code.

## 2026-09-03 — Radiation therapy planning is counted, but kept as its own category

**Decision.** Codes QKB, MUJ and IYE — radiation therapy image processing, treatment planning
systems, and medical linear accelerators, 79 devices — count as oncology, but as a separate
category from cancer detection rather than merged into a single radiology total.
**Alternatives.** (a) Excluding them as treatment-delivery infrastructure rather than
diagnostic AI; (b) merging them into one radiology count.
**Reason.** The brief asks for AI "as applied to treating cancer", and radiation therapy
planning is cancer treatment more directly than any diagnostic tool. But these devices automate
contouring and dose planning rather than interpreting an image for a diagnosis, and pathology
has no analogue, so folding them into a single number would inflate the radiology side of what
readers will take as a diagnostic comparison.
**Consequence.** Both comparisons can be read off the figure: 145 against 9 for all
cancer-directed AI, and 66 against 9 for detection and diagnosis alone. Prose quoting either
must say which one it is quoting. This is the specific error in the manuscript's current text,
which pairs an all-indications radiology number with an oncology-only pathology number.
**Who.** Claude, with the author's approval of the plan.

## 2026-09-03 — Product code NMN is classified by override

**Decision.** NMN is forced to `pathology` / `oncology` by an explicit override in
`config/oncology_codes.yaml`, against what openFDA returns for it.
**Alternatives.** Trusting the lookup, which would drop the device; or dropping pre-2000
devices from the figure entirely.
**Reason.** openFDA's current record for NMN is "Instrument, Clip, Forming/Cutting,
Reprocessed" under Neurology, regulation 882.4190. That is not the device authorized as
P950009 in 1995, the AUTOPAP 300 QC Automatic Pap Screener, which FDA's own AI list assigns to
the Pathology panel. FDA retires and reassigns product codes, so a code queried today can
describe something unrelated to a device authorized thirty years earlier.
**Consequence.** The classifier reports every code where openFDA's
`medical_specialty_description` disagrees with the config's assigned domain, so a future
reassignment surfaces as a report line rather than a silent misclassification. NMN is currently
the only such case.
**Who.** Claude, after the openFDA lookup returned an obviously wrong device type.

## 2026-09-03 — The two 1995 Pap screeners are counted

**Decision.** PAPNET (P940029) and AUTOPAP 300 QC (P950009), both authorized in 1995, are
counted as pathology AI authorizations.
**Alternatives.** Starting the series at 2015 with the modern era, and treating the 1990s
devices as a historical footnote.
**Reason.** They are on FDA's AI-enabled device list, they are neural-network cervical cytology
screeners, and they are genuinely the first authorized AI devices in pathology. Excluding them
because they are inconvenient for a clean time series would be choosing the data to fit the
story.
**Consequence.** Pathology's cumulative curve sits flat at 2 from 1995 to 2020 before Paige
Prostate. That flat stretch is a finding — a twenty-six-year gap — and Panel A has to render it
honestly rather than hide it behind a clipped axis.
**Who.** Claude.

## 2026-09-03 — The raw snapshot is tracked in git

**Decision.** `data/raw/<date>/` is committed, unlike `../trends-figure/data/raw/`, which is
gitignored.
**Alternatives.** Gitignoring it and relying on the manifest, as the sibling project does.
**Reason.** The sibling project's raw data is roughly 1 GB of PubMed XML across 306 files. This
project's is about 450 KB: one CSV and one JSON of classification records. It fits, and
committing it makes the figure reproducible from a clone with no network access at all.
**Consequence.** The FDA republishes its list in place at a fixed URL — the same URL returned
1,430 rows through 2025-12-30 and 1,524 rows through 2026-03-30 — so the URL is not a version
and the committed snapshot is the only durable record of what the figure was built from.
**Who.** Claude.

## 2026-09-03 — `regulation_number` is the config's value, never openFDA's

**Decision.** `authorizations.csv` carries the regulation number recorded in
`oncology_codes.yaml`, not the one the openFDA lookup returns.
**Reason.** For an overridden code the lookup describes a different device entirely. NMN
returns 882.4190, a neurology clip instrument, which is not the regulation the 1995 AUTOPAP was
authorized under. Writing openFDA's value would put a wrong number in a published table. For
every other code the two agree, and `classify.py --report` prints them side by side so a
divergence surfaces.
**Consequence.** NMN and MNM carry an empty `regulation_number`, matching what the config
records rather than inventing one.
**Who.** Claude (pipeline agent).

## 2026-09-03 — FDA's review panel is a check, not a filter

**Decision.** The product-code rule is applied first. A device carrying an oncology code but an
unexpected `Panel (Lead)` is still counted, and the disagreement is reported.
**Alternatives.** Requiring the panel to match before counting.
**Reason.** Filtering on panel would make the panel-agreement statistic circular: it would
report 100% by construction and corroborate nothing. Measured independently it is a genuine
second opinion on every counted device, and it currently reads 145/145 and 9/9.
**Consequence.** A test asserts that a panel mismatch stays visible rather than being filtered
away, so the statistic cannot quietly become an identity.
**Who.** Claude (pipeline agent).

## 2026-09-03 — Rows that cannot fill the frozen schema are excluded, not blanked

**Decision.** A counted device with no derivable pathway or no decision date is excluded with a
named reason (`pathway_unknown`, `no_decision_date`) rather than written with an empty field.
**Reason.** The output schema declares `pathway` over exactly three values and `year` as an
integer. A blank would flow into `pathway_by_domain.csv` as a fourth pathway and into the
figure as a fourth bar segment.
**Consequence.** Both counts are zero on this snapshot. They are still reported, so a future
snapshot that introduces one is visible.
**Who.** Claude (pipeline agent).

## 2026-09-03 — Product codes are read as text, never as numbers

**Decision.** `aggregate.read_labeled` reads every column as text and casts `year` back
explicitly.
**Reason.** A real bug, caught in the first aggregate run: pandas inferred `regulation_number`
as a float and wrote `892.2050` as `892.205`, silently dropping the trailing zero from a
regulatory identifier in a published table. The same trap exists in YAML, which is why the
config loader rejects an unquoted `regulation_number`.
**Who.** Claude (pipeline agent).

## 2026-09-03 — The ledger must record each config's current version, not merely mention the file

**Decision.** Added `test_the_ledger_records_each_config_current_version`, which fails when a
config declares a version the ledger does not carry.
**Reason.** The guard ported from `../trends-figure` skips a version the ledger has never seen,
on the principle that an unrecorded version is not evidence of tampering. That leaves a hole in
the opposite direction from the one it was built for: bumping `version` and forgetting to
append the hash passes every check, and the file is then unguarded from exactly the moment it
changed. The hole was found by bumping `source.yaml` to v2 and watching the suite stay green.
**Consequence.** Two guards now, in both directions: content may not move without the version
moving, and the version may not move without the ledger recording it. A paired test
demonstrates the hash guard alone lets the second case through.
**Who.** Claude.

## 2026-09-03 — `source.yaml` v1 to v2: the expected-counts block was stale

**Decision.** Corrected `expected:` to 145 radiology / 9 pathology with the per-category and
panel-agreement figures, and bumped to v2.
**Reason.** v1's block recorded 184 radiology and a 182/2/0 pathway split, written before QFM
was excluded. The 39-device difference is exactly QFM. Nothing reads the block — it is a record
of a past measurement, not an assertion the pipeline enforces — but a stale record beside a
correct pipeline is a trap for the next reader.
**Consequence.** No pipeline output changed; no pattern or URL moved. The bump exists because
the version rule applies to any content change, including a corrected number in a comment.
**Who.** Claude, after the pipeline agent reported the discrepancy rather than adjusting the
config to match its output.

## 2026-09-03 — Panel A draws no line for a series' pre-authorization years

**Decision.** The x axis runs 1995–2026 continuously with no break in either axis, and each
series is drawn only from the first year its cumulative count reaches one: pathology 1995,
cancer detection 2016, radiation therapy 2018. The zero years carry no mark at all. The y floor
sits at 0.8 so nothing is drawn on the spine.
**Alternatives.** (a) A broken axis across 1996–2015; (b) clipping x to 2016, radiology's first
authorization; (c) drawing pre-authorization years flat along the axis floor.
**Reason.** A log axis cannot draw a zero, and every way of pretending otherwise misleads. (a)
deletes the 26-year pathology plateau, which is the finding. (b) drops two of the nine pathology
devices the panel exists to name. (c) reads as "this series was at the floor value" when the
series was at zero — the exact misreading a log axis invites.
**Consequence.** Panel A has a large empty upper-left quadrant. That emptiness is the 21 years
before radiology's first cancer-directed authorization, so it is the argument rather than a
layout failure. `clinical_operations_summary.txt` prints each series' undrawn zero run so the
legend can state it in words, and the legend does.
**Who.** Claude (figure agent).

## 2026-09-03 — Style-guide deviations in the figure

Recorded because `../AGENTS.md` requires a deviation to be deliberate and written down. Each is
also commented in place in the code.

1. **Hairlines below the guide's 1.0 minimum stroke.** Label leaders 0.5 pt, segment borders
   0.8 pt. The guide's minimum is in SVG user units on a ~1355-unit canvas, about 0.4 pt at this
   figure's width; the sibling trends figure already draws 0.5–0.8 pt leaders and spines. The
   guide's ratios are preserved, not its absolute numbers.
2. **Panel B hatch is not the guide's §4 hatch.** That specification (`#F0F0F0` ground,
   `#BDBDBD` lines) is for masked, hidden, or inactive elements. De Novo and PMA are live
   quantities and two thirds of the pathology bar. Drawn instead with a white ground and hatch
   lines in the bar's own deep domain tint, so a segment never stops saying which field it
   belongs to.
3. **Panel B uses a three-swatch key rather than direct labels.** A texture cannot be labelled
   in place on a 1.4% sliver. The key is drawn in neutral ink so it claims no domain.
4. **Two series share one hue.** Cancer detection and radiation therapy are both radiology, and
   hue is fixed project-wide to the modality, so this applies the rule rather than breaking it.
   It is the first figure in the set where two series are deliberately the same colour; dash,
   marker, and direct end labels carry the distinction.
5. **Segment count colour chosen by measured WCAG contrast, not by eye.** White on radiology
   blue (5.2:1 against 3.6:1) and ink on pathology pink (6.1:1 against 3.1:1). The first pass
   put white on pink at 3.1:1 and it was visibly weak.

**Who.** Claude (figure agent).

## 2026-09-03 — Panel A's greyscale margin is thin, and that is accepted

**Decision.** Ship Panel A knowing that in greyscale its three series are near-indistinguishable
by tone.
**Reason.** Measured, not assumed: `#0072B2` and the pathology tint differ by 0.031 in relative
luminance, so a greyscale print renders them as effectively one colour. The style guide's
requirement is that colour is never the sole cue, and it is not — every series carries a
distinct dash pattern, a distinct marker, and a direct text label, and identification survives
greyscale on those alone. Under deuteranopia, protanopia and tritanopia simulation the two hues
stay clearly separate (RGB distance 0.27–0.67 on the lines), so the thin margin is specific to
greyscale.
**Consequence.** The direct labels are load-bearing and must not be dropped for space. If a
future revision adds a fourth series to Panel A, tone will not separate it and the panel needs
rethinking rather than another dash pattern.
**Who.** Claude (figure agent), reporting the measurement rather than asserting the check passed.

---

# 2026-09-03 (later) — The code-level rule failed an audit. What follows is the correction.

## 2026-09-03 — The code-only rule undercounts as a function of time, which is not a floor

**What happened.** The author looked at the figure and asked why radiology's first
cancer-directed authorization was 2016 when pathology had two in 1995. It was a good question
and the answer is that the figure was wrong.

FDA created its cancer-specific product codes only around 2018-2020 — MYN's own openFDA record
points at the Federal Register notice, "Radiology Devices; Reclassification of Medical Image
Analyzers" (85 FR 3541, 22 January 2020). Before that, mammography and lung computer-aided
detection were authorized under generic codes. MYN holds the **1998 M1000 ImageChecker**
(P970058), R2 Technology's mammography CAD and the first FDA-approved CAD device, plus the 2001
RapidScreen RS-2000 and the 2002 Second Look.

**Why the existing caveat did not cover it.** The count was documented as "a floor", and the
author approved the conservative rule on that basis. But this floor is not uniform — it tightens
the further back one looks, because the codes it depends on did not exist yet. A uniform
undercount is safe for a ratio. A time-varying one **fabricates a trend**. Panel A is a time
series, so "it's a floor" was the wrong caveat for the wrong quantity.

**Worse, MYN qualified under the rule as written.** Its regulation, 21 CFR 892.2070, names
cancer three times: "CADe devices for mammography breast cancer, ultrasound breast lesions,
radiograph lung nodules, and radiograph dental caries detection." It was excluded only because
openFDA's `definition` field returns a bare URL to the Federal Register notice instead of the
regulation text. The pipeline saw an unusable string, fell through to `indeterminate`, and
nobody opened the link. **The exclusion was a data-fetch artifact presented as a judgment.**

**Consequence.** Radiology's first cancer-directed authorization is 26 June 1998, not 2016. The
earlier `DECISIONS.md` entry claiming Panel A's empty upper-left quadrant "is the argument
rather than a layout failure" was wrong; it was a hole in the code list. The real history is
that both fields had authorizations in the 1990s and 2000s and both then went quiet for over a
decade — a different and more interesting finding than the one published.
**Who.** The author, by inspection. Confirmed by an independent adversarial audit.

## 2026-09-03 — Every safeguard tested precision; none tested recall

**What went wrong in the method, as distinct from the result.** The checks built into this
project were panel agreement, the QFM tripwire, excluded-code drift, and per-code count
reconciliation. Every one of them asks "is a counted device correctly counted?" None asks "is
an uncounted device correctly uncounted?" Panel agreement reading 145/145 was reported as
validation; it can only ever confirm the specialty of devices already admitted, and is
structurally incapable of detecting a wrongly excluded one.
**Consequence.** The report now carries an `UNADJUDICATED DEVICES` section that must read zero
before a figure is published, and the adjudication layer forces a recorded decision — with
evidence — on every in-scope device rather than letting a whole code fall through unexamined.
**Who.** Claude, after the audit.

## 2026-09-03 — POK was admitted on its name, and the config falsely certified otherwise

**What happened.** POK is named "Computer-Assisted Diagnostic Software For Lesions Suspicious
For Cancer" and was counted wholesale. Its openFDA *definition* says only "Assist users in
characterizing lesions identified on acquired medical images" and never mentions cancer. Of its
21 devices, **14 are not oncologic**: six stroke (Rapid ASPECTS x2, Brainomix 360 e-ASPECTS x2,
CINA-ASPECTS, StrokeSENS), four cardiac (EchoGo Pro, EchoSolv AS, AISAP Cardio, AutoAS), four
obstetric (Fetal EchoScan x3, Sonio Suspect).
**The certification.** `oncology_codes.yaml` stated: "Every code below was checked against the
devices actually authorized under it, not against its name alone." That was written after
checking the codes that were *suspected* — QFM, QTZ, IYE, MUJ, OTE, QNK, SEZ, QVD, MYN — and
then generalised to all of them. POK was never opened. It is the exact error the QFM entry was
written to warn about, committed in the same file that warns about it.
**Consequence.** A claim of completeness must be earned per item or not made. The rule is now
device-level throughout, so the claim is checkable rather than asserted.
**Who.** Claude wrote the false certification. An independent audit caught it.

## 2026-09-03 — The QFM exclusion is right and its recorded evidence was false

**What happened.** Three documents and one test recorded "One device of 39 (VinDr-Mammo) is
oncologic." There are six mammography devices under QFM: cmTriage (K183285), HealthMammo
(K200905), Saige-Q (K203517), CogNet QmTRIAGE (K220080), VinDr-Mammo (K233108), CogNet AI-MT+
(K252482).
**Reason it matters even though the conclusion stands.** Excluding QFM wholesale was right on
balance — 33 of 39 are acute-care triage — but the recorded evidence overstated the case by 6x,
and a test was built to protect that sentence. A wrong reason defended by a test is worse than
no reason, because it looks audited.
**Consequence.** The six mammography devices are now adjudicated individually and counted, and
the evidence text is corrected wherever it appears.
**Who.** Independent audit.

## 2026-09-03 — The figure counts authorizations, not capabilities

**Decision.** One row on FDA's list is one authorization, even when it covers an imaging
platform that bundles a cancer CAD feature among many others.
**Reason.** Raised by an adjudicator: rows such as "V8 Diagnostic Ultrasound System" or "LOGIQ
E10" are scanner clearances that ship optional oncologic features (S-Detect for Breast,
Breast Assistant) alongside cardiac and obstetric ones. A device-level oncology/not-oncology
binary cannot express "this clearance contains a cancer feature among others", so every such
row is forced to a wrong-ish answer.
**Consequence.** These are `not_oncology`, and the legend and report now say the figure counts
authorizations rather than cancer-directed AI capabilities reaching clinics. Under the other
reading several platform clearances would count and the radiology totals would rise. Stating
which quantity is drawn is what keeps the number honest.
**Who.** Claude, on an adjudicator's finding.

## 2026-09-03 — `unresolved` is reported, never folded into either side

**Decision.** A device whose purpose cannot be established from the published fields is recorded
`unresolved`, excluded from the counts, and reported as a residual band.
**Alternatives.** Folding it into `not_oncology`, which is what the previous rule did silently
to 955 devices.
**Reason.** The residual is the width of the error bar on every number in the figure. Hiding it
inside an exclusion category makes the counts look more precise than the data supports.
**Consequence.** An adjudicator noted that `unresolved` currently blends two different
uncertainties: a genuinely dual-use indication (IB Neuro's perfusion mapping, used for both
glioma and stroke) and a row that is simply silent about which bundled feature is AI-enabled.
These may deserve separate reporting if the residual grows large.
**Who.** Claude.

## 2026-09-03 — A descriptive-looking device name is still not evidence

**What happened.** The adjudication brief offered `Lung-CAD` as an example of a device name that
"plainly says what it does". An adjudicator refuted it. Imagen Technologies holds two MYN
clearances both named `Lung-CAD`: K223811 detects **interstitial thickening** and K230085
detects **lung hyperinflation**. Neither detects nodules and neither is cancer. The same
vendor's `Chest-CAD` is a generic eight-category detector and its `Aorta-CAD` is vascular.
**Consequence.** Any rule keyed on "CAD" or "Lung" in the device string gets all four wrong.
This is the device-level echo of the code-level lesson: the QFM code name said "Lesions" and
meant trauma triage; the `Lung-CAD` device name says lung and means emphysema. Names describe
marketing, not indications, at both levels. All four are `not_oncology` on their FDA
indications.
**Who.** Adjudicator, correcting the brief it was given.

## 2026-09-03 — QTZ resolved to liver tumour ablation, and the category scheme does not fit it

**Decision.** QTZ's three devices (VisAble.IO x2, BioTraceIO Vision) are counted as oncology.
They are one Techsomed product line for **liver tumour** ablation planning and response
prediction; BioTraceIO's De Novo was announced as the first ultrasound-based software for tissue
response prediction in liver tumour ablation, supported by NCT05582018. This reverses the
earlier `indeterminate` call, which had guessed the ambiguity was cardiac versus tumour ablation.
**The problem it exposes.** These are cancer *treatment* planning by thermal ablation, not
radiotherapy, and the only treatment-planning category available is labelled "Radiation therapy
planning". Filing them there puts three ablation products under a radiotherapy label in the
figure.
**Resolution.** Rename the category to cancer treatment planning, which covers radiotherapy and
interventional oncology both, rather than adding a fourth series to a panel whose greyscale
margin is already thin. The label is what a reader sees, so the label has to be true.
**Who.** Adjudicator raised it; Claude decided the rename.

## 2026-09-03 — The radiology/pathology split is a modality boundary, not a function boundary

**Noted, not resolved.** Two devices sit on the wrong side of the figure's headline comparison
for a defensible but unsatisfying reason. Perimeter's OTIS 2.1 images **excised tissue specimen
margins** and is functionally an intraoperative substitute for frozen-section pathology;
NinePoint's NvisionVLE targets Barrett's oesophagus dysplasia from the endoscopy side. Both are
filed under radiology because FDA assigns them the Radiology panel.
**Reason for leaving it.** The figure's domain axis is FDA's own panel, which is the only
assignment neither this project nor a reader has to argue about, and reassigning devices by
function would make the domain split a judgment call in exactly the place the comparison needs
to be mechanical. Both are recorded here so a reader who disagrees can find them.
**Who.** Adjudicator raised it; Claude decided to leave the panel as the boundary and disclose.
