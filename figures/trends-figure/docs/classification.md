# Classification

How a parsed PubMed record becomes a row in `data/processed/paper_labels.csv`, and how to
change a term without breaking anything.

Two modules do the work. `src/trends/classify.py` matches the term dictionaries against
each record and assigns labels; `src/trends/aggregate.py` reduces those labels to the three
tables the figure is drawn from. Neither reaches the network, neither calls a model, and
neither uses a random number. The same records and the same dictionaries give the same
labels, always.

---

## The command

```bash
~/.venvs/ccr-trends/bin/python -m trends.classify \
    --records data/interim/<run>/records.parquet \
    --config-dir config \
    --output data/processed/
```

Options:

| Flag | Effect |
|---|---|
| `--report` | Print the diagnostic report as well as writing it. Without it the command prints the manifest's count block. |
| `--partial-year YYYY` | Override the year flagged partial. Default: the end of the date range in `config/corpus.yaml`. |
| `--no-date-window` | Keep records whose year falls outside `date_range` in `corpus.yaml`. Makes the corpus's first year biased; see the fourth filter below. |
| `--no-hits` | Skip `pattern_hits.csv`. It is the largest output — about 5 rows per record, roughly 50 MB on the full corpus — and skipping it costs the ability to check a label. |
| `--top-patterns N` | How many patterns the report lists. Default 25. |

Six files are written:

| File | What it is |
|---|---|
| `paper_labels.csv` | One row per analysed paper. Schema fixed by `docs/figure-spec.md`. |
| `combination_counts.csv` | Papers per theme and exact modality combination. Drives Panel A. |
| `theme_year_counts.csv` | Papers per theme, domain, and year. Drives Panel B. |
| `pattern_hits.csv` | Provenance: one row per record, category, and pattern that fired, plus one `role = "fallback"` row wherever `other` was assigned because nothing named matched. |
| `run_manifest.json` | Input file and digest, dictionary versions and digests, counts in and out, exclusions, output digests. |
| `classification_report.txt` | The human-readable diagnostic. |

The three figure tables carry a `#` provenance header naming the record file and the
dictionary versions and digests. `trends.plotting.io` reads them with `comment="#"`, so the
header travels with the data.

Throughput is about 330 records a second, so the full 44,617-record corpus takes a little
over two minutes.

---

## What the classifier does, in order

1. **Reads the record table** written by `trends.parse`. Parquet or CSV; parquet preferred.
2. **Drops records that may not enter the analysis corpus**, counting each reason:
   - `book_records` — `PubmedBookArticle` rows. Reference works, not primary literature.
     Per `docs/DECISIONS.md` the filter lives here, where it is visible and reversible,
     rather than at retrieval, where it would be hidden.
   - `missing_pmid` — a record that cannot be identified.
   - `missing_year` — a record with no publication year. `paper_labels.csv` types `year` as
     an integer and the figure is a time series, so a yearless record has nowhere to go.
     The count is reported rather than absorbed.
   - `outside_date_range` — a record whose parsed year falls outside `date_range` in
     `corpus.yaml`. PubMed filtered on publication date; our year rule dates a paper to its
     first appearance, and the two disagree for a paper posted online before the window and
     issued inside it. In the real corpus that is 84 records, 0.19%, reaching back to 2007.
     Keeping them would make the corpus's first year a biased partial year at the low end —
     the mirror of the partial final year, holding only those early-online papers that
     happened to be issued later. The window is read from the config, never hard-coded, and
     `--no-date-window` turns the filter off.
3. **Builds the text** each record is matched against: `title + " \n " + abstract`. Both
   dictionaries declare this separator. It matters, because several patterns are anchored
   with `^` and read the title and the abstract as one string.
4. **Matches both dictionaries.** A record carries a category when at least one `include`
   pattern hits and no `exclude` pattern hits. Exclusion removes that one label from that
   one record; it never removes the record from the corpus. Exclude patterns are evaluated
   only where an include has already fired, so the report's exclude counts read as "labels
   suppressed", not "text contains".
5. **Assigns `other`**, which is *additive*. A record carries it when an `other` include
   pattern matched, when it matched no named modality at all, or both, and it may sit
   alongside named modalities. This matters more than it sounds: while `other` fired only as
   a fallback, a paper using MRI and genomics read as "MRI alone", and the theme named for
   multimodality was drawn as overwhelmingly unimodal. The two routes mean different things
   — "uses a data type outside the named rows" against "we could not tell what this paper
   uses" — so they are recorded apart. A pattern assignment leaves ordinary `include` rows
   in `pattern_hits.csv`; a fallback assignment leaves one row with `role = "fallback"` and
   `pattern_id = "other:fallback"`. The report prints both counts.
6. **Derives `domain`** from the modality labels, by the rule in `docs/figure-spec.md`:
   `radiology` for MRI, CT, PET, ultrasound, mammography, radiography, or radiology report;
   `pathology` for H&E, IHC, spatial proteomics, spatial transcriptomics, or pathology
   report; `both` when each side has a member; `none` when neither side is present.
   **Genomics, clinical data, and `other` take no side.** They are data types, not
   specialties: a paper using MRI and genomics is `radiology`, not `both`. The three sets
   live in `classify.py` as `RADIOLOGY_MODALITIES`, `PATHOLOGY_MODALITIES`, and
   `NO_DOMAIN_MODALITIES`, and every modality must be in exactly one of them.

