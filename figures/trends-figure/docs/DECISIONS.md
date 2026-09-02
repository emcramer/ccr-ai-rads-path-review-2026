# Decision log

Append-only. One entry per decision that a reader could reasonably question.
Format: date, decision, alternatives considered, reason, who/what made it.

---

## 2026-09-01 — Repository layout and language

**Decision.** Python 3.13, one package (`src/trends`), configuration in YAML, data in
`data/{raw,interim,processed}`, figures in `figures/`, documentation in `docs/`.
**Alternatives.** R; a single notebook.
**Reason.** The analysis is an API pull plus tabulation; Python's PubMed and plotting
tooling is adequate and the team already reads Python. A package with a CLI keeps every
step re-runnable, which a notebook does not.

## 2026-09-01 — Virtual environment lives outside OneDrive

**Decision.** `~/.venvs/ccr-trends`, recreated from `requirements.txt`.
**Reason.** The project directory is OneDrive-synced. A venv inside it would push
thousands of files into cloud sync. Reproducibility rests on the pinned requirements file,
not on the environment directory.

## 2026-09-01 — One broad corpus query, then rule-based multi-label classification

**Decision.** Retrieve a single corpus with one documented PubMed query, then assign
themes and modalities to each record by matching a versioned term dictionary against title
and abstract. Do not run one PubMed query per theme-modality cell.
**Alternatives.** (a) 40 separate combination queries; (b) LLM classification of abstracts.
**Reason.** (a) gives no shared denominator, double-counts papers across cells, and cannot
produce the co-occurrence sets Panel A needs. (b) is not deterministic and cannot be
re-run to the same answer by a reader, which Rule 1 of the task spec requires. A rule-based
classifier is reproducible from the term dictionary alone; its error rate is measurable
against a hand-labeled validation sample, and that measurement is reportable.
**Consequence.** Classifier accuracy must be reported, not assumed. See
`docs/validation.md` when it exists.

## 2026-09-01 — Partial final year

**Decision.** Retrieve through the query date (2026-09-01) but mark 2026 as partial
wherever it appears, and exclude it from any statement about a trend's direction.
**Reason.** A truncated year reads as a decline that is an artifact of the retrieval date.

## 2026-09-01 — PET added as an eleventh modality

**Decision.** Classify PET separately, in addition to the ten modalities in Table 1 of the
task spec.
**Reason.** PET appears as a row in the figure mockup, and it is a major oncologic imaging
modality. Its absence from Table 1 reads as an oversight. Author confirmed.
**Consequence.** PET and CT will co-occur often, because most oncologic PET is acquired as
PET/CT. That overlap is real and is left in place; it is reported, not suppressed.

## 2026-09-01 — Classifier validation by LLM labeling with an author audit

**Decision.** Measure classifier accuracy against a stratified sample of about 200
abstracts labeled by an agent, of which the author reviews 50. Report agreement three ways:
rules against LLM labels, rules against author labels, LLM against author.
**Alternatives.** Author hand-labels 100 abstracts; no formal validation.
**Reason.** The figure's claims rest on the classifier being roughly right. Some measured
error rate is required to state one in the legend. Full hand-labeling was judged too
expensive for the value added; the 50-abstract audit bounds how far the LLM labels can
drift from the author's judgment. Author chose this option.
**Consequence.** The reported accuracy is accuracy against LLM labels, calibrated by a
50-abstract author audit. The legend must say so plainly rather than implying a fully
hand-labeled gold standard.

## 2026-09-01 — Publication year rule

**Decision.** Use the article (electronic) date when it precedes the journal issue date;
otherwise use the issue date. Fall back to whichever exists, then to the PubMed history
date. Every row records `year_source` and both raw years.
**Reason.** Online-ahead-of-print publication puts a paper's real appearance date up to a
year before its issue date. Taking the issue date alone shifts the trend line right; taking
the article date alone is wrong when it is a later record-keeping stamp. In a 212-record
smoke sample the rule moved 5% of records back a year, which matters at the 2025/2026
boundary where the corpus ends.

## 2026-09-01 — Date range applied by esearch, not by the query string

**Decision.** `mindate`/`maxdate` with `datetype=pdat` are passed as E-utilities
parameters; the query string carries topic terms only. The resolved query translation NCBI
returns is stored in each run manifest.
**Reason.** Keeps one setting in one place. A date filter written into the query string as
well would filter twice, silently, and the two could drift apart.

## 2026-09-01 — Package installed, not path-injected

**Decision.** A minimal `pyproject.toml` at the project root; the package is installed into
the environment with `pip install -e .`.
**Reason.** Commands in the documentation then run verbatim, with no `PYTHONPATH` prefix
for a reader to copy wrongly.

## 2026-09-01 — Book records retained in the record table, excluded from the corpus

**Decision.** `PubmedBookArticle` records (StatPearls, GeneReviews and the like) are parsed
and tagged `record_type` rather than dropped at retrieval. The analysis stage excludes them,
by an explicit documented filter, and reports how many it removed.
**Reason.** They are reference works, not primary literature, so they do not belong in a
count of research papers. Dropping them at retrieval would hide them; dropping them at
analysis leaves the decision visible and reversible.

## 2026-09-01 — Raw capture is append-only

**Decision.** Each run writes a new dated directory under `data/raw/` with its own manifest
of query, parameters, counts, and per-file SHA-256. A run that would overwrite an existing
directory writes a numbered sibling instead. Verified live.
**Reason.** Provenance is worthless if a later run can quietly replace what an earlier claim
was based on.

## 2026-09-01 — Panel A shows the top 8 combinations per theme and prints its own tail

