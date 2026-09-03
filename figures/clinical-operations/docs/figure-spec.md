# Figure specification — clinical operations

The deliverable is one two-panel portrait figure for the CCR review manuscript: **how many
oncology AI devices FDA has authorized, in radiology and in pathology, and by which
marketing pathway**. This file fixes the figure's content, the canonical key vocabulary, the
schema of the tables it is drawn from, and the figure geometry, so that the plotting code
and the classification code can be written and reviewed independently.

Style is not settled here. `../ink_style_guide.md` is normative, `../AGENTS.md` is
operational, and `../trends-figure/src/trends/plotting/style.py` is both of them compiled
into Python. This project **imports** that module and re-declares no token from it. The
sibling figure built from the same tokens is `../trends-figure/`.

AACR redraws figures from author sketches. Deliver a clear, complete, unfussy figure with a
full legend. Do not over-polish.

---

## What the figure is allowed to claim

Every number here counts **oncology-certain** authorizations on the FDA
Artificial Intelligence-Enabled Medical Devices list, snapshot through **2026-03-30**,
classified by the product-code rule in `config/oncology_codes.yaml`. That rule is
deliberately conservative: a product code counts only where FDA's own regulation definition
or device-type name states the cancer indication, which leaves ~800 devices under generic
codes (QIH alone holds 274) uncounted. **The figure is a floor, not an estimate**, and the
legend must say so. Panels state counts of *authorizations*, never of products in clinical
use, and never of "AI devices" in general.

---

## Panel A — Cumulative Oncology AI Authorizations

One plot. X is the decision year, y is the cumulative count of authorizations, **log
scale**. Three series:

| Series (`category`) | Drawn as | Devices through 2026-03-30 |
|---|---|---|
| `radiology_cancer_detection` | blue, solid, circle | 66 |
| `radiology_radiation_therapy` | blue, long dash, triangle | 79 |
| `pathology` | deep pink, dash-dot, square | 9 |

The log scale is the panel's whole reason for existing. Radiology's 145 against pathology's
9 is a 16-fold gap; on a linear axis pathology draws as a flat line on the floor and the
reader learns nothing about its shape. On a log axis both slopes are legible at once, and
the flat 26-year pathology plateau is visible as a plateau rather than as a line at zero.

The two radiology series share one hue, because hue is fixed project-wide to the **data
modality** and both are radiology. They are separated by dash, by marker, and by a direct
end-of-line label, so nothing about the panel depends on colour being seen.

### The zero problem, and what this figure does about it

A log axis cannot draw a zero. Three of the honest options were considered:

1. **A broken axis** across the 1996–2015 stretch, so the plot opens at 1995 and resumes at
   2016. **Rejected.** The 26 years in which pathology sat at two devices and nothing
   happened is the panel's finding. Compressing it into a break mark deletes the finding to
   save an inch of paper.
2. **Clip the x range to 2016**, the first radiology authorization. **Rejected.** It would
   put pathology's first two authorizations — the 1995 Pap screeners — off the page, and a
   figure that drops two of the nine devices it is about cannot be published.
3. **Plot each series only from its own first nonzero year.** **Adopted.**

So: the x axis runs **1995 to 2026 continuously, with no break in either axis**. 1995 is
the first authorization anywhere in the data, so nothing is off frame. Each series' line
begins at the first year its cumulative count reaches 1 — 1995 for pathology, 2016 for
cancer detection, 2018 for radiation therapy — and the years before that carry **no mark at
all**. A zero is not drawn as a point near the floor, because that point would be a value
the data does not hold.

The y axis floor sits at **0.8**, below the smallest drawable value, so no series is drawn
on top of the bottom spine. The final year is treated as **partial** whenever the snapshot's
latest decision date falls before December of it — the 2026-03-30 file holds one quarter of
2026 — and is then banded, its final segment dotted and its final marker drawn open, the
same treatment the sibling trends figure gives its partial year. No statement about a
slowdown may rest on that year. Ticks are 1, 2, 5, 10, 20, 50, 100, labelled as plain integers,
with unlabelled minor ticks at every integer decade step. The axis title says "log scale"
in words; a reader must not have to infer the transform from tick spacing.

**Explicitly rejected: drawing the pre-authorization years as a flat line along the axis
floor.** It reads as "this series was at the floor value" when the series was at zero, which
is the exact misreading a log axis invites. The absence of a line is the honest mark for the
absence of a device.

That every line begins at its first authorization is a statement about the drawing, not a
label of an element, so it goes in the figure legend and not in the artwork
(`../AGENTS.md`, content rules).

### The nine pathology devices

With n = 9 the pathology devices are namable, and naming them is the argument: the whole
regulatory history of AI in cancer pathology fits in a list a reader can read in ten
seconds. Each device is anchored to the point the pathology line actually draws in its
decision year, and labelled with a hairline leader.

