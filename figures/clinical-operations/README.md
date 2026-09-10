# Clinical operations figure

Trends in FDA authorization of cancer-directed AI devices, radiology against pathology, for the
CCR review manuscript's Current Clinical Operations section.

Built by the same procedure as `../trends-figure`: versioned YAML configuration that the code
reads and nobody hard-codes around, append-only raw snapshots, per-stage manifests recording
input and output hashes, a decision log, and a committed build script so the next revision is
re-renderable.

## The short version

FDA's AI-enabled device list has no indication-for-use field, so "applied to cancer" has to be
derived. Each in-scope device is judged **individually** against its authorized indication and
recorded with written evidence in `config/adjudication/`. Product codes are a prior, not the
rule: they do not separate cancer reliably in either direction, because the cancer-specific
codes were created only around 2018-2020 and earlier computer-aided detection sits under generic
ones. Devices that cannot be resolved from the published fields are excluded rather than
guessed, which makes the published counts **a floor rather than an estimate**.

On the snapshot through 2026-03-30: **193 radiology** against **8 pathology** cancer-directed
authorizations — 107 for cancer detection and assessment and 86 for radiation therapy planning,
a 24-fold gap overall and 13-fold restricted to detection. Of 1,524 devices read, 886 were
judged not cancer-directed, 86 could not be resolved, and 351 sit under codes outside the two
panels.

Numbers here are refilled from `figures/clinical_operations_summary.txt`. If they disagree with
it, it is right and this file is stale.

## Setup

The virtual environment lives **outside** this directory. The project is OneDrive-synced and a
venv inside it would push tens of thousands of files into cloud sync. Reproducibility rests on
the pinned `requirements.txt`, not on an environment directory.

```bash
python3 -m venv ~/.venvs/ccr-clinops
~/.venvs/ccr-clinops/bin/pip install -r requirements.txt -e . -e ../trends-figure
~/.venvs/ccr-clinops/bin/python -m pytest tests/ -q
```

`-e ../trends-figure` is required: the plotting layer imports the project's shared style tokens
from `trends.plotting.style` rather than re-declaring them. See `../AGENTS.md`.

## Rebuild

```bash
~/.venvs/ccr-clinops/bin/python -m clinops.fetch    --config config/source.yaml
~/.venvs/ccr-clinops/bin/python -m clinops.classify --config-dir config --report
~/.venvs/ccr-clinops/bin/python -m clinops.aggregate
~/.venvs/ccr-clinops/bin/python -m clinops.plot     --input data/processed --output figures/ --layout both
```

`fetch` downloads the live FDA list, so a run made later will produce a larger snapshot than the
one committed here. To reproduce the published figure exactly, skip `fetch` and run from the
committed snapshot in `data/raw/`.

## Layout

| Path | What it holds |
|---|---|
| `task-spec.md` | The assignment, in the author's terms |
| `config/` | `source.yaml`, `oncology_codes.yaml` (a prior, not the rule), `adjudication/*.yaml` (**the authoritative per-device rule**), and the `VERSIONS.json` hash ledger |
| `src/clinops/` | One CLI per stage: fetch, enrich, classify, aggregate, plot |
| `data/raw/<date>/` | Append-only snapshots. **Tracked in git** — small enough, and FDA republishes in place |
| `data/processed/` | The tables the figure is drawn from, plus the run manifest |
| `docs/` | Source strategy, classification rules, figure spec, decision log, legend |
| `figures/` | `clinical_operations{,_landscape}.{pdf,png,svg}` and a summary number sheet per layout. The manuscript uses the landscape variant |
| `tests/` | pytest; includes the config ledger guard and an offline-only fixture |

`CODEBOOK.md` describes every file individually. If a row there disagrees with the file, the
file is right and the row is a bug.

## Reading order

`task-spec.md` → `docs/source-strategy.md` → `docs/classification.md` → `docs/figure-spec.md`
→ `docs/DECISIONS.md`.

## Before you quote a number from this project

Read `docs/source-strategy.md` §4, "What this project can and cannot claim". In particular: an
authorization is permission to market, not evidence of deployment or of benefit; the radiology
counts are a floor; and the most recent months are under-reported by construction because FDA
adds authorizations whose decision summaries were not published within a collection period in a
later update.