**Decision.** Cap Panel A at eight modality combinations per theme, and print under each
block how many combinations and papers the cap excludes.
**Alternatives.** Ten columns; no cap.
**Reason.** The distribution of modality combinations is long-tailed — in the synthetic
test, over a hundred distinct sets per theme. No cap can show them, and raising the cap to
ten recovers a few points of coverage while narrowing every column. The honest move is a
readable cap plus a visible statement of what it hides. The long tail is itself worth a
sentence in the manuscript.

## 2026-09-01 — One bar scale across all four theme blocks

**Decision.** Panel A bars share a single y axis across themes, and every bar is labeled
with its count.
**Alternatives.** Per-theme axis scaling.
**Reason.** Per-theme scaling would draw a Digital Twins bar of 18 papers at the same
height as a Clinical bar of 283, which misleads at a glance. The cost is that sparse themes
draw as hairlines; the printed counts recover the exact value.

## 2026-09-01 — Colour carries no information

**Decision.** Okabe-Ito palette. Panel A encodes nothing in colour. Panel B distinguishes
lines by dash pattern, marker, and a direct end label as well as hue.
**Reason.** The figure must survive greyscale printing and colour-vision deficiency.
Verified by rendering both panels in greyscale.

## 2026-09-01 — The clinical theme's two lines are not additive

**Decision.** In Panel B the Clinical Applications / FDA Approval theme is drawn as a
radiology line and a pathology line, with no combined line. A paper using both counts in
both.
**Reason.** The sketch asks for the radiology-versus-pathology contrast, which is the point
of that theme. The two lines therefore do not sum to the theme total, and the legend says so.

## 2026-09-01 — Corpus query: three ANDed blocks, MeSH plus text words

**Decision.** METHOD (AI/ML/DL) AND DOMAIN (radiology and pathology imaging) AND CANCER.
MeSH terms where a tree does real work (`Artificial Intelligence`, `Diagnostic Imaging`,
`Neoplasms`); text words for the rest. 44,617 records, 2015-01-01 to 2026-09-01.
**Reason for not using MeSH alone.** MeSH indexing lags publication. Only 60% of the
corpus's 2026 records are MEDLINE-indexed, against 86% of its 2019 records. A MeSH-only
query would understate 2026 by roughly 40% and manufacture a decline in the trend line.
**Measured precision.** 38 of 40 sampled records were on topic (95%); 86% under a strict
reading requiring radiology or pathology specifically.

## 2026-09-01 — Five candidate patterns measured and rejected

**Decision.** Dropped `histolog*` from the corpus query (40% precise over 16 reads; it
admitted 1,434 papers whose only tie was "histologically confirmed"), bare `US` for
ultrasound (2 of 6), "virtual patient/cohort" for digital twins (0 of 2), `Vectra` for
spatial proteomics (collides with Canfield VECTRA photography, 0 of 1), and "BI-RADS
assessment/category" for radiology reports (0 of 2).
**Reason.** A term that fails a read-the-titles check does not belong in a published
method, however plausible it looks. Each rejection is recorded in `docs/search-strategy.md`
with its sample.

## 2026-09-01 — Acronyms matched case-sensitively

**Decision.** `CT`, `PET`, `IHC`, `MRI` match case-sensitively with word boundaries.
Regex patterns are case-sensitive by default; `(?i)` at position 0 opts out.
**Reason.** Measured: case-sensitive `\bCT\b` was 22 of 22 correct and `\bPET\b` 16 of 16.
Case-insensitive `pet` matches animals and polyethylene terephthalate.

## 2026-09-01 — Clinical Applications / FDA Approval means regulatory language only

**Decision.** The theme covers clearance, approval, and regulatory-device language: roughly
130 papers. It excludes general clinical-deployment language, which would have made it
roughly 3,290 — a twenty-fold difference. The deployment vocabulary is retained in the
config file, marked unused, so the decision can be reversed without rediscovering the terms.
**Reason.** Author's decision. A thin pathology line is not a defect of the figure; it is
the review's argument. Radiology holds roughly 1,100 FDA-cleared AI devices against fewer
than ten in pathology, and a theme diluted with deployment language would hide that gap.
**Consequence.** The theme is small enough that per-year counts will be noisy. The legend
must say so, and the manuscript should not read a trend into single-digit yearly changes.

## 2026-09-01 — Mammography and radiography as separate modality rows

**Decision.** Add `mammography` and `xray` (Radiography), bringing the figure to thirteen
modality rows. Both count as radiology for the `domain` rule.
**Reason.** Mammography is a projection X-ray technique and could sit inside a single X-ray
row. The author split them because mammographic screening AI carries the strongest
clinical-trial evidence in the review (MASAI, PRAIM) and would be invisible inside a generic
radiography bucket. Both were also a large, unlabeled share of `other`.

## 2026-09-01 — PubMed caps retrieval at 9,999 records; the corpus is fetched in date slices

**Decision.** Retrieve in publication-date slices, each kept under the ceiling and
subdivided automatically when a slice exceeds it, then deduplicate by PMID.
**Reason.** Discovered by running the real query: `usehistory=y` does not lift PubMed's
limit, and the pull failed at `retstart=9500` with an explicit NCBI error. Date slicing is
the technique NCBI's own EDirect uses.
**Consequence.** Slices overlap, because a publication-date filter matches both electronic
and print dates: summed year queries give 50,298 records against 44,617 for the whole range,
a 12.7% overlap. Deduplication by PMID reconciles the two exactly, and the run asserts that
reconciliation rather than trusting it. A record's year always comes from the parsed record,
never from the slice that matched it.

## 2026-09-01 — Matching contract: regex case-sensitive, phrase case-insensitive

