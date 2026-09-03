"""Device-level oncology decisions inside the generic product codes.

WHY THIS EXISTS

``oncology_codes.yaml`` classifies a whole product code at once, from FDA's
regulation definition for that code. That rule is auditable -- 47 decisions
instead of 1,103 -- but it has a failure mode that a first pass missed and that
matters more than the undercount it was known to cause.

FDA only created cancer-specific product codes around 2018-2020; the MYN
definition points at the Federal Register notice, "Radiology Devices;
Reclassification of Medical Image Analyzers" (85 FR 3541, 22 January 2020).
Before that, mammography and lung computer-aided detection were authorized under
generic codes, overwhelmingly MYN, "Analyzer, Medical Image". MYN holds the 1998
M1000 ImageChecker -- the first FDA-approved mammography CAD -- the 2001
RapidScreen RS-2000 and the 2002 Second Look, alongside a large number of dental
caries products.

So a code-only rule does not merely undercount. It undercounts *as a function of
time*, because the codes it keys on did not exist for the first twenty years of
the series. A uniform undercount is safe for a ratio; a time-varying one
fabricates a trend. The published figure showed radiology's first cancer-directed
authorization as 2016 when it is 1998.

WHAT THIS MODULE DOES

It reads hand-adjudicated, per-device decisions for the devices sitting under
codes the code-level rule calls ``indeterminate``, and exposes them keyed by
submission number. Each decision is one of:

``oncology``
    Counted, into the category the entry names.
``not_oncology``
    Excluded, with the reason recorded.
``unresolved``
    Excluded, and **counted separately**. These are devices whose purpose cannot
    be established from the published fields -- mostly brand names that say
    nothing. They are the honest residual, and the figure reports them as an
    uncertainty band rather than silently folding them into either side.

The fragments live in ``config/adjudication/`` so that several people can work on
disjoint code groups without editing one file. They are merged here, and a
submission number appearing in two fragments is an error rather than a
last-one-wins.

WHAT THIS MODULE IS NOT

It is not a classifier. Nothing here infers a decision; every decision is written
down by a person or agent with its evidence, and this module only loads,
validates, and merges. A device with no entry is not silently dropped -- it is
reported as unadjudicated, which is a hole in the dictionary and a run-time
warning, exactly as an unlisted product code is.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import yaml

from clinops.config import CATEGORY_KEYS, ConfigError

#: Decisions an adjudicated device may carry.
VALID_DECISIONS: Final[frozenset[str]] = frozenset(
    {"oncology", "not_oncology", "unresolved"}
)

#: Confidence levels an ``oncology`` decision may declare.
VALID_CONFIDENCE: Final[frozenset[str]] = frozenset({"high", "medium"})

#: Shortest evidence string that can be called evidence. A decision this module
#: cannot show a reason for is worse than no decision, because it looks
#: authoritative in the output table.
MIN_EVIDENCE_CHARS: Final[int] = 25

#: Where the fragments live, relative to the config directory.
ADJUDICATION_DIRNAME: Final[str] = "adjudication"


class AdjudicationError(ValueError):
    """An adjudication fragment is unreadable or fails a check.

    The message lists every problem found, not the first, because these files
    are written in bulk and fixing them one error per run is slow.
    """


@dataclass(frozen=True)
class DeviceDecision:
    """One device, adjudicated.

    Attributes:
        submission_number: The FDA submission number. The join key.
        device: Device name as it appears in the FDA list, verbatim.
        product_code: The generic code the device sits under.
        decision: One of :data:`VALID_DECISIONS`.
        category: The category an ``oncology`` decision assigns into; empty
            otherwise.
        confidence: ``high`` or ``medium`` for an ``oncology`` decision; empty
            otherwise.
        evidence: Why. Required for every decision.
        source: The fragment file this came from, for blame.
    """

    submission_number: str
    device: str
    product_code: str
    decision: str
    category: str
    confidence: str
    evidence: str
    source: str

    @property
    def counted(self) -> bool:
        """Whether this decision puts the device into the figure."""
        return self.decision == "oncology"


@dataclass(frozen=True)
class AdjudicationSet:
    """Every device decision, merged across fragments.

    Attributes:
        decisions: Submission number to :class:`DeviceDecision`.
        codes: Product codes the fragments claim to cover.
        fragments: Fragment filename to its SHA-256, for the run manifest.
        versions: Fragment filename to its declared version.
        directory: Where the fragments were read from.
    """

    decisions: dict[str, DeviceDecision]
    codes: frozenset[str]
    fragments: dict[str, str]
    versions: dict[str, int]
    directory: Path
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def get(self, submission_number: str) -> DeviceDecision | None:
        """Return the decision for a submission number, if adjudicated."""
        return self.decisions.get(str(submission_number).strip().upper())

    def counts(self) -> dict[str, int]:
        """Decisions by value, for the report and the manifest."""
        out = {value: 0 for value in sorted(VALID_DECISIONS)}
        for decision in self.decisions.values():
            out[decision.decision] += 1
        return out

    def counts_by_category(self) -> dict[str, int]:
        """Counted devices by category, in figure order."""
        out: dict[str, int] = {}
        for decision in self.decisions.values():
            if decision.counted:
                out[decision.category] = out.get(decision.category, 0) + 1
        return {key: out[key] for key in CATEGORY_KEYS if key in out}

    @property
    def n_counted(self) -> int:
        return sum(1 for d in self.decisions.values() if d.counted)

    @property
    def n_unresolved(self) -> int:
        return sum(1 for d in self.decisions.values() if d.decision == "unresolved")


def _digest(path: Path) -> str:
    """SHA-256 of a file's raw bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_entry(
    entry: Any, index: int, source: str, problems: list[str]
) -> DeviceDecision | None:
    """Validate one adjudication entry.

    Returns ``None`` and appends to ``problems`` rather than raising, so one
    pass reports every fault in a fragment.
    """
    where = f"{source}[{index}]"
    if not isinstance(entry, dict):
        problems.append(f"{where}: entry is {type(entry).__name__}, not a mapping")
        return None

    submission = str(entry.get("submission_number", "")).strip().upper()
    if not submission:
        problems.append(f"{where}: no submission_number, which is the join key")
        return None

    decision = str(entry.get("decision", "")).strip()
    if decision not in VALID_DECISIONS:
        problems.append(
            f"{where} ({submission}): decision {decision!r} is not one of "
            f"{sorted(VALID_DECISIONS)}"
        )
        return None

    category = str(entry.get("category", "") or "").strip()
    confidence = str(entry.get("confidence", "") or "").strip()

    if decision == "oncology":
        if category not in CATEGORY_KEYS:
            problems.append(
                f"{where} ({submission}): decision is 'oncology' but category "
                f"{category!r} is not one of {list(CATEGORY_KEYS)}. A counted device "
                "must say which series it joins."
            )
        if confidence and confidence not in VALID_CONFIDENCE:
            problems.append(
                f"{where} ({submission}): confidence {confidence!r} is not one of "
                f"{sorted(VALID_CONFIDENCE)}"
            )
    else:
        # A non-counted decision carrying a category would be read as counted by
        # anyone scanning the table.
        if category:
            problems.append(
                f"{where} ({submission}): decision is {decision!r} but a category "
                f"({category!r}) is set. Only an 'oncology' decision takes a category."
            )
        category = ""
        confidence = ""

    evidence = str(entry.get("evidence", "") or "").strip()
    if len(evidence) < MIN_EVIDENCE_CHARS:
        problems.append(
            f"{where} ({submission}): evidence is {len(evidence)} characters. Every "
            "decision must record why, specifically enough for a reader to check it. "
            "An unexplained decision looks authoritative in the output table and is "
            "not."
        )

    return DeviceDecision(
        submission_number=submission,
        device=str(entry.get("device", "") or "").strip(),
        product_code=str(entry.get("product_code", "") or "").strip().upper(),
        decision=decision,
        category=category,
        confidence=confidence,
        evidence=evidence,
        source=source,
    )


