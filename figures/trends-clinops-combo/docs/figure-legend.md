# Figure legend — combined four-panel figure

CCR house form: bold panel letters, sentence case, definitions and caveats in the legend
rather than in the artwork. **Refill every number from
`figures/combined_figure_summary.txt`, never by reading the picture.**

## Read this before quoting anything

**Two panels changed letter.** The source projects still build their own two-panel figures
and their docs still say "Panel A" and "Panel B":

| Here | Source project | Called there |
|---|---|---|
| **A** | `../trends-figure` | Panel A — modality combinations by theme |
| **B** | `../trends-figure` | Panel B — theme volume over time |
| **C** | `../clinical-operations` | Panel A — cumulative authorizations |
| **D** | `../clinical-operations` | Panel B — authorization pathway |

**The source legends are not a safe starting point.**
`../clinical-operations/docs/figure-legend.md` is **stale against its own data** — it says
145 radiology and 9 pathology devices, a 16-fold gap, a 3/3/3 pathology split, and a
30 March 2026 snapshot. The current tables say **193 and 8**, a **24-fold** gap, a **2/3/3**
split, and a 27 March 2026 snapshot, and its two radiology categories have been renamed.
The numbers below are refilled from the current summary. That file needs the same
treatment on its own account; it is not this figure's to fix.

---

## For the manuscript (≈400 words)

**Figure [N]. Where AI in radiology and pathology is being published, and what has been
authorized for clinical use.**

**A,** Modality combinations used by **primary research** papers in each of four themes.
Rows are the fifteen data modalities, coloured by modality group; a filled dot marks a
modality present in a combination, and joined dots mark modalities used together. Bar
height is that combination's share of the theme's own papers; the hatched column holds all
remaining combinations, so the bars sum to the theme total and nothing is hidden.
Multimodal integration is defined by combination, so A draws only its papers carrying two
or more modalities: 2,727 of the theme's primary-research papers.
**B,** Papers per year in **all article types**, including reviews and perspectives, so the
panel measures attention rather than practice. Two plots with separate linear y axes: the
lower axis is about 27 times finer than the upper, and the dashed rule marks the lower
plot's full range. Foundation models, multimodal integration, and clinical applications are
each divided by clinical domain — radiology, pathology, or cross-specialty for papers using
both. Colour and marker denote domain; dash pattern denotes theme. Papers using no imaging
or report data carry no domain and appear on no divided line.
**C,** Cumulative FDA authorizations of cancer-directed AI on a logarithmic scale, by
device category. Radiology reaches 193 devices — 107 for detection and assessment and 86
for treatment planning — against eight in pathology: a 24-fold gap overall, and 13-fold
restricted to detection. Each series is drawn from the first year its count reaches one;
earlier years are zero and are drawn as no line rather than as a line along the axis floor,
which a logarithmic axis cannot represent. Pathology's eight devices are named
individually: two neural-network cervical cytology screeners authorized in 1995, then a
twenty-six-year gap before Paige Prostate in 2021.
**D,** Marketing pathway as a share of each field's own total. Of radiology's 193
authorizations, 185 (96%) were 510(k) clearances against an existing predicate;
pathology's eight divide 2/3/3 across 510(k), De Novo, and premarket approval. Radiology
iterates inside device categories that already exist; pathology has had to establish a new
one almost every time.

Papers were retrieved from PubMed on 1 September 2026 and labelled by matching a versioned
term dictionary against each title and abstract; of 44,625 records, 43,079 were retained
for B, of which 36,321 are primary research and form A. A modality is counted when the work
required it during training, and labelling is multi-label, so every count is an upper bound
on demonstrated use. Device counts are from the FDA Artificial Intelligence-Enabled Medical
Devices list through 27 March 2026, and include a device only where its authorized
indication names the cancer indication — they are a **floor**, not a census. Authorization
is permission to market, not evidence of deployment or of benefit. Shading marks 2026,
which is partial in both B and C.

**A, B, C, and D carry three different populations and no number from one may be quoted
against another:** A is primary research only, B is all article types, and C and D count
devices rather than papers.

---

## LaTeX float