**Decision.** A `regex` pattern is compiled as written, case-sensitively; `(?i)` at
position 0 opts out. A `phrase` pattern is case-insensitive, word-bounded, and tolerant of
whitespace. A per-pattern `case_sensitive` override exists and flips neither default.
**Reason.** The acronym measurements the vocabulary rests on — `\bCT\b` at 22 of 22,
`\bPET\b` at 16 of 16 — depend on case-sensitive regex. A global case-insensitive default
would have silently destroyed them. `config/README.md` originally said the opposite; it was
wrong and has been corrected.

## 2026-09-01 — Label provenance kept in a separate file

**Decision.** `data/processed/pattern_hits.csv` records one row per record, category, and
pattern that fired, with the pattern text, hit count, whether the label was assigned, and a
short context excerpt. `paper_labels.csv` stays exactly to the figure spec.
**Reason.** Any label in the figure can be traced to the words that produced it. Suppressed
labels are kept too, marked unassigned, so an exclusion rule is as auditable as an inclusion
rule. The file will run to tens of megabytes on the full corpus; that is the price of being
able to answer "why is this paper counted as multimodal?" and it is worth paying.

## 2026-09-01 — Records without a parsable year are dropped

**Decision.** Drop them, count them, and report the count in the run manifest.
**Reason.** Both panels are indexed by year; a record with no year cannot be placed in
either. None appeared in the 212-record smoke set. If the count on the full corpus is
material, the figure legend must say so.

## 2026-09-01 — Clinical papers with no modality domain appear on neither Panel B line

**Decision.** Panel B's radiology and pathology lines are drawn from papers labeled with a
radiology or a pathology modality. A clinical-theme paper matching only `other` appears on
neither line, and the count of such papers is reported.
**Reason.** The alternative — inventing a domain for them — would be a guess presented as
data. The consequence is that Panel B under-counts the clinical theme relative to Panel A,
in the opposite direction from the double-counting of papers that use both. Both asymmetries
belong in the legend.

## 2026-09-01 — Date slices are fetched as they are settled, and the total is asserted

**Decision.** Each date slice is fetched immediately after its count is known, rather than
planning all slices first. A run whose deduplicated PMID total does not equal the
whole-range count fails, with its manifest written for inspection.
**Reason.** E-utilities history handles expire; planning twenty-three slices before
fetching any would leave the earliest handles idle for minutes. Asserting the reconciliation
rather than logging it means a silent partial pull cannot reach the figure — which is the
failure mode that produced this fix in the first place.
**Verification.** Slicing was proven behavior-preserving: on a small query, the sliced and
deduplicated output was identical to the pre-fix single-search output, cell for cell.
**Consequence.** Slices overlap by about 17% on the real corpus, because a publication-date
filter matches both electronic and print dates and 2025 must be split into months. The
overlap is deduplicated by PMID and reported.

## 2026-09-01 — Clinical theme narrowed: 93 papers, measured over the whole population

**Decision.** The regulatory-only `clinical_fda` category matches 93 corpus papers at 95.7%
precision. Precision was measured by downloading all 834 corpus records containing any
regulatory vocabulary and reading all 93 matches, rather than by sampling.
**Reason.** A 93-paper category puts too few records into a 3,000-record sample to measure.
**Patterns rejected on measurement.** Bare "regulatory approval" was 44% precise (nine of
sixteen were aspirational — "further validation and regulatory approval are needed"), so
only possession-constrained forms ship. Generic FDA patterns now require a software or
device noun within 90 characters, because without it they matched drug and radiotracer
approvals discussed inside genuine AI imaging papers.
**Residual error.** Four false positives remain, all drug or biomarker approvals inside real
AI imaging papers. No pattern separates them without losing true positives.

## 2026-09-01 — Bare "x-ray" is not used

**Decision.** The `xray` row matches named examinations — radiograph, chest radiograph, CXR,
plain film, fluoroscopy — and not the bare string "x-ray".
**Reason.** Measured at roughly 31% precision. It leaks five ways at once: radiotherapy dose
("exposed to X-ray radiation, 3 × 8 Gy"), X-ray fluorescence, DXA, the X-ray physics of CT
("CT uses x-ray radiation"), and mammography ("a low-dose X-ray technique"). Excluding the
crystallography family alone does not fix it. The adjective "radiographic" is also excluded,
because in oncology it is RECIST vocabulary describing CT and MRI.
**Measured result.** `mammography` 16 of 16 precise; `xray` about 17 of 18. Adding both cut
the `other` modality from 22.7% to 18.9% of the corpus.

## 2026-09-01 — Panel B splits into two stacked plots

