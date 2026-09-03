"""Load and validate ``config/source.yaml`` and ``config/oncology_codes.yaml``.

``source.yaml`` says where the device records come from and what a run may
assume about their shape. ``oncology_codes.yaml`` says which FDA product codes
count as cancer-directed, and records FDA's own words next to each decision.
Neither is read anywhere else in the package: no URL, no product code, and no
category name is hard-coded outside this module's constants.

A malformed file raises :class:`ConfigError` listing every problem found, not
the first, so the file is fixed once rather than once per run. Both files are
digested as read, and the digest travels into the run manifest, because the
version field alone cannot prove which content a figure was built from.

Nothing here touches the network, and nothing here writes.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import yaml

#: The two domains the figure splits on. Frozen: ``authorizations.csv``
#: declares ``domain`` over exactly these values and the plotting code assigns a
#: fixed hue to each (radiology blue, pathology pink, per figures/AGENTS.md).
VALID_DOMAINS: Final[frozenset[str]] = frozenset({"radiology", "pathology"})

#: Category keys, in figure order. Frozen for the same reason: another agent is
#: drawing against this exact set, so a renamed category must fail the load
#: rather than silently empty a series.
CATEGORY_KEYS: Final[tuple[str, ...]] = (
    "radiology_cancer_detection",
    "radiology_radiation_therapy",
    "pathology",
)

#: Confidence tiers a code may carry. Only ``oncology`` enters the figure;
#: ``indeterminate`` is the reason the published count is a floor.
VALID_TIERS: Final[frozenset[str]] = frozenset({"oncology", "indeterminate"})

#: Marketing pathway labels. Frozen: ``authorizations.csv`` declares ``pathway``
#: over exactly these three.
PATHWAY_LABELS: Final[frozenset[str]] = frozenset({"510(k)", "De Novo", "PMA"})

#: The groups ``excluded:`` may declare. Each becomes an exclusion reason in the
#: run manifest, so adding a group here is a schema change, not a config edit.
EXCLUSION_GROUPS: Final[tuple[str, ...]] = ("not_oncology", "indeterminate")

#: An FDA product code is three letters. Checked because a lowercase or
#: whitespace-padded code in the config silently matches nothing, and a rule
#: that matches nothing is indistinguishable from a code with no devices.
_CODE_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Z]{3}$")

# openFDA's anonymous limits are 240 requests/minute and 1,000/day. The ceilings
# below sit under them with room to spare; a config asking for more is a bug in
# the config, not a throttle to be discovered at runtime.
MAX_BATCH_SIZE: Final[int] = 100
MAX_REQUESTS_PER_SECOND: Final[int] = 4


class ConfigError(ValueError):
    """Raised when a configuration file is missing, malformed, or unusable.

    The message names the file and lists every problem found, one per line.
    """


# --------------------------------------------------------------------------
# source.yaml
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DeviceListSource:
    """Where the FDA AI-enabled device list is published and what it must hold.

    Attributes:
        name: Human-readable source name, for the manifest and the citation.
        landing_page: The page the file is published from. Recorded, not fetched.
        csv_url: The media URL the pipeline downloads. It is stable across
            republications, which is why a run snapshots rather than streams.
        alternate_urls: Other serialisations of the same list, recorded so a
            reader knows they exist.
        scope_note: FDA's own statement of what the list is. It bounds every
            claim the figure can make.
        required_columns: Columns the parser insists on, exactly, after the
            tolerated ones are dropped.
        tolerated_columns: Columns dropped when present and never required.
    """

    name: str
    landing_page: str
    csv_url: str
    alternate_urls: dict[str, str]
    scope_note: str
    required_columns: tuple[str, ...]
    tolerated_columns: tuple[str, ...]


@dataclass(frozen=True)
class ClassificationLookup:
    """openFDA device-classification endpoint settings.

    Attributes:
        name: Human-readable source name.
        endpoint: The JSON endpoint. No API key is used or wanted.
        batch_size: Product codes per ``search=product_code:(...)`` query.
        requests_per_second: Ceiling the client throttles itself to.
        fields: Fields kept from each record; the rest of the response is
            discarded downstream. The raw response is still snapshotted whole.
    """

    name: str
    endpoint: str
    batch_size: int
    requests_per_second: int
    fields: tuple[str, ...]


@dataclass(frozen=True)
class SourceConfig:
    """A validated ``source.yaml``.

    Attributes:
        version: Bumped by hand on every content change and recorded in every
            manifest, so a table can be traced to the source definition that
            produced it.
        device_list: The FDA list.
        classification_lookup: The openFDA lookup.
        pathways: Submission-number prefix to marketing pathway, longest prefix
            first so ``DEN`` is tested before ``D``-anything.
        expected: The counts measured at design time. Recorded for drift, never
            asserted: the list legitimately grows.
        path: Where the config was read from.
        sha256: Digest of the file as read.
        raw: The parsed YAML, unmodified.
    """

    version: int
    device_list: DeviceListSource
    classification_lookup: ClassificationLookup
    pathways: tuple[tuple[str, str], ...]
    expected: dict[str, Any]
    path: Path
    sha256: str
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def pathway_of(self, submission_number: str) -> str | None:
        """Return the marketing pathway a submission number's prefix implies.

        FDA publishes no pathway column, but the prefix is unambiguous: ``DEN``
        is a De Novo, ``K`` a 510(k), ``P`` a PMA. Supplements keep their parent
        prefix (``P140011/S008`` is a PMA), so the test is on the prefix alone.

        Returns ``None`` for a number matching no configured prefix, which the
        caller must treat as an exclusion rather than as a default.
        """
        candidate = submission_number.strip().upper()
        for prefix, label in self.pathways:
            if candidate.startswith(prefix):
                return label
        return None


# --------------------------------------------------------------------------
# oncology_codes.yaml
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CodeAssignment:
    """One product code's oncology classification, as the rule will apply it.

    Attributes:
        code: The three-letter FDA product code.
        category: Which of :data:`CATEGORY_KEYS` it belongs to.
        domain: ``radiology`` or ``pathology``.
        tier: ``oncology``; a code in a category is by construction certain.
        regulation_number: The regulation the config records for this code, or
            ``None`` where openFDA returns none. This, not the live lookup, is
            what reaches ``authorizations.csv`` -- see :mod:`clinops.classify`.
        device_name: FDA's device-type name, as recorded in the config.
        definition: The abridged FDA definition and the reason for the call.
        overridden: True when an ``overrides:`` entry supplied the domain and
            tier because the openFDA record does not describe the device that
            was authorized under the code.
        override_reason: Why the lookup cannot be trusted for this code.
    """

    code: str
    category: str
    domain: str
    tier: str
    regulation_number: str | None
    device_name: str
    definition: str
    overridden: bool = False
    override_reason: str = ""


@dataclass(frozen=True)
class Category:
    """One figure category and the codes that constitute it.

    Attributes:
        key: One of :data:`CATEGORY_KEYS`.
        label: Display string for figure axes.
        domain: ``radiology`` or ``pathology``.
        tier: ``oncology``.
        codes: The code assignments, in file order.
        notes: Why this category exists and what its inclusion costs.
    """

    key: str
    label: str
    domain: str
    tier: str
    codes: tuple[CodeAssignment, ...]
    notes: str


@dataclass(frozen=True)
class ExcludedCode:
    """One code deliberately left out of the figure, with its reason.

    Attributes:
        code: The product code.
        group: Which of :data:`EXCLUSION_GROUPS` it was excluded under.
        n: Devices the config observed under this code, at the version it was
            written against. Recorded for drift; never asserted.
        why: The reason, in the config author's words.
    """

    code: str
    group: str
    n: int
    why: str


@dataclass(frozen=True)
class OncologyCodes:
    """A validated ``oncology_codes.yaml``.

    Attributes:
        version: Bumped by hand on every content change.
        categories: Category key to :class:`Category`, in :data:`CATEGORY_KEYS`
            order.
        assignments: Product code to :class:`CodeAssignment`, overrides already
            applied. This is the whole oncology rule, flattened.
        excluded: Product code to :class:`ExcludedCode`.
        exclusion_reasons: Group name to the reason the config gives for it.
        path: Where the config was read from.
        sha256: Digest of the file as read.
        raw: The parsed YAML, unmodified.
    """

    version: int
    categories: dict[str, Category]
    assignments: dict[str, CodeAssignment]
    excluded: dict[str, ExcludedCode]
    exclusion_reasons: dict[str, str]
    path: Path
    sha256: str
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def overridden_codes(self) -> tuple[str, ...]:
        """Codes whose classification came from ``overrides:``, sorted."""
        return tuple(sorted(c for c, a in self.assignments.items() if a.overridden))

    def domain_of(self, category: str) -> str:
        """Return the domain a category belongs to."""
        return self.categories[category].domain


# --------------------------------------------------------------------------
# Field helpers. Each appends to ``problems`` and returns ``None`` on failure,
# so a caller collects every fault in one pass instead of stopping at the first.
# --------------------------------------------------------------------------


def _require_str(
    mapping: dict[str, Any], key: str, field_name: str, problems: list[str]
) -> str | None:
    """Pull a non-empty string out of a mapping."""
    if key not in mapping:
        problems.append(f"{field_name}: missing.")
        return None
    value = mapping[key]
    if not isinstance(value, str) or not value.strip():
        problems.append(f"{field_name}: expected a non-empty string, got {value!r}.")
        return None
    return value.strip()


def _require_int(
    mapping: dict[str, Any],
    key: str,
    field_name: str,
    problems: list[str],
    *,
    minimum: int,
    maximum: int,
) -> int | None:
    """Pull a bounded integer out of a mapping."""
    if key not in mapping:
        problems.append(f"{field_name}: missing.")
        return None
    value = mapping[key]
    if isinstance(value, bool) or not isinstance(value, int):
        problems.append(f"{field_name}: expected an integer, got {value!r}.")
        return None
    if not minimum <= value <= maximum:
        problems.append(f"{field_name}: {value} is outside {minimum}-{maximum}.")
        return None
    return value


def _require_str_list(
    mapping: dict[str, Any],
    key: str,
    field_name: str,
    problems: list[str],
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    """Pull a list of non-empty strings out of a mapping."""
    if key not in mapping:
        if not allow_empty:
            problems.append(f"{field_name}: missing.")
        return ()
    value = mapping[key]
    if value is None and allow_empty:
        return ()
    if not isinstance(value, list):
        problems.append(f"{field_name}: expected a list, got {type(value).__name__}.")
        return ()
    if not value and not allow_empty:
        problems.append(f"{field_name}: empty. It must name at least one entry.")
        return ()
    items: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            problems.append(
                f"{field_name}[{index}]: expected a non-empty string, got {item!r}."
            )
            continue
        items.append(item.strip())
    duplicates = sorted({item for item in items if items.count(item) > 1})
    if duplicates:
        problems.append(f"{field_name}: repeated entr(ies) {', '.join(duplicates)}.")
    return tuple(items)


def _read_yaml_mapping(path: Path) -> tuple[dict[str, Any], str]:
    """Read a YAML file, returning its top-level mapping and its SHA-256.

    Raises:
        ConfigError: The file is missing, unreadable, not valid YAML, empty, or
            not a mapping. These are fatal before any field check can run.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigError(f"Config file not found: {path}") from exc
    except OSError as exc:
        raise ConfigError(f"Cannot read config file {path}: {exc}") from exc

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path} is not valid YAML: {exc}") from exc

    if data is None:
        raise ConfigError(f"{path} is empty.")
    if not isinstance(data, dict):
        raise ConfigError(
            f"{path}: top level must be a mapping of keys, got {type(data).__name__}."
        )
    return data, hashlib.sha256(text.encode("utf-8")).hexdigest()


