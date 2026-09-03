# Current Clinical Operations — full rewrite (draft)

Drop-in replacement for `CCR_reviews/main.tex` lines 264–281, between the existing
`%%%%%%%%%% CURRENT CLINICAL OPERATIONS SECTION START/END` markers.

**Not applied.** `main.tex` is owned by another process.

---

## LaTeX

```latex
%%%%%%%%%% CURRENT CLINICAL OPERATIONS SECTION START
\section{Current Clinical Operations}

Radiology and pathology are separated in the clinic by regulatory and infrastructural history more than by algorithm quality. Through 30 March 2026 the FDA had authorized 1,524 AI-enabled devices, of which 1,164 carry the Radiology panel and nine carry Pathology~\cite{FDA2025AIDeviceList}. That comparison spans all indications and overstates the oncology gap. Restricting to product codes that are cancer-directed by their own regulation definition leaves 145 radiology authorizations against the same nine, and 79 of the 145 are radiation therapy planning or auto-contouring, so the like-for-like diagnostic comparison is 66 to nine (Figure~\ref{fig:clinops}). Even 145 is a floor: roughly 800 devices sit under generic codes whose oncology status cannot be recovered from published fields. The pathway split is the more informative number. Of the 145 radiology authorizations, 140 were cleared as 510(k)s against existing predicates, with two De Novo and three PMA; pathology's nine divide evenly, three of each. Radiology iterates inside device categories that already exist; pathology has had to create a new one almost every time. None of these counts is evidence of local clinical utility, and routine use is not autonomy.

\subsection{Current Clinical Operations in Radiology}

Mammography carries nearly all of the prospective evidence. MASAI, a randomized, single-blinded non-inferiority screening trial and the only randomized trial in this literature to have reported, found that AI-supported reading cut screen-reading workload by 44\% without loss of detection; its endpoints were workload and cancer detection, not mortality~\cite{Lng2023}. PRAIM measured adoption instead. Among 461,818 women at 12 German sites, 260,739 of them screened with AI support, detection rose from 5.7 to 6.7 per 1,000 with slightly lower recall, normal-case reading time fell from 67 to 39 seconds, and a safety net surfaced 204 cancers that would otherwise have been missed, while radiologists found 20 cancers among examinations the model had called normal~\cite{Leibig2025MammographyAI}. That is augmentation, not autonomy, and three features of the design bound the claim: PRAIM was observational, radiologists chose whether to use AI, and some preferentially opened the AI viewer for cases they had already judged normal, an unanticipated selection bias corrected post hoc with propensity-score overlap weighting. More than half the detection gain was ductal carcinoma in situ, up from 0.8 to 1.4 per 1,000 against 4.8 to 5.2 for invasive cancer, raising an overdiagnosis question the design cannot answer. A Danish regional program reports larger effects in the same direction across 156,151 AI-supported screens: detection 6.5 to 7.8 per 1,000, the two-year interval-cancer ratio 30.3\% to 26.7\%, and 36\% less reading work. It is an unreviewed preprint against historical controls screened at different intervals, and four of its five authors hold financial interests in ScreenPoint Medical, whose software it evaluates~\cite{lauritzen_comprehensive_2025}. A paired non-inferiority trial extends AI triage to tomosynthesis~\cite{RodriguezRuiz2026DBT}.

Outside mammography the evidence thins quickly. A rapid evidence assessment of 11 chest radiograph triage studies found a weighted mean 42.3\% of examinations autonomously triageable at a pooled sensitivity of 97.8\%; pooled specificity was 94.8\%, but its 95\% confidence interval ran from 53.0\% to 99.7\%, and only three of the 11 studies used datasets reflecting real-world disease prevalence~\cite{vasilev_2025}. The interval, not the point estimate, is the result. Across 38 implementation studies in routine imaging, 82\% measured efficiency and 71\% of those reported improvement, yet only 13\% measured workload and 34\% reported any patient outcome; success turned on workflow fit, training, local testing, and continuous maintenance, and poor integration erased technical gains outright~\cite{wenderott_facilitators_2025}. Maintenance is the determinant most easily deferred and the one that model drift (Table~\ref{tab:glossary}) makes non-optional.

\subsection{Current Clinical Operations in Pathology}

All nine pathology authorizations are cancer-directed, though not all are whole-slide image algorithms, and their timing is the argument. Two are neural-network Papanicolaou screeners cleared in 1995 (PAPNET, AUTOPAP); nothing followed until Paige Prostate in 2021, then Tempus xT CDx in 2023, Genius Digital Diagnostics in 2024, and four in 2025 (Galen Second Read, ArteraAI Prostate, GENESEEQPRIME, INFINITT DPS)~\cite{FDA2025AIDeviceList}. The rate limiter is not the model but the laboratory: digitization, scanner and stain harmonization, whole-slide storage, quality control, and integration with the laboratory information system~\cite{omoush2026theroleof}. Credible uses stay narrow, and one recent evaluation shows their ceiling. EagleEye read 99 archived cervical punch biopsies at 93.3\% sensitivity and 71.8\% specificity for CIN2+ against the original sign-out, but the cohort was retrospective, single-center, and deliberately balanced across grades, so those operating characteristics are not the ones a routine case mix would produce; the system ran standalone in a laboratory that was not fully digitized, and reading time, workload, and workflow effects went unmeasured. Its authors correctly classify the efficiency claims as hypothesis-generating~\cite{andreassen_digital_2025}. Diagnostic accuracy in an experimental reader study is not deployed operational benefit.

The same digitization changes how researchers work with clinical-grade tissue. Digitized archives and AI-enabled workflows are entering clinical trials for central review, stratification, and prescreening, including models that read a targetable mutation such as AKT1 E17K from routine H\&E in place of sequencing~\cite{sebastian2026applicationsandchallenges}. Those demonstrations are retrospective and not pre-specified, are sensitive to wet-lab and scanner variation, and would face years of model locking, analytical verification, and clinical validation to serve as companion diagnostics. What pathology needs from both directions is the same: prospective measurement of case time, re-review burden, discrepancy resolution, turnaround time, and outcomes.

\subsection{Overall trend in current clinical operations}

Clinical AI is shifting from isolated ``second-reader'' algorithms toward workflow redesign: risk-based triage, delegation of confident normals, and safety-net alerts. The strongest evidence supports human--AI teams on bounded tasks, and the step most programs stop at is shadow deployment (Table~\ref{tab:glossary}). Mammography is the one setting where the workflow question has been asked prospectively at scale; chest-radiograph triage is scaling on thinner evidence; and pathology remains infrastructure-limited, its device count a measure of how few regulatory categories exist rather than of how few models work.

%%%%%%%%%% CURRENT CLINICAL OPERATIONS SECTION END
```

