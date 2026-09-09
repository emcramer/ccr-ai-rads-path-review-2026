# Codebook and data dictionary

Every file in this project, what it holds, and who or what writes it. If you add a file, add a
row. **If a row here disagrees with the file, the file is right and the row is a bug.**

Sizes and counts are from the snapshot of 2026-03-30.

---

## 1. Root

| File | Written by | What it holds |
|---|---|---|
| `README.md` | hand | Orientation, setup, rebuild commands, layout table |
| `CODEBOOK.md` | hand | This file |
| `task-spec.md` | hand | The assignment in the author's terms, the five project rules, reading order |
| `pyproject.toml` | hand | Package `ccr-clinops`, module `clinops`, Python ≥3.12, pytest config |
| `requirements.txt` | hand | Fully pinned dependencies, matching `../trends-figure` version for version |

## 2. `config/` — the rules, versioned

Nothing in `src/` hard-codes a product code or a URL. Everything comes from here.

| File | Written by | What it holds |
|---|---|---|
| `source.yaml` | hand | **v2.** FDA and openFDA URLs, required column contract, pathway prefixes, and an `expected:` block recording the last measurement. Non-normative: nothing asserts it |
| `oncology_codes.yaml` | hand | **v3.** No longer the rule — a *prior*. Category definitions, FDA regulation text per code, and the recorded exclusions. Its header carries a retraction: v1 claimed every code had been checked against its devices, and that was false. Superseded for decisions by `adjudication/` |
| `adjudication/*.yaml` | hand | **The authoritative rule.** One entry per in-scope device: `oncology`, `not_oncology`, or `unresolved`, each with written evidence. Split by product-code group so fragments cannot overlap |
| `VERSIONS.json` | hand | Append-only ledger: config file → version → SHA-256. Never edit an existing entry |
| `README.md` | hand | The schema both configs follow, and the matching contract |

**Version rule.** Bump `version` on *any* content change, including a corrected number inside a
comment. A run manifest records the version and the hash; content moving under a fixed version
makes that manifest wrong. Two tests enforce it in both directions — content may not move
without the version moving, and the version may not move without the ledger recording it.

## 3. `src/clinops/` — one CLI per stage

| Module | Lines | CLI | What it does |
|---|---|---|---|
| `__init__.py` | 21 | — | Package version |
| `config.py` | 914 | — | Loads and validates both configs into frozen dataclasses. Collects every problem and raises one error listing all of them. Computes each file's SHA-256 for the manifest |
| `fetch.py` | 608 | `python -m clinops.fetch` | Downloads the FDA CSV and the openFDA classification records; writes a dated, append-only snapshot plus `manifest.json` |
| `enrich.py` | 386 | `python -m clinops.enrich` | Joins each device row to its product code's classification record; derives decision date, year, and marketing pathway. Makes no oncology judgment |
| `classify.py` | 800 | `python -m clinops.classify --report` | Applies the rule; writes the labelled table and the report. **A device decision outranks its product code, always** — the code is wrong in both directions |
| `adjudication.py` | 300 | — | Loads and merges the per-device decisions in `config/adjudication/`. Validates every entry; a submission number claimed by two fragments is an error |
| `aggregate.py` | 458 | `python -m clinops.aggregate` | Builds the three processed tables and the run manifest |
| `plot.py` | 560 | `python -m clinops.plot [--layout portrait\|landscape\|both]` | Draws the figure in each layout; writes PDF, PNG, SVG and a summary sheet per layout |
| `plotting/io.py` | 385 | — | Loads and schema-validates the three input tables, naming file, column, and problem on failure |
| `plotting/panel_a.py` | 645 | — | Cumulative log-scale panel, including the pathology device annotations |
| `plotting/panel_b.py` | 430 | — | Marketing-pathway composition bars, rows or columns. One code path draws both: the stacked direction is *along*, the categorical one *across*, and only their mapping onto x and y changes |
| `plotting/__init__.py` | 301 | — | Canonical vocabulary, series appearance, and the label-measurement helpers |

**Style tokens are not defined here.** `plotting/` imports them from
`trends.plotting.style` in the sibling project, which is why `pip install -e ../trends-figure`
is required. Radiology is `#0072B2`, pathology is `#CC79A7`, fixed project-wide. See
`../AGENTS.md`.

## 4. `data/raw/<snapshot-date>/` — append-only, tracked in git

The directory is named for the **maximum decision date in the file**, not the day it was
fetched: that is what identifies the content. FDA republishes its list in place at a fixed URL
and does not version it, so the URL is not a version and this snapshot is the only durable
record of what the figure was built from. **Nothing here is ever edited or overwritten.** A
later run writes a new directory.

