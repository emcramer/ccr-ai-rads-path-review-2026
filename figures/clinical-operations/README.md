# Clinical operations figure

Trends in FDA authorization of cancer-directed AI devices, radiology against pathology, for the
CCR review manuscript's Current Clinical Operations section.

Built by the same procedure as `../trends-figure`: versioned YAML configuration that the code
reads and nobody hard-codes around, append-only raw snapshots, per-stage manifests recording
input and output hashes, a decision log, and a committed build script so the next revision is
re-renderable.

## The short version

FDA's AI-enabled device list has no indication-for-use field, so "applied to cancer" is derived
from each device's FDA product code via the openFDA classification database. A code counts when
its FDA regulation definition names cancer, tumors, or radiation therapy. Codes with generic
definitions are excluded, which makes the published counts **a floor rather than an estimate**.

On the snapshot through 2026-03-30: **145 radiology** against **9 pathology** cancer-directed
authorizations; 66 against 9 restricting to detection and diagnosis alone.

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
~/.venvs/ccr-clinops/bin/python -m clinops.plot     --input data/processed --output figures/
```

`fetch` downloads the live FDA list, so a run made later will produce a larger snapshot than the
one committed here. To reproduce the published figure exactly, skip `fetch` and run from the
committed snapshot in `data/raw/`.

## Layout

| Path | What it holds |
|---|---|
| `task-spec.md` | The assignment, in the author's terms |
| `config/` | `source.yaml`, `oncology_codes.yaml`, and the `VERSIONS.json` hash ledger |
| `src/clinops/` | One CLI per stage: fetch, enrich, classify, aggregate, plot |
| `data/raw/<date>/` | Append-only snapshots. **Tracked in git** — small enough, and FDA republishes in place |
| `data/processed/` | The tables the figure is drawn from, plus the run manifest |
| `docs/` | Source strategy, classification rules, figure spec, decision log, legend |
| `figures/` | `clinical_operations.{pdf,png,svg}` and the summary number sheet |
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
