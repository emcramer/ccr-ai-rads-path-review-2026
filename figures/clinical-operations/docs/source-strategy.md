# Source strategy

What the sources are, what they can support, and what they cannot. Read this before quoting a
number from this project in the manuscript.

---

## 1. The FDA AI-enabled device list

**What it is.** A curated list FDA publishes as a downloadable file from
<https://www.fda.gov/medical-devices/software-medical-device-samd/artificial-intelligence-enabled-medical-devices>.
There is no API. The CSV, XLSX and XML serialisations are the same content at three fixed media
URLs.

**What FDA says it is**, quoted from the landing page on 2026-09-03:

> ...includes AI-enabled medical devices that were identified primarily based on the use of
> AI-related terms in the summary descriptions of their marketing authorization document
> and/or the device's classification.

and, importantly:

> The list is not a comprehensive resource of AI-enabled medical devices.

**What that means for the figure.** Inclusion depends on how a device's authorization
paperwork was written. A device using machine learning whose summary avoids AI vocabulary is
absent. This bounds every claim: the figure describes *devices FDA identified as AI-enabled*,
not *devices that use AI*. The manuscript must not silently upgrade the one to the other.

FDA also states that authorizations whose decision summaries were not published within a
collection period are added in a later update, so the most recent months are systematically
under-counted. The final period in any snapshot is partial.

### The URL is not a version

The same CSV URL returned 1,430 rows through 2025-12-30 and 1,524 rows through 2026-03-30. FDA
republishes in place and does not version the file. A figure built from the live URL is
therefore not reproducible, and a reader who downloads the list a month later will not
reproduce the counts.

This is why `fetch.py` writes an append-only dated snapshot under `data/raw/` and every
downstream stage reads the snapshot rather than the network. The snapshot directory is named
for the **maximum decision date in the file**, not the day it was retrieved, because that is
what identifies the content.

The snapshot is small — about 1.1 MB — so it is committed. The figure is reproducible from a
clone with no network access.

### Schema drift is real

The copy cached at `../../data/ai-ml-enabled-devices-excel.csv` carries seven columns,
including a duplicate `submission` column that the live file does not have. FDA has already
changed this schema once. `fetch.py` normalises the tolerated duplicate away and then asserts
the required column set exactly, so a future rename fails the run instead of silently
producing a wrong figure.

### Fields available

`Date of Final Decision`, `Submission Number`, `Device`, `Company`, `Panel (Lead)`,
`Primary Product Code`. Six fields. Note what is **not** there: no indication for use, no
imaging modality, no cancer type, no autonomy level, no clinical-evidence descriptor.

The marketing pathway is not a column either, but it is recoverable without ambiguity from the
submission number prefix: `DEN` is De Novo, `K` is 510(k), `P` is PMA.

---

## 2. openFDA device classification

**What it is.** <https://api.fda.gov/device/classification.json>, the device classification
database. Maps a product code to its regulation number, device class, medical specialty, device
type name, and a regulation definition. No API key required; anonymous limits (240 requests per
minute, 1,000 per day) are far above what this pipeline needs, since distinct codes are queried
in batches.

**What it gives us.** The oncology restriction. FDA's regulation definition states what a
device *type* is for, and that is the only published text in the whole chain that speaks to
indication.

**Where it fails.** Product codes are retired and reassigned. Querying a code today returns
its *current* meaning, which may have nothing to do with a device authorized under it decades
earlier. In this data set, code `NMN` returns "Instrument, Clip, Forming/Cutting, Reprocessed"
under Neurology — not the 1995 AUTOPAP Pap screener that FDA's own list assigns to Pathology
under that code. See `config/oncology_codes.yaml` under `overrides:`, and the entry in
`DECISIONS.md`.

Six codes in the radiology and pathology subset return no regulation number at all (`OTE`,
`QNK`, `LDK`, `PQP`, `MNM`, `NMN`). Four of them still return a usable device-type name and
definition; two do not.

The classifier reports every code where openFDA's `medical_specialty_description` disagrees
with the domain the config assigns, so a future reassignment surfaces as a report line rather
than a silent misclassification.

---

## 3. Deriving "applied to cancer"

The central problem. There is no indication field, so the label must be derived.

### What does not work: device names

The only free-text field is `Device`, and it holds brand names. A deliberately generous
cancer-term regular expression — `mammo|breast|prostat|nodule|lesion|tumou?r|oncolog|cancer|
carcinom|melanoma|polyp|colorect|hepat|thyroid|metasta|biops|neoplas|Gleason|radiothera|...` —
matched **42 of 1,103** radiology and pathology rows, 4%.

The misses are not marginal. `Transpara`, `ProFound AI` and `Genius AI Detection` are
mammography CAD products whose names contain no cancer term. The hits include false positives
from words like "segment" and "screening" used non-oncologically. Device names cannot carry
this decision.

### What half-works: product codes

Each product code resolves to a regulation definition. Where that definition names cancer,
tumors, or radiation therapy, every device under the code is cancer-directed by construction.
47 distinct codes appear in the radiology and pathology subset, so a code-level rule is 47
decisions a reader can audit rather than 1,103.

That was the original design, and it failed in two directions at once.