---

## Word count

**968 words**, against 408 for the text it replaces (+560). Counted with the same
method used on the current section: cite keys, LaTeX macros, and braces stripped;
section headings included (19 of the 968). Prose only: 949.

Per paragraph: lead-in 184 · radiology/mammography 258 · radiology/other 131 ·
pathology 185 · researchers 97 · trend 85.

Per the brief I wrote what the argument needs rather than to budget. If the section
has to come back toward 400–500, cut in this order — each item is self-contained and
loses one qualification rather than one claim:

| Cut | Saves | What is lost |
|---|---|---|
| The `RodriguezRuiz2026DBT` tomosynthesis sentence | 12 w + **1 reference** | An extension, not a claim. Cheapest cut in the section. |
| Lauritzen's three effect sizes, keeping only the conflict-of-interest and preprint caveat | ~30 | Numbers from a study we are already discounting. |
| PRAIM's DCIS/overdiagnosis sentence | ~35 | Required by the Edison source; cut only under duress. |
| The 800-generic-codes floor caveat | ~28 | Honesty about the 145. Do not cut this before the two above. |
| EagleEye's spectrum-balance qualification | ~25 | The reason its 71.8% specificity is not a routine-practice number. |

---

## Citations

**Net change: zero.** The section cites the same ten keys it cited before —
`FDA2025AIDeviceList`, `Lng2023`, `Leibig2025MammographyAI`,
`lauritzen_comprehensive_2025`, `RodriguezRuiz2026DBT`, `vasilev_2025`,
`wenderott_facilitators_2025`, `omoush2026theroleof`, `andreassen_digital_2025`,
`sebastian2026applicationsandchallenges`. Nothing added, nothing dropped, no
`[CITE!]` markers needed. All ten verified present in `CCR_reviews/bibliography.bib`.

