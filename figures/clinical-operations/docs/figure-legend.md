# Figure legend

CCR house form: bold panel letters, sentence case, definitions and caveats in the legend
rather than in the artwork. Refill every number from
`figures/clinical_operations_summary.txt`, not by reading the picture.

Snapshot: FDA Artificial Intelligence-Enabled Medical Devices list, decisions through
30 March 2026. The latest *cancer-directed* authorization in it is 27 March 2026, which is
the date the summary sheet reports as "snapshot through"; both are correct and they count
different populations.

---

## For the manuscript (≈205 words)

**Figure [N]. FDA authorization of cancer-directed AI, radiology against pathology,
1995–2026.**
**A,** Cumulative authorizations on a logarithmic scale, by device category. Radiology
reaches 193 devices — 107 for cancer detection and assessment and 86 for radiation therapy
planning — against eight in pathology, a 24-fold gap overall and 13-fold restricted to
detection. Each series is drawn from the first year its count reaches one; earlier years
are zero and are drawn as no line rather than as a line along the axis floor, which a
logarithmic axis cannot represent. Pathology's eight devices are named individually: two
neural-network cervical cytology screeners cleared in 1995, then a twenty-six-year gap
before Paige Prostate in 2021. Shading marks 2026, for which the snapshot covers only the
first quarter. **B,** Marketing pathway as a share of each field's own total. Of
radiology's 193 authorizations, 185 (96%) were 510(k) clearances against an existing
predicate; pathology's eight divide across two 510(k) clearances, three De Novo
authorizations, and three premarket approvals. Radiology iterates inside device categories
that already exist; pathology has had to establish a new one almost every time.

Each counted device is judged individually against its authorized indication, so the counts
are a floor: of 1,524 devices, 886 were judged not cancer-directed and 86 could not be
resolved from published fields. One row is one authorization, not one cancer-directed
capability. Authorization is permission to market, not evidence of deployment or benefit.

---

## LaTeX float

`main.tex` has no `\graphicspath`, so the PDF must be copied into `CCR_reviews/` alongside
the source. The manuscript uses the **landscape** variant.

```latex
\begin{figure}[htbp]
\centering
\includegraphics[width=\linewidth]{clinical_operations_landscape.pdf}
\caption{FDA authorization of cancer-directed AI, radiology against pathology, 1995--2026.
\textbf{(A)} Cumulative authorizations on a logarithmic scale, by device category.
Radiology reaches 193 devices---107 for cancer detection and assessment and 86 for
radiation therapy planning---against eight in pathology, a 24-fold gap overall and 13-fold
restricted to detection. Each series is drawn from the first year its count reaches one;
earlier years are zero and are drawn as no line rather than as a line along the axis floor,
which a logarithmic axis cannot represent. Pathology's eight devices are named
individually: two neural-network cervical cytology screeners cleared in 1995, then a
twenty-six-year gap before Paige Prostate in 2021. Shading marks 2026, for which the
snapshot covers only the first quarter. \textbf{(B)} Marketing pathway as a share of each
field's own total. Of radiology's 193 authorizations, 185 (96\%) were 510(k) clearances
against an existing predicate; pathology's eight divide across two 510(k) clearances, three
De Novo authorizations, and three premarket approvals. Radiology iterates inside device
categories that already exist; pathology has had to establish a new one almost every time.
Each counted device is judged individually against its authorized indication, so the counts
are a floor: of 1,524 devices, 886 were judged not cancer-directed and 86 could not be
resolved from published fields. Authorization is permission to market, not evidence of
deployment or of benefit. Data: FDA Artificial Intelligence-Enabled Medical Devices list,
decisions through 30 March 2026~\cite{FDA2025AIDeviceList}.}
\label{fig:clinops}
\end{figure}
```

---

## Numbers this legend asserts, and where each comes from

| Claim | Source |
|---|---|
| 193 radiology, 8 pathology | `clinical_operations_summary.txt`, Panel A totals |
| 107 detection and assessment, 86 radiation therapy | same, category totals |
| 24-fold and 13-fold gaps | same, "gap" line (24.1× and 13.4×, rounded down) |
| 185 of 193 are 510(k), 96% | same, Panel B (95.9% rounded) |
| Pathology 2 / 3 / 3 across 510(k), De Novo, PMA | same, Panel B |
| Two 1995 screeners, Paige Prostate 2021 | same, pathology device list (1995-09-29, 1995-11-08, 2021-09-21) |
| 1,524 devices read; 886 not cancer-directed; 86 unresolved | `data/processed/classification_report.txt`, COUNTS block |
| Snapshot through 30 March 2026 | `data/raw/2026-03-30/manifest.json` |

The report also excludes 351 devices under product codes outside the radiology and
pathology panels. They are omitted from the legend because they were never candidates,
not because they were judged.

## Caveats that must survive editing

Two sentences carry the project's honesty and should not be cut for length:

1. **The floor.** "Each counted device is judged individually against its authorized
   indication, so the counts are a floor." Without it the figure reads as a census, and 86
   unresolved devices plus a deliberately strict rule make that wrong.
2. **Authorization is not deployment.** The manuscript's own argument is that regulatory
   clearance does not demonstrate local clinical utility. A figure of authorizations
   placed inside that argument must say which it is showing.

## Cross-references

- Referenced in text as `(Figure~\ref{fig:clinops})` in Current Clinical Operations.
- **`main.tex`'s own caption is stale**: it still says "Pathology's nine devices are named
  individually". The figure draws eight. Replace the caption with the float above.
- `main.tex:211` (AI in Pathology) states "only four image-based oncology pathology
  algorithms... against more than a thousand in radiology". That pairs an all-indications
  radiology number with an oncology-only pathology number and disagrees with this figure's
  193 against 8. It still needs reconciling.
- `main.tex:302` says the FDA has authorized 1,524 devices "of which 1,164 are designated
  for radiology and nine for pathology". Those are FDA *panel* designations across all
  indications and are correct as written — do not "fix" the nine to eight. The eight is the
  cancer-directed subset this figure draws.