**It missed devices, and it missed them as a function of time.** FDA created its cancer-specific
product codes only around 2018-2020 — MYN's own openFDA record points at the Federal Register
notice, "Radiology Devices; Reclassification of Medical Image Analyzers" (85 FR 3541, 22 January
2020). Before that, mammography and lung CAD were authorized under generic codes. MYN holds the
**1998 M1000 ImageChecker** (P970058), the first FDA-approved CAD device, plus the 2001
RapidScreen RS-2000 and the 2002 Second Look. A rule keyed on cancer-named codes cannot see any
of them, so it reported radiology as beginning in 2016.

This is the failure that matters most, and the "it's a floor" caveat did not cover it. A floor
that is uniform is safe for a ratio. This floor tightens the further back you look, because the
codes it depends on did not exist yet — and a time-varying undercount **fabricates a trend**
rather than merely shortening one.

Worse, MYN qualified under the rule as written: 21 CFR 892.2070 names cancer three times. It was
excluded only because openFDA's `definition` field returns a bare URL to the Federal Register
notice instead of the regulation text. A data-fetch artifact was presented as a judgment.

**It also over-counted.** POK is named "Computer-Assisted Diagnostic Software For Lesions
Suspicious For Cancer" and was counted wholesale. Its actual openFDA definition says only
"Assist users in characterizing lesions identified on acquired medical images" and never
mentions cancer. Of its 21 devices, 14 are stroke, cardiac, or obstetric.

### What works: device-level adjudication, with the code as a prior

Every in-scope device now carries its own recorded decision — `oncology`, `not_oncology`, or
`unresolved` — with written evidence. The product code is a prior, not a verdict. See
`docs/classification.md` and `config/adjudication/`.

**Names are not evidence, at either level.** The code name QFM says "Lesions" and its devices are
trauma triage. The device name `Lung-CAD` appears on two Imagen clearances that detect
interstitial thickening and lung hyperinflation — neither is nodules, neither is cancer. Names
describe marketing. Only the indication counts, and where the row does not carry one, the honest
answer is `unresolved`.

### The residual is reported, not hidden

`unresolved` devices are excluded from the counts and reported as a band. They are the width of
the error bar on every number here. Folding them into "not oncology" — which the code-level rule
did silently to 955 devices — makes the counts look more precise than the data supports.

Two different uncertainties currently share that band, and adjudicators flagged it consistently:
a genuinely dual-use indication (IB Neuro's perfusion mapping serves both glioma and stroke), and
a platform clearance that bundles a cancer feature among many others (Siemens `syngo.via MI
Workflows`, Arterys `MICA`). The second is *mixed*, not *unknown*. If the band grows they should
be reported separately.

## 4. What this project can and cannot claim

**Can support.**

- How many devices FDA identified as AI-enabled were authorized under cancer-directed device
  types, by year, by domain, and by marketing pathway.
- That the radiology-to-pathology ratio in that count is roughly 16:1 overall and 7:1 for
  detection and diagnosis alone.
- That radiology's authorizations are almost entirely 510(k) clearances against existing
  predicates while pathology's split evenly across all three pathways — a statement about
  regulatory precedent, and the most interesting finding here.
- That pathology's cumulative curve was flat for twenty-six years between the 1995 Pap
  screeners and Paige Prostate in 2021.

**Cannot support.**

- Anything about clinical use, uptake, installed base, or patient volume. An authorization is
  permission to market, not evidence of deployment, and certainly not of benefit. The
  manuscript's own framing — that regulatory clearance does not demonstrate local clinical
  utility — applies to this figure and should be stated near it.
- Anything about device performance, evidence quality, or autonomy level.
- A complete census of cancer-directed AI. Devices that could not be resolved from the published
  fields are excluded and reported as a residual band.
- **Capabilities, as opposed to authorizations.** One row is one authorization even when it
  covers an imaging platform bundling a cancer CAD feature among many others. Several scanner
  clearances ship optional oncologic modules and are counted `not_oncology`; under a
  capability-counting reading the radiology totals would rise.
- Anything about non-US markets. CE-marked devices are absent.
- A clean comparison of the most recent months, which are under-reported by construction.

**Boundaries a reader should know about.**

- **The domain axis is FDA's review panel**, not device function. Perimeter's OTIS images excised
  tissue margins and is functionally a frozen-section substitute; NinePoint's NvisionVLE targets
  Barrett's dysplasia endoscopically. Both count as radiology because that is the panel FDA
  assigns. The panel is used precisely because it is the one assignment neither this project nor
  a reader has to argue about.
- **Breast density products are `not_oncology`.** Density is a risk factor, and these measure
  tissue composition rather than cancer. This is applied consistently and it is the largest
  single systematic exclusion — around a dozen devices, several of them density modules sold by
  single-purpose mammography-CAD vendors, and it falls disproportionately on the pre-2016 era.
- **Acquisition, reconstruction and enhancement are `not_oncology`** even where the stated
  purpose is a cancer screening programme. A low-dose CT option built for lung-cancer screening
  and a fast whole-body cancer-screening MRI protocol are both excluded, because what is cleared
  is the acquisition, not a cancer-directed analysis.
