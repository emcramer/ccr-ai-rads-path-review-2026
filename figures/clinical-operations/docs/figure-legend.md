# Figure legend

CCR house form: bold panel letters, sentence case, definitions and caveats in the legend
rather than in the artwork. Refill every number from
`figures/clinical_operations_summary.txt`, not by reading the picture.

Snapshot: FDA Artificial Intelligence-Enabled Medical Devices list, decisions through
30 March 2026.

---

## For the manuscript (≈210 words)

**Figure [N]. FDA authorization of cancer-directed AI, radiology against pathology,
1995–2026.**
**A,** Cumulative authorizations on a logarithmic scale, by device category. Radiology
reaches 145 devices — 66 for cancer detection and diagnosis and 79 for radiation therapy
planning — against nine in pathology, a 16-fold gap overall and 7-fold restricted to
detection and diagnosis. Each series is drawn from the first year its count reaches one;
earlier years are zero and are drawn as no line rather than as a line along the axis
floor, which a logarithmic axis cannot represent. Pathology's nine devices are named
individually: two neural-network cervical cytology screeners cleared in 1995, then a
twenty-six-year gap before Paige Prostate in 2021. Shading marks 2026, for which the
snapshot covers only the first quarter. **B,** Marketing pathway as a share of each
field's own total. Of radiology's 145 authorizations, 140 (97%) were 510(k) clearances
against an existing predicate; pathology's nine divide evenly across 510(k), De Novo, and
premarket approval. Radiology iterates inside device categories that already exist;
pathology has had to establish a new one almost every time.

Counts include a device only where FDA's regulation definition for its product code names
the cancer indication, so they are a floor: roughly 800 devices under generic codes are
excluded. Authorization is permission to market, not evidence of deployment or benefit.

---

## LaTeX float

`main.tex` has no `\graphicspath`, so `clinical_operations.pdf` must be copied into
`CCR_reviews/` alongside the source.

```latex
\begin{figure}[htbp]
\centering
\includegraphics[width=\linewidth]{clinical_operations.pdf}
\caption{FDA authorization of cancer-directed AI, radiology against pathology, 1995--2026.
\textbf{(A)} Cumulative authorizations on a logarithmic scale, by device category.
Radiology reaches 145 devices---66 for cancer detection and diagnosis and 79 for radiation
therapy planning---against nine in pathology, a 16-fold gap overall and 7-fold restricted
to detection and diagnosis. Each series is drawn from the first year its count reaches
one; earlier years are zero and are drawn as no line rather than as a line along the axis
floor, which a logarithmic axis cannot represent. Pathology's nine devices are named
individually: two neural-network cervical cytology screeners cleared in 1995, then a
twenty-six-year gap before Paige Prostate in 2021. Shading marks 2026, for which the
snapshot covers only the first quarter. \textbf{(B)} Marketing pathway as a share of each
field's own total. Of radiology's 145 authorizations, 140 (97\%) were 510(k) clearances
against an existing predicate; pathology's nine divide evenly across 510(k), De Novo, and
premarket approval. Radiology iterates inside device categories that already exist;
pathology has had to establish a new one almost every time. Counts include a device only
where FDA's regulation definition for its product code names the cancer indication, and
are therefore a floor: roughly 800 devices under generic codes are excluded. Authorization
is permission to market, not evidence of deployment or of benefit. Data: FDA Artificial
Intelligence-Enabled Medical Devices list, decisions through 30 March
2026~\cite{FDA2025AIDeviceList}.}
\label{fig:clinops}
\end{figure}
```

---

## Numbers this legend asserts, and where each comes from

| Claim | Source |
|---|---|
| 145 radiology, 9 pathology | `clinical_operations_summary.txt`, Panel A totals |
| 66 detection, 79 radiation therapy | same, category totals |
| 16-fold and 7-fold gaps | same, "gap" line (16.1× and 7.3×, rounded down) |
| 140 of 145 are 510(k), 97% | same, Panel B, 96.6% rounded |
| 3/3/3 pathology split | same, Panel B |
| Two 1995 screeners, Paige Prostate 2021 | same, pathology device list |
| ~800 devices under generic codes | `data/processed/classification_report.txt`, `code_indeterminate` = 955 across all panels; 800 is the in-scope radiology and pathology share. **Verify before submission** |
| Snapshot through 30 March 2026 | `data/raw/2026-03-30/manifest.json` |

## Caveats that must survive editing

Two sentences carry the project's honesty and should not be cut for length:

1. **The floor.** "Counts include a device only where FDA's regulation definition names
   the cancer indication, and are therefore a floor." Without it the figure reads as a
   census, and about 800 excluded devices make that wrong.
2. **Authorization is not deployment.** The manuscript's own argument is that regulatory
   clearance does not demonstrate local clinical utility. A figure of authorizations
   placed inside that argument must say which it is showing.

## Cross-references

- Referenced in text as `(Figure~\ref{fig:clinops})` in Current Clinical Operations.
- `main.tex:185` (AI in Pathology) currently states "only four image-based oncology
  pathology algorithms... against more than a thousand in radiology". That pairs an
  all-indications radiology number with an oncology-only pathology number and is stale
  against this snapshot. It needs reconciling with this figure.