This matters because the active zone (`main.tex` lines 35 to the archive banner) is at
**75 unique keys against a 75 cap**, with AI in Radiology still unwritten. Any citation
added here would have had to be paid for. Two ways to *return* a reference from this
section if radiology needs one:

1. Drop `RodriguezRuiz2026DBT` (used only here; a one-clause extension).
2. Drop `omoush2026theroleof` (used only here) and let the digitization claim lean on
   `polit2026digitalpathologyand`, already cited in AI in Pathology and therefore free.
   `omoush` is the better citation for the specific claim, so this is a real trade.

The editor's second charge — how AI changes the way *researchers* interact with
clinical-grade imaging data — is now covered by the second pathology paragraph, built
on `sebastian2026applicationsandchallenges`, which was already cited. No new reference
was needed for it.

**Build check.** Compiled against a scratch copy of `main.tex` with this section
swapped in: 0 LaTeX errors, 0 undefined citations, 0 BibTeX "didn't find a database
entry". The only warning is `Reference 'fig:clinops' undefined`, expected until the
figure float exists.

---

## What I could not verify

- **MASAI's 44% workload reduction.** Not present in any project source; already flagged
  in `STATUS.md` §6 as taken from model knowledge. Carried over unchanged from the
  current draft. The design description ("randomized, single-blinded non-inferiority
  screening accuracy") *is* verified — it is the bib entry's title.
- **`RodriguezRuiz2026DBT`.** Verified only to the bib title: a paired, non-inferiority
  trial of AI triage and decision support in mammography and tomosynthesis. No numbers
  asserted, deliberately.
- **AKT1 E17K from H&E.** Reported inside `sebastian2026applicationsandchallenges` as
  work shown at Pathology Visions 2025, i.e. a conference report reached through a
  review. I hedged it as an example and attached the review's own limitations. If the
  author would rather not cite a conference result at second hand, the sentence works
  without it: strike "including models that read a targetable mutation such as AKT1 E17K
  from routine H&E in place of sequencing" and keep the trials clause.
- Everything else — PRAIM (all figures, the selection bias, the propensity weighting,
  DCIS 0.8→1.4 vs invasive 4.8→5.2), Lauritzen (all figures, historical controls, the
  ScreenPoint conflict), `vasilev_2025` (42.3%, 97.8%, 94.8% with 95% CI 53.0–99.7%,
  3 of 11 real-world prevalence), `wenderott_facilitators_2025` (38 studies, 82/71/13/34,
  the determinants), `andreassen_digital_2025` (99 biopsies, 93.3%/71.8%,
  spectrum-balanced, standalone, not fully digitized) — is verified against
  `docs/CCR_Review_DTs_Clinical_edison.pdf` §4 or against the bib entry's own abstract.

### One number I corrected rather than carried over

The current draft says pooled specificity "spanned 53.0–99.7%". That is not a range
across studies — it is the **95% confidence interval around a pooled specificity of
94.8%** (`vasilev_2025` abstract, in the bib). The rewrite states it that way, which is
both accurate and a stronger version of the same point.

### One ambiguity I resolved

The current draft's "82% measured efficiency and 71% reported improvement" reads as two
percentages of the same denominator. In the source they are not: of the 82% that
measured efficiency, 71% reported improvement, 6% harm, 23% no change (they sum to 100).
Rewritten as "82% measured efficiency and 71% of those reported improvement".

---

## Where the author's judgment is needed

1. **The four 2025 pathology authorizations are named in the text.** The brief supplied
   them, and naming is the house convention. But they are not all the same kind of
   object — INFINITT DPS is digital pathology display/management software, not a
   diagnostic algorithm — which is why the paragraph opens with "though not all are
   whole-slide image algorithms" rather than claiming nine deployed algorithms. If that
   hedge feels too thin to carry four product names, drop the parenthetical and keep
   "four in 2025".

2. **Naming Tempus xT CDx.** `RULES.md` §4 records an explicit instruction not to list
   Tempus as having FDA-cleared *pathology AI* — that warning was aimed at an error in
   `docs/literature_review.md`. The new snapshot puts Tempus xT CDx among the nine
   Pathology-panel authorizations, which is a different and defensible statement, and the
   sentence is about the timeline of authorizations rather than about image algorithms.
   Flagging it so the decision is deliberate rather than accidental.

3. **Cross-section consistency with AI in Pathology.** `main.tex:185` currently reads
   "only four image-based oncology pathology algorithms have been authorized by the FDA,
   against more than a thousand in radiology" — citing `FDA2025AIDeviceList`. Under the
   new snapshot that sentence is stale on both halves, and its "more than a thousand"
   is the all-indications radiology number paired against an oncology-only pathology
   number, which is exactly the conflation this rewrite removes. Someone should
   reconcile 185 with the new numbers; I did not touch it.

4. **`fig:clinops` needs an actual float.** The `\ref` is in place, but the
   `\begin{figure}...\caption{...}\label{fig:clinops}\end{figure}` block does not exist
   yet. Journal rules require a legend for every float, and this takes the manuscript
   from 1 of 5 floats to 2 of 5.

5. **The `[CITE!]` at `main.tex:82`** is untouched and still open. Not mine, noting it.

---

## Bibliography defects (verified — not fixed, another process owns the .bib)

Checked against `CCR_reviews/bibliography.bib` and against the rendered `main.bbl`.

| Reported | Status | Detail |
|---|---|---|
| `wenderott_facilitators_2025` duplicated | **Not confirmed — no duplicate exists** | Exactly one entry, line 1412. `grep -c '^@article{wenderott_facilitators_2025,'` returns 1, and a duplicate-key scan over the whole file finds none. What is probably being seen: a *second, different* Wenderott paper, `wenderott_integration_2022` at line 1427 (Wenderott, Gambashidze, Weigl — a different study). Leave both. |
| `vasilev_2025` has `YEAR={2026}` | **Confirmed, and worse than reported** | Line ~1390. `YEAR={2026}` against a 2025 key, plus `VOLUME={Volume 7 - 2025}` — a literal string, not a volume number. It renders as `Frontiers in Digital Health. 2026;Volume 7 - 2025.` Should be `year={2025}`, `volume={7}`, and it needs an article number (`pages={1685771}`); the entry has none, so the reference has no locator at all. |
| `Leibig2025MammographyAI` has `others`, first author is Eisemann | **Confirmed, plus two more defects** | (a) `author = {Eisemann, Nora and Bunk, Stefan and Mukama, Taulant and others}` renders `Eisemann N, Bunk S, Mukama T, et al.` — three authors before *et al.*, where CCR/Vancouver requires **six**. Correct byline: Eisemann N, Bunk S, Mukama T, Baltus H, Elsner SA, Gomille T, et al. (b) The third author's given name is **Trasias**, not Taulant. (c) The key itself says Leibig, who is the thirteenth author, not the first — cosmetic, but it is what led to the mis-citation in the first place. |
| `FDA2025AIDeviceList` note is stale | **Confirmed** | `note = {Authorized device list; 1,430 entries through 30 December 2025. Accessed 2026}`. Needs the new snapshot: **1,524 entries through 30 March 2026**. Also consider `year = {2026}`. |

Two further defects found while checking:

- **`FDA2025AIDeviceList` author renders as `{U S  Food and Drug Administration}`** —
  the double-braced `{{U.S. Food and Drug Administration}}` loses its periods and gains a
  double space in the Vancouver output. Cosmetic, but a copy-editor will query it.
- **`RodriguezRuiz2026DBT` carries `doi = {10.1038/s41591-026-04277-x}`.** Nature Medicine
  DOIs run `s41591-0YY-...` where YY is the two-digit year; `026` is not a form that
  appears in the other Nature Medicine entries in this bib (`Leibig2025MammographyAI`
  uses `s41591-024-03408-6`). Worth resolving the DOI before submission — I could not
  verify it offline.
