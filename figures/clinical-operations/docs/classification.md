# Classification

How a device becomes a counted row, and how to change that safely.

---

## The chain

```
FDA AI device list row
  → Primary Product Code
    → openFDA regulation definition        (what this device TYPE is for)
      → config/oncology_codes.yaml         (does that definition name cancer?)
        → domain + category + tier
          → counted, or excluded with a recorded reason
```

Marketing pathway is read separately, from the submission number prefix: `DEN` → De Novo,
`K` → 510(k), `P` → PMA.

The unit of classification is the **device type**, not the device. That is what makes the rule
auditable: 47 codes appear in the radiology and pathology subset, so a reader checks 47
decisions rather than 1,103. It is also the source of the rule's main limitation, since a
generic code holds both oncologic and non-oncologic devices and cannot be split without
per-device adjudication.

## The rule

A code is `tier: oncology` when the FDA regulation definition, or the code's own device-type
name, **states the cancer indication**. Everything else is excluded, into one of two groups:

- `not_oncology` — the definition names a non-cancer indication (fracture, bone density,
  coronary flow, fibrotic lung disease, obstetric dating).
- `indeterminate` — the definition is generic. Some devices under the code are oncologic and
  some are not, and the published fields do not say which.

Excluding `indeterminate` is what makes the count a floor. About 800 devices sit there. See
`docs/source-strategy.md` §3 and the `DECISIONS.md` entry of 2026-09-03.

## The code name is not the rule

`QFM` is the case to remember. Its device-type name is "Radiological Computer-Assisted
Prioritization Software For Lesions", which reads oncologic. Its 39 devices are pneumothorax
and pulmonary-embolism triage, vertebral compression fracture, aneurysm triage, and trauma
triage. One of 39 is oncologic.

**Every code must be checked against the devices actually authorized under it.** A test,
`test_the_qfm_exclusion_is_documented`, exists specifically to catch someone re-including QFM
after reading only its name.

## Overrides

FDA retires and reassigns product codes. A code queried today can describe something unrelated
to a device authorized under it decades earlier. `config/oncology_codes.yaml` has an
`overrides:` block for this, and it currently holds one entry:

`NMN` returns "Instrument, Clip, Forming/Cutting, Reprocessed" under Neurology. The device
authorized as P950009 in 1995 under that code is the AUTOPAP 300 QC Automatic Pap Screener,
which FDA's own list assigns to the Pathology panel.

An override contradicts the authoritative source, so the schema requires it to justify itself
and a test enforces that the justification is substantive.

`classify.py --report` prints **every** code where openFDA's `medical_specialty_description`
disagrees with the domain the config assigns. A future reassignment therefore surfaces as a
report line instead of a silent misclassification. Read that section of the report on every run.

---

## Changing a classification

1. **Read the devices first.** Before moving any code, list what was authorized under it:

   ```bash
   ~/.venvs/ccr-clinops/bin/python - <<'EOF'
   import csv, collections
   rows = list(csv.DictReader(open('data/raw/<snapshot>/ai-enabled-devices.csv', encoding='utf-8-sig')))
   for r in rows:
       if r['Primary Product Code'] == 'XXX':
           print(r['Date of Final Decision'][-4:], r['Device'])
   EOF
   ```

   If the devices do not match the code's name, the devices are right. That is the QFM lesson.

2. **Edit `config/oncology_codes.yaml`.** Record the FDA definition verbatim in the entry, and
   the reason in the category's `notes` or in the exclusion entry's `why`. A code carrying no
   evidence fails `test_every_counted_code_records_its_evidence`.

3. **Bump `version`** in the file you edited, and append the new version and its SHA-256 to
   `config/VERSIONS.json`:

   ```bash
   shasum -a 256 config/oncology_codes.yaml
   ```

   Never edit a hash already in the ledger; append a new entry. The version rule applies to
   **any** content change, including a corrected number in a comment — a run manifest that
   records the old hash under an unchanged version is wrong.

4. **Re-run with the report.**

   ```bash
   ~/.venvs/ccr-clinops/bin/python -m clinops.classify --config-dir config --report
   ```

5. **Read the report before the figure**, in this order:
   - **Counts per category and per domain.** Does the change move the number by what you
     expected? A code you thought held three devices holding thirty is the signal to stop.
   - **Panel agreement.** FDA's own `Panel (Lead)` against the config's `domain`. Any
     disagreement is either a reassignment needing an override or a mistake in your edit.
   - **Specialty mismatches.** Codes where openFDA and the config disagree.
   - **Unresolved codes.** Codes openFDA returned nothing for.

6. **Re-run the tests.** The ledger guard will fail if you edited without bumping.

   ```bash
   ~/.venvs/ccr-clinops/bin/python -m pytest tests/ -q
   ```

7. **Regenerate the figure and the summary**, and update any manuscript sentence that quotes a
   number. `figures/clinical_operations_summary.txt` is the sheet to refill the legend from —
   do not read numbers off the picture.

## What must not happen

Do not adjust the config to make a number match an expectation. If the pipeline produces counts
that differ from what `config/source.yaml`'s `expected:` block records, that block is a record
of a past measurement, not a target. Either the list grew, which is normal and the block should
be updated with a new `measured_on` date, or something is wrong and the config is the last
thing that should move.