A record matching no theme keeps four zeroes and stays in the corpus. It is in the
denominator; it is simply in none of Panel A's four blocks.

---

## The matcher contract

Both dictionaries state this in their headers. It is repeated here because it is the part
most easily got wrong.

### `kind: phrase`

A literal. Word-bounded, case-insensitive by default, and tolerant of the amount of
whitespace between its words.

- `whole slide imaging` matches `whole  slide imaging` and `whole\nslide imaging`.
- It does **not** match `whole-slide imaging`. Whitespace is flexible; punctuation is not.
- It does **not** match its own plural. `digital twin` will not match `digital twins`.
  Write `(?i)\bdigital twins?\b` as a regex when the plural is wanted.
- A boundary is asserted only at an end that is itself a word character, so `510(k)` and
  `H&E` behave. `\b` alone would assert the wrong thing there.

### `kind: regex`

A Python regular expression, compiled exactly as written, and therefore **case-sensitive**.
Write `(?i)` at position 0 to opt into case-insensitivity; Python rejects a global inline
flag anywhere else in the pattern.

This is the whole reason bare acronyms are usable. `\bCT\b` matches `chest CT` and not
`qPCR Ct`; `\bPET\b` matches `PET/CT` and not `pet ownership`. Case-insensitive matching
would make both worthless. The measurements behind that claim are in
`docs/search-strategy.md`.

### `case_sensitive: true | false`

Optional, per pattern. The only extension the classifier makes to the schema in
`config/README.md`. Omit it and the per-kind default above applies.

- On a **phrase**, `case_sensitive: true` is the readable way to write an acronym:
  `pattern: "IHC"` matches `IHC` and not `ihc`, with no regex to get wrong.
- On a **regex**, `case_sensitive: false` adds `re.IGNORECASE` to a pattern written without
  `(?i)`.
- `case_sensitive: true` on a regex that already carries `(?i)` is a contradiction and is
  rejected at load.

Every shipped pattern in `config/themes.yaml` and `config/modalities.yaml` is currently
`kind: regex`, so the phrase path is exercised by the test fixtures rather than by the real
dictionaries.

### Conjunctive patterns

The schema ORs the entries of `include`. An AND is written as one regex of anchored
lookaheads:

```
(?i)^(?=[\s\S]*\bpathology reports?\b)(?=[\s\S]*(natural language processing|\bNLP\b))
```

`[\s\S]` rather than `.` because the text contains newlines, and `^` rather than
`\A` only for readability — the pattern is searched without `re.MULTILINE`, so `^` matches
at the start of the whole title-plus-abstract string and nowhere else. **These patterns
break if anyone changes the classifier to match the title and abstract separately.**

---

## What is checked at load

A malformed dictionary stops the run and lists every problem at once. The checks:

- `version` is a positive integer.
- Every category has a non-empty `label`.
- Every pattern has a non-empty `pattern` and a `kind` of `phrase` or `regex`.
- Every regex compiles.
- No unknown fields on a pattern.
- `case_sensitive`, if present, is a boolean and does not contradict an inline `(?i)`.
- The category keys are exactly the canonical keys of `docs/figure-spec.md` — a renamed
  category is an error, not a silently empty figure block.
- Every named category has at least one `include` pattern. A patternless category can never
  match, which is a mistake worth stopping for.
- `other` is the one category permitted to declare no `include` patterns, because the
  classifier assigns it as a fallback as well. It may also carry patterns, and does.
- Every modality is in exactly one of the three domain lists. A modality in none of them
  would take no side by accident rather than by decision, so its papers would read
  `domain = none` and fall off both of Panel B's clinical lines — a wrong figure rather
  than a crash, which is worse. `NO_DOMAIN_MODALITIES` is how a deliberate omission is
  told from an oversight; putting genomics in a domain list to quiet the check would make
  a genomics paper read as pathology.

## Adding a modality

The category keys are written down in four places, and they must agree. Change all four in
one go:

1. `config/modalities.yaml` — the patterns, and a `notes` entry saying why.
2. The key table in `docs/figure-spec.md`, and the `domain` derivation sentence above it.
3. `MODALITY_KEYS` in `src/trends/aggregate.py`, and exactly one of
   `RADIOLOGY_MODALITIES`, `PATHOLOGY_MODALITIES`, or `NO_DOMAIN_MODALITIES` in
   `src/trends/classify.py`.
4. `MODALITY_ORDER`, `MODALITY_LABELS`, and the matching domain set in
   `src/trends/plotting/style.py`.

Then add the category to `tests/fixtures/classify_modalities.yaml` and a record that carries
it to `tests/fixtures/classify_records.csv`.

Three guards make a half-finished change fail readably rather than as a wall of unrelated
errors elsewhere:

- `tests/test_classify.py::test_canonical_keys_agree_everywhere` compares the keys in
  `config/`, `trends.aggregate`, and `trends.plotting.style`, and names the odd one out.