| File | Bytes | What it holds |
|---|---|---|
| `devices.csv` | 132,922 | The FDA AI-enabled device list, verbatim. 1,524 rows, 6 columns |
| `classification_001..004.json` | 985,153 | openFDA classification responses, verbatim, one per batch |
| `manifest.json` | 5,019 | Retrieval timestamp, source URLs, per-file SHA-256, row counts, openFDA's `last_updated` |

openFDA responses are stored whole rather than field-projected. Most of the bulk is
`k_number` / `registration_number` / `fei_number` arrays that `enrich.py` discards; keeping only
the used fields would cut this to about 270 KB. The raw capture is the evidence, and which
fields the pipeline reads is a downstream choice that may change.

## 5. `data/interim/`

| File | Written by | What it holds |
|---|---|---|
| `labeled_devices.csv` | `classify.py` | **All 1,524 devices**, counted or not, each with its label or its one exclusion reason. Tracked: it is the complete audit trail for the rule, and it is what lets a reader check why any given device was left out |
| `classification_run.json` | `classify.py` | Config versions and hashes, input digest, and every count the report prints |

Excluded devices stay in this table. Dropping them would shrink the denominator every count is
reported against.

## 6. `data/processed/` — what the figure reads

| File | Written by | Rows | Schema |
|---|---|---|---|
| `authorizations.csv` | `aggregate.py` | 201 | `submission_number, decision_date, year, device, company, panel_lead, product_code, domain, category, category_label, pathway, regulation_number` |
| `cumulative_by_year.csv` | `aggregate.py` | 96 | `year, category, domain, annual_count, cumulative_count` |
| `pathway_by_domain.csv` | `aggregate.py` | 9 | `domain, category, pathway, count` |
| `run_manifest.json` | `aggregate.py` | — | Generation time, tool and library versions, input path + SHA-256 + count, config versions and hashes, every exclusion and its count, per-category and per-domain counts, and the SHA-256 of each output |
| `classification_report.txt` | `classify.py --report` | — | The human-readable run report. **Read this before the figure** |

Every CSV carries a leading `#` provenance header naming the snapshot, the config versions, and
the generation time. Readers use `comment="#"`.

Both tables are **dense**: `cumulative_by_year.csv` carries every (year, category) pair from
1995 to 2026 with explicit zeros, and `pathway_by_domain.csv` carries every (category, pathway)
pair. A sparse table would make a 26-year gap look like missing data rather than like zeros,
and would let a stacked bar's segments change order between runs.

### Field values

| Field | Values |
|---|---|
| `domain` | `radiology`, `pathology` |
| `category` | `radiology_cancer_detection`, `radiology_radiation_therapy`, `pathology` |
| `pathway` | `510(k)`, `De Novo`, `PMA` — derived from the submission-number prefix `K`, `DEN`, `P` |
| `basis` | `device` where a recorded per-device decision counted it, `code` where the product-code rule did. Currently `device` for all 201 |
| `regulation_number` | The **config's** value, never openFDA's. For an overridden code the lookup describes a different device, so its regulation number would be wrong. Empty where the config records none |
| `exclusion_reason` | `device_not_oncology`, `device_unresolved`, `code_not_oncology`, `code_indeterminate`, `code_unlisted_in_panel`, `code_unlisted_off_panel`, `pathway_unknown`, `no_decision_date` — exactly one per excluded device. `code_indeterminate` now means *unadjudicated*, which is a hole in the dictionary and must read zero before publishing |

## 7. `figures/`

Two layouts are built on every run from one set of tables, so they cannot drift apart.
**Portrait** is the published arrangement, panels stacked, 7.0 x 8.0 in; it keeps the
unsuffixed filenames, which is what `CCR_reviews/main.tex` includes. **Landscape** puts the
panels side by side at 12.0 x 5.5 in, for a spread or a slide.

| File | Written by | What it holds |
|---|---|---|
| `clinical_operations.pdf` | `plot.py` | The deliverable. Fonts referenced, not outlined (fonttype 42) |
| `clinical_operations.png` | `plot.py` | 300 dpi raster, for visual inspection |
| `clinical_operations.svg` | `plot.py` | Editable vector, `svg.fonttype="none"` |
| `clinical_operations_summary.txt` | `plot.py` | **The number sheet the legend is refilled from.** Refill from this file rather than reading the picture |
| `clinical_operations_landscape.{pdf,png,svg}` | `plot.py` | The same figure, panels side by side |
| `clinical_operations_landscape_summary.txt` | `plot.py` | Its number sheet. The counts match the portrait sheet by construction; only the layout line and the measured margin differ |

Build one layout with `--layout portrait` or `--layout landscape`; the default is `both`.