def _raise_if_problems(path: Path, problems: list[str]) -> None:
    """Raise one :class:`ConfigError` listing every problem, or return."""
    if problems:
        raise ConfigError(
            f"{path} is not usable. {len(problems)} problem(s):\n  - "
            + "\n  - ".join(problems)
        )


# --------------------------------------------------------------------------
# Loaders
# --------------------------------------------------------------------------


def load_source_config(path: str | Path) -> SourceConfig:
    """Read and validate ``source.yaml``.

    Args:
        path: Path to the file.

    Returns:
        The validated source definition.

    Raises:
        ConfigError: The file is unreadable or fails any check. The message
            lists every problem at once.
    """
    path = Path(path)
    data, sha256 = _read_yaml_mapping(path)
    problems: list[str] = []

    version = _require_int(data, "version", "version", problems, minimum=1, maximum=10_000)

    # -- device_list -------------------------------------------------------
    device_list = None
    block = data.get("device_list")
    if block is None:
        problems.append("device_list: missing.")
    elif not isinstance(block, dict):
        problems.append(f"device_list: expected a mapping, got {type(block).__name__}.")
    else:
        name = _require_str(block, "name", "device_list.name", problems)
        landing = _require_str(block, "landing_page", "device_list.landing_page", problems)
        csv_url = _require_str(block, "csv_url", "device_list.csv_url", problems)
        if csv_url is not None and not csv_url.startswith("https://"):
            problems.append(
                f"device_list.csv_url: {csv_url!r} is not an https URL. The FDA list is "
                "fetched over TLS; a plain-http URL is a typo or a downgrade."
            )
        scope = _require_str(block, "scope_note", "device_list.scope_note", problems)
        required = _require_str_list(
            block, "required_columns", "device_list.required_columns", problems
        )
        tolerated = _require_str_list(
            block, "tolerated_columns", "device_list.tolerated_columns", problems,
            allow_empty=True,
        )
        overlap = sorted(set(required) & set(tolerated))
        if overlap:
            problems.append(
                "device_list: column(s) "
                + ", ".join(repr(item) for item in overlap)
                + " are listed as both required and tolerated. A tolerated column is "
                "dropped before the required set is checked, so such a column can "
                "never be satisfied. Remove it from one list."
            )
        alternates_raw = block.get("alternate_urls") or {}
        alternates: dict[str, str] = {}
        if not isinstance(alternates_raw, dict):
            problems.append(
                f"device_list.alternate_urls: expected a mapping, got "
                f"{type(alternates_raw).__name__}."
            )
        else:
            for key, value in alternates_raw.items():
                if not isinstance(value, str) or not value.strip():
                    problems.append(
                        f"device_list.alternate_urls.{key}: expected a URL, got {value!r}."
                    )
                    continue
                alternates[str(key)] = value.strip()
        if None not in (name, landing, csv_url, scope) and required:
            device_list = DeviceListSource(
                name=name,  # type: ignore[arg-type]
                landing_page=landing,  # type: ignore[arg-type]
                csv_url=csv_url,  # type: ignore[arg-type]
                alternate_urls=alternates,
                scope_note=scope,  # type: ignore[arg-type]
                required_columns=required,
                tolerated_columns=tolerated,
            )

    # -- classification_lookup --------------------------------------------
    lookup = None
    block = data.get("classification_lookup")
    if block is None:
        problems.append("classification_lookup: missing.")
    elif not isinstance(block, dict):
        problems.append(
            f"classification_lookup: expected a mapping, got {type(block).__name__}."
        )
    else:
        name = _require_str(block, "name", "classification_lookup.name", problems)
        endpoint = _require_str(block, "endpoint", "classification_lookup.endpoint", problems)
        if endpoint is not None and not endpoint.startswith("https://"):
            problems.append(
                f"classification_lookup.endpoint: {endpoint!r} is not an https URL."
            )
        batch_size = _require_int(
            block, "batch_size", "classification_lookup.batch_size", problems,
            minimum=1, maximum=MAX_BATCH_SIZE,
        )
        rps = _require_int(
            block, "requests_per_second", "classification_lookup.requests_per_second",
            problems, minimum=1, maximum=MAX_REQUESTS_PER_SECOND,
        )
        fields = _require_str_list(
            block, "fields", "classification_lookup.fields", problems
        )
        if "product_code" not in fields:
            problems.append(
                "classification_lookup.fields: must include 'product_code'. It is the "
                "join key; without it a record cannot be matched to a device row."
            )
        if None not in (name, endpoint, batch_size, rps) and fields:
            lookup = ClassificationLookup(
                name=name,  # type: ignore[arg-type]
                endpoint=endpoint,  # type: ignore[arg-type]
                batch_size=batch_size,  # type: ignore[arg-type]
                requests_per_second=rps,  # type: ignore[arg-type]
                fields=fields,
            )

    # -- pathways ----------------------------------------------------------
    pathways: list[tuple[str, str]] = []
    block = data.get("pathways")
    if block is None:
        problems.append("pathways: missing.")
    elif not isinstance(block, list) or not block:
        problems.append("pathways: expected a non-empty list of prefix/label mappings.")
    else:
        seen_prefixes: set[str] = set()
        for index, entry in enumerate(block):
            if not isinstance(entry, dict):
                problems.append(
                    f"pathways[{index}]: expected a mapping, got {type(entry).__name__}."
                )
                continue
            prefix = _require_str(entry, "prefix", f"pathways[{index}].prefix", problems)
            label = _require_str(entry, "label", f"pathways[{index}].label", problems)
            if prefix is not None and prefix != prefix.upper():
                problems.append(
                    f"pathways[{index}].prefix: {prefix!r} must be uppercase. Submission "
                    "numbers are upper-cased before the prefix test."
                )
            if prefix is not None and prefix in seen_prefixes:
                problems.append(f"pathways[{index}].prefix: {prefix!r} is declared twice.")
            if label is not None and label not in PATHWAY_LABELS:
                problems.append(
                    f"pathways[{index}].label: {label!r} is not one of "
                    f"{', '.join(sorted(PATHWAY_LABELS))}. authorizations.csv declares "
                    "`pathway` over exactly those three and the figure is drawn against "
                    "them; a new label needs a schema change, not a config edit."
                )
            if prefix is not None and label is not None:
                seen_prefixes.add(prefix)
                pathways.append((prefix, label))

    # Longest prefix first, so a future one-letter prefix cannot shadow a
    # three-letter one that starts with the same character.
    pathways.sort(key=lambda item: (-len(item[0]), item[0]))

    expected = data.get("expected") or {}
    if not isinstance(expected, dict):
        problems.append(f"expected: expected a mapping, got {type(expected).__name__}.")
        expected = {}

    _raise_if_problems(path, problems)
    assert version is not None and device_list is not None and lookup is not None
    return SourceConfig(
        version=version,
        device_list=device_list,
        classification_lookup=lookup,
        pathways=tuple(pathways),
        expected=expected,
        path=path,
        sha256=sha256,
        raw=data,
    )


