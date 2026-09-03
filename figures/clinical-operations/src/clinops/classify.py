"""Apply the oncology rule in ``oncology_codes.yaml`` to a snapshot.

Usage::

    python -m clinops.classify --config-dir config --report

The rule is entirely code-driven. A device is counted when its
``Primary Product Code`` appears in a category of ``oncology_codes.yaml``, which
is to say when FDA's own regulation definition for that code names cancer,
tumors, or radiation therapy. Everything else is excluded, and every exclusion
carries a reason drawn from the config rather than invented here.

The rule is deliberately conservative, so the published count is a floor. Code
QIH alone holds 274 devices under "Automated Radiological Image Processing
Software", some of them plainly oncologic; counting them would mean adjudicating
several hundred brand names one at a time. They are excluded as
``code_indeterminate`` and the legend has to say so.

Two checks exist because the lookup can be wrong, and both are printed by
``--report`` rather than resolved silently:

* **Specialty disagreement.** Where openFDA's ``medical_specialty_description``
  for a code does not match the domain the config assigns it. Code NMN is the
  live case: openFDA now describes a reprocessed neurology clip instrument,
  because the code was reassigned after the AUTOPAP 300 QC was authorized under
  it in 1995. The config overrides it; the report keeps the disagreement
  visible so a future reassignment surfaces instead of quietly moving a device.
* **Panel agreement.** FDA labels every row with its own ``Panel (Lead)``. That
  label is independent of the product-code rule, so agreement between the two
  is a check on the rule rather than a restatement of it. The report measures
  it; it is not asserted, because a disagreement is a finding.

Outputs
-------
``data/interim/labeled_devices.csv``
    Every device row with its assignment or its exclusion reason. This is the
    audit trail for any disputed count, and what :mod:`clinops.aggregate` reads.
``data/interim/classification_run.json``
    Provenance and counts for the run manifest :mod:`clinops.aggregate` writes.
``data/processed/classification_report.txt``
    The human-readable summary. Read it before trusting a figure.
"""

from __future__ import annotations

import argparse
import json
import logging
import platform
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

import pandas as pd

from clinops import __version__
from clinops.adjudication import (
    AdjudicationSet,
    DeviceDecision,
    load_adjudication,
    provenance as adjudication_provenance,
)
from clinops.config import (
    CATEGORY_KEYS,
    ConfigError,
    OncologyCodes,
    SourceConfig,
    config_provenance,
    load_configs,
)
from clinops.enrich import OPENFDA_PREFIX, Snapshot, SnapshotError, load_snapshot
from clinops.fetch import DEFAULT_RAW_ROOT, SchemaError, file_digest

log = logging.getLogger("clinops.classify")

#: File names this stage writes. :mod:`clinops.aggregate` reads the first two.
LABELED_DEVICES: Final[str] = "labeled_devices.csv"
CLASSIFICATION_RUN: Final[str] = "classification_run.json"
REPORT: Final[str] = "classification_report.txt"

DEFAULT_INTERIM_DIR: Final[Path] = Path("data/interim")
DEFAULT_PROCESSED_DIR: Final[Path] = Path("data/processed")

#: Column order of ``labeled_devices.csv``. The first twelve are exactly the
#: frozen schema of ``authorizations.csv``, in its order, so
#: :mod:`clinops.aggregate` selects rather than rebuilds.
LABELED_COLUMNS: Final[tuple[str, ...]] = (
    "submission_number",
    "decision_date",
    "year",
    "device",
    "company",
    "panel_lead",
    "product_code",
    "domain",
    "category",
    "category_label",
    "pathway",
    "regulation_number",
    "counted",
    "basis",
    "adjudication_confidence",
    "exclusion_reason",
    "code_overridden",
    "has_classification",
    "openfda_regulation_number",
    "openfda_medical_specialty_description",
    "openfda_device_name",
)

#: Exclusion reasons, in report order. Every excluded device carries exactly
#: one, and every reason is counted in the run manifest. The two ``unlisted``
#: reasons are kept apart on purpose: a code the dictionary has never seen is
#: unremarkable on the Cardiovascular panel and a hole in the rule on the
#: Radiology one.
EXCLUSION_REASONS: Final[tuple[str, ...]] = (
    "code_not_oncology",
    # Devices under a generic code, adjudicated one at a time. `code_indeterminate`
    # now means only "generic code, and no adjudication entry exists" -- a hole in
    # the dictionary rather than a decision. See clinops.adjudication.
    "device_not_oncology",
    "device_unresolved",
    "code_indeterminate",
    "code_unlisted_in_panel",
    "code_unlisted_off_panel",
    "pathway_unknown",
    "no_decision_date",
)