- `test_the_fixture_dictionaries_cover_every_canonical_category` requires the fixture to
  declare every key **and** requires a fixture record to carry every named category, so a
  new modality cannot arrive as a row no test ever touches.
- `trends.classify.check_domain_coverage` refuses to classify when a named modality is in
  neither domain list, and names it.

What does **not** need editing: the aggregation. `trends.aggregate` reads its theme and
modality set from the `theme_` and `mod_` columns of the table in front of it, and the
classifier builds those columns from the dictionaries it loaded. The constants in
`aggregate.py` supply the figure's row order and are what the cross-check test compares;
they are not a list the reductions depend on.

---

## Changing a term

1. Edit `config/themes.yaml` or `config/modalities.yaml`. Add the reason to that category's
   `notes`, and the measurement to `docs/search-strategy.md`.
2. **Bump `version`** in the file you edited, and append the new version and its SHA-256 to
   `config/VERSIONS.json`. The manifest records the version and the hash, and that is how a
   figure is traced back to the terms that made it — a guarantee that breaks the moment a
   file changes without its version moving, because the manifest then names a version that
   no longer means what it meant. That happened three times on 2026-09-02/03, so it is now a
   test rather than a rule: `tests/test_classify.py::test_config_files_match_the_version_ledger`
   fails when a config's current hash is not the one its version froze at, and
   `test_the_version_ledger_never_reuses_a_version` fails when a version is re-pointed at
   different content. Never edit a hash already in the ledger; append a new entry. Versions
   the ledger does not carry are skipped, so a reconstructed history with gaps is fine.
3. Re-run the command above with `--report`.
4. Read the report before the figure. In order:
   - **Records per theme and per modality.** A count that moved a long way from the last
     run is the change you made, or one you did not intend.
   - **Most frequently firing patterns.** A pattern matching a large share of the corpus is
     either the theme's backbone or a runaway term. The report ranks by records matched, so
     a new term near the top deserves a look at `pattern_hits.csv`.
   - **Exclude patterns.** How many labels each one suppressed.
   - **Patterns that never fired.** Dead weight, a typo, or a term the corpus does not use.
5. Check a sample of labels in `pattern_hits.csv`. Every row names the record, the category,
   the pattern identifier (`ihc:include[1]`), the pattern text, how many times it matched,
   whether the category ended up assigned, and an excerpt of the first match. Filter to a
   pattern you distrust and read twenty excerpts; that is the whole method the dictionary's
   own precision figures came from.

Pattern identifiers are positional. Inserting a pattern in the middle of an `include` list
renumbers the ones after it, so identifiers are stable within a dictionary version and not
across versions. The manifest records the version, which is what makes an old report
readable.

---

## The two count tables

**`combination_counts.csv`.** Within a theme, a paper appears in exactly one row: the row
for its exact modality set. The counts therefore sum to the theme's paper count, and the
tests hold them to it. Sets are the modality keys sorted alphabetically and joined by `+`;
`other` alone is a legitimate set. Rows rank by paper count descending, ties breaking on
set size ascending and then on the set string, so the ranking is reproducible rather than
whatever order the grouping happened to produce.

**`theme_year_counts.csv`.** Every theme gets the whole domain breakdown — `all`,
`radiology`, `pathology`, `both`, `none` — and Panel B chooses which rows to draw. Emitting
all of it costs a few hundred rows and saves a schema change each time the author wants a
different split.

Two facts about those rows, and the legend must state the second:

- `radiology + pathology + both + none == all`, for every theme and every year. Each paper
  carries exactly one `domain` value, so the four rows partition the theme. A test asserts
  this identity.
- `radiology + pathology` alone does **not** sum to the theme. `radiology` means radiologic
  and *not* pathologic; a cross-specialty paper sits in `both`, and a paper whose only
  labels are genomics, clinical data, or `other` sits in `none`. The two single-specialty
  lines therefore under-count their theme.

The value stays `both` in the data even though the figure displays it as "cross-specialty",
so that this table and `paper_labels.csv` never disagree. The year axis is dense between the
first and last year in the corpus, so a year with no papers draws as a zero rather than a
gap. Exactly one year carries `partial_year = 1`: the retrieval year, taken from
`config/corpus.yaml`.

---

## Tests

```bash
~/.venvs/ccr-trends/bin/python -m pytest tests/test_classify.py tests/test_aggregate.py -q
```

They run against hand-written fixture dictionaries (`tests/fixtures/classify_*.yaml`) and a
hand-written record table (`tests/fixtures/classify_records.csv`), not against the real
corpus, so an edit to `config/*.yaml` cannot make a test pass or fail. One test loads the
real dictionaries, and only to prove they compile.

The fixtures prove the matcher's contract: word boundaries, whitespace tolerance, case
sensitivity, the acronym traps, exclusion, multi-label assignment, the `other` fallback, the
record filters, and the combination arithmetic. They prove nothing about whether the real
terms select the right literature. That is measured in `docs/search-strategy.md` and by the
validation sample described in `docs/DECISIONS.md`.