In landscape, **Panel B is drawn as columns rather than rows**, because the space beside Panel A
is narrow and tall. Rows there would leave most of the height empty while squeezing radiology's
two thin segments into the width that remains: at 3.30 in wide, its 1.0 % De Novo segment is
0.03 in across. Upright in a 3.55 in column it is 0.13 in tall. The bars stay 100 %-normalized,
so nothing about the comparison changes; in that orientation each field's total moves from
beside the bar to under its name, because above the column it lands on the panel title.

**The landscape canvas is 12.0 in wide for a reason that is not obvious.** Panel A's gutter
labels are placed in *data* coordinates a fixed number of years past the last point, but their
text has a fixed *physical* width. The gutter is only 1.53 in wide while Panel A's axes are
4.85 in wide over the same thirty-two years. Narrowing Panel A to save canvas would not shrink
the labels -- it would push them into Panel B, and `measure_margin` would not catch it because
they would still be on the paper. `tests/test_plot.py` asserts the width is preserved.

## 8. `docs/`

| File | Written by | What it holds |
|---|---|---|
| `source-strategy.md` | hand | What the sources are, what they can and cannot support. **Read §4 before quoting any number in the manuscript** |
| `classification.md` | hand | How the rule works, and the procedure for changing a classification safely |
| `figure-spec.md` | hand | Panel content, canonical vocabulary, input schemas, panel rects. Written before the drawing code |
| `figure-legend.md` | hand | The CCR-form legend, the LaTeX float, and a table tracing every asserted number to its source |
| `DECISIONS.md` | hand | Append-only. One entry per judgment call a reader could question |
| `section-draft.md` | hand | The rewritten Current Clinical Operations section, not yet applied to `main.tex` |

## 9. `tests/`

Run from the project root: `~/.venvs/ccr-clinops/bin/python -m pytest tests/ -q`. **78 tests.**

| File | Tests | What it covers |
|---|---|---|
| `conftest.py` | — | Puts `src` on the path; an autouse fixture that fails any test touching the network |
| `test_config.py` | 15 | The version ledger in both directions, plus its own guard tests; the oncology rule's internal integrity |
| `test_classify.py` | 17 | The rule applied: counting, every exclusion reason, the NMN override, panel agreement measured rather than asserted |
| `test_aggregate.py` | 10 | Table invariants: dense axes, monotone cumulative counts, totals that reconcile, stable ordering |
| `test_adjudication.py` | 17 | Device-level decisions: merging, every validation check, the 1998 ImageChecker tripwire |
| `test_plot.py` | 16 | Layout geometry: panels on-canvas and non-overlapping, Panel A's gutter width preserved across layouts, Panel B's orientation matching its rect's shape, both layouts drawing identical segments |
| `fixtures/*.csv` | — | Small stand-in tables for the plotting layer |

**No test touches the network.** Every test builds its own small snapshot rather than reading
the committed one, so a later FDA snapshot cannot turn them red for reasons unrelated to the
code. The two exceptions are marked: they read the committed processed tables as a regression
on the published numbers, and they skip when those tables are absent.

## 10. `logs/`

`fetch_<UTC-timestamp>.log`, one per retrieval. Gitignored.

---

## Rebuilding from nothing

```bash
python3 -m venv ~/.venvs/ccr-clinops
~/.venvs/ccr-clinops/bin/pip install -r requirements.txt -e . -e ../trends-figure
~/.venvs/ccr-clinops/bin/python -m clinops.fetch    --config config/source.yaml
~/.venvs/ccr-clinops/bin/python -m clinops.classify --config-dir config --report
~/.venvs/ccr-clinops/bin/python -m clinops.aggregate
~/.venvs/ccr-clinops/bin/python -m clinops.plot     --input data/processed --output figures/
~/.venvs/ccr-clinops/bin/python -m pytest tests/ -q
```

The venv lives outside this directory on purpose: the project is OneDrive-synced and a venv
inside it would push tens of thousands of files into cloud sync.

`fetch` downloads the live list, which grows. To reproduce the published figure exactly, skip
`fetch` and run from the committed snapshot.

## What a later snapshot will change

The FDA list grows, so a rerun will produce larger counts. That is expected and is not a bug.
What must happen alongside it:

1. `config/source.yaml`'s `expected:` block gets the new measurement and a new `measured_on` —
   which is a content change, so bump to v3 and append to the ledger.
2. The two regression tests naming published counts get updated, **together with every sentence
   in the manuscript that quotes a number**. That coupling is deliberate.
3. `figures/clinical_operations_summary.txt` is regenerated, and the legend is refilled from it.
4. `classify.py --report` is read before the figure, especially the panel-agreement, specialty
   disagreement, and excluded-code-drift sections.
