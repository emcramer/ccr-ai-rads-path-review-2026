"""Assign themes and modalities to parsed PubMed records.

The classifier reads the record table :mod:`trends.parse` writes, matches the
versioned term dictionaries in ``config/`` against each record's title and
abstract, and writes the three tables the figure is drawn from, a provenance
table naming every pattern that fired, a run manifest, and a diagnostic report.

Nothing here is stochastic and nothing here reaches the network. The same
records and the same dictionaries give the same labels, always.

Matcher contract
----------------
Both dictionaries declare the same contract, and it is repeated in
``config/README.md`` and ``docs/classification.md``:

``kind: phrase``
    A literal, matched case-insensitively, word-bounded, and tolerant of the
    amount of whitespace between its words. ``"whole slide"`` matches
    ``"whole  slide"`` and ``"whole\\nslide"``; it does not match
    ``"whole-slide"`` and it does not match ``"whole slides"``.

``kind: regex``
    A Python regular expression, compiled as written and therefore matched
    **case-sensitively**. Opt into case-insensitivity by writing ``(?i)`` at
    position 0 of the pattern; Python rejects a global inline flag anywhere
    else.

``case_sensitive: true|false``
    Optional per-pattern override, and the only extension this module makes to
    the schema in ``config/README.md``. Omitted, it leaves the per-kind default
    above in place. Set on a ``phrase`` it is the readable way to write an
    acronym: ``pattern: "IHC"`` with ``case_sensitive: true`` matches ``IHC``
    and not ``ihc``. Set ``false`` on a ``regex`` it adds ``re.IGNORECASE``.
    Setting it ``true`` on a regex that already carries ``(?i)`` is a
    contradiction and is rejected.

A record carries a category when at least one ``include`` pattern hits and no
``exclude`` pattern hits. Exclusion is record-level and category-level: it
removes that one label from that one record, not the record from the corpus.

Command line
------------
::

    python -m trends.classify \\
        --records data/interim/smoke/records.parquet \\
        --config-dir config \\
        --output data/processed/

Add ``--report`` to print the diagnostic summary as well as writing it.

To ask whether an existing output directory is still current::

    python -m trends.classify --check --output data/processed --config-dir config

That compares the config digests the run recorded against the files on disk and
exits non-zero if they have moved. It answers a question the config version
ledger cannot: the ledger checks a config against its own recorded hash, and so
never notices that a *run* consumed a state which no longer exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import platform
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, Iterable

import pandas as pd
import yaml

from . import aggregate

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Canonical keys
#
# THEME_KEYS, MODALITY_KEYS, and OTHER_MODALITY are declared once, in
# trends.aggregate, which owns the output schema. They are re-exported here so
# a reader of the classifier can see them without chasing an import.
# trends.plotting.style holds a third copy for the drawing code, because the
# plotting package is required to depend on nothing but the three processed
# tables; a test holds the two copies equal.
# --------------------------------------------------------------------------

from .aggregate import (  # noqa: E402
    MINIMUM_MODALITIES,
    MODALITY_KEYS,
    OTHER_MODALITY,
    THEME_KEYS,
)

#: Modalities that make a paper radiological, per the ``domain`` rule in the spec.
RADIOLOGY_MODALITIES: Final[frozenset[str]] = frozenset(
    {"mri", "ct", "pet", "ultrasound", "mammography", "xray", "radiology_report"}
)

#: Modalities that make a paper pathological, per the same rule.
PATHOLOGY_MODALITIES: Final[frozenset[str]] = frozenset(
    {"he_histology", "ihc", "spatial_proteomics", "spatial_transcriptomics", "pathology_report"}
)

#: Modalities that deliberately take no side of the ``domain`` rule.
#:
#: Genomics, clinical data, and ``other`` are data types, not specialties. A
#: paper using MRI and genomics is ``radiology``, not ``both``: the genomics does
#: not make it pathology. Membership here is a positive statement that a modality
#: was considered and placed outside the rule, which is what lets
#: :func:`check_domain_coverage` tell a deliberate omission from an oversight.
NO_DOMAIN_MODALITIES: Final[frozenset[str]] = frozenset(
    {"genomics", "clinical_data", "other"}
)

#: Record-table columns the classifier requires. Written by :mod:`trends.parse`.
REQUIRED_RECORD_COLUMNS: Final[tuple[str, ...]] = (
    "pmid", "title", "abstract", "year", "year_source", "record_type",
)

#: Record types excluded from the analysis corpus, per docs/DECISIONS.md.
EXCLUDED_RECORD_TYPES: Final[frozenset[str]] = frozenset({"PubmedBookArticle"})

#: PubMed publication types that mark a record as secondary literature.
#:
#: The author's ruling, 2026-09-08: "don't include review articles or
#: perspectives, just primary research studies." A record carrying any of these
#: types leaves the corpus.
#:
#: An honest note about how long this took. The exclusion was raised once
#: before: the search-strategy agent's very first report counted 168 retracted
#: papers, 467 editorials, and 379 comments in the corpus and flagged them. That
#: finding was never routed to the author and never decided, so it sat
#: unaddressed until the author asked for the same thing independently. Every
#: count published before 2026-09-08 therefore included reviews, editorials,
#: comments, and retracted papers. The filter exists because it was requested,
#: not because the pipeline caught its own gap.
#:
#: Preprints are NOT here. The author considered them and kept them.
SECONDARY_PUBLICATION_TYPES: Final[frozenset[str]] = frozenset({
    "Review",
    "Systematic Review",
    "Meta-Analysis",
    "Editorial",
    "Comment",
    "Letter",
    "News",
    "Historical Article",
    "Guideline",
    "Practice Guideline",
    "Consensus Development Conference",
    "Published Erratum",
    "Retracted Publication",
    "Scoping Review",
})

#: Modality-dictionary categories that drive an exclusion instead of a figure row.
#:
#: ``non_specialty`` holds the vocabulary of data types belonging to neither
#: radiology nor pathology — endoscopy, dermoscopy, colposcopy, optical coherence
#: tomography, thermography, clinical photography, wearables, ECG and EEG,
#: radiotherapy dosimetry. The author's ruling, 2026-09-08: "limit to modalities
#: that belong to either radiology or pathology."
#:
#: The vocabulary is kept in the dictionary rather than deleted so that the
#: exclusion is auditable, but it is not a figure row: no ``mod_non_specialty``
#: column is written and it never joins a ``modality_set``. See
#: :func:`classify_records` for the rule, which is deliberately conjunctive.
EXCLUSION_CATEGORIES: Final[tuple[str, ...]] = ("non_specialty",)

#: Separator between title and abstract in the text patterns are matched against.
#: Declared in the header of both dictionaries; changing it changes what the
#: anchored ``^(?=...)`` patterns see.
TEXT_SEPARATOR: Final[str] = " \n "

#: Characters of context kept either side of a pattern's first match, so a
#: disputed label can be checked without reopening the abstract.
EXCERPT_CONTEXT: Final[int] = 40

#: File names written into the output directory.
EXCLUSIONS = "exclusions.csv"
PATTERN_HITS = "pattern_hits.csv"
RUN_MANIFEST = "run_manifest.json"
REPORT = "classification_report.txt"

_GLOBAL_FLAGS = re.compile(r"^\(\?([aiLmsux]+)\)")
_WORD = re.compile(r"\w")


class TermDictionaryError(ValueError):
    """A term dictionary is missing, malformed, or will not compile.

    The message names the file and lists every problem found, one per line, so
    the file is fixed once rather than once per run.
    """


class RecordTableError(ValueError):
    """The record table is missing, unreadable, or lacks a required column."""


# --------------------------------------------------------------------------
# Patterns and dictionaries
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Pattern:
    """One compiled include or exclude pattern.

    Attributes:
        category: Key of the category the pattern belongs to.
        role: ``"include"`` or ``"exclude"``.
        index: Position within that list, counting from zero.
        kind: ``"phrase"`` or ``"regex"``.
        source: The pattern exactly as written in the YAML.
        case_sensitive: Whether matching distinguishes case, after the per-kind
            default and any ``case_sensitive`` override.
        regex: The compiled expression actually used.
    """

    category: str
    role: str
    index: int
    kind: str
    source: str
    case_sensitive: bool
    regex: re.Pattern[str]

    @property
    def pattern_id(self) -> str:
        """Stable identifier, e.g. ``ihc:include[1]``, used in provenance rows."""
        return f"{self.category}:{self.role}[{self.index}]"


@dataclass(frozen=True)
class PatternHit:
    """One pattern firing on one record.

    Attributes:
        pattern: The pattern that fired.
        count: How many times it matched in the record's text.
        span: Character offsets of the first match.
        excerpt: The first match with surrounding context, whitespace collapsed.
    """

    pattern: Pattern
    count: int
    span: tuple[int, int]
    excerpt: str


@dataclass(frozen=True)
class CategoryMatch:
    """What one category did to one record.

    ``matched`` is true when at least one include pattern fired and no exclude
    pattern did. Both lists are kept whatever the outcome, so a label that was
    suppressed by an exclude is as checkable as one that was assigned.
    """

    category: str
    matched: bool
    include_hits: tuple[PatternHit, ...]
    exclude_hits: tuple[PatternHit, ...]


@dataclass(frozen=True)
class Category:
    """One category of a term dictionary."""

    key: str
    label: str
    type: str | None
    include: tuple[Pattern, ...]
    exclude: tuple[Pattern, ...]
    notes: str

    @property
    def patterns(self) -> tuple[Pattern, ...]:
        """Include and exclude patterns together, includes first."""
        return self.include + self.exclude


@dataclass(frozen=True)
class TermDictionary:
    """A loaded, compiled term dictionary.

    Attributes:
        kind: ``"themes"`` or ``"modalities"``; used in messages and provenance.
        version: The file's ``version`` field, recorded in the run manifest.
        categories: Category key to :class:`Category`, in YAML order.
        path: Where the file was read from.
        sha256: Digest of the file as read.
    """

    kind: str
    version: int
    categories: dict[str, Category]
    path: Path
    sha256: str

    @property
    def keys(self) -> tuple[str, ...]:
        """Category keys, in the order the file declares them."""
        return tuple(self.categories)

    @property
    def n_patterns(self) -> int:
        """Total include and exclude patterns in the file."""
        return sum(len(category.patterns) for category in self.categories.values())


def _excerpt(text: str, start: int, end: int) -> str:
    """Return the matched text with context either side, whitespace collapsed."""
    left = max(0, start - EXCERPT_CONTEXT)
    right = min(len(text), end + EXCERPT_CONTEXT)
    fragment = re.sub(r"\s+", " ", text[left:right]).strip()
    return ("..." if left > 0 else "") + fragment + ("..." if right < len(text) else "")


def compile_phrase(source: str, *, case_sensitive: bool) -> re.Pattern[str]:
    """Compile a phrase pattern: a word-bounded, whitespace-tolerant literal.

    Words are escaped and joined with ``\\s+``, so the amount and kind of
    whitespace between them does not matter. A boundary is asserted only at an
    end that is itself a word character, so ``510(k)`` and ``H&E`` compile
    correctly where ``\\b`` would misbehave.

    Args:
        source: The literal to match.
        case_sensitive: Whether to distinguish case.

    Returns:
        The compiled expression.

    Raises:
        ValueError: The literal is empty or only whitespace.
    """
    tokens = source.split()
    if not tokens:
        raise ValueError("phrase pattern is empty")
    body = r"\s+".join(re.escape(token) for token in tokens)
    prefix = r"(?<!\w)" if _WORD.match(tokens[0][0]) else ""
    suffix = r"(?!\w)" if _WORD.match(tokens[-1][-1]) else ""
    return re.compile(prefix + body + suffix, 0 if case_sensitive else re.IGNORECASE)


def _has_inline_ignorecase(source: str) -> bool:
    """Say whether a regex opens with a global inline flag group containing ``i``."""
    match = _GLOBAL_FLAGS.match(source)
    return bool(match) and "i" in match.group(1)


def _compile_pattern(
    entry: Any, category: str, role: str, index: int, problems: list[str]
) -> Pattern | None:
    """Compile one dictionary entry, appending a message on any failure."""
    where = f"{category}.{role}[{index}]"
    if not isinstance(entry, dict):
        problems.append(f"{where}: expected a mapping with 'pattern' and 'kind'.")
        return None
    source = entry.get("pattern")
    if not isinstance(source, str) or not source.strip():
        problems.append(f"{where}: 'pattern' must be a non-empty string, got {source!r}.")
        return None
    kind = entry.get("kind", "phrase")
    if kind not in ("phrase", "regex"):
        problems.append(f"{where}: 'kind' must be 'phrase' or 'regex', got {kind!r}.")
        return None
    override = entry.get("case_sensitive")
    if override is not None and not isinstance(override, bool):
        problems.append(f"{where}: 'case_sensitive' must be true or false, got {override!r}.")
        return None
    unknown = sorted(set(entry) - {"pattern", "kind", "case_sensitive", "notes"})
    if unknown:
        problems.append(f"{where}: unknown field(s) {', '.join(unknown)}.")
        return None

    if kind == "phrase":
        case_sensitive = bool(override)
        try:
            compiled = compile_phrase(source, case_sensitive=case_sensitive)
        except ValueError as exc:
            problems.append(f"{where}: {exc}.")
            return None
    else:
        inline = _has_inline_ignorecase(source)
        if override is True and inline:
            problems.append(
                f"{where}: 'case_sensitive: true' contradicts the '(?i)' the pattern "
                "already carries. Remove one of them."
            )
            return None
        case_sensitive = not (inline or override is False)
        try:
            compiled = re.compile(source, 0 if case_sensitive else re.IGNORECASE)
        except re.error as exc:
            problems.append(f"{where}: will not compile as a regex ({exc}): {source!r}.")
            return None

    return Pattern(
        category=category,
        role=role,
        index=index,
        kind=kind,
        source=source,
        case_sensitive=case_sensitive,
        regex=compiled,
    )


def load_term_dictionary(
    path: str | Path,
    *,
    kind: str,
    expected_keys: Iterable[str] | None = None,
    optional_include: Iterable[str] = (),
) -> TermDictionary:
    """Read, validate, and compile one term dictionary.

    Args:
        path: Path to ``themes.yaml`` or ``modalities.yaml``.
        kind: ``"themes"`` or ``"modalities"``, used in messages.
        expected_keys: Category keys the file must declare, no more and no
            fewer. Passing the canonical keys catches a renamed category before
            it silently empties a figure block.
        optional_include: Keys permitted to declare no include patterns. Only
            ``other`` qualifies, because the classifier also assigns it as a
            fallback; it may still carry include patterns, and does. Any other
            category with an empty include list matches nothing, which is a
            mistake worth stopping for.

    Returns:
        The compiled dictionary.

    Raises:
        TermDictionaryError: The file is missing, is not valid YAML, or fails
            any check. The message lists every problem at once.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise TermDictionaryError(f"Term dictionary not found: {path}") from exc
    except OSError as exc:
        raise TermDictionaryError(f"Cannot read {path}: {exc}") from exc

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise TermDictionaryError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise TermDictionaryError(
            f"{path}: top level must be a mapping, got {type(data).__name__}."
        )

    problems: list[str] = []
    version = data.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        problems.append(f"version: expected a positive integer, got {version!r}.")
        version = 0

    raw_categories = data.get("categories")
    categories: dict[str, Category] = {}
    if not isinstance(raw_categories, dict) or not raw_categories:
        problems.append("categories: expected a non-empty mapping.")
        raw_categories = {}

    optional_include = set(optional_include)
    for key, body in raw_categories.items():
        if not isinstance(body, dict):
            problems.append(f"{key}: expected a mapping, got {type(body).__name__}.")
            continue
        label = body.get("label")
        if not isinstance(label, str) or not label.strip():
            problems.append(f"{key}.label: expected a non-empty string, got {label!r}.")
            label = str(key)
        include_raw = body.get("include") or []
        exclude_raw = body.get("exclude") or []
        if not isinstance(include_raw, list) or not isinstance(exclude_raw, list):
            problems.append(f"{key}: 'include' and 'exclude' must be lists.")
            continue
        if not include_raw and key not in optional_include:
            problems.append(
                f"{key}: no include patterns, so the category can never match. "
                "Only 'other' may go without them, because the classifier assigns "
                "it as a fallback as well."
            )
        include = tuple(
            pattern
            for index, entry in enumerate(include_raw)
            if (pattern := _compile_pattern(entry, key, "include", index, problems))
        )
        exclude = tuple(
            pattern
            for index, entry in enumerate(exclude_raw)
            if (pattern := _compile_pattern(entry, key, "exclude", index, problems))
        )
        categories[key] = Category(
            key=key,
            label=label,
            type=body.get("type"),
            include=include,
            exclude=exclude,
            notes=str(body.get("notes") or "").strip(),
        )

    if expected_keys is not None:
        expected = list(expected_keys)
        missing = [key for key in expected if key not in categories]
        extra = [key for key in categories if key not in expected]
        if missing:
            problems.append(f"categories: missing {', '.join(missing)}.")
        if extra:
            problems.append(
                f"categories: {', '.join(extra)} are not canonical keys. "
                "Adding a category means updating four places together: the key table "
                "in docs/figure-spec.md, MODALITY_KEYS/THEME_KEYS in trends.aggregate, "
                "MODALITY_ORDER/THEME_ORDER and the domain sets in "
                "trends.plotting.style, and the fixture dictionaries in "
                "tests/fixtures/. tests/test_classify.py::test_canonical_keys_agree_"
                "everywhere checks all of them."
            )

    if problems:
        raise TermDictionaryError(
            f"{path} is not usable. {len(problems)} problem(s):\n  - "
            + "\n  - ".join(problems)
        )

    return TermDictionary(
        kind=kind,
        version=int(version),
        categories=categories,
        path=path,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def check_domain_coverage(modality_keys: Iterable[str]) -> None:
    """Confirm every named modality is assigned to a domain side.

    The ``domain`` column is derived from three lists in this module: the two
    domain sides, and :data:`NO_DOMAIN_MODALITIES` for data types that belong to
    neither. A modality added to ``config/modalities.yaml`` and to none of them
    would take no side by accident rather than by decision, so its papers would
    read ``none`` and drop off both of Panel B's clinical lines. That is a wrong
    figure rather than a crash, which is worse, so it is checked here and named.

    Raises:
        TermDictionaryError: A modality is in none of the three lists, or in
            more than one.
    """
    unassigned, doubled = [], []
    for key in modality_keys:
        if key in EXCLUSION_CATEGORIES:
            continue  # matched for exclusion, never labelled, so it takes no side
        sides = (
            (key in RADIOLOGY_MODALITIES)
            + (key in PATHOLOGY_MODALITIES)
            + (key in NO_DOMAIN_MODALITIES)
        )
        if sides == 0:
            unassigned.append(key)
        elif sides > 1:
            doubled.append(key)
    problems = []
    if unassigned:
        problems.append(
            f"in none of the three lists: {', '.join(unassigned)}. Put each in "
            "RADIOLOGY_MODALITIES, PATHOLOGY_MODALITIES, or NO_DOMAIN_MODALITIES in "
            "trends.classify, and mirror the choice in trends.plotting.style and in "
            "the domain rule in docs/figure-spec.md. NO_DOMAIN_MODALITIES is the "
            "right home for a data type that is neither radiological nor "
            "pathological, such as genomics or clinical data; putting one in a "
            "domain list to quiet this message would make a genomics paper read as "
            "pathology."
        )
    if doubled:
        problems.append(f"in more than one list: {', '.join(doubled)}.")
    if problems:
        raise TermDictionaryError(
            "The modality dictionary and the domain rule disagree. "
            + " ".join(problems)
        )


def load_dictionaries(config_dir: str | Path) -> tuple[TermDictionary, TermDictionary]:
    """Load ``themes.yaml`` and ``modalities.yaml`` from a configuration directory.

    Returns:
        The theme dictionary and the modality dictionary, in that order.

    Raises:
        TermDictionaryError: Either file is missing or fails a check.
    """
    config_dir = Path(config_dir)
    themes = load_term_dictionary(
        config_dir / "themes.yaml", kind="themes", expected_keys=THEME_KEYS
    )
    modalities = load_term_dictionary(
        config_dir / "modalities.yaml",
        kind="modalities",
        expected_keys=MODALITY_KEYS + EXCLUSION_CATEGORIES,
        optional_include={OTHER_MODALITY},
    )
    check_domain_coverage(modalities.keys)
    return themes, modalities


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------


def record_text(title: Any, abstract: Any) -> str:
    """Join a record's title and abstract into the string patterns see.

    The separator is declared in both dictionaries. It matters: the conjunctive
    patterns are anchored with ``^``, so they read the title and the abstract as
    one string, and a missing abstract still leaves the title matchable.
    """
    title = title if isinstance(title, str) else ""
    abstract = abstract if isinstance(abstract, str) else ""
    return f"{title}{TEXT_SEPARATOR}{abstract}"


def publication_types_of(value: Any) -> set[str]:
    """Return one record's PubMed publication types.

    Reads both shapes the record table comes in: the list that parquet keeps, and
    the ``"; "``-joined string of the CSV twin. A missing value gives an empty
    set rather than raising, because a record with no publication type is
    ordinary, not broken.
    """
    if value is None:
        return set()
    if isinstance(value, str):
        return {part.strip() for part in value.split(";") if part.strip()}
    try:
        return {str(item).strip() for item in value if str(item).strip()}
    except TypeError:
        return set()


def _hits(patterns: Iterable[Pattern], text: str) -> tuple[PatternHit, ...]:
    """Return a hit for every pattern that fires on ``text``."""
    found: list[PatternHit] = []
    for pattern in patterns:
        matches = list(pattern.regex.finditer(text))
        if not matches:
            continue
        first = matches[0]
        found.append(
            PatternHit(
                pattern=pattern,
                count=len(matches),
                span=(first.start(), first.end()),
                excerpt=_excerpt(text, first.start(), first.end()),
            )
        )
    return tuple(found)


def match_text(dictionary: TermDictionary, text: str) -> dict[str, CategoryMatch]:
    """Match one record's text against every category of one dictionary.

    Args:
        dictionary: The compiled dictionary.
        text: Title and abstract joined by :func:`record_text`.

    Returns:
        A mapping from category key to :class:`CategoryMatch`, holding only the
        categories where at least one pattern fired. A category whose include
        patterns fired but whose exclude patterns also fired appears with
        ``matched=False``, which is how a suppressed label stays visible.
    """
    result: dict[str, CategoryMatch] = {}
    for key, category in dictionary.categories.items():
        include_hits = _hits(category.include, text)
        exclude_hits = _hits(category.exclude, text) if include_hits else ()
        if not include_hits and not exclude_hits:
            continue
        result[key] = CategoryMatch(
            category=key,
            matched=bool(include_hits) and not exclude_hits,
            include_hits=include_hits,
            exclude_hits=exclude_hits,
        )
    return result


def derive_domain(modalities: Iterable[str]) -> str:
    """Return ``radiology``, ``pathology``, ``both``, or ``none`` for a modality set.

    The rule is fixed by ``docs/figure-spec.md``: a paper is radiological if it
    carries any of MRI, CT, PET, ultrasound, mammography, radiography, or
    radiology report; pathological
    if it carries any of H&E, IHC, spatial proteomics, spatial transcriptomics,
    or pathology report; ``both`` if each side has a member; ``none`` if it
    carries only ``other``.
    """
    present = set(modalities)
    radiology = bool(present & RADIOLOGY_MODALITIES)
    pathology = bool(present & PATHOLOGY_MODALITIES)
    if radiology and pathology:
        return "both"
    if radiology:
        return "radiology"
    if pathology:
        return "pathology"
    return "none"


# --------------------------------------------------------------------------
# Classifying a record table
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ClassificationResult:
    """Everything one classification run produced.

    Attributes:
        labels: ``paper_labels.csv`` in memory, one row per analysed record.
        hits: One row per record, category, and pattern that fired.
        exclusions: Reason to number of records dropped before classification.
        n_records_in: Rows read from the record table.
        exclusion_detail: Per-reason breakdown where one exists, such as the
            publication types behind ``secondary_publication_type``.
        panel_a_shortfalls: Theme key to the number of primary-research papers
            held out of Panel A's block for carrying fewer modalities than
            :data:`aggregate.MINIMUM_MODALITIES` requires. The label is kept and
            the paper stays in the corpus and in Panel B; only Panel A's view
            excludes it.
        corpus_wide_shortfalls: The same shortfall counted over every retained
            record, reviews included. This is the measure of how far a theme's
            language over-calls, and the number that should fall as the
            vocabulary is tightened. Reported beside the first, never instead
            of it: the two together separate theme over-calling from modality
            under-recall.
        excluded: One row per excluded record and per retracted label — ``pmid``,
            ``reason``, and the scope it applies to — so every removal is
            auditable rather than merely counted.
    """

    labels: pd.DataFrame
    hits: pd.DataFrame
    exclusions: dict[str, int]
    n_records_in: int
    exclusion_detail: dict[str, dict[str, int]] = field(default_factory=dict)
    panel_a_shortfalls: dict[str, int] = field(default_factory=dict)
    corpus_wide_shortfalls: dict[str, int] = field(default_factory=dict)
    excluded: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def n_records_out(self) -> int:
        """Records that reached the retained corpus. Panel B's denominator."""
        return int(len(self.labels))

    @property
    def n_primary_research(self) -> int:
        """Records flagged primary research. Panel A's denominator."""
        if aggregate.PRIMARY_RESEARCH not in self.labels.columns:
            return self.n_records_out
        return int(self.labels[aggregate.PRIMARY_RESEARCH].sum())


def read_records(path: str | Path) -> pd.DataFrame:
    """Read a record table written by :mod:`trends.parse`.

    Parquet and CSV are both accepted, chosen by suffix. Parquet is preferred:
    the CSV twin flattens the list columns and cannot be split back apart.

    Raises:
        RecordTableError: The file is missing, unreadable, or lacks a column
            the classifier needs.
    """
    path = Path(path)
    if not path.exists():
        raise RecordTableError(f"Record table not found: {path}")
    try:
        frame = (
            # ``pmid`` is an identifier, not a number. Left to itself pandas
            # reads a CSV column of digits as float64 and turns 1001 into
            # "1001.0" the moment one row is blank.
            pd.read_csv(path, dtype={"pmid": "string"})
            if path.suffix.lower() == ".csv"
            else pd.read_parquet(path)
        )
    except Exception as exc:  # pragma: no cover - the reader's message is the useful part
        raise RecordTableError(f"{path}: could not be read ({exc})") from exc
    missing = [column for column in REQUIRED_RECORD_COLUMNS if column not in frame.columns]
    if missing:
        raise RecordTableError(
            f"{path}: missing required column(s): {', '.join(missing)}. "
            "The table should be the records.parquet written by trends.parse."
        )
    return frame


def _filter_records(
    frame: pd.DataFrame, year_range: tuple[int, int] | None = None
) -> tuple[pd.DataFrame, dict[str, int], list[dict[str, str]]]:
    """Drop the records that may not enter the corpus at all, and say why.

    Four field-based filters, each explicit and each counted. A fifth,
    ``non_specialty_only``, needs the term dictionaries and so lives in
    :func:`classify_records`. Secondary publication types are NOT dropped here:
    since 2026-09-08 they are flagged rather than removed, because Panel B counts
    them. See :func:`primary_research_flags`.

    1. Book records. ``PubmedBookArticle`` rows are reference works, not primary
       literature; ``docs/DECISIONS.md`` requires the filter to be visible here
       rather than hidden at retrieval.
    2. Records with no PMID. They cannot be identified or de-duplicated.
    3. Records with no publication year. ``paper_labels.csv`` types ``year`` as
       an integer and the figure is a time series, so a yearless record has
       nowhere to go.
    4. Records whose year falls outside the retrieval window. PubMed filtered on
       publication date; our year rule dates a record to its first appearance,
       and the two disagree for a paper posted online before the window and
       issued inside it. Keeping them would make the corpus's first year a biased
       partial year, the mirror of the partial final year. The window comes from
       ``date_range`` in ``corpus.yaml``.

    Returns:
        The surviving records, the count per reason, and one row per dropped
        record naming its reason and the view it applies to.
    """
    exclusions: dict[str, int] = {}
    dropped: list[dict[str, str]] = []
    kept = frame

    def drop(mask: pd.Series, reason: str) -> None:
        """Record and remove the rows a filter rejects."""
        nonlocal kept
        exclusions[reason] = int(mask.sum())
        for pmid in kept.loc[mask, "pmid"].astype("string").fillna(""):
            dropped.append({"pmid": str(pmid), "reason": reason, "applies_to": "corpus"})
        kept = kept.loc[~mask]

    drop(kept["record_type"].astype("string").isin(EXCLUDED_RECORD_TYPES), "book_records")

    pmid = kept["pmid"].astype("string").fillna("").str.strip()
    drop(pmid == "", "missing_pmid")

    year = pd.to_numeric(kept["year"], errors="coerce")
    drop(year.isna(), "missing_year")

    if year_range is not None:
        first, last = year_range
        year = pd.to_numeric(kept["year"], errors="coerce")
        drop((year < first) | (year > last), "outside_date_range")
    else:
        exclusions["outside_date_range"] = 0

    return kept.reset_index(drop=True), exclusions, dropped


def primary_research_flags(frame: pd.DataFrame) -> tuple[pd.Series, dict[str, int]]:
    """Say which records are primary research, and count what is not.

    The author's ruling of 2026-09-08: **Panel A shows primary research; Panel B
    shows engagement.** A record carrying any publication type in
    :data:`SECONDARY_PUBLICATION_TYPES` is flagged 0 and **kept**. It is excluded
    from ``combination_counts.csv``, which asks what data primary research
    actually uses and would be corrupted by a review discussing a modality
    without using one; it is counted in ``theme_year_counts.csv``, which asks how
    attention to a theme moves over time, where a review naming a theme as a
    future direction is exactly that attention.

    Until 2026-09-08 these records were dropped outright, and before that they
    were counted as primary research; neither is true now.

    Returns:
        A boolean Series, True for primary research, and the count of records per
        secondary publication type.
    """
    if "publication_types" not in frame.columns:
        return pd.Series(True, index=frame.index), {}
    types = frame["publication_types"].map(publication_types_of)
    secondary = types.map(lambda found: bool(found & SECONDARY_PUBLICATION_TYPES))
    counter: Counter[str] = Counter()
    for found in types.loc[secondary]:
        counter.update(found & SECONDARY_PUBLICATION_TYPES)
    return ~secondary, dict(counter.most_common())


def classify_records(
    frame: pd.DataFrame,
    themes: TermDictionary,
    modalities: TermDictionary,
    *,
    year_range: tuple[int, int] | None = None,
) -> ClassificationResult:
    """Label every record in a record table.

    The record filters of :func:`_filter_records` run first and are counted.
    Each surviving record is matched against both dictionaries. A record
    matching no theme keeps its theme flags at zero and stays in the corpus.

    ``other`` is additive. A record carries it when an ``other`` include pattern
    matched, when it matched no named modality at all, or both; it may sit
    alongside named modalities, so a paper using MRI and a radiotherapy dose map
    reads as MRI *and* other rather than as MRI alone. The two routes are
    distinguishable afterwards: a pattern assignment leaves ordinary
    ``include`` rows in the provenance table, and a fallback assignment leaves
    one row with ``role = "fallback"``.

    Args:
        frame: The record table, as :func:`read_records` returns it.
        themes: The compiled theme dictionary.
        modalities: The compiled modality dictionary.
        year_range: Inclusive publication-year window; records outside it are
            dropped and counted. ``None`` applies no window.

    Returns:
        The labels, the provenance rows, and the exclusion counts.
    """
    missing = [column for column in REQUIRED_RECORD_COLUMNS if column not in frame.columns]
    if missing:
        raise RecordTableError(
            f"record table missing required column(s): {', '.join(missing)}"
        )
    check_domain_coverage(modalities.keys)
    n_in = int(len(frame))
    kept, exclusions, dropped = _filter_records(frame, year_range)
    is_primary, secondary_detail = primary_research_flags(kept)

    # The label columns come from the dictionaries that were loaded, not from a
    # constant, so a category added to config/*.yaml gets its column with no
    # code change here. Exclusion categories are the exception: they are matched
    # but never labelled, so they get no column and never join a modality set.
    theme_keys = aggregate.order_keys(themes.keys, THEME_KEYS)
    modality_keys = aggregate.order_keys(
        [key for key in modalities.keys if key not in EXCLUSION_CATEGORIES], MODALITY_KEYS
    )
    label_columns = aggregate.paper_label_columns(theme_keys, modality_keys)
    named_set = {key for key in modality_keys if key != OTHER_MODALITY}
    label_rows: list[dict[str, Any]] = []
    hit_rows: list[dict[str, Any]] = []

    for position, row in enumerate(kept.itertuples(index=False)):
        text = record_text(getattr(row, "title", ""), getattr(row, "abstract", ""))
        theme_matches = match_text(themes, text)
        modality_matches = match_text(modalities, text)

        assigned_themes = {key for key, match in theme_matches.items() if match.matched}
        matched_modalities = {
            key for key, match in modality_matches.items() if match.matched
        }
        assigned_modalities = matched_modalities & named_set
        # `other` is additive: an include pattern of its own, or nothing named
        # matching, or both. The fallback is what keeps every paper in exactly
        # one column of Panel A.
        other_by_pattern = OTHER_MODALITY in matched_modalities
        other_by_fallback = not assigned_modalities
        if other_by_pattern or other_by_fallback:
            assigned_modalities = assigned_modalities | {OTHER_MODALITY}

        domain = derive_domain(assigned_modalities)
        # A record whose only imaging evidence is a data type outside both
        # specialties leaves the corpus, and leaves it for BOTH panels: this is
        # about the review's scope, not about article type.
        #
        # The rule is conjunctive on purpose. A colonoscopy paper that also reads
        # CT keeps its CT label and stays; excluding on the non-specialty match
        # alone would throw away genuine multimodal work.
        #
        # That produces an asymmetry worth stating plainly rather than leaving a
        # reader to find it: a paper labelled only `genomics` stays, while the
        # same paper plus an endoscopy mention leaves. It is deliberate, and it
        # follows the principle this pipeline already uses for the `other`
        # fallback — drop what we have positive evidence belongs elsewhere, keep
        # what we merely cannot classify. The broader alternative, dropping every
        # paper whose domain is `none`, would remove 7,737 records and is a much
        # larger decision than the author made. Coordinator's ruling, 2026-09-08.
        if domain == "none" and matched_modalities & set(EXCLUSION_CATEGORIES):
            dropped.append({
                "pmid": str(row.pmid).strip(),
                "reason": "non_specialty_only",
                "applies_to": "corpus",
            })
            continue

        pmid = str(row.pmid).strip()
        label: dict[str, Any] = {
            "pmid": pmid,
            "year": int(row.year),
            "year_source": str(getattr(row, "year_source", "") or ""),
        }
        for key in theme_keys:
            label[f"theme_{key}"] = int(key in assigned_themes)
        for key in modality_keys:
            label[f"mod_{key}"] = int(key in assigned_modalities)
        label["domain"] = domain
        label[aggregate.PRIMARY_RESEARCH] = int(bool(is_primary.iloc[position]))
        label_rows.append(label)

        for dictionary_kind, matches in (
            ("theme", theme_matches),
            ("modality", modality_matches),
        ):
            for key, match in matches.items():
                # `other` may be assigned by the fallback even where its own
                # patterns were suppressed, so its rows report the assignment
                # that actually stands rather than the pattern outcome alone.
                assigned = (
                    OTHER_MODALITY in assigned_modalities
                    if key == OTHER_MODALITY and dictionary_kind == "modality"
                    else match.matched
                )
                for hit in match.include_hits + match.exclude_hits:
                    hit_rows.append(
                        {
                            "pmid": pmid,
                            "dictionary": dictionary_kind,
                            "category": key,
                            "role": hit.pattern.role,
                            "pattern_id": hit.pattern.pattern_id,
                            "kind": hit.pattern.kind,
                            "case_sensitive": int(hit.pattern.case_sensitive),
                            "pattern": hit.pattern.source,
                            "n_hits": hit.count,
                            "category_matched": int(assigned),
                            "excerpt": hit.excerpt,
                        }
                    )
        if other_by_fallback and not other_by_pattern:
            hit_rows.append(
                {
                    "pmid": pmid,
                    "dictionary": "modality",
                    "category": OTHER_MODALITY,
                    "role": "fallback",
                    "pattern_id": f"{OTHER_MODALITY}:fallback",
                    "kind": "",
                    "case_sensitive": 0,
                    "pattern": "",
                    "n_hits": 0,
                    "category_matched": 1,
                    "excerpt": "no named modality matched",
                }
            )

    exclusions["non_specialty_only"] = sum(
        1 for row in dropped if row["reason"] == "non_specialty_only"
    )
    labels = pd.DataFrame(label_rows, columns=list(label_columns))
    # Secondary publications are retained; they are excluded from Panel A only,
    # so the ledger records the view rather than implying they left the corpus.
    for pmid in labels.loc[labels[aggregate.PRIMARY_RESEARCH] == 0, "pmid"]:
        dropped.append({
            "pmid": str(pmid),
            "reason": "secondary_publication_type",
            "applies_to": "panel_a",
        })
    detail = {"secondary_publication_type": secondary_detail} if secondary_detail else {}

    # A theme defined by combination admits only papers carrying its minimum, and
    # that is a condition on Panel A's VIEW, not on the label. The predicate comes
    # from what a multimodal model is — it used two modalities while being built —
    # so it applies to a study that built something and not to a review, which
    # uses none. Enforcing it on the label would drop reviews that genuinely
    # discuss the theme, which is a category error for an engagement measure.
    # Coordinator's ruling, 2026-09-09. See aggregate.MINIMUM_MODALITIES.
    panel_a_short, corpus_short = aggregate.minimum_modality_shortfalls(labels)
    modality_count = labels[
        [f"mod_{key}" for key in aggregate.modality_keys_of(labels)]
    ].sum(axis=1)
    for theme, minimum in MINIMUM_MODALITIES.items():
        if f"theme_{theme}" not in labels.columns:
            continue
        short = (
            (labels[f"theme_{theme}"] == 1)
            & (modality_count < minimum)
            & (labels[aggregate.PRIMARY_RESEARCH] == 1)
        )
        for pmid in labels.loc[short, "pmid"]:
            dropped.append({
                "pmid": str(pmid),
                "reason": "below_minimum_modalities",
                "applies_to": f"panel_a:{theme}",
            })
    hits = pd.DataFrame(hit_rows, columns=aggregate.PATTERN_HIT_COLUMNS)
    return ClassificationResult(
        labels=labels,
        hits=hits,
        exclusions=exclusions,
        n_records_in=n_in,
        exclusion_detail=detail,
        panel_a_shortfalls=dict(panel_a_short),
        corpus_wide_shortfalls=dict(corpus_short),
        excluded=pd.DataFrame(dropped, columns=["pmid", "reason", "applies_to"]),
    )


# --------------------------------------------------------------------------
# Diagnostic report
# --------------------------------------------------------------------------


#: Used only when the plotting package cannot be imported. Kept equal to
#: ``panel_a.DEFAULT_TOP_N`` by ``test_the_report_follows_the_figures_cap``.
_FALLBACK_COLUMN_CAP: Final[int] = 12


def figure_column_cap() -> int:
    """Return how many combination columns Panel A draws per theme.

    Read from the plotting package rather than repeated here, so the diagnostic
    and the figure cannot drift apart. The import is deliberately late and
    guarded: the classifier must run on a machine with no matplotlib, and a
    missing figure is no reason to refuse to classify.
    """
    try:
        from .plotting import panel_a
    except Exception:  # pragma: no cover - only when matplotlib is unavailable
        return _FALLBACK_COLUMN_CAP
    return int(getattr(panel_a, "DEFAULT_TOP_N", _FALLBACK_COLUMN_CAP))


def other_route_counts(result: ClassificationResult) -> dict[str, int]:
    """Count how the ``other`` label was reached, by route.

    ``other`` is additive, so it arrives two ways: an include pattern of its own
    matched, or nothing named matched and the fallback applied. The two mean
    different things — "uses a data type outside the named rows" against "we
    could not tell what this paper uses" — and a figure that conflates them
    would be reporting an unknown as a finding.

    Returns:
        ``by_pattern``, ``by_fallback``, and ``total`` papers carrying ``other``.
    """
    hits = result.hits
    labels = result.labels
    total = int(labels[f"mod_{OTHER_MODALITY}"].sum()) if len(labels) else 0
    if not len(hits):
        return {"by_pattern": 0, "by_fallback": 0, "total": total}
    is_other = hits["category"] == OTHER_MODALITY
    by_pattern = int(
        hits.loc[is_other & (hits["role"] == "include") & (hits["category_matched"] == 1),
                 "pmid"].nunique()
    )
    by_fallback = int(hits.loc[hits["role"] == "fallback", "pmid"].nunique())
    return {"by_pattern": by_pattern, "by_fallback": by_fallback, "total": total}


def _bar(count: int, total: int, width: int = 28) -> str:
    """Return a fixed-width ASCII bar, for reading counts down a column."""
    if total <= 0:
        return ""
    filled = int(round(width * count / total))
    return "#" * filled


def format_report(
    result: ClassificationResult,
    themes: TermDictionary,
    modalities: TermDictionary,
    combinations: pd.DataFrame,
    *,
    top_patterns: int = 25,
    top_combinations: int | None = None,
    source: str = "",
    freshness: Freshness | None = None,
) -> str:
    """Render the human-readable diagnostic summary.

    The report exists to catch a runaway term before it reaches the figure. It
    gives counts per theme, per modality, and per modality combination; how many
    records matched no theme and no modality; the patterns that fired on the most
    records; and the exclude patterns that suppressed a label.

    Args:
        result: The classification to summarise.
        themes: The theme dictionary used.
        modalities: The modality dictionary used.
        combinations: ``combination_counts.csv`` as a frame.
        top_patterns: How many patterns to list in the firing table.
        top_combinations: How many combinations to list per theme. ``None``
            takes the figure's own column cap, so the two cannot drift.
        source: The record table the run read, named in the header.
        freshness: Result of re-checking the configs after classification. Its
            banner goes at the very top, before any number, because a reader who
            stops after the first screen must still learn the output is stale.

    Returns:
        The report text.
    """
    if top_combinations is None:
        top_combinations = figure_column_cap()
    labels = result.labels
    primary_labels = aggregate.primary_research(labels)
    theme_keys = aggregate.theme_keys_of(labels)
    modality_keys = aggregate.modality_keys_of(labels)
    total = len(labels)
    lines: list[str] = []
    add = lines.append

    if freshness is not None:
        add(freshness.banner())
        add("")
    add("CLASSIFICATION DIAGNOSTIC REPORT")
    add("=" * 78)
    add(f"generated_utc   : {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    if source:
        add(f"records         : {source}")
    add(f"themes.yaml     : v{themes.version}  {themes.sha256[:12]}  "
        f"{len(themes.categories)} categories, {themes.n_patterns} patterns")
    add(f"modalities.yaml : v{modalities.version}  {modalities.sha256[:12]}  "
        f"{len(modalities.categories)} categories, {modalities.n_patterns} patterns")
    add("")
    add(f"records read     : {result.n_records_in:>7,}")
    for reason, count in result.exclusions.items():
        share = f"{count / result.n_records_in:>6.1%}" if result.n_records_in else ""
        add(f"  excluded, {reason:<26}{count:>7,}{share}")
        for name, n in (result.exclusion_detail.get(reason) or {}).items():
            add(f"      {name:<32}{n:>7,}")
    add(f"records analysed : {total:>7,}")
    add("")
    add("TWO POPULATIONS. The panels answer different questions and their")
    add("denominators differ; no number from one may be quoted against the other.")
    primary = result.n_primary_research
    add(f"  Panel B, engagement      (all retained records) : {total:>7,}")
    add(f"  Panel A, primary research (is_primary_research) : {primary:>7,}")
    secondary = total - primary
    if result.n_records_in:
        add(f"  flagged secondary, kept for Panel B only        : {secondary:>7,}"
            f"{secondary / total:>7.1%}" if total else "")
        for name, n in (result.exclusion_detail.get("secondary_publication_type") or {}).items():
            add(f"      {name:<40}{n:>7,}")
    if total == 0:
        add("")
        add("No records reached the corpus. Nothing further to report.")
        return "\n".join(lines) + "\n"
    years = labels["year"]
    add(f"year range       : {int(years.min())}-{int(years.max())}")
    add("")

    if result.panel_a_shortfalls:
        add("THEMES DEFINED BY COMBINATION")
        add("-" * 78)
        add("A theme defined by combination cannot be satisfied by one modality. This is")
        add("a condition on PANEL A'S VIEW, alongside primary research; the label is kept")
        add("and Panel B still counts the paper. A review uses no modalities, so the")
        add("predicate does not apply to it.")
        add("")
        add("Read the two counts together. The shortfall measures how far the theme's")
        add("language over-calls AND how far modality recall falls short: a paper")
        add("predicting Ki-67 from CT is multimodal and reads as single-modality only")
        add("because the target was not labelled. A count that falls when recall improves")
        add("was never about the theme.")
        for theme in sorted(result.panel_a_shortfalls):
            minimum = MINIMUM_MODALITIES.get(theme, 0)
            in_theme = int(labels[f"theme_{theme}"].sum())
            in_primary = int(primary_labels[f"theme_{theme}"].sum())
            held = result.panel_a_shortfalls[theme]
            wide = result.corpus_wide_shortfalls.get(theme, 0)
            add(f"  {theme}  (minimum {minimum} modalities)")
            add(f"    held out of Panel A      {held:>7,} of {in_primary:,} primary "
                f"({held / in_primary:.1%}) -> Panel A draws {in_primary - held:,}")
            add(f"    corpus-wide shortfall    {wide:>7,} of {in_theme:,} retained "
                f"({wide / in_theme:.1%})   <- the over-call measure")
        add("")

    add("THEMES")
    add("-" * 78)
    add("`retained` is Panel B's count; `primary` is Panel A's. They are different")
    add("populations, not an error.")
    add(f"{'theme':<26}{'retained':>10}{'primary':>10}{'share':>8}  distribution")
    for key in theme_keys:
        count = int(labels[f"theme_{key}"].sum())
        n_primary = int(primary_labels[f"theme_{key}"].sum())
        add(f"{key:<26}{count:>10,}{n_primary:>10,}{count / total:>8.1%}  "
            f"{_bar(count, total)}")
    no_theme = int((labels[[f'theme_{key}' for key in theme_keys]].sum(axis=1) == 0).sum())
    add(f"{'(no theme)':<26}{no_theme:>8,}{no_theme / total:>8.1%}  {_bar(no_theme, total)}")
    multi = int((labels[[f'theme_{key}' for key in theme_keys]].sum(axis=1) > 1).sum())
    add(f"{'(two or more themes)':<26}{multi:>8,}{multi / total:>8.1%}")
    add("")

    add("MODALITIES")
    add("-" * 78)
    add(f"{'modality':<26}{'papers':>8}{'share':>8}  distribution")
    for key in modality_keys:
        count = int(labels[f"mod_{key}"].sum())
        add(f"{key:<26}{count:>8,}{count / total:>8.1%}  {_bar(count, total)}")
    named = [f"mod_{key}" for key in modality_keys if key != OTHER_MODALITY]
    counts_per_paper = labels[named].sum(axis=1)
    multi = int((counts_per_paper > 1).sum())
    add(f"{'(two or more named)':<26}{multi:>8,}{multi / total:>8.1%}")
    add("")
    routes = other_route_counts(result)
    add("How `other` was assigned. A pattern match means the paper uses a data type")
    add("outside the named rows; the fallback means no named modality was found at all,")
    add("which is an unknown, not a finding.")
    add(f"{'  other by pattern':<26}{routes['by_pattern']:>8,}")
    add(f"{'  other by fallback':<26}{routes['by_fallback']:>8,}")
    add("")
    add("Named modalities per paper. The multimodal theme is drawn from this.")
    for n in range(0, 5):
        label = f"  {n} named" + ("" if n < 4 else "+")
        count = int((counts_per_paper >= 4).sum() if n == 4 else (counts_per_paper == n).sum())
        add(f"{label:<26}{count:>8,}{count / total:>8.1%}  {_bar(count, total)}")
    add("")

    add("DOMAIN")
    add("-" * 78)
    for value, count in labels["domain"].value_counts().items():
        add(f"{str(value):<26}{int(count):>8,}{int(count) / total:>8.1%}  "
            f"{_bar(int(count), total)}")
    add("")

    add(f"MODALITY COMBINATIONS  (the top {top_combinations} per theme, "
        "as Panel A draws them)")
    add("-" * 78)
    add(f"PRIMARY RESEARCH ONLY: {result.n_primary_research:,} of {total:,} retained "
        "records. These")
    add("counts are Panel A's and are smaller than the theme counts above.")
    add(f"Panel A draws these {top_combinations} columns and one further column holding")
    add("every remaining paper in the theme. Nothing is hidden and no paper is dropped:")
    add("each block's bars sum to the theme's paper count. The line under each block")
    add("says what the remainder column carries.")
    add("")
    for key in theme_keys:
        block = combinations.loc[combinations["theme"] == key].sort_values("rank_in_theme")
        theme_total = int(primary_labels[f"theme_{key}"].sum())
        add(f"{key}  ({theme_total:,} papers, {len(block)} distinct combinations)")
        if block.empty:
            add("    (none)")
            add("")
            continue
        shown = block.head(top_combinations)
        for row in shown.itertuples(index=False):
            share = row.n_papers / theme_total if theme_total else 0.0
            add(f"    {row.rank_in_theme:>2}. {row.modality_set:<46}{row.n_papers:>7,}"
                f"{share:>8.1%}")
        remainder = block.iloc[top_combinations:]
        if theme_total:
            papers = int(remainder["n_papers"].sum())
            add(f"    remainder column: {len(remainder)} further combination(s), "
                f"{papers:,} papers ({papers / theme_total:.1%})")
        add("")

    add(f"MOST FREQUENTLY FIRING PATTERNS  (top {top_patterns} by records matched)")
    add("-" * 78)
    add("A pattern matching a large share of the corpus is either the theme's "
        "backbone or a runaway term. Check any you did not expect.")
    add("")
    if result.hits.empty:
        add("    (no pattern fired)")
    else:
        counts = (
            result.hits.groupby(["pattern_id", "pattern", "role"], sort=False)["pmid"]
            .nunique()
            .reset_index(name="records")
            .sort_values(["records", "pattern_id"], ascending=[False, True])
        )
        add(f"{'records':>8}{'share':>8}  pattern")
        for row in counts.head(top_patterns).itertuples(index=False):
            add(f"{row.records:>8,}{row.records / total:>8.1%}  {row.pattern_id}  "
                f"{row.pattern[:60]}")
        add("")
        excludes = counts.loc[counts["role"] == "exclude"]
        add("EXCLUDE PATTERNS  (labels suppressed)")
        add("-" * 78)
        if excludes.empty:
            add("    (no exclude pattern fired)")
        else:
            for row in excludes.itertuples(index=False):
                add(f"{row.records:>8,}  {row.pattern_id}  {row.pattern[:60]}")
        add("")
        silent = [
            pattern.pattern_id
            for dictionary in (themes, modalities)
            for category in dictionary.categories.values()
            for pattern in category.patterns
            if pattern.pattern_id not in set(counts["pattern_id"])
        ]
        add("PATTERNS THAT NEVER FIRED")
        add("-" * 78)
        add("Dead weight, a typo, or a term the corpus does not use. Not "
            "necessarily wrong; worth a look.")
        add(f"    {len(silent)} of {themes.n_patterns + modalities.n_patterns}: "
            + (", ".join(silent) if silent else "none"))
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Run manifest
# --------------------------------------------------------------------------


#: Config files whose digest the manifest records and this module re-checks.
CHECKED_CONFIGS: Final[tuple[str, ...]] = ("themes", "modalities", "corpus")


@dataclass(frozen=True)
class Freshness:
    """Whether a processed directory was built from the configs now on disk.

    The version ledger answers "is this config self-consistent?". It cannot
    answer "did a run consume a state that no longer exists?", because it compares
    the file on disk against its own recorded hash and never looks at a run's
    output. That second question is the one that has bitten this project
    repeatedly: a config is edited after a run, the ledger still passes, and the
    published numbers came from bytes nobody can produce again.

    This closes that gap by comparing the digests a run recorded in its manifest
    against the files on disk right now.

    Attributes:
        manifest: The manifest that was read, whether or not it existed.
        problems: One message per config that has moved since the run.
        checked: Names of the configs actually compared.
    """

    manifest: Path
    problems: tuple[str, ...]
    checked: tuple[str, ...]

    @property
    def is_stale(self) -> bool:
        """True when at least one config has changed since the run."""
        return bool(self.problems)

    def banner(self) -> str:
        """Return a block for the top of the diagnostic report."""
        if not self.checked:
            return (
                "FRESHNESS: NOT CHECKED\n"
                f"  No usable manifest at {self.manifest}, so these numbers cannot be "
                "tied to a config state."
            )
        if not self.problems:
            names = ", ".join(self.checked)
            return (
                "FRESHNESS: current at the time of writing.\n"
                f"  {names} on disk match the digests this run consumed.\n"
                "  Re-check before quoting any number from this file:\n"
                "      python -m trends.classify --check --output <dir> --config-dir config"
            )
        lines = [
            "!" * 78,
            "STALE OUTPUT. The configuration has changed since this run.",
            "These numbers came from a config state that is no longer on disk, so they",
            "cannot be reproduced and must not be quoted. Re-run before using them.",
        ]
        lines += [f"  - {problem}" for problem in self.problems]
        lines.append("!" * 78)
        return "\n".join(lines)


def check_freshness(output_dir: str | Path, config_dir: str | Path) -> Freshness:
    """Compare a run manifest's config digests with the files on disk.

    Args:
        output_dir: A ``data/processed`` directory holding ``run_manifest.json``.
        config_dir: The configuration directory to compare against.

    Returns:
        A :class:`Freshness`. A missing or unreadable manifest is reported as
        "not checked" rather than as a pass, because an unverifiable number is
        not a verified one.
    """
    manifest_path = Path(output_dir) / RUN_MANIFEST
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Freshness(manifest_path, (), ())

    recorded_raw = (manifest.get("config") or {}) if isinstance(manifest, dict) else {}
    recorded = {
        name: (entry.get("version"), str(entry["sha256"]))
        for name, entry in recorded_raw.items()
        if name in CHECKED_CONFIGS and isinstance(entry, dict) and entry.get("sha256")
    }
    problems, checked = compare_config_digests(recorded, config_dir)
    return Freshness(manifest_path, tuple(problems), tuple(checked))


def compare_config_digests(
    recorded: dict[str, tuple[Any, str]], config_dir: str | Path
) -> tuple[list[str], list[str]]:
    """Compare recorded ``(version, sha256)`` pairs with the configs on disk.

    Shared by :func:`check_freshness`, which reads the pairs out of a stored
    manifest, and by :func:`run`, which holds them from the dictionaries it just
    loaded. One comparison, so a live run and a stored output are judged alike.
    """
    problems: list[str] = []
    checked: list[str] = []
    for name in CHECKED_CONFIGS:
        entry = recorded.get(name)
        if entry is None:
            continue
        version, sha = entry
        path = Path(config_dir) / f"{name}.yaml"
        checked.append(f"{name}.yaml")
        if not path.exists():
            problems.append(f"{path} recorded by the run is missing from disk")
            continue
        # The manifest records the term dictionaries' digest over decoded text and
        # corpus.yaml's over raw bytes. They agree for a file with Unix line
        # endings; both are accepted so a CRLF checkout is not a false alarm.
        on_disk = {
            file_digest(path),
            hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest(),
        }
        if sha not in on_disk:
            was, now = sha[:12], sorted(on_disk)[0][:12]
            problems.append(
                f"config/{name}.yaml: the run consumed v{version} at {was}…, "
                f"but the file on disk now hashes to {now}…. "
                + (
                    "The version number did not move, so the state the run used cannot "
                    "be recovered from the ledger."
                    if str(version) == str(_config_version(path))
                    else f"The file on disk is now v{_config_version(path)}."
                )
            )
    return problems, checked


def _config_version(path: Path) -> Any:
    """Return a config file's declared version, or None if it cannot be read."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    return data.get("version") if isinstance(data, dict) else None


def file_digest(path: str | Path) -> str:
    """Return the SHA-256 of a file, or ``""`` if it cannot be read."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:  # pragma: no cover - only reachable on a vanished file
        return ""


def build_manifest(
    result: ClassificationResult,
    themes: TermDictionary,
    modalities: TermDictionary,
    *,
    records_path: Path,
    outputs: dict[str, Path],
    partial_year: int | None,
    partial_year_source: str,
    corpus: dict[str, Any] | None,
    year_range: tuple[int, int] | None = None,
    config_changed: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Assemble the run manifest written beside the outputs.

    It records what went in, which dictionary versions and digests produced the
    labels, what came out, and what was excluded, so a figure can be traced to
    the terms that made it.
    """
    return {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool": "trends.classify",
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "input": {
            "records": str(records_path),
            "sha256": file_digest(records_path),
            "n_records": result.n_records_in,
        },
        "config": {
            "themes": {
                "path": str(themes.path),
                "version": themes.version,
                "sha256": themes.sha256,
                "n_categories": len(themes.categories),
                "n_patterns": themes.n_patterns,
            },
            "modalities": {
                "path": str(modalities.path),
                "version": modalities.version,
                "sha256": modalities.sha256,
                "n_categories": len(modalities.categories),
                "n_patterns": modalities.n_patterns,
            },
            "corpus": corpus,
        },
        "counts": {
            "records_in": result.n_records_in,
            "records_retained": result.n_records_out,
            "records_analysed": result.n_records_out,
            "records_primary_research": result.n_primary_research,
            "denominators": {
                "panel_b_engagement": result.n_records_out,
                "panel_a_primary_research": result.n_primary_research,
                "note": "Different populations by the author's ruling of 2026-09-08. "
                        "No number from one panel may be quoted against the other.",
            },
            "exclusions": dict(result.exclusions),
            "exclusion_detail": dict(result.exclusion_detail),
            "minimum_modalities": dict(MINIMUM_MODALITIES),
            "combination_shortfalls": {
                "panel_a_held_out": dict(result.panel_a_shortfalls),
                "corpus_wide": dict(result.corpus_wide_shortfalls),
                "note": "Panel A's view excludes these; the label is kept and Panel B "
                        "counts them. corpus_wide is the over-call measure and should "
                        "fall as the theme vocabulary is tightened.",
            },
            "papers_per_theme": {
                key: int(result.labels[f"theme_{key}"].sum())
                for key in aggregate.theme_keys_of(result.labels)
            },
            "papers_per_theme_primary_research": {
                key: int(aggregate.primary_research(result.labels)[f"theme_{key}"].sum())
                for key in aggregate.theme_keys_of(result.labels)
            },
            "papers_per_modality": {
                key: int(result.labels[f"mod_{key}"].sum())
                for key in aggregate.modality_keys_of(result.labels)
            },
            "papers_per_domain": {
                str(value): int(count)
                for value, count in result.labels["domain"].value_counts().items()
            },
            "papers_with_no_theme": int(
                (
                    result.labels[
                        [f"theme_{key}" for key in aggregate.theme_keys_of(result.labels)]
                    ].sum(axis=1)
                    == 0
                ).sum()
            ),
        },
        "config_changed_during_run": list(config_changed or ()),
        "partial_year": {"year": partial_year, "source": partial_year_source},
        "year_range_applied": (
            None if year_range is None else {"first": year_range[0], "last": year_range[1]}
        ),
        "other_assignment": other_route_counts(result),
        "outputs": {
            name: {"path": str(path), "sha256": file_digest(path)}
            for name, path in outputs.items()
        },
    }


def _year_of(value: Any) -> int | None:
    """Pull the year out of a ``YYYY/MM/DD`` date string, or return None."""
    if isinstance(value, str) and len(value) >= 4 and value[:4].isdigit():
        return int(value[:4])
    return None


@dataclass(frozen=True)
class CorpusWindow:
    """The retrieval window read from ``corpus.yaml``.

    Attributes:
        years: Inclusive ``(first, last)`` publication years, or ``None`` when
            the file gave no usable date range.
        partial_year: The year the corpus was retrieved in, which is the last
            year of the window and the one flagged partial.
        source: Where the partial year came from, for the manifest.
        meta: File path, version, and digest, for the manifest.
    """

    years: tuple[int, int] | None
    partial_year: int | None
    source: str
    meta: dict[str, Any] | None


def read_corpus_window(path: str | Path) -> CorpusWindow:
    """Read the retrieval window and provenance out of ``corpus.yaml``.

    The window bounds which publication years may enter the corpus, and its end
    is the partial year. A missing or unreadable file is not fatal: no window is
    applied, the caller falls back to the newest year present, and the manifest
    records which route was taken.
    """
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return CorpusWindow(None, None, "unavailable", None)
    if not isinstance(data, dict):
        return CorpusWindow(None, None, "unavailable", None)
    date_range = data.get("date_range") or {}
    start, end = date_range.get("start"), date_range.get("end")
    first, last = _year_of(start), _year_of(end)
    years = (first, last) if first is not None and last is not None else None
    meta = {
        "path": str(path),
        "version": data.get("version"),
        "sha256": file_digest(path),
        "date_range_start": start,
        "date_range_end": end,
    }
    return CorpusWindow(years, last, f"{path}:date_range.end", meta)


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------


def run(
    records_path: Path,
    config_dir: Path,
    output_dir: Path,
    *,
    partial_year: int | None = None,
    write_hits: bool = True,
    top_patterns: int = 25,
    apply_date_window: bool = True,
) -> dict[str, Any]:
    """Classify a record table and write every output.

    Args:
        records_path: ``records.parquet`` from :mod:`trends.parse`.
        config_dir: Directory holding ``themes.yaml`` and ``modalities.yaml``.
        output_dir: Directory to write the tables, manifest, and report into.
        partial_year: Year to flag partial. ``None`` reads it from
            ``corpus.yaml``, and failing that uses the newest year present.
        write_hits: Write the per-pattern provenance table. It is the largest
            output; turning it off costs the ability to check a label.
        top_patterns: How many patterns the report lists.
        apply_date_window: Drop records whose year falls outside the
            ``date_range`` in ``corpus.yaml``. Turning it off keeps the
            early-online records, and makes the first year of the corpus a
            biased partial year.

    Returns:
        The run manifest.
    """
    themes, modalities = load_dictionaries(config_dir)
    frame = read_records(records_path)
    window = read_corpus_window(Path(config_dir) / "corpus.yaml")
    year_range = window.years if apply_date_window else None
    result = classify_records(frame, themes, modalities, year_range=year_range)
    log.info(
        "Classified %d of %d records (%s)",
        result.n_records_out,
        result.n_records_in,
        ", ".join(f"{reason}={count}" for reason, count in result.exclusions.items()),
    )

    year_source = window.source
    if partial_year is not None:
        year_source = "--partial-year"
    else:
        partial_year = window.partial_year
    if partial_year is None and len(result.labels):
        partial_year = int(result.labels["year"].max())
        year_source = "newest year in corpus"

    provenance = (
        f"records: {records_path}",
        f"themes.yaml v{themes.version} sha256:{themes.sha256[:16]}",
        f"modalities.yaml v{modalities.version} sha256:{modalities.sha256[:16]}",
    )
    outputs = aggregate.write_tables(
        result.labels,
        output_dir,
        partial_year=partial_year,
        provenance=provenance,
    )
    output_dir = Path(output_dir)
    # Every excluded record, by name and reason. A count says how many left; this
    # says which, which is what makes an exclusion auditable rather than trusted.
    exclusions_path = output_dir / EXCLUSIONS
    result.excluded.to_csv(exclusions_path, index=False)
    outputs["exclusions"] = exclusions_path
    if write_hits:
        hits_path = output_dir / PATTERN_HITS
        result.hits.to_csv(hits_path, index=False)
        outputs["pattern_hits"] = hits_path

    # Re-read the configs now that classification is done. A four-minute run is
    # long enough for a dictionary to be edited underneath it, and that has
    # happened: a run recorded a digest that had already been superseded before
    # its own report was written.
    problems, checked = compare_config_digests(
        {
            "themes": (themes.version, themes.sha256),
            "modalities": (modalities.version, modalities.sha256),
        },
        config_dir,
    )
    freshness = Freshness(
        Path(output_dir) / RUN_MANIFEST, tuple(problems), tuple(checked)
    )
    if freshness.is_stale:
        for problem in problems:
            log.warning("Config changed during the run: %s", problem)

    combinations = aggregate.build_combination_counts(result.labels)
    report_text = format_report(
        result,
        themes,
        modalities,
        combinations,
        top_patterns=top_patterns,
        source=str(records_path),
        freshness=freshness,
    )
    report_path = Path(output_dir) / REPORT
    report_path.write_text(report_text, encoding="utf-8")
    outputs["report"] = report_path

    manifest = build_manifest(
        result,
        themes,
        modalities,
        records_path=Path(records_path),
        outputs=outputs,
        partial_year=partial_year,
        partial_year_source=year_source,
        corpus=window.meta,
        year_range=year_range,
        config_changed=problems,
    )
    manifest_path = Path(output_dir) / RUN_MANIFEST
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    manifest["report_text"] = report_text
    return manifest


def main(argv: list[str] | None = None) -> int:
    """Classify a record table from the command line."""
    parser = argparse.ArgumentParser(
        prog="python -m trends.classify",
        description="Assign themes and modalities to parsed PubMed records.",
    )
    parser.add_argument("--records", type=Path,
                        help="records.parquet (or records.csv) from trends.parse. "
                             "Required unless --check is given.")
    parser.add_argument("--config-dir", type=Path, default=Path("config"),
                        help="Directory holding themes.yaml and modalities.yaml.")
    parser.add_argument("--output", type=Path, default=Path("data/processed"),
                        help="Directory to write the processed tables into.")
    parser.add_argument("--partial-year", type=int, default=None,
                        help="Year to flag partial. Default: the end of the corpus "
                             "date range in config/corpus.yaml.")
    parser.add_argument("--no-date-window", action="store_true",
                        help="Keep records whose year falls outside date_range in "
                             "corpus.yaml. Makes the corpus's first year biased.")
    parser.add_argument("--no-hits", action="store_true",
                        help="Skip pattern_hits.csv, the per-pattern provenance table.")
    parser.add_argument("--top-patterns", type=int, default=25,
                        help="How many patterns the diagnostic report lists.")
    parser.add_argument("--report", action="store_true",
                        help="Print the diagnostic report as well as writing it.")
    parser.add_argument("--check", action="store_true",
                        help="Classify nothing. Compare the config digests recorded in "
                             "--output's run_manifest.json with the files in --config-dir "
                             "and exit non-zero if the output is stale. Exit 0 current, "
                             "3 stale, 4 no manifest to check.")
    args = parser.parse_args(argv)

    if args.check:
        freshness = check_freshness(args.output, args.config_dir)
        stream = sys.stdout if not freshness.is_stale else sys.stderr
        print(freshness.banner(), file=stream)
        if not freshness.checked:
            return 4
        return 3 if freshness.is_stale else 0

    if args.records is None:
        parser.error("--records is required unless --check is given")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        manifest = run(
            args.records,
            args.config_dir,
            args.output,
            partial_year=args.partial_year,
            write_hits=not args.no_hits,
            top_patterns=args.top_patterns,
            apply_date_window=not args.no_date_window,
        )
    except (TermDictionaryError, RecordTableError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    report_text = manifest.pop("report_text")
    if args.report:
        print(report_text)
    else:
        print(json.dumps(manifest["counts"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
