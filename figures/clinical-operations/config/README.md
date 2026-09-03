# Configuration schema

Two files drive the pipeline. Code reads them; no URL, no product code, and no category
name is hard-coded anywhere else. Both are loaded and checked by `clinops.config`, which
reports every problem in a file at once rather than the first one it hits.

- `source.yaml`         — where the device records come from and what a run may assume
                          about their shape.
- `oncology_codes.yaml` — which FDA product codes count as cancer-directed, with FDA's own
                          words recorded next to each decision.
- `VERSIONS.json`       — append-only `version -> SHA-256` ledger for both files.

## The version rule

Every config carries a `version`. **Bump it on any content change, including prose in a
comment or a corrected number.** A run manifest records the version *and* the SHA-256; if
content moves under a fixed version, that manifest is a lie. `VERSIONS.json` is the ledger
that catches it: append the new version and hash in the same commit, and never edit or
delete an existing entry.

## `source.yaml`

```yaml
version: 1                          # bump on any edit; recorded in every manifest

device_list:
  name: "…"                         # source name, for the manifest and the citation
  landing_page: "https://…"         # the page the file is published from; recorded, not fetched
  csv_url: "https://…"              # what the pipeline downloads
  alternate_urls:                   # other serialisations of the same list; recorded only
    xlsx: "https://…"
    xml:  "https://…"
  scope_note: >-                    # FDA's own statement of what the list is. It bounds
    …                               # every claim the figure can make.
  required_columns:                 # asserted exactly, after tolerated ones are dropped
    - "Date of Final Decision"
    - "Submission Number"
    - "Device"
    - "Company"
    - "Panel (Lead)"
    - "Primary Product Code"
  tolerated_columns:                # dropped when present; never required
    - "submission"

classification_lookup:
  name: "openFDA device classification"
  endpoint: "https://api.fda.gov/device/classification.json"
  batch_size: 50                    # product codes per query; 1-100
  requests_per_second: 2            # self-imposed ceiling; 1-4. No API key is used.
  fields:                           # kept from each record; must include product_code
    - product_code
    - device_name
    - definition
    - regulation_number
    - device_class
    - medical_specialty_description
    - review_panel

pathways:                           # submission-number prefix -> marketing pathway
  - {prefix: "DEN", label: "De Novo"}
  - {prefix: "K",   label: "510(k)"}
  - {prefix: "P",   label: "PMA"}

expected:                           # what the last run measured. Recorded for drift.
  …                                 # NOT asserted: the list legitimately grows.
```

### The column contract

`required_columns` is checked as an exact set, not as a subset: a missing column fails the
run and so does an unexpected one, because an unexpected column is how a rename presents
itself. `tolerated_columns` is dropped first — the repo's 2025-12-30 snapshot carries a
duplicate `submission` column that the live file does not.

A drifted schema raises before anything is written, so a snapshot directory never holds a
file the parser could not read. Fixing it is a config edit (decide what the new column
means, then move it into `required_columns` or `tolerated_columns`), a `version` bump, and
a `VERSIONS.json` append — never an edit to the downloaded CSV.

### Pathways

FDA publishes no marketing-pathway column, but the submission number's prefix is
unambiguous and stable, and a supplement keeps its parent's prefix, so `P140011/S008` is a
PMA. Prefixes are tested longest-first. `label` must be one of `510(k)`, `De Novo`, `PMA`:
`authorizations.csv` declares `pathway` over exactly those three and the figure is drawn
against them, so a fourth label is a schema change, not a config edit.

### `expected`

Counts measured at design time, so a later snapshot's drift is *visible* rather than
silent. Nothing asserts them — the FDA list grows with every republication, and a run that
failed because the world moved would be useless. `clinops.fetch` logs a warning when
`total_devices` no longer matches; that is the whole enforcement.

## `oncology_codes.yaml`

```yaml
version: 1

overrides:                          # codes whose openFDA record describes a different device
  NMN:
    domain: pathology               # must match the domain of the category listing the code
    tier: oncology
    reason: >-                      # why the lookup cannot be trusted here
      …

categories:                         # exactly these three keys, in this order
  radiology_cancer_detection:
    label: "Cancer detection and diagnosis"   # exact string used in figure axes
    domain: radiology               # radiology | pathology
    tier: oncology                  # a category is what the figure counts, so always oncology
    codes:
      - code: QDQ                   # three uppercase letters
        regulation_number: "892.2090"   # QUOTED, or null. See the trap below.
        device_name: "…"            # FDA's device-type name
        definition: >-              # FDA's regulation definition, abridged, plus the reason
          …
    notes: >-                       # why this category exists and what including it costs
      …
  radiology_radiation_therapy: {…}
  pathology: {…}

excluded:                           # recorded so the rule can be audited, not just trusted
  not_oncology:
    reason: "…"                     # what this group means
    codes:
      - {code: QFM, n: 39, why: "…"}    # n = devices observed when the exclusion was written
  indeterminate:
    reason: "…"
    codes:
      - {code: QIH, n: 274, why: "…"}
```