Two placements, chosen by how far a device sits from the gutter:

- Devices within `panel_a.LEADER_MAX_SPAN` (10) years of the last year are labelled in the
  **right-hand gutter**, stacked. Chronological order equals cumulative order, so the stack
  is in the same order as the points and **no two leaders cross**.
- Earlier devices — the 1995 pair, thirty years from the gutter — are labelled **inline**,
  just below their own point, in the empty band between the pathology plateau and the axis
  floor. A leader from 1995 to the gutter would cross the whole plot and every radiology
  line in it, which is why the gutter is not used for everything.

Where several devices share one point, as the four 2025 authorizations do, their labels fan
from that point: four devices in one year is what the step is.

- Labels are **year + device name only** — four words or fewer, no explanatory text, per the
  style guide's content rules. FDA's own `device` strings are longer than the gutter
  ("AUTOPAP(R) 300 QC AUTOMATIC PAP SCREENER/QC SYSTEM"), so the display name is
  hand-wrapped in `DEVICE_LABELS`, keyed by submission number; a device with no hand-written
  label falls back to the first four words of its `device` field.
- The cap is `panel_a.MAX_ANNOTATED_DEVICES = 12`. A later snapshot with more pathology
  authorizations than that must redesign this annotation rather than shed labels, so the
  build **raises** `panel_a.TooManyDevices` instead of dropping any device silently.

### Panel A summary of marks

| Mark | Meaning |
|---|---|
| Line | Cumulative authorizations in one category, from its first authorization onward |
| Marker at each year | A measured year. A flat run of markers is a run of years with no new authorization, not a gap in the data |
| Gutter label + leader | One pathology device, its year and its name |

---

## Panel B — Authorization Pathway

Two horizontal 100 %-normalized stacked bars, one per `domain`: radiology (n = 145) and
pathology (n = 9). Each bar is divided into the three FDA marketing pathways in the order
510(k), De Novo, PMA.

The finding: **radiology iterates inside established device categories and pathology keeps
having to create new ones.** 140 of radiology's 145 authorizations are 510(k)s cleared
against an existing predicate; pathology's nine split 3 / 3 / 3 evenly across all three
pathways, which is what a field with no predicates to clear against looks like.

- **Normalized, not counts.** 145 against 9 on a shared count axis draws pathology as a
  stub, and composition — the actual claim — becomes unreadable. The raw numbers are not
  lost: each segment prints its own count, and each bar prints `n = …` at its end.
- **Pathway is encoded by fill texture, never by hue**: 510(k) solid, De Novo diagonal
  hatch, PMA cross hatch, with a three-swatch key beneath the panel drawn in neutral ink.
  No new hue is introduced anywhere in this figure.
- **Hue encodes the domain**, which is a modality statement and therefore semantic under the
  style guide: radiology `style.RADIOLOGY_IMAGING`, pathology `style.DIGITAL_PATHOLOGY`.
  Bars are areas, so they take the border hues; hatch lines and small type are thin, so they
  take the deep variants, per the guide's own parenthetical.
- Radiology's De Novo (1.4 %) and PMA (2.1 %) segments are slivers. Their counts are printed
  **above** the bar with hairline leaders rather than inside the segment, because type
  inside a 0.07 in sliver is not type. Whether a segment can hold its count is measured in
  inches against `panel_b.MIN_INSIDE_LABEL_IN`, not assumed from the data.
- A count printed inside a segment takes whichever of white and ink has the higher WCAG
  contrast against that segment's own fill: white on radiology blue (5.2 against 3.6), ink
  on pathology pink (6.1 against 3.1).
- The panel aggregates the two radiology categories, because the pathway claim is a claim
  about the domain. The per-category pathway table is written to the run summary, so the
  legend can quote it without it being read off the picture.

---

## Input schema — `data/processed/`

Plotting code reads only these three files. It classifies nothing, filters nothing, and
recounts nothing beyond what the layout needs. Every table is read with `comment="#"` so a
generated table can carry a provenance header, and every table is validated before a single
artist is created; a failure raises `io.SchemaError` naming **file, column, and problem**.

### `cumulative_by_year.csv` — drives Panel A

| Column | Type | Meaning |
|---|---|---|
| `year` | integer | Decision year |
| `category` | string | One of the three canonical category keys |
| `domain` | string | `radiology` or `pathology`; must agree with the category's own domain |
| `annual_count` | integer ≥ 0 | Authorizations in that category in that year |
| `cumulative_count` | integer ≥ 0 | Running total through that year |

Dense: every (`year`, `category`) pair from the minimum to the maximum year is present, with
zeros filled. Validated: no duplicate (`year`, `category`); `cumulative_count` is
non-decreasing within a category and equals the running sum of `annual_count`; the year grid
is complete for every category.