**Decision.** Two line plots sharing one x-axis: high-volume themes above, low-volume below,
each with its own linear scale. Per-year counts throughout.
**Alternatives.** One linear plot (small themes invisible); cumulative counts (monotone, but
hides the acceleration the sketch was about); a log axis (cannot draw the eight consecutive
zeros that are the review's argument); four small multiples (loses volume comparison).
**Reason.** Author's decision. Theme sizes differ by two orders of magnitude. Splitting keeps
per-year shape, keeps small themes readable, and distorts nothing.

## 2026-09-01 — Retryability is decided by response body, not status code

**Decision.** An HTTP 400 whose body carries an NCBI timeout signature is retried with
backoff; a 400 that is a genuine client error still fails immediately.
**Reason.** NCBI returns transient server timeouts with a client-error status code, which
killed a corpus pull twenty slices in. Making all 400s retryable would have turned the
`retstart` ceiling bug into twenty minutes of silent retries instead of a clear error.
**Related.** Batches that fail transiently are refetched at half size rather than retried at
the same size, since large responses are what time out. Runs append a progress journal, so a
killed run resumes from digest-verified files. Verified live by killing a run mid-flight:
output was byte-identical across single-search, sliced, and killed-then-resumed routes.

## 2026-09-01 — batch_size 200, not 500

**Decision.** Fetch 200 records per request.
**Reason.** Measured on the real query: 500 records is a 9.7 MB response at 3.7 s median,
200 is 3.9 MB at 1.6 s. Over the whole corpus 500 saves 42 seconds — 13% — at 2.5 times the
response size. Large responses are what NCBI times out on, and this pull is not on anyone's
critical path.

## 2026-09-01 — `config/*.yaml` has one owner

**Decision.** The search-strategy role owns the term dictionaries. Nobody else edits them;
changes are routed rather than applied directly.
**Reason.** Two agents edited `modalities.yaml` concurrently and one wrote unmeasured
patterns over measured ones — including the bare `x-ray` pattern that had already been
measured at 31% precision and rejected. The overlap was caught and merged, keeping the
measured patterns, but only by luck of timing.

## 2026-09-02 — Corpus retrieved: 44,625 records, reconciled

**Fact, not a decision.** The full pull ran in 8.9 minutes: 23 date slices, 53,575 records
fetched, 8,950 duplicates dropped, 44,625 unique PMIDs, matching the whole-range count
exactly. No batch needed splitting. The corpus grew by 8 records between the design-time
measurement (44,617) and retrieval, as PubMed does daily. Raw capture and manifest are at
`data/raw/2026-09-02/`.

## 2026-09-02 — `other` becomes an additive modality, and two data types get their own rows

**Decision.** `other` may now appear alongside named modalities and takes its own include
patterns. Two new rows are added: `genomics` (Genomics / Transcriptomics) and
`clinical_data` (Clinical / EHR Data). Fifteen modality rows in total. Neither new row
counts toward the radiology/pathology `domain` rule.
**Reason.** Measured on the real corpus: 61.6% of the 5,796 multimodal-integration papers
carried exactly one named modality, and 44.8% of those mention genomic, clinical, or
proteomic data. Because `other` fired only when nothing named matched, a paper using MRI and
genomics read as "MRI alone" — so the theme named for multimodality was about to be drawn as
overwhelmingly unimodal. Table 1 of the task spec defines Other as "all other modalities",
which is additive; the residual-only reading was a misimplementation of the spec, and naming
the two largest unnamed data types is more informative than lumping them.
**Consequence.** Modality labels no longer partition the corpus. Panel A's combination counts
will change materially, and the tail share must be re-checked before the 8-combination cap
is confirmed.

## 2026-09-02 — Records outside the date window are dropped

**Decision.** Records whose parsed year falls outside `date_range` are excluded, counted, and
reported. The window is read from the config, not hard-coded.
**Reason.** 84 records (0.19%) parse to 2014 or earlier because they were posted online in
2014 and issued in 2015 or later; PubMed's publication-date filter caught them, and our
first-appearance year rule dates them correctly to 2014. The year rule stands. But the effect
is a biased partial 2014 — only those 2014-online papers that happened to be issued later —
which is the mirror of partial 2026 at the other end of the axis.

## 2026-09-02 — Vocabulary v2: genomics, clinical data, additive other

**Result.** The fix works and was measured, not assumed. On a 3,000-record sample, the share
of multimodal-integration papers carrying exactly one modality fell from 65.1% to 45.3%, and
48.5% of the previously-single-modality papers gained a second label. That independently
reproduces the 44.8% estimate from the production run, which is the strongest available
evidence that the new rows capture the population that was being missed. The residual 45.3%
is not all error: a multiparametric MRI study legitimately occupies one row.

**`genomics`** — about 4,280 corpus papers, 19 of 20 precise. The boundary with
`spatial_transcriptomics` was measured, not guessed: bare "transcriptomic" matched 28 of the
29 spatial papers and would have made that row redundant; bare "gene expression" raised the
overlap from 14 to 23, because it describes the spatial assay itself. Neither ships. With the
shipped patterns the overlap is 14 papers, of which 12 were read and confirmed as genuinely
integrating non-spatial molecular data. Two collisions are guarded: "10x Genomics" the vendor,
and "tissue microarray", which is a histology term.

**`clinical_data`** — about 3,630 corpus papers, roughly 96% precise over 49 records read
across two independent samples. Bare nouns are unusable and none ships: "clinical data",
"clinical features", and "clinicopathologic" almost always describe the cohort, not a model
input. Every shipped pattern requires a record system, a named hybrid type, or fusion
phrasing.
**The honest limitation is not the precision figure.** The category counts papers that *say*
they fused clinical variables with imaging. It over-counts papers that merely report clinical
variables alongside a model, and under-counts papers that fuse without saying so. It is not a
precise count of multimodal clinical-imaging models, and the legend must not claim it is.

**`other` additive** — 23 patterns, 14 of 14 precise; 294 papers match a pattern and 383 more
arrive by the no-named-modality fallback. One pattern was rejected on measurement:
"radiotherapy dose" fired on acquisition dose in 24 of 26 cases — a scanner setting, not a
data type.

**Dead patterns.** Four of the five that never fired were confirmed absent from the corpus and
removed. The fifth was a near-miss rather than dead weight and was rewritten.

## 2026-09-02 — Panel A: twelve columns plus an explicit remainder bar

**Decision.** Each theme block shows its top twelve modality combinations and then a
separate, visually distinct column carrying every remaining paper in the theme, labeled "all
other combinations", with the number of distinct sets it represents printed beneath it. Bars
sum to the theme total.
**Alternatives.** Raise the cap to twenty and state the tail (still hid 28% of multimodal
papers, and eighty narrow columns across four blocks); drop single-modality columns and show
only co-occurrences (changes what the panel means).
**Reason.** Making `other` additive roughly doubled the distinct combinations per theme —
multimodal integration went to 314 — because a paper gaining `other` beside a named modality
creates a new set rather than joining an existing column. At the old cap of eight, that theme
hid 48.7% of its papers, and the project had already committed to the principle that a cap
hiding most of the data is a failed figure. A remainder column hides nothing: the reader sees
exactly how much lives in the tail, which for this theme is the interesting part.
**Consequence worth stating in the manuscript.** Multimodal integration's twelve largest
columns are mostly *single* modalities; its multimodality is dispersed across hundreds of
small combinations. The dispersion is a finding, not a defect of the drawing.

## 2026-09-02 — Final corpus after all exclusions

**Fact.** 44,625 records retrieved; 8 book records and 84 records outside the 2015-2026
window excluded; **44,533 papers analysed**. Themes: foundation models 1,529, multimodal
integration 5,794, digital twins 64, clinical/FDA 94; 37,454 papers carry no theme.
Within the multimodal-integration theme, papers carrying two or more modality labels rose
from 23.1% to 54.0% once `other` became additive and the two data-type rows were added.
Corpus-wide the figure is 32.9%, or 28.9% counting named modalities only. The 54.0% belongs
to that theme and must not be quoted as a corpus figure.

## 2026-09-02 — Panel A is drawn on a share scale

**Decision.** Panel A bars show each combination's percent of its own theme's papers, not raw
counts. Exact counts remain in `figures/trends_figure_summary.txt` and in the classification
report.
**Reason.** Measured on the real data, not argued in the abstract. Under a shared count scale
the multimodal remainder bar (2,149 papers) sets the axis, and both small themes draw as
hairlines indistinguishable from the axis line — including their remainder bars. That is the
worst possible failure for this figure: the count scale makes the remainder look like a
rounding error in precisely the two blocks where the remainder is a third of the theme. Under
share, all four blocks are legible, bars sum to 100% by construction, and multimodal
integration's remainder reads as what it is — the largest bar in its block, taller than MRI
alone.
**Cost.** In a 64-paper theme percentages are coarse: one paper is 2%, and five bars read 3%.
Volume is carried instead by Panel B and by the `n =` printed under each block.
**Related.** A broken or logarithmic bar axis was rejected earlier for a different reason and
remains rejected; see the note at the top of `panel_a.py`.

## 2026-09-02 — Validation round 1: the classifier is good at modalities, weaker at themes

**Result.** 200 papers, six disjoint strata, seed 20260902, labeled blind — the labeling sheet
carried item, PMID, title, and abstract, and nothing else.

Imaging modalities held up: CT, MRI, PET, ultrasound, and mammography ran 85-96% precision
and 94-98% recall. `clinical_fda` ran 92% precision and 96% recall, which vindicates measuring
that category over its whole population rather than sampling it.

Themes were weaker. `foundation_models` 59% precision, `digital_twins` 68%,
`multimodal_integration` 64% precision and 69% recall. `clinical_data` recall 41%.

**Causes traced, not guessed.** 12 of foundation models' 19 false positives come from one
pattern matching "self-supervised" — a training technique, not a foundation model. Eight of
fourteen `multi-modal` false positives are multiparametric MRI. Eleven papers fire the fusion
patterns on network architecture rather than on data. Two acronym collisions: `LMM` matching
linear mixed-effects models and `PRISM` matching a drug-screen compound set.

**What may be claimed.** Per-category rates with their counts, against agent labels calibrated
by an author audit. **No single accuracy number exists**: precision runs from 25% to 100% and
the strata are not proportional to the corpus. The agent demonstrated that weighting the strata
back to corpus scale reproduces known counts with a median error of 19% and a worst case of
+106%, so no weighted corpus projection may be published.

**Two facts belong in the manuscript, not only the legend.** The digital-twins count of 64 is
roughly two-thirds genuine, and `clinical_data` under-counts by about half.

## 2026-09-02 — Patterns revised after validation, so validation is repeated on a fresh sample

**Decision.** The defects above are being fixed, then classification re-runs and a **fresh
sample with a new seed** is drawn for the affected categories. Both rounds are reported.
**Reason.** Changing patterns after inspecting a validation sample means that sample no longer
measures the revised dictionary — it has been fitted to. Reporting round one alone would
overstate the fixed classifier; reporting round two alone would hide that the patterns were
revised after seeing data.
**Boundary held.** Fixes must address the defect a paper revealed, not the paper. Dropping
"self-supervised" because self-supervised learning is not a foundation model is a definitional
fix; adding an exclusion aimed at one title would be fitting.
**Also recorded.** The sample cannot see what the corpus query itself missed. None of these
figures bound recall against the literature — only against the corpus.

## 2026-09-02 — The author's audit sheet waits for the revised labels

**Decision.** Hold the 50-row audit sheet until the revised classification has run.
**Reason.** The sheet carries the rule labels beside each abstract. Auditing labels that are
about to change would spend an hour of the author's time on a version of the classifier that
no longer exists.

## 2026-09-02 — Dictionary v3: seven validation-driven fixes, costs measured

**Decision.** Both term dictionaries move to version 3. Each fix was measured for what it cost
in genuine hits as well as what it removed.

| Fix | Effect |
|---|---|
| Dropped "self-supervised" from foundation models | theme falls roughly 1,610 → 1,320 |
| Dropped `LMM`, after rescuing its genuine hits (see below) | no genuine loss |
| Dropped `PRISM` | no genuine loss in a 12-record read |
| Moved "imaging mass spectrometry" to `other`, added "secondary ion mass spectrometry" | spatial proteomics 19 → 15 per sample |
| Dropped "patch-level" from H&E | no measurable change |
| Constrained the fusion patterns, added a context-aware mpMRI exclusion | multimodal 358 → 291 per sample |
| Broadened `clinical_data` for recall | +57% records, precision 96% → 94% |
| Qualified `TCGA` to require a molecular noun | genomics+H&E co-occurrence −31% |

**Three findings worth keeping.**

*The qualified self-supervised pattern was built, measured, and rejected.* Requiring
foundation-model language near "self-supervised" added exactly one record, itself doubtful. A
fix that recovers nothing is not worth its complexity. "Zero-shot" and "few-shot" were dropped
for the same definitional reason — they are evaluation regimes characteristic of foundation
models but not exclusive to them — and that goes beyond the reported defect, so it is flagged
for the fresh validation round to test rather than assumed correct.

*`LMM` was not purely a collision.* Two of its six corpus records were genuine: "Large
multimodality model" and "Large multimodal model". Dropping the acronym alone would have lost
them, so the spelled-out pattern was broadened first and verified to catch both. Net cost zero.
The general lesson: a colliding acronym may still be carrying real hits nobody else catches.

*The mpMRI exclusion had to be context-aware.* A blunt exclusion on "multimodal MRI" fires on
18 records, six of which genuinely pair MRI with another data type. The shipped exclusion fires
only when no other data type is named anywhere in the record. Building it caught two errors in
its own first draft, which had wrongly excluded an MRI-plus-liquid-biopsy paper and an MRI-EEG
digital-twin paper.

**TCGA, the most consequential fix.** Independent reproduction of the measurement: 71% of
TCGA-only papers also carried H&E, against 66% measured here. Of 24 such papers, 21 were
dropped and all 21 were read — pathomics signatures, whole-slide tumour recognition, slide
retrieval, and prediction *from* histology. The change costs one or two genuine hits. It trades
a little real recall to remove a much larger amount of manufactured co-occurrence in exactly
the pairing the figure exists to display.

**Net effect on the multimodal theme.** Papers carrying two or more modality labels: 21.2% at
v1, 54.7% at v2, **64.6% at v3**.

**Standing caveat, now more important, not less.** `clinical_data` counts papers that *say*
they fused clinical variables with imaging. Broadened to 382 sample records it will over-count
papers that merely mention clinicopathological factors in a statistical adjustment.

## 2026-09-02 — Digital twins measures interest, not construction

**Decision.** The `digital_twins` theme counts papers that engage with the digital-twin
concept in any capacity — proposing a framework, building a component toward one, or naming
it as a future direction — not only papers that build something meeting the manuscript's
criteria. Author's decision, correcting a brief written against the strict reading:

> "This figure is meant to track trends of interest in the literature, not successful
> construction of a digital twin."

**Consequence for Panel A's meaning.** It is no longer uniform across themes. Three themes
count the data a study consumes; digital twins counts engagement with an idea. The legend
must say so.
**Consequence for the pipeline.** Good: under the inclusive standard the residual error is
only lexical collision — the CamelCase acronym "DiGital tuMor pArameTErs", "Digi-TAS",
"DGMate", "digital patient files", "digital tumor signatures" meaning autoencoder latents, VR
surgical avatars, a "patient avatar" that is a 3D photograph, and a "Twin-GRU" whose authors
disclaim the twin sense. Patterns can remove those, so the theme stays fully rule-based and
reproducible with no hand-curation in the path.
**Recall is now the binding problem.** Under a strict standard, missing an aspirational
mention cost little. Under "any capacity" it costs a great deal, and one of the strongest
papers in the row entered only through its closing sentence. Terms rejected earlier against
the strict reading — "virtual patient", "virtual cohort", "in silico patient" — are being
re-measured against this one.

## 2026-09-02 — The strict screen is kept as a finding in its own right

**Decision.** Both verdicts are retained per paper, `verdict_strict` and `verdict_inclusive`.
**Reason.** Of 64 candidate papers, 18 build something meeting the manuscript's criteria while
21 more only gesture at the concept, over half of those in a closing sentence. Of the 34 papers
dated 2026, 22 are strict drops — largely reviews of other subjects that added digital twins to
a closing list. **The phrase is growing faster than the literature.** That is a publishable
observation for a review whose stated posture is to resist definitional drift, and it lets the
manuscript write "N papers engage with the idea, of which 18 build something meeting our
criteria." Discarding the strict screen would have thrown away the evidence for that sentence.

## 2026-09-02 — Dictionary v4

**Shipped.** `genomics` restricted to input use — all 17 dropped records were the target class
(radiomics predicting mutation status, deep learning predicting alterations from histology).
`MIBI` removed outright rather than guarded: the technetium-prefix guard was built and measured,
still admitted "Ultrasound and MIBI are the most commonly used imaging methods", and all five
genuine multiplexed-ion-beam papers survive removal through other patterns. The mpMRI exclusion
was rewritten to key on sequence names rather than phrase order. `early/late/intermediate fusion`
removed. The two auxiliary digital-twin patterns removed after the hand screen found they
contributed zero unique records.
**Residue that cannot be fixed at abstract level.** A paper predicting molecular subtype from
histology that also mentions the sequencing used to generate its ground-truth labels survives
the input-only rule. Tightening the rescue clause changed nothing. Documented, not papered over.

## 2026-09-02 — The operational line for "engages with the digital-twin concept"

**Decision.** A paper counts if it **invokes the digital-twin idea itself, in the twin
vocabulary** — not merely if it supplies something a twin would need.
**Reason.** "A building block for one", read broadly, has no stopping point: every
longitudinal imaging study is a building block, and the theme swallows the corpus. This line
keeps the inclusive standard the author asked for while remaining decidable from an abstract.
It is what separates two otherwise similar Monte Carlo papers — one whose authors write "each
patient was represented by 75 digital twins", and one using ordinary phantom vocabulary that
predates the digital-twin literature — and it is why bare "mechanistic model" is not added to
the vocabulary.
**Inclusive screen result.** 56 of 64 keep, 8 drop. Every strict keep is an inclusive keep;
31 of the 39 strict drops flip.
**Recorded reservation.** Three of the 56 model devices rather than patients, and one models
the pathologist. They are tagged `device_or_clinician_twin`. If the manuscript describes the
block as *clinical* digital twins, those three inflate it by about 5% and can be filtered in
one line.

## 2026-09-02 — A finding the figure cannot show, worth a sentence in the review

Of the 56 papers engaging with digital twins, **18 describe a patient-specific model meeting
the manuscript's criteria, and only 3 update as new measurements arrive** — two through daily
CBCT re-optimization, one through continuous EEG. This has independent support from inside the
corpus: PMID 42330729, a scoping review of 64 diagnostic digital twins, finds 97% below
closed-loop maturity. The manuscript's claim that continuous updating is what separates a twin
from a prognostic model is therefore corroborated by this literature's own systematic
reviewers, not only by our reading.

## 2026-09-02 — Dictionary v5: a negative result on recall, and one real bug

**Result.** Every ranked recall candidate yielded **zero** unique papers.
`patient-specific computational model` (1 corpus hit), `virtual human twin` (1), and
`virtual replica` (0) are all already captured — in each case the paper uses the head term in
the same sentence as the proposed synonym. `in silico trial`, `virtual trial`, `virtual
cohort`, and bare `virtual patient` do occur uniquely but were rejected on the operational
line: they are virtual *imaging* trials over phantoms, XCAT models, and GAN synthetic data,
none of which reach for the digital-twin idea. The construction `digital <modifier> twin` does
not occur.
**So `digital_twins` ships one include pattern.** That is the finding: the field names this
idea one way.

**The operational line reverted the agent's own work.** An earlier v5 draft added
`digital patient/human model`, `virtual patient model`, and `patient-specific
simulation/computational model`, gaining five records. Tested against the line, none of the
five contains any twin vocabulary — a biobank's patient model, an image-registration
coordinate space, two 3D surgical-planning models, and a finite-element tumour-growth
simulation. Exactly the "supplies what a twin needs but never invokes it" class. Reverted.

**One fix that was not cosmetic.** A literal space in the pattern missed "modeling
digital-twin of renal functions". Tolerating a hyphen took the count 55 → 56, closing the
entire gap with the hand screen's independent figure. The pattern is now
`(?i)\bdigital[\s-]+twin(s|ning)?\b`, and the file carries a warning never to anchor it on a
modifier, since the modifiers vary without limit and all precede the head noun.

**Collisions.** All seven are gone. `patient avatars?` was removed rather than guarded — one
corpus record, displaying CNN heatmaps on 3D total-body-photography avatars, so the removal
cost nothing. No guard was needed against "digital tumour signatures", so genuine "digital twin
of the tumour" phrasing is untouched.

## 2026-09-02 — Twin-GRU is counted

**Decision.** PMID for the "Digital Twin-Inspired Closed-Loop Latent Simulation Framework" stays
in the theme, against the hand screener's strict reading, which classed it a lexical collision
because its authors disclaim the twin sense.
**Reason.** The author's standard is engagement with the idea in any capacity, and a title
framing the work as digital-twin-inspired is engagement in twin vocabulary. It satisfies the
operational line. Dropping it would require an exclusion by PMID, which is curation, not a rule
— and the theme is deliberately rule-based.
**Recorded so it can be reversed:** one paper, and the screen's `verdict_strict` column already
marks it, so anyone preferring the strict reading can filter it out.

## 2026-09-02 — Validation round 3: the genomics residue is the dominant defect

**Targeted round**, 106 papers, seed 20260904, covering only the categories changed since
round two. Rounds one, two, and three measure v2, v3, and v4/v5 respectively; the report
states which version each measured.

**The finding that matters.** The predicted-molecular-label residue — a paper predicting a
molecular subtype *from* an image, which mentions the sequencing behind its ground-truth
labels — is not a curiosity. It is 9 of 18 genomics false positives, and in the genomics ∩ H&E
stratum it is 8 of 11, where precision is **45% (95% CI 26-66%)**. Against that stratum's 853
papers, **300 to 630 of the genomics + H&E pairings are spurious**. That pairing is the cell
this figure is read for. Either it is fixed from the prediction side, or the number goes in the
legend and the manuscript. A stated 45% is publishable; an unstated one is not.

**The mpMRI exclusion demonstrates nothing.** Multimodal precision 55% (34-74%) against 67%
before — overlapping intervals. Mechanism measured: the exclusion requires both a T1-family and
a T2-family sequence to be named, but only 245 of 3,452 multimodal candidates (7.1%) name both,
so it fires on 2.4%.

**A latent defect, correctly reported as latent.** In the same context list, `SPECT` and `CT\b`
are unprotected against case-insensitive matching: `(?i)SPECT` matches "retrospective" in 51% of
the corpus and `(?i)CT\b` matches "predict" in 64%. It changes today's count by zero, because
the sequence-pair test is the binding constraint and hides it. It must be fixed before that
constraint is loosened. The validator nearly reported this as live, checked, and reported it
accurately.

**Clean results.** Spatial proteomics 93% (13 of 14), measurable for the first time since the
MIBI removal. No round-three false positive comes from a fusion term. The `following` removal
eliminated its false positive.

**Digital twins: 56 of 56 correct (94-100%)**, all read across three rounds. The validator noted
this is near-tautological — one pattern matching a vocabulary, judged against genuine use of
that vocabulary — so the defensible claim is that the collisions are gone, not that the row is
accurate in a deeper sense. Recall is independently clean: "virtual twin", "in-silico twin", and
"computational twin" match zero corpus records.

## 2026-09-02 — The audit sheet was rebuilt rather than redrawn

**Decision.** When the dictionaries moved to v5, the sheet's rule labels were refreshed in
place: the strata, seed, weights, and 200 sampled PMIDs are the sample *design* and stay fixed;
only the system under test is re-read.
**Reason.** Redrawing would have discarded the reference labeling and changed which papers are
in the sample, because the strata are defined by rule labels. 37 of the 50 audit rows are
unchanged, so author effort already spent carries over.
**Disclosed, because it is a real limitation.** The digital-twins column of that sheet was
relabeled under the inclusive standard *after* the v3 scoring was seen, so it is not blind. The
blind measurement of the new standard is round three, which is why round three read the row as
a census rather than a sample.

## 2026-09-02 — The in-figure notes move to the legend; SVG added

**Decision.** The change-of-scale note and the small-count warning no longer print in the gap
between Panel B's plots. Both statements move to the figure legend. The gap narrows from 0.34
to 0.20 inches, since it now only has to read as a break in the axis rather than hold two
lines of text. Author's decision.
**Reason.** The journal prints the legend beneath the figure, so the statements still reach
every reader, and the figure carries less furniture.
**What was kept.** The scale difference is still shown graphically — two labelled axes, a real
break between the plots, and the band on the upper plot marking the lower plot's whole range —
so removing the prose costs the reader nothing the drawing does not already say. Setting
`panel_b.SHOW_GAP_NOTES = True` restores both lines and widens the gap again to fit them; a
test asserts that switch still works, so the decision is reversible without a code edit.
**Recorded risk.** The small-count warning now rests on the legend alone. If the legend is
shortened further, that caveat should move into the body text rather than disappear — noted in
`figure-legend.md`.

## 2026-09-02 — SVG is a third output

**Decision.** Every build writes PDF, PNG, and SVG.
**Reason.** AACR redraws figures from author sketches. SVG keeps text as text, so an
illustrator can restyle every label without redrawing the figure.

## 2026-09-02 — Legend split from description

**Decision.** `docs/figure-legend.md` is the roughly 205-word legend for the manuscript.
The former long legend is `docs/figure-description.md`, a working document holding the full
account of the figure and its limitations.
**Reason.** The legend that ships must be short enough for a journal to print; the reasoning
behind it must still be written down somewhere. The description file records what was cut from
the legend, so a later editor can tell the difference between a claim that was dropped and a
claim that was never made.

## 2026-09-02 — The project moved to `CCR/figures/trends-figure/`

The editable install was re-pointed and stale `__pycache__` from the old path removed; its
compiled files were reporting the old location in tracebacks. Stale figure variants built on
superseded dictionary versions were deleted, so nothing in `figures/` predates the current run.

## 2026-09-02 — The figure follows the project's ink style guide

**Decision.** Restyled to `figures/ink_style_guide.md`. Colour is now semantic rather than
decorative: Panel A's dots take their row's fixed modality colour, Panel A's bars are neutral
because a bar is a combination rather than one modality, and the only colour in Panel B marks
the clinical theme's radiology and pathology series — which are modality-domain series, and
are also the comparison the review turns on. The other three themes are distinguished by ink
tone, dash, and marker. Type is IBM Plex Serif for panel letters and block titles and IBM Plex
Sans elsewhere; the faces are vendored at `assets/fonts/` under the Open Font Licence, and the
build raises `FontsUnavailable` rather than substituting Georgia and Arial silently, as §2
requires.

**Three annotations were removed from the artwork** under §6, which reserves the artwork for
functional labels of four words or fewer: the pathology zero-run callout, the sentence
explaining the dashed range rule, and the "top 12 of N combinations" line. All three moved into
the legend. Removing them let the gap between Panel B's plots close and the lower plot's
headroom tighten, which moved the published scale ratio from 36× to 43×; the legend and the
description were updated together.

**One deliberate departure from the guide, recorded in code and asserted by a test.** §4
assigns its pale hatch — `#F0F0F0` ground, `#BDBDBD` lines — to "masked, hidden, or inactive"
elements. Panel A's remainder column is none of those: in the multimodal block it is 45% of the
theme and the tallest bar present, and this project had already resolved not to let a redraw
shrink it into a rounding error. Rendered to the letter of §4 it became the faintest mark in
the block. It is hatched in the bars' own ink instead, which keeps it visibly a different kind
of quantity while carrying the weight its height deserves. A test asserts the hatch colour
equals the bar fill, so restoring the pale spec fails rather than passing review.

**Type was not scaled literally.** The guide's sizes are units on a canvas about 1,355 wide;
this figure is 540 pt wide, so literal scaling puts body text near 5 pt and the guide's own
9.5-unit floor near 3.8 pt — below print legibility, and below floors this project had already
measured and tested. The guide's hierarchy and its ratios are preserved at the tested sizes.

**Two greyscale defects were measured and fixed** while applying the palette: the pathology
line was the lightest stroke on the page at luminance 151, which mattered because it carries
the review's central argument, and now uses the guide's deep pathology tint at 100; and the
genomics dots had the narrowest margin against the absent dots, widened from 52 to 65 by
lightening the absent dot rather than by altering a fixed assignment.

**Open, and not ours to settle.** The guide names `figure1_ink_2x2.svg` and `build_variants.py`
as the reference implementation — "when in doubt, match it" — and neither is in this
repository. Four things had to be decided without them: the hatch stroke weight, which grey
"1 px gray border" means, which neutrals the Panel B theme series take, and whether Panel A's
row labels count as tick labels or as primary labels. Those four are where this figure and
Figure 1 could drift apart.