#: Panels whose devices the oncology rule is written against. A device outside
#: them carrying an unlisted code is expected; one inside them is a gap.
IN_SCOPE_PANELS: Final[frozenset[str]] = frozenset({"Radiology", "Pathology"})

#: How many unadjudicated devices the report lists individually before it stops.
#: The count is always exact; the listing is a sample to act on.
_MAX_UNADJUDICATED_LISTED: Final[int] = 40


class ClassificationError(ValueError):
    """Classification could not be run on the snapshot given."""


@dataclass(frozen=True)
class ClassificationResult:
    """One classification run.

    Attributes:
        labeled: Every device row, counted or not, in
            :data:`LABELED_COLUMNS` order.
        n_devices_in: Rows read from the snapshot.
        n_devices_counted: Rows that survived the rule.
        exclusions: Reason to count, in :data:`EXCLUSION_REASONS` order.
        specialty_disagreements: Per oncology code, openFDA's medical specialty
            against the domain the config assigns. Only the codes that disagree.
        panel_agreement: Per domain, how many counted devices carry FDA's
            matching ``Panel (Lead)``, and which panels the rest carry.
        code_counts: Devices per oncology code.
        excluded_code_drift: Excluded codes whose observed device count differs
            from the ``n:`` the config recorded.
    """

    labeled: pd.DataFrame
    n_devices_in: int
    n_devices_counted: int
    exclusions: dict[str, int]
    specialty_disagreements: tuple[dict[str, Any], ...]
    panel_agreement: dict[str, dict[str, Any]]
    code_counts: dict[str, int]
    excluded_code_drift: tuple[dict[str, Any], ...] = field(default=())
    #: Counted devices by how they were counted: by product code, or by
    #: device-level adjudication inside a generic code.
    basis_counts: dict[str, int] = field(default_factory=dict)
    #: Devices under a generic code that carry no adjudication entry. A hole in
    #: the dictionary, reported the same way an unlisted product code is.
    unadjudicated: tuple[dict[str, Any], ...] = field(default=())


def _exclusion_reason(
    product_code: str,
    panel_lead: str,
    pathway: str,
    decision_date: str,
    codes: OncologyCodes,
    device_decision: DeviceDecision | None = None,
) -> str:
    """Return the one reason this row is not counted, or ``""`` if it is.

    The code rule is applied before the row-level checks, and deliberately so:
    a device carrying an oncology code but an unexpected panel is counted, and
    the panel-agreement section of the report is where that surfaces. Making
    the panel a filter instead would hide exactly the disagreement the check
    exists to find.
    """
    # A DEVICE DECISION OUTRANKS ITS PRODUCT CODE, ALWAYS.
    #
    # The code is a prior, not a verdict, and it is wrong in both directions.
    # It missed the 1998 M1000 ImageChecker because no cancer-specific radiology
    # code existed in 1998 (MYN), and it wrongly counted 14 stroke, cardiac and
    # obstetric devices because POK's *name* says "Lesions Suspicious For
    # Cancer" while its definition says nothing about cancer. Letting the code
    # win anywhere would reintroduce one of those two failures.
    if device_decision is not None:
        if device_decision.decision == "oncology":
            # The frozen output schema declares `pathway` over three values and
            # `year` as an integer, so a row that cannot supply either is
            # excluded rather than written as a blank.
            if not pathway:
                return "pathway_unknown"
            if not decision_date:
                return "no_decision_date"
            return ""
        return f"device_{device_decision.decision}"

    if product_code in codes.assignments:
        if not pathway:
            return "pathway_unknown"
        if not decision_date:
            return "no_decision_date"
        return ""
    excluded = codes.excluded.get(product_code)
    if excluded is not None:
        # An unadjudicated generic code is a hole in the dictionary, not a
        # decision: the device is silently absent from the figure, and the
        # report says so.
        return f"code_{excluded.group}"
    return (
        "code_unlisted_in_panel"
        if panel_lead in IN_SCOPE_PANELS
        else "code_unlisted_off_panel"
    )


