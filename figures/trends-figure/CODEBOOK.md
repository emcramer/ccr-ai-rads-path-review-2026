# Codebook and data dictionary

Every file in this project, what it holds, and who or what writes it. If you add a file,
add a row. If a row here disagrees with the file, the file is right and the row is a bug.

Written 2026-09-01. Sections marked *pending* describe files the pipeline will create on
the first full run.

---

## 1. Reading order for a newcomer

1. `task-spec.md` — the assignment, in the author's words.
2. `docs/search-strategy.md` — how the paper pool was defined and what it misses.
3. `docs/classification.md` — how a paper acquires its theme and modality labels.
4. `docs/figure-spec.md` — what the figure shows and the schema of its inputs.
5. `docs/DECISIONS.md` — every judgment call, with its reason.

## 2. Configuration — `config/`

Code reads these. No search term is hard-coded anywhere else.

| File | Contents |
|---|---|
| `README.md` | The term-dictionary schema and the matching contract. |
| `corpus.yaml` | The PubMed query, the date range, retrieval settings, and the record counts measured at design time (`expected:`). |
| `themes.yaml` | Term dictionary for the four themes. |
| `modalities.yaml` | Term dictionary for the thirteen modalities. |

Every dictionary carries a `version`. Bump it when you change a pattern: run manifests
record the version, so an old report stays interpretable.

## 3. Source — `src/trends/`

| Module | Role |
|---|---|
| `config.py` | Loads and validates `corpus.yaml`. Reports every problem at once, not the first. |
| `pubmed.py` | E-utilities client: throttling, retries, date-sliced retrieval, raw capture, manifest. |
| `parse.py` | PubMed XML to one row per record. Holds the publication-year rule. |
| `fetch.py` | Command line for retrieval; logging setup. |
| `classify.py` | Compiles the term dictionaries, matches them against title and abstract, writes labels and provenance. |
| `aggregate.py` | Builds the three tables the figure reads. Owns the output schema. |
| `plot.py` | Command line for the figure. |
| `plotting/style.py` | Canonical keys, display labels, row order, colours, type sizes. |
| `plotting/io.py` | Reads and validates the three tables. Refuses to draw a malformed table. |
| `plotting/panel_a.py` | The per-theme UpSet blocks. |
| `plotting/panel_b.py` | The time series. |
| `plotting/synthetic.py` | Generates fake tables for layout testing. Never used for real output. |
| `validate.py` | Draws the stratified validation samples, scores rules against reference labels, and builds the author's audit sheet. Sampling is reproducible from its recorded seed. |

## 4. Data

### `data/raw/<retrieval-date>/` — append-only
PubMed's efetch responses exactly as returned, plus `manifest.json`: the query, the config
version and hash, the retrieval timestamp, E-utilities parameters, every date slice with
its count, per-file SHA-256, and expected against actual record counts. A later run writes
a new directory. Nothing here is ever edited or overwritten.

`smoke/` and `smoke-002/` hold throwaway-query test pulls, marked `"query_source":
"cli-override"` in their manifests. They are not the corpus.

### `data/interim/<run>/records.parquet` and `.csv`
One row per retrieved record.

| Column | Type | Meaning |
|---|---|---|
| `pmid` | string | PubMed identifier. Unique after deduplication. |
| `doi` | string | Digital object identifier, where present. |
| `title` | string | Article title. |
| `abstract` | string | Abstract. Structured abstracts keep their section labels; copyright notices are removed. |
| `journal` | string | Journal title. |
| `year` | integer | Publication year, by the rule in §6. |
| `year_source` | string | Which date field supplied the year. |
| `publication_types` | string | PubMed publication types, semicolon-separated. |
| `mesh_terms` | string | MeSH descriptors, semicolon-separated. Absent for records not yet indexed. |
| `language` | string | Article language. |
| `record_type` | string | `journal_article` or `book_article`. Book records are excluded at classification. |

### `data/processed/` — the figure's inputs
`paper_labels.csv`, `combination_counts.csv`, `theme_year_counts.csv`: schemas are defined
in `docs/figure-spec.md` and validated by `plotting/io.py`. Also written:

| File | Contents |
|---|---|
| `pattern_hits.csv` | One row per record, category, and pattern that fired: the pattern, its hit count, whether the label was assigned, and a short context excerpt. Large. This is the audit trail for any disputed label. |
| `run_manifest.json` | Input file, config versions and hashes, timestamp, records in and out, every exclusion with its count. |
| `classification_report.txt` | Human-readable summary: records per theme, per modality, per combination, records matching nothing, most frequently firing patterns. Read this before trusting a figure. |

