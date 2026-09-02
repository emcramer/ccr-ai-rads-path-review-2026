# Trends figure — AI in pathology and radiology

Builds the two-panel trends figure for the CCR review manuscript: which data modalities
each research theme uses (Panel A), and how theme volume moves over time (Panel B).

Status: **in construction.** See `docs/DECISIONS.md` for what has been settled and
`CODEBOOK.md` for what every file holds.

## Layout

```
trends-figure/
├── config/          search strategy and term dictionaries (YAML; code reads these)
├── src/trends/      the pipeline package
├── data/raw/        PubMed responses exactly as returned, plus a retrieval manifest
├── data/interim/    parsed records
├── data/processed/  the tables the figure is drawn from
├── figures/         figure output (PDF and PNG)
├── docs/            search strategy, decision log, validation report
├── tests/           unit tests
└── logs/            run logs
```

`data/raw/` is never edited by hand and never overwritten by a later run.

## Setup

```bash
python3 -m venv ~/.venvs/ccr-trends
~/.venvs/ccr-trends/bin/pip install -r requirements.txt
```