def classify_devices(
    snapshot: Snapshot,
    codes: OncologyCodes,
    adjudication: AdjudicationSet | None = None,
) -> ClassificationResult:
    """Apply the oncology rule to every device row in a snapshot.

    Args:
        snapshot: The joined snapshot from :mod:`clinops.enrich`.
        codes: The validated code dictionary, overrides already folded in.

    Returns:
        The labelled table and every count the report and the manifest need.
    """
    frame = snapshot.devices
    rows: list[dict[str, Any]] = []
    exclusions: Counter[str] = Counter()

    for record in frame.to_dict("records"):
        code = str(record["product_code"])
        pathway = str(record["pathway"])
        decision_date = str(record["decision_date"])
        panel = str(record["panel_lead"])
        device_decision = (
            adjudication.get(record["submission_number"]) if adjudication else None
        )
        reason = _exclusion_reason(
            code, panel, pathway, decision_date, codes, device_decision
        )
        assignment = codes.assignments.get(code)
        counted = reason == ""
        # A device counted by adjudication has no code-level assignment: its
        # category comes from the entry, and its regulation number is blank
        # because the generic code's regulation does not describe it.
        adjudicated_in = (
            device_decision.category if counted and device_decision is not None else ""
        )
        if not counted:
            exclusions[reason] += 1

        year = record["year"]
        rows.append(
            {
                "submission_number": record["submission_number"],
                "decision_date": decision_date,
                "year": pd.NA if pd.isna(year) else int(year),
                "device": record["device"],
                "company": record["company"],
                "panel_lead": panel,
                "product_code": code,
                # Domain, category and regulation number are written only for a
                # counted device. An excluded row carrying a half-filled
                # assignment invites a reader to sum the wrong column.
                "domain": (
                    codes.domain_of(adjudicated_in)
                    if adjudicated_in
                    else (assignment.domain if counted and assignment else "")
                ),
                "category": (
                    adjudicated_in
                    if adjudicated_in
                    else (assignment.category if counted and assignment else "")
                ),
                "category_label": (
                    codes.categories[adjudicated_in].label
                    if adjudicated_in
                    else (
                        codes.categories[assignment.category].label
                        if counted and assignment
                        else ""
                    )
                ),
                "pathway": pathway if counted else "",
                # The config's regulation number, not openFDA's. For an
                # overridden code the lookup describes a different device
                # entirely, so its regulation number would be wrong; for every
                # other code the two agree, and the report checks that they do.
                "regulation_number": (
                    (assignment.regulation_number or "") if counted and assignment else ""
                ),
                "counted": counted,
                "basis": ("device" if adjudicated_in else "code") if counted else "",
                "adjudication_confidence": (
                    device_decision.confidence
                    if counted and adjudicated_in and device_decision
                    else ""
                ),
                "exclusion_reason": reason,
                "code_overridden": bool(assignment.overridden) if assignment else False,
                "has_classification": bool(record["has_classification"]),
                "openfda_regulation_number": record.get(
                    f"{OPENFDA_PREFIX}regulation_number"
                ) or "",
                "openfda_medical_specialty_description": record.get(
                    f"{OPENFDA_PREFIX}medical_specialty_description"
                ) or "",
                "openfda_device_name": record.get(f"{OPENFDA_PREFIX}device_name") or "",
            }
        )

    labeled = pd.DataFrame(rows, columns=list(LABELED_COLUMNS))
    counted = labeled.loc[labeled["counted"]]

    return ClassificationResult(
        labeled=labeled,
        n_devices_in=len(labeled),
        n_devices_counted=len(counted),
        exclusions={
            reason: int(exclusions.get(reason, 0)) for reason in EXCLUSION_REASONS
        },
        specialty_disagreements=_specialty_disagreements(snapshot, codes),
        panel_agreement=_panel_agreement(counted),
        basis_counts={
            basis: int((counted["basis"] == basis).sum()) for basis in ("code", "device")
        },
        unadjudicated=tuple(
            labeled.loc[
                labeled["exclusion_reason"] == "code_indeterminate",
                ["submission_number", "device", "product_code"],
            ]
            .head(_MAX_UNADJUDICATED_LISTED)
            .to_dict("records")
        ),
        code_counts={
            code: int((labeled["product_code"] == code).sum())
            for code in sorted(codes.assignments)
        },
        excluded_code_drift=_excluded_code_drift(labeled, codes),
    )


def _specialty_disagreements(
    snapshot: Snapshot, codes: OncologyCodes
) -> tuple[dict[str, Any], ...]:
    """Return every oncology code whose openFDA specialty is not its domain.

    openFDA states a ``medical_specialty_description`` per product code, and the
    config states a domain. When the two differ, either the config is wrong or
    FDA has reassigned the code. Both are worth a human reading, and neither is
    something this module may decide, so every case is returned and printed.

    An absent or ``Unknown`` specialty is reported too, marked as such: it is
    not a contradiction, but it means the lookup corroborates nothing.
    """
    rows: list[dict[str, Any]] = []
    for code in sorted(codes.assignments):
        assignment = codes.assignments[code]
        record = snapshot.classifications.get(code)
        specialty = (record or {}).get("medical_specialty_description") or ""
        stated = specialty.strip()
        if stated.lower() == assignment.domain.lower():
            continue
        rows.append(
            {
                "code": code,
                "category": assignment.category,
                "config_domain": assignment.domain,
                "openfda_specialty": stated or "(no record)",
                "openfda_device_name": (record or {}).get("device_name") or "",
                "kind": (
                    "no_record" if record is None
                    else "unstated" if stated.lower() in ("", "unknown")
                    else "conflict"
                ),
                "overridden": assignment.overridden,
                "override_reason": assignment.override_reason,
            }
        )
    return tuple(rows)