def _load_overrides(data: dict[str, Any], problems: list[str]) -> dict[str, dict[str, str]]:
    """Validate the ``overrides:`` block and return it keyed by product code."""
    block = data.get("overrides") or {}
    if not isinstance(block, dict):
        problems.append(f"overrides: expected a mapping, got {type(block).__name__}.")
        return {}
    overrides: dict[str, dict[str, str]] = {}
    for code, entry in block.items():
        code = str(code)
        if not _CODE_PATTERN.match(code):
            problems.append(
                f"overrides.{code}: {code!r} is not a three-letter uppercase FDA product "
                "code. A malformed code matches no device and fails silently."
            )
            continue
        if not isinstance(entry, dict):
            problems.append(
                f"overrides.{code}: expected a mapping, got {type(entry).__name__}."
            )
            continue
        domain = _require_str(entry, "domain", f"overrides.{code}.domain", problems)
        tier = _require_str(entry, "tier", f"overrides.{code}.tier", problems)
        reason = _require_str(entry, "reason", f"overrides.{code}.reason", problems)
        if domain is not None and domain not in VALID_DOMAINS:
            problems.append(
                f"overrides.{code}.domain: {domain!r} is not one of "
                f"{', '.join(sorted(VALID_DOMAINS))}."
            )
        if tier is not None and tier not in VALID_TIERS:
            problems.append(
                f"overrides.{code}.tier: {tier!r} is not one of "
                f"{', '.join(sorted(VALID_TIERS))}."
            )
        if None not in (domain, tier, reason):
            overrides[code] = {"domain": domain, "tier": tier, "reason": reason}  # type: ignore[dict-item]
    return overrides