### `pathway_by_domain.csv` — drives Panel B

| Column | Type | Meaning |
|---|---|---|
| `domain` | string | `radiology` or `pathology` |
| `category` | string | Canonical category key; must agree with `domain` |
| `pathway` | string | `510(k)`, `De Novo`, or `PMA` |
| `count` | integer ≥ 0 | Authorizations in that cell |

Validated: no duplicate (`category`, `pathway`).

### `authorizations.csv` — one row per authorization

| Column | Type | Meaning |
|---|---|---|
| `submission_number` | string, unique | e.g. `K241232`, `DEN200080`, `P940029` |
| `decision_date` | ISO date | Date of final decision |
| `year` | integer | Year of `decision_date` |
| `device` | string | FDA's device name |
| `company` | string | Applicant |
| `panel_lead` | string | FDA lead review panel |
| `product_code` | string | Primary product code |
| `domain` | string | `radiology` or `pathology` |
| `category` | string | Canonical category key |
| `category_label` | string | Display label from `config/oncology_codes.yaml` |
| `pathway` | string | `510(k)`, `De Novo`, or `PMA` |
| `regulation_number` | string, may be blank | FDA regulation, where openFDA returns one |

Panel A reads this table for the pathology device names and dates. Nothing else in the
figure depends on it, but it is validated in full, because a table that disagrees with the
aggregates is a broken pipeline whether or not this figure draws the disagreeing column.

### Cross-table checks

These run in `io.load_figure_data` and raise `SchemaError` naming both files:

1. Rows of `authorizations.csv` per (`category`, `year`) equal `annual_count`.
2. Rows of `authorizations.csv` per (`category`, `pathway`) equal `count`.
3. `pathway_by_domain.csv` totals per category equal that category's final
   `cumulative_count`.

A figure that quotes n = 145 in one panel and draws 143 devices in the other is worse than
no figure, because it looks finished.

---

## Canonical keys — fixed, used by every file and every module

Categories, in figure order:

| Key | Display label | Domain |
|---|---|---|
| `radiology_cancer_detection` | Cancer detection | `radiology` |
| `radiology_radiation_therapy` | Radiation therapy | `radiology` |
| `pathology` | Digital pathology | `pathology` |

Radiation therapy is a **separate category and not merged into radiology**, for the reason
recorded in `config/oncology_codes.yaml`: those 79 devices automate contouring and dose
planning rather than interpreting an image for a diagnosis, pathology has no analogue, and
counting them inflates the radiology side of a diagnostic comparison. Keeping them separate
lets both the 145-vs-9 and the 66-vs-9 comparison be read off Panel A.

Domains: `radiology`, `pathology`.

Pathways, in figure order: `510(k)`, `De Novo`, `PMA`. Read from the submission-number
prefix (`K`, `DEN`, `P`) by the upstream pipeline; the figure trusts the column.

End-of-line series labels, hand-wrapped so three of them stack in Panel A's gutter without
colliding: `Cancer detection\n(radiology)`, `Radiation therapy\n(radiology)`,
`Digital pathology`.

---

## Geometry

Portrait, `FIGURE_SIZE = (7.0, 8.0)` inches. Panel rectangles are hard-coded figure
fractions, documented in inches in `src/clinops/plot.py` with a change history, exactly as
in `../trends-figure/src/trends/plot.py`. Reserved space:

- Panel A: 0.62 in left gutter for the y ticks and axis title; **1.53 in right gutter** for
  the three series end labels and the nine device labels. That gutter is what sets the
  figure's width — a longer device label needs the gutter widened, not the type shrunk.
- Panel B: 0.95 in left for the domain labels, 0.85 in right for the `n = …` totals, a key
  row beneath the axis for the three pathway swatches.

Type comes from the `FS_*` ladder in `style`; nothing in this figure sets a size that is not
in that ladder. Minimum stroke 1.0 pt. Every label is measured against the canvas at build
time and the build prints what it measured.

---

## Output

Written by one command, with no manual step afterward:

```bash
PYTHONPATH=src .venv/bin/python -m clinops.plot --input data/processed --output figures/
```

- `figures/clinical_operations.pdf` — vector, the version that goes to the journal
- `figures/clinical_operations.png` — 300 dpi, for drafts and slides
- `figures/clinical_operations.svg` — text as text, for the journal's illustrator
- `figures/clinical_operations_summary.txt` — the machine-written number sheet the figure
  legend is refilled from. Every number quoted in the legend must come from this file and
  never be read off the picture.

`--tag` suffixes the stem, so a build from stand-in fixtures cannot be mistaken for a build
from the real tables. The summary always names the directory it was built from.