def _panel_agreement(counted: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Measure agreement between FDA's ``Panel (Lead)`` and the config domain.

    FDA assigns a lead review panel independently of the product-code rule, so
    this is a genuine second opinion on every counted device rather than a
    restatement of the rule. It is measured, never asserted: a snapshot in which
    the two diverge is telling us something.
    """
    agreement: dict[str, dict[str, Any]] = {}
    for domain in sorted(set(counted["domain"])):
        block = counted.loc[counted["domain"] == domain]
        matches = block["panel_lead"].str.lower() == domain.lower()
        disagreeing = block.loc[~matches, "panel_lead"].value_counts()
        agreement[domain] = {
            "n_devices": int(len(block)),
            "n_panel_matches": int(matches.sum()),
            "rate": float(matches.sum() / len(block)) if len(block) else 0.0,
            "other_panels": {str(k): int(v) for k, v in disagreeing.items()},
        }
    return agreement


def _excluded_code_drift(
    labeled: pd.DataFrame, codes: OncologyCodes
) -> tuple[dict[str, Any], ...]:
    """Return excluded codes whose device count differs from the config's ``n``.

    ``oncology_codes.yaml`` records how many devices each excluded code held
    when the exclusion was written. A changed count does not invalidate the
    exclusion, but a code that has grown by an order of magnitude deserves
    re-reading before the next figure goes out.
    """
    observed = labeled["product_code"].value_counts()
    rows = []
    for code, entry in sorted(codes.excluded.items()):
        found = int(observed.get(code, 0))
        if found != entry.n:
            rows.append(
                {"code": code, "group": entry.group, "config_n": entry.n, "observed_n": found}
            )
    return tuple(rows)


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------


def _bar(count: int, total: int, width: int = 28) -> str:
    """Render a proportion as a fixed-width bar of hashes."""
    filled = 0 if total <= 0 else round(width * count / total)
    return "#" * filled


def format_report(
    result: ClassificationResult,
    snapshot: Snapshot,
    source: SourceConfig,
    codes: OncologyCodes,
    adjudication: AdjudicationSet | None = None,
) -> str:
    """Render the human-readable diagnostic summary.

    The report exists to catch a wrong number before it reaches the figure. It
    gives the counts the figure will draw, the reason for every device left out,
    the disagreements between openFDA's view of a code and the config's, and the
    agreement between FDA's own panel label and the rule.
    """
    labeled = result.labeled
    counted = labeled.loc[labeled["counted"]]
    total_in = result.n_devices_in
    total_out = result.n_devices_counted
    lines: list[str] = []
    add = lines.append

    add("ONCOLOGY CLASSIFICATION REPORT")
    add("=" * 78)
    add(f"generated_utc      : {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    add(f"snapshot           : {snapshot.directory}")
    add(f"snapshot_date      : {snapshot.snapshot_date}  "
        "(max Date of Final Decision in the list)")
    add(f"devices.csv        : sha256 {snapshot.device_csv_sha256[:16]}")
    add(f"source.yaml        : v{source.version}  {source.sha256[:16]}")
    add(f"oncology_codes.yaml: v{codes.version}  {codes.sha256[:16]}  "
        f"{len(codes.categories)} categories, {len(codes.assignments)} oncology codes, "
        f"{len(codes.excluded)} excluded codes")
    add("")

    add("COUNTS")
    add("-" * 78)
    add(f"devices read       : {total_in:>7,}")
    for reason, count in result.exclusions.items():
        add(f"  excluded, {reason:<24}: {count:>6,}")
    add(f"devices counted    : {total_out:>7,}")
    if total_out == 0:
        add("")
        add("Nothing survived the rule. Nothing further to report.")
        return "\n".join(lines) + "\n"
    years = counted["year"].dropna().astype(int)
    add(f"year range         : {int(years.min())}-{int(years.max())}")
    add("")

    add("BY CATEGORY  (what the figure draws)")
    add("-" * 78)
    for key in CATEGORY_KEYS:
        block = counted.loc[counted["category"] == key]
        label = codes.categories[key].label if key in codes.categories else key
        add(f"{key:<30}{len(block):>6,}{len(block) / total_out:>8.1%}  "
            f"{_bar(len(block), total_out)}")
        add(f"    {label}")
    add(f"{'TOTAL':<30}{total_out:>6,}")
    add("")

    add("BY DOMAIN")
    add("-" * 78)
    for domain, count in counted["domain"].value_counts().items():
        add(f"{str(domain):<30}{int(count):>6,}{int(count) / total_out:>8.1%}  "
            f"{_bar(int(count), total_out)}")
    add("")

    add("BY MARKETING PATHWAY")
    add("-" * 78)
    add(f"{'domain':<14}{'category':<32}{'pathway':<10}{'n':>6}")
    for row in (
        counted.groupby(["domain", "category", "pathway"], sort=True)
        .size()
        .reset_index(name="n")
        .itertuples(index=False)
    ):
        add(f"{row.domain:<14}{row.category:<32}{row.pathway:<10}{row.n:>6,}")
    add("")
    add(f"{'domain':<14}{'pathway':<10}{'n':>6}")
    for row in (
        counted.groupby(["domain", "pathway"], sort=True)
        .size()
        .reset_index(name="n")
        .itertuples(index=False)
    ):
        add(f"{row.domain:<14}{row.pathway:<10}{row.n:>6,}")
    add("")

    add("CUMULATIVE AUTHORIZATIONS BY DOMAIN AND YEAR")
    add("-" * 78)
    add("Years with no authorization are omitted here; cumulative_by_year.csv is dense.")
    for domain in sorted(set(counted["domain"])):
        block = counted.loc[counted["domain"] == domain]
        per_year = block["year"].dropna().astype(int).value_counts().sort_index()
        running = 0
        parts: list[str] = []
        for year, count in per_year.items():
            running += int(count)
            parts.append(f"{year}:+{int(count)}={running}")
        add(f"{domain} ({len(block)} total)")
        for start in range(0, len(parts), 6):
            add("    " + "  ".join(parts[start : start + 6]))
    add("")

    add("PANEL AGREEMENT  (FDA's own Panel (Lead) against the config-derived domain)")
    add("-" * 78)
    add("FDA assigns a lead review panel independently of the product-code rule, so this")
    add("is a second opinion on every counted device, not a restatement of the rule. It")
    add("is measured, never asserted: a disagreement is a finding, not a bug to silence.")
    add("")
    for domain, stats in sorted(result.panel_agreement.items()):
        add(f"{domain:<14}{stats['n_panel_matches']:>5} / {stats['n_devices']:<5}"
            f"{stats['rate']:>8.1%}")
        for panel, count in sorted(stats["other_panels"].items()):
            add(f"    disagreeing: Panel (Lead) = {panel} ({count})")
    add("")

    add("PRODUCT CODES COUNTED  (openFDA's view of each, against the config's)")
    add("-" * 78)
    add(f"{'code':<6}{'category':<30}{'n':>5}  {'cfg reg':<10}{'openFDA reg':<12}"
        f"{'specialty':<12}")
    for code in sorted(codes.assignments):
        assignment = codes.assignments[code]
        record = snapshot.classifications.get(code) or {}
        n = int((counted["product_code"] == code).sum())
        config_reg = assignment.regulation_number or "-"
        openfda_reg = record.get("regulation_number") or "-"
        specialty = record.get("medical_specialty_description") or "(no record)"
        flag = ""
        if openfda_reg != "-" and config_reg != "-" and openfda_reg != config_reg:
            flag = "  <- regulation number differs from openFDA"
        elif assignment.overridden:
            flag = "  <- override in effect"
        add(f"{code:<6}{assignment.category:<30}{n:>5}  {config_reg:<10}"
            f"{openfda_reg:<12}{specialty:<12}{flag}")
    add("")

    add("SPECIALTY DISAGREEMENTS  (openFDA medical_specialty_description vs config domain)")
    add("-" * 78)
    add("Printed so a future code reassignment surfaces instead of quietly moving a")
    add("device. `conflict` means openFDA names a different specialty; `unstated` means")
    add("it names none, which corroborates nothing either way.")
    add("")
    if not result.specialty_disagreements:
        add("    (none: every counted code's openFDA specialty matches its domain)")
    for row in result.specialty_disagreements:
        add(f"  {row['code']}  [{row['kind']}]  config={row['config_domain']}  "
            f"openFDA={row['openfda_specialty']}")
        if row["openfda_device_name"]:
            add(f"      openFDA device name: {row['openfda_device_name']}")
        if row["overridden"]:
            add("      OVERRIDE IN EFFECT. " + " ".join(row["override_reason"].split())[:300])
        elif row["kind"] == "conflict":
            add("      NO OVERRIDE. Either oncology_codes.yaml assigns the wrong domain,")
            add("      or FDA has reassigned this code. Read the record before the next run.")
    add("")

    add("CODES WITH NO openFDA CLASSIFICATION RECORD")
    add("-" * 78)
    add("A code openFDA has no record for cannot be resolved from the lookup. Devices")
    add("carrying one are kept and classified from the config alone.")
    if snapshot.codes_without_record:
        for code in snapshot.codes_without_record:
            n = int((labeled["product_code"] == code).sum())
            where = "COUNTED" if code in codes.assignments else "excluded"
            add(f"    {code}  {n:>4} device(s)  [{where}]")
    else:
        add("    (none: every product code in the list resolved)")
    add("")

    add("EXCLUDED CODES  (config's recorded n against this snapshot's)")
    add("-" * 78)
    add("The config records what each excluded code held when the exclusion was written.")
    add("A changed count does not invalidate the exclusion, but a code that has grown a")
    add("lot is worth re-reading before the next figure.")
    if result.excluded_code_drift:
        add(f"    {'code':<6}{'group':<16}{'config n':>9}{'observed':>10}")
        for row in result.excluded_code_drift:
            add(f"    {row['code']:<6}{row['group']:<16}{row['config_n']:>9}"
                f"{row['observed_n']:>10}")
    else:
        add("    (none: every excluded code holds exactly the count the config recorded)")
    add("")

    add("SCOPE COVERAGE  (Radiology and Pathology panels)")
    add("-" * 78)
    add("Every device on these two panels should be either counted or excluded by a")
    add("named code. A row reaching `code_unlisted_in_panel` is a hole in the")
    add("dictionary: a code the config has never adjudicated.")
    in_scope = labeled.loc[labeled["panel_lead"].isin(IN_SCOPE_PANELS)]
    unlisted = in_scope.loc[in_scope["exclusion_reason"] == "code_unlisted_in_panel"]
    add(f"    devices on those panels     : {len(in_scope):>6,}")
    add(f"    counted                     : {int(in_scope['counted'].sum()):>6,}")
    add(f"    excluded by a named code    : "
        f"{len(in_scope) - int(in_scope['counted'].sum()) - len(unlisted):>6,}")
    add(f"    unlisted code (a gap)       : {len(unlisted):>6,}")
    if len(unlisted):
        for code, count in unlisted["product_code"].value_counts().items():
            add(f"        {code}  {int(count)} device(s)  "
                f"e.g. {unlisted.loc[unlisted['product_code'] == code, 'device'].iloc[0][:48]}")
    add("")

    add("DEVICE-LEVEL ADJUDICATION")
    add("-" * 78)
    add("A product code's regulation does not always describe the devices authorized")
    add("under it, and the mismatch is not random. FDA created the cancer-specific codes")
    add("only around 2018-2020, so before then mammography and lung CAD were authorized")
    add("under generic codes -- MYN holds the 1998 M1000 ImageChecker. A code-only rule")
    add("therefore undercounts as a FUNCTION OF TIME, which bends a trend line rather")
    add("than merely shortening it. Devices under generic codes are adjudicated one at a")
    add("time; see clinops.adjudication and config/adjudication/.")
    add("")
    if adjudication is None or not adjudication.decisions:
        add("    NO ADJUDICATION LOADED. Every generic code is excluded wholesale, and")
        add("    the counts below understate the early years more than the late ones.")
    else:
        counts = adjudication.counts()
        add(f"    fragments        : {len(adjudication.fragments)} "
            f"({', '.join(sorted(adjudication.fragments)) or 'none'})")
        add(f"    codes covered    : {', '.join(sorted(adjudication.codes)) or '(none)'}")
        add(f"    devices decided  : {len(adjudication.decisions):,}")
        for value in ("oncology", "not_oncology", "unresolved"):
            add(f"      {value:<16s} {counts.get(value, 0):>6,}")
        add("")
        add("    counted by category:")
        by_category = adjudication.counts_by_category()
        if by_category:
            for key, count in by_category.items():
                add(f"      {codes.categories[key].label:<34s} {count:>4,}")
        else:
            add("      (none)")
        add("")
        add("    HOW EACH COUNTED DEVICE WAS COUNTED")
        add("    A device counted `by code` was admitted by its product code's own")
        add("    regulation. One counted `by device` sits under a generic code and was")
        add("    adjudicated individually. The split says how much of the figure rests")
        add("    on hand judgment rather than on FDA's own wording.")
        for basis in ("code", "device"):
            n = result.basis_counts.get(basis, 0)
            share = n / result.n_devices_counted if result.n_devices_counted else 0.0
            add(f"      by {basis:<7s} {n:>5,}  {share:6.1%}")
        add("")
        add("    UNRESOLVED  (the honest residual)")
        add(f"    {counts.get('unresolved', 0):,} devices could not be decided from the")
        add("    published fields -- brand names that say nothing about indication. They")
        add("    are excluded, and the figure reports them as an uncertainty band rather")
        add("    than folding them into either side. They are the width of the error bar")
        add("    on every count here.")
    add("")

    add("UNADJUDICATED DEVICES  (holes in the dictionary)")
    add("-" * 78)
    add("A device under a generic code with no adjudication entry. Not a decision --")
    add("an omission. Each one is silently absent from the figure, so this must be zero")
    add("before a figure is published.")
    holes = int(result.exclusions.get("code_indeterminate", 0))
    if not holes:
        add("    (none: every device under a generic code has been adjudicated)")
    else:
        add(f"    {holes:,} device(s) unadjudicated. First "
            f"{min(holes, _MAX_UNADJUDICATED_LISTED)}:")
        for row in result.unadjudicated:
            add(f"      {row['submission_number']:<12s} {row['product_code']:<5s} "
                f"{str(row['device'])[:46]}")
        if holes > len(result.unadjudicated):
            add(f"      ... and {holes - len(result.unadjudicated):,} more")
    add("")

    add("WHAT THIS COUNT IS NOT")
    add("-" * 78)
    add("An authorization is permission to market. It is not evidence of deployment,")
    add("of installed base, or of benefit, and nothing here speaks to how any of these")
    add("devices performs or whether it is used.")
    add("")
    add("The count is also not a census of cancer-directed AI. Where a device could not")
    add("be resolved it was left out, and a clearance covering a whole imaging platform")
    add("is counted as one authorization even when the platform bundles a cancer CAD")
    add("feature among others. The figure counts AUTHORIZATIONS, not capabilities.")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------


def build_run_record(
    result: ClassificationResult,
    snapshot: Snapshot,
    source: SourceConfig,
    codes: OncologyCodes,
    adjudication: AdjudicationSet | None = None,
    *,
    outputs: dict[str, Path],
) -> dict[str, Any]:
    """Assemble the provenance and counts :mod:`clinops.aggregate` will carry.

    Everything the run manifest needs about the input and the rule is fixed
    here, at the moment the rule was applied, rather than re-derived later from
    files that may since have moved.
    """
    counted = result.labeled.loc[result.labeled["counted"]]
    return {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool": "clinops.classify",
        "clinops": __version__,
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "input": {
            "snapshot": str(snapshot.directory),
            "snapshot_date": snapshot.snapshot_date.isoformat(),
            "devices_csv": str(snapshot.directory / "devices.csv"),
            "sha256": snapshot.device_csv_sha256,
            "n_rows": snapshot.n_device_rows,
            "openfda_last_updated": (
                (snapshot.manifest.get("classification_lookup") or {}).get("last_updated")
            ),
            "codes_without_openfda_record": list(snapshot.codes_without_record),
        },
        "config": config_provenance(source, codes),
        "adjudication": (
            adjudication_provenance(adjudication) if adjudication else None
        ),
        "basis_counts": dict(result.basis_counts),
        "counts": {
            "devices_in": result.n_devices_in,
            "devices_counted": result.n_devices_counted,
            "exclusions": dict(result.exclusions),
            "by_category": {
                key: int((counted["category"] == key).sum()) for key in CATEGORY_KEYS
            },
            "by_domain": {
                str(k): int(v) for k, v in counted["domain"].value_counts().items()
            },
            "by_domain_pathway": {
                f"{domain}|{pathway}": int(n)
                for (domain, pathway), n in
                counted.groupby(["domain", "pathway"]).size().items()
            },
            "by_product_code": result.code_counts,
        },
        "checks": {
            "panel_agreement": result.panel_agreement,
            "specialty_disagreements": [dict(row) for row in result.specialty_disagreements],
            "excluded_code_drift": [dict(row) for row in result.excluded_code_drift],
        },
        "outputs": {
            name: {"path": str(path), "sha256": file_digest(path)}
            for name, path in outputs.items()
        },
    }


def run(
    config_dir: str | Path = Path("config"),
    *,
    snapshot_dir: str | Path | None = None,
    raw_root: str | Path = DEFAULT_RAW_ROOT,
    interim_dir: str | Path = DEFAULT_INTERIM_DIR,
    processed_dir: str | Path = DEFAULT_PROCESSED_DIR,
) -> tuple[dict[str, Any], str]:
    """Classify one snapshot and write every output.

    Args:
        config_dir: Directory holding ``source.yaml`` and ``oncology_codes.yaml``.
        snapshot_dir: Snapshot to classify. ``None`` takes the newest finished
            one under ``raw_root``.
        raw_root: Where snapshots live.
        interim_dir: Where the labelled table and the run record go.
        processed_dir: Where the report goes, beside the tables it describes.

    Returns:
        The run record and the report text.
    """
    source, codes = load_configs(config_dir)
    log.info("source.yaml v%d (%s), oncology_codes.yaml v%d (%s)",
             source.version, source.sha256[:12], codes.version, codes.sha256[:12])

    adjudication = load_adjudication(config_dir)
    if adjudication.decisions:
        log.info(
            "Device adjudication: %d devices across %d fragment(s); %d counted, "
            "%d unresolved",
            len(adjudication.decisions), len(adjudication.fragments),
            adjudication.n_counted, adjudication.n_unresolved,
        )
    else:
        log.warning(
            "No device adjudication found in %s. Generic product codes carry no "
            "verdict of their own, so the run will undercount -- and will undercount "
            "more the further back in time it looks, because FDA created the "
            "cancer-specific codes only around 2018-2020.",
            config_dir,
        )

    snapshot = load_snapshot(snapshot_dir, source, raw_root=raw_root)
    result = classify_devices(snapshot, codes, adjudication)
    log.info(
        "Counted %d of %d devices (%s)",
        result.n_devices_counted, result.n_devices_in,
        ", ".join(f"{reason}={count}" for reason, count in result.exclusions.items() if count),
    )

    interim_dir = Path(interim_dir)
    processed_dir = Path(processed_dir)
    interim_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    labeled_path = interim_dir / LABELED_DEVICES
    result.labeled.to_csv(labeled_path, index=False)
    log.info("Wrote %s (%d rows)", labeled_path, len(result.labeled))

    report_text = format_report(result, snapshot, source, codes, adjudication)
    report_path = processed_dir / REPORT
    report_path.write_text(report_text, encoding="utf-8")
    log.info("Wrote %s", report_path)

    record = build_run_record(
        result, snapshot, source, codes, adjudication,
        outputs={"labeled_devices": labeled_path, "classification_report": report_path},
    )
    run_path = interim_dir / CLASSIFICATION_RUN
    run_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    log.info("Wrote %s", run_path)
    return record, report_text


def build_parser() -> argparse.ArgumentParser:
    """Define the command line."""
    parser = argparse.ArgumentParser(
        prog="python -m clinops.classify",
        description=(
            "Apply the oncology rule in oncology_codes.yaml to a raw snapshot: label "
            "every device counted or excluded, with a reason for each."
        ),
        epilog=(
            "The rule is code-driven and conservative. A device is counted only where "
            "FDA's regulation definition for its product code names cancer, tumors or "
            "radiation therapy, so the result is a floor rather than an estimate. "
            "--report prints the diagnostic summary, which is where the openFDA "
            "specialty disagreements, the FDA-panel agreement check and the excluded "
            "codes' drift are reported. Read it before trusting a figure."
        ),
    )
    parser.add_argument("--config-dir", type=Path, default=Path("config"),
                        help="Directory holding source.yaml and oncology_codes.yaml. "
                             "Default: config.")
    parser.add_argument("--snapshot", type=Path, default=None,
                        help="Snapshot directory to classify. Default: the newest "
                             "finished one under --raw-root.")
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT,
                        help=f"Where snapshots live. Default: {DEFAULT_RAW_ROOT}.")
    parser.add_argument("--interim-dir", type=Path, default=DEFAULT_INTERIM_DIR,
                        help=f"Where labeled_devices.csv and classification_run.json "
                             f"go. Default: {DEFAULT_INTERIM_DIR}.")
    parser.add_argument("--output", type=Path, default=DEFAULT_PROCESSED_DIR,
                        help=f"Where classification_report.txt goes, beside the tables "
                             f"it describes. Default: {DEFAULT_PROCESSED_DIR}.")
    parser.add_argument("--report", action="store_true",
                        help="Print the diagnostic report as well as writing it.")
    parser.add_argument("--version", action="version", version=f"clinops {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Classify one snapshot from the command line. Returns an exit status."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    try:
        record, report_text = run(
            args.config_dir,
            snapshot_dir=args.snapshot,
            raw_root=args.raw_root,
            interim_dir=args.interim_dir,
            processed_dir=args.output,
        )
    except ConfigError as exc:
        print(f"Configuration is unusable:\n{exc}", file=sys.stderr)
        return 2
    except (SnapshotError, SchemaError, ClassificationError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.report:
        print(report_text)
    else:
        print(json.dumps(record["counts"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
