# Task Specification for the Clinical Operations Figure

## Goal

To create a figure for the CCR review manuscript showing trends in **clinical approvals** of
AI-enabled software and devices across radiology and pathology, as applied to cancer.

The manuscript's Current Clinical Operations section argues that radiology has deployed AI at
scale and pathology has not, and that the gap is infrastructural rather than algorithmic. That
argument currently rests on two bare numbers cited to the FDA device list. This figure builds
the evidence for it from the primary source, so a reader can see the shape of the gap, when it
opened, and how the two fields differ in the regulatory route they take.

## Sources

1. **FDA, Artificial Intelligence-Enabled Medical Devices.**
   <https://www.fda.gov/medical-devices/software-medical-device-samd/artificial-intelligence-enabled-medical-devices>
   The authorized-device list. A published file, not an API.
2. **FDA, Artificial Intelligence in Software as a Medical Device.**
   <https://www.fda.gov/medical-devices/software-medical-device-samd/artificial-intelligence-software-medical-device>
   Defines the three marketing pathways — 510(k) clearance, De Novo classification, and PMA
   approval — that the classification dimension of the figure quantifies.
3. **openFDA device classification endpoint.**
   <https://api.fda.gov/device/classification.json>
   Maps each FDA product code to its regulation number, device class, and regulation
   definition. This is what makes the oncology restriction possible.

## The problem this task had to solve

The FDA list publishes six fields: decision date, submission number, device, company, panel,
and primary product code. **There is no indication-for-use field.** "Applied to cancer" is
therefore not in the data and has to be derived.

Device names cannot carry the decision — they are brand names. A deliberately generous
cancer-term regular expression over device names matched 42 of 1,103 radiology and pathology
rows, missing every mammography product whose name does not contain "mammo".

Product codes can. Each resolves to an FDA regulation definition stating what the device type
is for. Where that definition names cancer, tumors, or radiation therapy, the code is
cancer-directed by construction. That decision is made once per code in
`config/oncology_codes.yaml`, with FDA's own words recorded beside it.

The rule is deliberately conservative: codes with generic definitions are excluded even though
some of their devices are certainly oncologic. **The published counts are a floor, not an
estimate, and the figure legend says so.**

## Figure content

**Panel A.** Cumulative oncology-directed AI authorizations over time, radiology against
pathology, on a log scale. Three series: radiology cancer detection and diagnosis, radiology
radiation therapy planning, and pathology. All nine pathology devices are named individually.

**Panel B.** Marketing pathway composition by domain — 510(k), De Novo, PMA.

## Rules

1. Make everything reproducible and follow all best practices for coding style, software
   engineering project organization, data provenance, keeping track of decision-making, etc.
2. Answers must always be concise, clear, and direct. Avoid aphorisms. Follow writing
   conventions and rules set forth by Strunk and White in their book on writing, the Elements
   of Style.
3. Avoid jargon and define key terms as necessary when communicating. Keep communication
   professional and academic.
4. Keep workspace tidy. Don't clutter with unnecessary files and use proper directory structure
   for easy organization.
5. Document all code appropriately and keep a code book and data dictionary that describes the
   purpose and use of every file.

These are the same five rules that govern `../trends-figure`, and this project follows that
project's procedure throughout: versioned YAML configuration that the code reads and nobody
hard-codes around, append-only raw snapshots, per-stage manifests recording input and output
hashes, a decision log, and a figure built by a committed script so the next revision is
re-renderable.

## Reading order for a newcomer

1. This file.
2. `docs/source-strategy.md` — what the sources are and what they can and cannot support.
3. `docs/classification.md` — how the oncology rule works and how to change it safely.
4. `docs/figure-spec.md` — what the figure shows and why.
5. `docs/DECISIONS.md` — every judgment call, with its alternatives.
6. `CODEBOOK.md` — every file in the project and who writes it.