def _load_categories(
    data: dict[str, Any], overrides: dict[str, dict[str, str]], problems: list[str]
) -> tuple[dict[str, Category], dict[str, CodeAssignment]]:
    """Validate ``categories:`` and flatten it into per-code assignments."""
    block = data.get("categories")
    if block is None:
        problems.append("categories: missing.")
        return {}, {}
    if not isinstance(block, dict):
        problems.append(f"categories: expected a mapping, got {type(block).__name__}.")
        return {}, {}

    declared = tuple(block)
    missing = [key for key in CATEGORY_KEYS if key not in declared]
    unexpected = [key for key in declared if key not in CATEGORY_KEYS]
    if missing or unexpected:
        problems.append(
            "categories: the figure schema is frozen at "
            f"{', '.join(CATEGORY_KEYS)}."
            + (f" Missing: {', '.join(missing)}." if missing else "")
            + (f" Unexpected: {', '.join(unexpected)}." if unexpected else "")
            + " authorizations.csv declares `category` over exactly those keys and the "
            "plotting code indexes on them, so a rename here empties a series without "
            "an error. Change clinops.config.CATEGORY_KEYS and the figure together."
        )

    categories: dict[str, Category] = {}
    assignments: dict[str, CodeAssignment] = {}
    for key in CATEGORY_KEYS:
        entry = block.get(key)
        if entry is None:
            continue
        if not isinstance(entry, dict):
            problems.append(
                f"categories.{key}: expected a mapping, got {type(entry).__name__}."
            )
            continue
        label = _require_str(entry, "label", f"categories.{key}.label", problems)
        domain = _require_str(entry, "domain", f"categories.{key}.domain", problems)
        tier = _require_str(entry, "tier", f"categories.{key}.tier", problems)
        notes = entry.get("notes") or ""
        if domain is not None and domain not in VALID_DOMAINS:
            problems.append(
                f"categories.{key}.domain: {domain!r} is not one of "
                f"{', '.join(sorted(VALID_DOMAINS))}."
            )
        if tier is not None and tier != "oncology":
            problems.append(
                f"categories.{key}.tier: {tier!r}. A category is what the figure counts, "
                "so every category is tier 'oncology'. An indeterminate code belongs "
                "under `excluded:`, where its reason is recorded."
            )
        codes_raw = entry.get("codes")
        if not isinstance(codes_raw, list) or not codes_raw:
            problems.append(f"categories.{key}.codes: expected a non-empty list.")
            codes_raw = []

        code_entries: list[CodeAssignment] = []
        for index, item in enumerate(codes_raw):
            where = f"categories.{key}.codes[{index}]"
            if not isinstance(item, dict):
                problems.append(f"{where}: expected a mapping, got {type(item).__name__}.")
                continue
            code = _require_str(item, "code", f"{where}.code", problems)
            if code is None:
                continue
            if not _CODE_PATTERN.match(code):
                problems.append(
                    f"{where}.code: {code!r} is not a three-letter uppercase FDA product "
                    "code. A malformed code matches no device and fails silently."
                )
                continue
            if code in assignments:
                problems.append(
                    f"{where}.code: {code} is already assigned to category "
                    f"{assignments[code].category!r}. A code belongs to exactly one "
                    "category, or a device would be counted twice."
                )
                continue
            regulation = item.get("regulation_number")
            if regulation is not None and not isinstance(regulation, str):
                problems.append(
                    f"{where}.regulation_number: expected a quoted string or null, got "
                    f"{regulation!r}. Unquoted, YAML reads 892.2090 as a float and drops "
                    "a digit."
                )
                regulation = None
            device_name = _require_str(item, "device_name", f"{where}.device_name", problems)
            definition = _require_str(item, "definition", f"{where}.definition", problems)
            override = overrides.get(code)
            code_entries.append(
                CodeAssignment(
                    code=code,
                    category=key,
                    domain=(override or {}).get("domain") or domain or "",
                    tier=(override or {}).get("tier") or tier or "",
                    regulation_number=regulation.strip() if isinstance(regulation, str) else None,
                    device_name=device_name or "",
                    definition=definition or "",
                    overridden=override is not None,
                    override_reason=(override or {}).get("reason", ""),
                )
            )
            assignments[code] = code_entries[-1]

        if None in (label, domain, tier):
            continue
        categories[key] = Category(
            key=key,
            label=label,  # type: ignore[arg-type]
            domain=domain,  # type: ignore[arg-type]
            tier=tier,  # type: ignore[arg-type]
            codes=tuple(code_entries),
            notes=str(notes).strip(),
        )

    # An override that names no listed code is dead config: it will never fire,
    # and the reader who wrote it believes a device is being reclassified.
    for code in overrides:
        if code not in assignments:
            problems.append(
                f"overrides.{code}: no category lists code {code}, so the override can "
                "never apply. Add the code to a category, or delete the override."
            )
    # An override restates its category's domain rather than contradicting it.
    # That is not redundancy: the override's job is to record that the openFDA
    # lookup does not describe the device authorized under this code, so the
    # classification is asserted from the device's identity instead. Stating a
    # *different* domain, however, would put a code in a category whose domain
    # it does not share, and `cumulative_by_year.csv` reads one domain per
    # category. Such a code belongs in a different category, not in an override.
    for code, override in overrides.items():
        assignment = assignments.get(code)
        if assignment is None:
            continue
        category = categories.get(assignment.category)
        if category is not None and override["domain"] != category.domain:
            problems.append(
                f"overrides.{code}: domain {override['domain']!r} contradicts category "
                f"{assignment.category!r}, which is {category.domain!r}. A category maps "
                "to exactly one domain in the output tables. Move the code to a category "
                "of the domain you want, or fix the override."
            )
    return categories, assignments