### The rule

A device is counted when its `Primary Product Code` appears under `categories:`. That is
the whole rule. Nothing matches on device names: the FDA list publishes no
indication-for-use field, and its only free text is the `Device` column, which holds brand
names — Transpara, ProFound AI, AIR Recon DL. A generous cancer-term regex over those names
matched 4% of radiology and pathology rows and missed every mammography CAD product whose
name does not say "mammo".

The rule is deliberately conservative. `tier: oncology` requires that FDA's regulation
definition, or the code's own device-type name, states the cancer indication. A code whose
definition is generic goes under `excluded.indeterminate` even though some of its devices
are certainly oncologic — QIH alone holds 274 devices, among them plainly oncologic tools.
**The published count is a floor, not an estimate, and the legend must say so.**

The code name alone is never enough. QFM's device-type name is "Radiological
Computer-Assisted Prioritization Software For Lesions", which reads oncologic; its 39
devices are pneumothorax, pulmonary-embolism, fracture, aneurysm and trauma triage. Every
code was checked against the devices actually authorized under it.

### What is checked at load

Beyond types and required fields:

- `categories` declares **exactly** `radiology_cancer_detection`,
  `radiology_radiation_therapy`, `pathology`. A rename would empty a figure series without
  an error, so it fails the load instead. Changing the set means changing
  `clinops.config.CATEGORY_KEYS` and the figure together.
- A product code appears in **exactly one** category, and never in both a category and an
  exclusion list. Either would double-count or contradict.
- Every code matches `^[A-Z]{3}$`. A lowercase or space-padded code matches no device, and
  a rule that matches nothing is indistinguishable from a code with no devices.
- Every `overrides:` entry names a code some category lists, and states that category's
  domain. An override that names an unlisted code can never fire; one that names a
  different domain would put a code in a category whose domain it does not share, and
  `cumulative_by_year.csv` reads one domain per category.
- `domain` is `radiology` or `pathology`; `tier` is `oncology` or `indeterminate`; a
  category's `tier` is always `oncology`.
- `excluded` declares exactly the groups `not_oncology` and `indeterminate`. Each becomes
  an exclusion reason in the run manifest, so adding one is a schema change.

### The `regulation_number` trap

**Quote it, or write `null`.** Unquoted, YAML reads `892.2090` as a float and hands back
`892.209` — a different regulation, one digit short, and nothing downstream would notice.
The loader rejects a non-string, non-null value for this reason. The same trap bites on the
way back out: `clinops.aggregate` reads the interim table with `dtype=str` so pandas cannot
re-infer the column as a float.

The value written into `authorizations.csv` is **the config's**, not openFDA's. For an
overridden code the lookup describes a different device entirely, so its regulation number
would be wrong; for every other code the two agree, and
`data/processed/classification_report.txt` prints them side by side so a divergence
surfaces.

### Overrides

An override records that openFDA's current record does not describe the device authorized
under that code. FDA retires and reassigns codes, so a code queried today can describe
something unrelated to a device authorized decades ago. NMN is the live case: openFDA
returns "Instrument, Clip, Forming/Cutting, Reprocessed" under Neurology, which is not the
AUTOPAP 300 QC Automatic Pap Screener authorized as P950009 in 1995.

An override does not silence the mismatch. `clinops.classify --report` prints **every**
code whose openFDA `medical_specialty_description` differs from its assigned domain,
whether or not an override covers it, so a future reassignment surfaces instead of quietly
moving a device.

### `n` in the exclusion lists

The device count each excluded code held when the exclusion was written. Recorded for
drift, never asserted. The report prints any code whose observed count has moved: that does
not invalidate the exclusion, but a code that has grown by an order of magnitude is worth
re-reading before the next figure goes out.

## Changing a config safely

1. Edit the file. Record *why* in the `notes:` or `why:` field next to the change.
2. Bump `version`.
3. `sha256sum config/<file>` and append `version -> hash` to `VERSIONS.json`.
4. Re-run the pipeline and read `data/processed/classification_report.txt` before trusting
   the figure. The exclusion counts, the panel-agreement rates and the specialty
   disagreements are all there.
5. Add the judgment call to `docs/DECISIONS.md`.