### `data/processed/validation/`
One directory per validation round, plus the digital-twins screen.

| File | Contents |
|---|---|
| `round<N>/sample.csv` | The papers drawn, their stratum, and the seed that drew them. |
| `round<N>/labels_reference.csv` | Labels assigned by reading title and abstract, blind to the rule output. |
| `round<N>/agreement.csv` | Per-category precision, recall, F1, confusion counts, and Wilson intervals. |
| `round<N>/disagreements.csv` | Every disagreement, hand-coded with one cause. |
| `round<N>/audit_sheet.csv` | 50 rows for the author: 25 random and 25 disagreements, marked by `audit_stratum` so the two are never pooled, with blank `author_*` columns. |
| `digital_twins_screen.csv` | All 64 candidate papers with `verdict_strict` and `verdict_inclusive`, a reason for each, and the patterns that matched. |

A round measures one dictionary version. The version each round measured is recorded in
`docs/validation.md`; do not compare rates across rounds without it.

### `data/processed/synthetic/` — not real
Fake tables with a fixed seed, for layout testing. Every file says so. Never cite a number
from this directory.

## 5. Documentation — `docs/`

| File | Contents |
|---|---|
| `search-strategy.md` | The corpus query, the retrieval date, measured counts, precision spot-checks with sample sizes, and what the strategy knowingly misses. |
| `classification.md` | How matching works and how to change a term safely. |
| `figure-spec.md` | Panel layouts, the three input schemas, and the canonical theme and modality keys. |
| `figure-legend.md` | The legend as it will appear in the manuscript. |
| `DECISIONS.md` | Append-only log of every judgment call. |
| `validation.md` | Classifier accuracy: strata, seeds, per-category rates with Wilson intervals, the causes of each divergence, and the author's audit instructions. Three rounds, measuring dictionary versions 2, 3, and 4/5. |
| `digital_twins_screen.md` | The hand screen of all 64 candidate digital-twins papers, under both the strict and the inclusive standard, with the definition each was screened against. |
| `search-strategy.md` §8a | The mention-versus-use bias, stated as a property with a known direction rather than an apology. |

## 6. Rules a reader needs in order to interpret a number

- **Papers are multi-label.** One paper may carry several themes and several modalities. Theme counts do not sum to the corpus, and modality counts do not sum to the paper count.
- **Publication year** is the article (electronic) date when it precedes the journal issue date, otherwise the issue date. Each row records which field it used.
- **2026 is partial**, cut at the retrieval date. Never read a trend from it.
- **Excluded from analysis, each counted in the run manifest:** book records, records with no PMID, records with no parsable year.
- **Panel B's clinical lines are not additive.** A paper using both radiology and pathology data appears on both; a clinical paper with no named modality appears on neither.
- **Acronyms match case-sensitively.** `CT`, `PET`, `IHC`, `MRI`. This is deliberate and measured; see `docs/DECISIONS.md`.
- **Modality marks record what a title and abstract indicate, not what a paper demonstrably used.** Hand-coding of every validation disagreement found 43% of false positives were mentions rather than uses, with none in the opposite direction. Every modality count is an upper bound.
- **The four themes do not measure the same kind of thing.** Three count what a paper does; `digital_twins` counts engagement with an idea, including a paper that only names the concept as a future direction. Of its 56 papers, 18 build something meeting the manuscript's definition and 3 update as new measurements arrive.
- **`genomics` counts input data only.** A paper predicting a molecular label from an image is not counted as using genomic data. The rule catches the recognizable form of the problem, not all of it; the genomics-and-H&E cell is the least reliable in the figure.
- **`other` carries two meanings.** A pattern match means an unlisted data type was found; the fallback means no modality could be identified at all. They are recorded apart in `pattern_hits.csv` and scored apart in validation. Do not sum them.

## 7. Rebuilding everything from nothing

```bash
python3 -m venv ~/.venvs/ccr-trends
~/.venvs/ccr-trends/bin/pip install -r requirements.txt
~/.venvs/ccr-trends/bin/pip install -e .
cd "…/CCR/trends-figure"

~/.venvs/ccr-trends/bin/python -m trends.fetch --config config/corpus.yaml
~/.venvs/ccr-trends/bin/python -m trends.classify \
    --records data/interim/<run>/records.parquet --config-dir config \
    --output data/processed/ --report
~/.venvs/ccr-trends/bin/python -m trends.plot --input data/processed --output figures/
~/.venvs/ccr-trends/bin/python -m pytest tests/ -q
```

PubMed grows daily, so a later retrieval will not reproduce these counts exactly. That is
why `data/raw/` is kept: the figure is reproducible from the captured XML even when the
query is not reproducible from PubMed.