def _load_excluded(
    data: dict[str, Any], assignments: dict[str, CodeAssignment], problems: list[str]
) -> tuple[dict[str, ExcludedCode], dict[str, str]]:
    """Validate ``excluded:`` and return it keyed by product code."""
    block = data.get("excluded")
    if block is None:
        problems.append(
            "excluded: missing. The exclusion lists are what make the rule auditable; "
            "without them a reader cannot find the code they would have counted."
        )
        return {}, {}
    if not isinstance(block, dict):
        problems.append(f"excluded: expected a mapping, got {type(block).__name__}.")
        return {}, {}

    unexpected = [key for key in block if key not in EXCLUSION_GROUPS]
    if unexpected:
        problems.append(
            f"excluded: unknown group(s) {', '.join(unexpected)}. Each group becomes an "
            f"exclusion reason in the run manifest, so the set is frozen at "
            f"{', '.join(EXCLUSION_GROUPS)}. Adding one is a schema change."
        )

    excluded: dict[str, ExcludedCode] = {}
    reasons: dict[str, str] = {}
    for group in EXCLUSION_GROUPS:
        entry = block.get(group)
        if entry is None:
            problems.append(f"excluded.{group}: missing.")
            continue
        if not isinstance(entry, dict):
            problems.append(
                f"excluded.{group}: expected a mapping, got {type(entry).__name__}."
            )
            continue
        reason = _require_str(entry, "reason", f"excluded.{group}.reason", problems)
        reasons[group] = reason or ""
        codes_raw = entry.get("codes")
        if not isinstance(codes_raw, list) or not codes_raw:
            problems.append(f"excluded.{group}.codes: expected a non-empty list.")
            continue
        for index, item in enumerate(codes_raw):
            where = f"excluded.{group}.codes[{index}]"
            if not isinstance(item, dict):
                problems.append(f"{where}: expected a mapping, got {type(item).__name__}.")
                continue
            code = _require_str(item, "code", f"{where}.code", problems)
            if code is None:
                continue
            if not _CODE_PATTERN.match(code):
                problems.append(f"{where}.code: {code!r} is not a three-letter code.")
                continue
            if code in assignments:
                problems.append(
                    f"{where}.code: {code} is also listed under category "
                    f"{assignments[code].category!r}. A code is counted or excluded, "
                    "never both."
                )
                continue
            if code in excluded:
                problems.append(
                    f"{where}.code: {code} is already excluded under group "
                    f"{excluded[code].group!r}."
                )
                continue
            n = _require_int(item, "n", f"{where}.n", problems, minimum=0, maximum=100_000)
            why = _require_str(item, "why", f"{where}.why", problems)
            excluded[code] = ExcludedCode(
                code=code, group=group, n=n if n is not None else 0, why=why or ""
            )
    return excluded, reasons