def load_adjudication(config_dir: str | Path) -> AdjudicationSet:
    """Read and merge every fragment in ``config/adjudication/``.

    Args:
        config_dir: The configuration directory holding ``adjudication/``.

    Returns:
        The merged set. An empty set when the directory does not exist, so the
        pipeline still runs on a code-level rule alone.

    Raises:
        AdjudicationError: A fragment is unreadable, an entry fails a check, or
            two fragments claim the same submission number. The message lists
            every problem at once.
    """
    directory = Path(config_dir) / ADJUDICATION_DIRNAME
    if not directory.is_dir():
        return AdjudicationSet({}, frozenset(), {}, {}, directory)

    problems: list[str] = []
    decisions: dict[str, DeviceDecision] = {}
    codes: set[str] = set()
    fragments: dict[str, str] = {}
    versions: dict[str, int] = {}
    raw: dict[str, Any] = {}

    for path in sorted(directory.glob("*.yaml")):
        source = path.name
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as error:
            problems.append(f"{source}: not valid YAML -- {error}")
            continue
        if not isinstance(data, dict):
            problems.append(f"{source}: top level is not a mapping")
            continue

        fragments[source] = _digest(path)
        raw[source] = data

        version = data.get("version")
        if not isinstance(version, int) or version < 1:
            problems.append(f"{source}: version must be an integer >= 1, got {version!r}")
        else:
            versions[source] = version

        for code in data.get("codes") or []:
            codes.add(str(code).strip().upper())

        entries = data.get("adjudicated")
        if not isinstance(entries, list):
            problems.append(f"{source}: `adjudicated` must be a list")
            continue

        declared = data.get("n_devices")
        if isinstance(declared, int) and declared != len(entries):
            problems.append(
                f"{source}: declares n_devices: {declared} but carries {len(entries)} "
                "entries. The count is there to catch a truncated file; fix whichever "
                "is wrong."
            )

        for index, entry in enumerate(entries):
            decision = _check_entry(entry, index, source, problems)
            if decision is None:
                continue
            existing = decisions.get(decision.submission_number)
            if existing is not None:
                problems.append(
                    f"{decision.submission_number} is adjudicated twice: "
                    f"{existing.source} says {existing.decision!r}, {source} says "
                    f"{decision.decision!r}. One device, one decision -- split the "
                    "fragments by product code so they cannot overlap."
                )
                continue
            decisions[decision.submission_number] = decision

    if problems:
        raise AdjudicationError(
            f"{directory}: {len(problems)} problem(s)\n  - " + "\n  - ".join(problems)
        )

    return AdjudicationSet(
        decisions=decisions,
        codes=frozenset(codes),
        fragments=fragments,
        versions=versions,
        directory=directory,
        raw=raw,
    )


def provenance(adjudication: AdjudicationSet) -> dict[str, Any]:
    """The adjudication block a run manifest carries."""
    return {
        "directory": str(adjudication.directory),
        "fragments": adjudication.fragments,
        "versions": adjudication.versions,
        "codes_covered": sorted(adjudication.codes),
        "n_devices": len(adjudication.decisions),
        "decisions": adjudication.counts(),
        "counted_by_category": adjudication.counts_by_category(),
    }