`main.tex` has no `\graphicspath`, so `combined_figure.pdf` must be copied into
`CCR_reviews/` alongside the source. The figure is 14.6 × 10.0 in, so it wants a full page
in landscape; `\includegraphics[width=\textwidth]` on a portrait page will set the type
below legibility. AACR redraws from the sketch, so this is a proof concern rather than a
print one, but a referee reads the proof.

```latex
\begin{figure*}[p]
\centering
\includegraphics[width=\textwidth]{combined_figure.pdf}
\caption{Where AI in radiology and pathology is being published, and what has been
authorized for clinical use. \textbf{(A)} Modality combinations used by primary research
papers in each of four themes; bar height is that combination's share of the theme's own
papers and the hatched column holds all remaining combinations, so nothing is hidden.
\textbf{(B)} Papers per year in all article types, so the panel measures attention rather
than practice; two plots with separate linear y axes, the lower about 27 times finer.
Colour and marker denote clinical domain, dash pattern denotes theme. \textbf{(C)}
Cumulative FDA authorizations of cancer-directed AI, logarithmic scale: 193 radiology
devices against eight in pathology, a 24-fold gap. Each series is drawn from the first year
its count reaches one; earlier years are zero and are drawn as no line, which a logarithmic
axis cannot represent. \textbf{(D)} Marketing pathway as a share of each field's own total.
Panels A, B, and C--D carry three different populations---primary research, all article
types, and authorized devices---and no number from one may be quoted against another.
Counts include a device only where its authorized indication names cancer and are therefore
a floor; authorization is permission to market, not evidence of deployment or of benefit.
Data: PubMed, retrieved 1 September 2026; FDA Artificial Intelligence-Enabled Medical
Devices list, decisions through 27 March 2026~\cite{FDA2025AIDeviceList}.}
\label{fig:landscape}
\end{figure*}
```

---

## Caveats that must survive editing

Four sentences carry the two projects' honesty. The source legends' author notes mark the
first three as un-cuttable; the fourth exists only because the figures were merged.

1. **The two paper populations.** A is primary research, B is all article types. Their
   denominators differ and their counts are not comparable.
2. **Multi-label, upper bound.** A mark records what an abstract reports, so every count is
   an upper bound on demonstrated use.
3. **The device floor, and that authorization is not deployment.** Without the first the
   panel reads as a census; without the second it reads as evidence of clinical benefit,
   which is the opposite of the manuscript's argument.
4. **Three populations on one float.** Papers and devices now sit side by side under one
   figure number, which invites exactly the cross-quote the first caveat forbids.

If length forces cuts, take them from B's colour-and-marker sentence and from C's
"drawn from the first year" sentence — both are recoverable from the source projects'
`figure-description.md`. Cut none of the four above.

## Numbers this legend asserts, and where each comes from

Every row is in `figures/combined_figure_summary.txt`, which is the two projects' own
summary sheets concatenated — so each number still traces to the pipeline that computed it.

| Claim | Section of the summary |
|---|---|
| 2,727 multimodal primary-research papers; per-theme n | Trends, Panel A table |
| 43,079 retained, 36,321 primary research | Trends, corpus line, and the classification report |
| lower axis 27× finer than the upper | Trends, Panel B, `lower y scale` |
| 193 radiology, 8 pathology; 107 + 86 | Clinical operations, Panel A totals |
| 24-fold and 13-fold gaps | same, `gap` line (24.1× and 13.4×) |
| 185 of 193 are 510(k), 96% | same, Panel B (95.9%) |
| 2/3/3 pathology split | same, Panel B |
| two 1995 screeners, Paige Prostate 2021 | same, pathology device list |
| snapshot through 27 March 2026 | same, `snapshot through` |

## Cross-references

- One float, so one `\ref`. Both the Multimodal Integration section and the Current
  Clinical Operations section now point at the same figure and must name their panels:
  `(Figure~\ref{fig:landscape}A,B)` and `(Figure~\ref{fig:landscape}C,D)`.
- `main.tex:185` (AI in Pathology) states "only four image-based oncology pathology
  algorithms... against more than a thousand in radiology". That pairs an all-indications
  radiology number with an oncology-only pathology number and is stale against this
  snapshot. It needs reconciling with panel C. Carried over from the clinical-operations
  legend, still open.