def load_oncology_codes(path: str | Path) -> OncologyCodes:
    """Read and validate ``oncology_codes.yaml``.

    The file is the whole oncology rule. Validation is stricter than YAML's
    because every failure mode here is silent: a lowercase product code, a code
    listed in two categories, an override naming a code no category holds. Each
    of those produces a plausible-looking figure with the wrong number in it.

    Args:
        path: Path to the file.

    Returns:
        The validated code dictionary, overrides already folded into
        :attr:`OncologyCodes.assignments`.

    Raises:
        ConfigError: The file is unreadable or fails any check. The message
            lists every problem at once.
    """
    path = Path(path)
    data, sha256 = _read_yaml_mapping(path)
    problems: list[str] = []

    version = _require_int(data, "version", "version", problems, minimum=1, maximum=10_000)
    overrides = _load_overrides(data, problems)
    categories, assignments = _load_categories(data, overrides, problems)
    excluded, reasons = _load_excluded(data, assignments, problems)

    _raise_if_problems(path, problems)
    assert version is not None
    return OncologyCodes(
        version=version,
        categories=categories,
        assignments=assignments,
        excluded=excluded,
        exclusion_reasons=reasons,
        path=path,
        sha256=sha256,
        raw=data,
    )


def load_configs(config_dir: str | Path) -> tuple[SourceConfig, OncologyCodes]:
    """Load both configuration files from a directory.

    Returns:
        ``(source.yaml, oncology_codes.yaml)``, in that order.

    Raises:
        ConfigError: Either file is missing or fails a check.
    """
    config_dir = Path(config_dir)
    return (
        load_source_config(config_dir / "source.yaml"),
        load_oncology_codes(config_dir / "oncology_codes.yaml"),
    )


def config_provenance(source: SourceConfig, codes: OncologyCodes) -> dict[str, Any]:
    """Return the config block every manifest carries.

    Path, version and digest for both files. The digest is the load-bearing
    field: a version can be left unbumped by hand, a SHA-256 cannot.
    """
    return {
        "source": {
            "path": str(source.path),
            "version": source.version,
            "sha256": source.sha256,
        },
        "oncology_codes": {
            "path": str(codes.path),
            "version": codes.version,
            "sha256": codes.sha256,
            "n_categories": len(codes.categories),
            "n_oncology_codes": len(codes.assignments),
            "n_excluded_codes": len(codes.excluded),
            "overrides": list(codes.overridden_codes),
        },
    }
