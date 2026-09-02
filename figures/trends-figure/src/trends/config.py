"""Load and validate ``config/corpus.yaml``.

The corpus file defines the paper pool: one PubMed query, one date range, and
the E-utilities settings the retrieval runs under. This module reads that file,
checks every field, and returns a frozen :class:`CorpusConfig`. A malformed
file raises :class:`ConfigError` listing every problem found, so the user fixes
the file once rather than once per run.

Nothing here touches the network, and nothing here writes.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

# The rate ceiling NCBI grants a client holding an API key. Requesting more is
# a violation of the E-utilities usage policy, so the config may not ask for it.
MAX_REQUESTS_PER_SECOND = 10

# efetch will return more than this per call, but large batches time out and
# waste work when they fail. NCBI's own guidance for efetch is a few hundred.
MAX_BATCH_SIZE = 10_000

_DATE_PATTERN = re.compile(r"^\d{4}/\d{2}/\d{2}$")


class ConfigError(ValueError):
    """Raised when the corpus configuration is missing, malformed, or unusable.

    The message names the file and lists every problem found, one per line.
    """


@dataclass(frozen=True)
class RetrievalSettings:
    """E-utilities settings: which database, who is calling, and how fast."""

    db: str
    tool: str
    email: str
    batch_size: int
    requests_per_second: int


@dataclass(frozen=True)
class CorpusConfig:
    """A validated corpus definition.

    Attributes:
        version: Config version, bumped by hand on every edit and recorded in
            the run manifest so a figure can be traced to the terms that made it.
        start_date: Inclusive lower bound of the publication date filter.
        end_date: Inclusive upper bound.
        query: The PubMed query, normalized to a single line (see
            :func:`normalize_query`). This exact string is what gets sent.
        retrieval: E-utilities settings.
        path: Where the config was read from.
        sha256: Digest of the file as read, for the manifest.
        raw: The parsed YAML, unmodified, for anything a later step needs.
    """

    version: int
    start_date: date
    end_date: date
    query: str
    retrieval: RetrievalSettings
    path: Path
    sha256: str
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def mindate(self) -> str:
        """Start date in the ``YYYY/MM/DD`` form E-utilities expects."""
        return self.start_date.strftime("%Y/%m/%d")

    @property
    def maxdate(self) -> str:
        """End date in the ``YYYY/MM/DD`` form E-utilities expects."""
        return self.end_date.strftime("%Y/%m/%d")


def normalize_query(raw_query: str) -> tuple[str, int]:
    """Strip comment lines from a query block and flatten it to one line.

    A line whose first non-blank character is ``#`` is a comment and is dropped.
    Remaining lines are joined with single spaces, because PubMed treats a query
    as one string and stray newlines have caused silent term loss in the past.

    Returns the normalized query and the number of comment lines removed.
    """
    kept: list[str] = []
    comments = 0
    for line in raw_query.splitlines():
        if line.strip().startswith("#"):
            comments += 1
            continue
        kept.append(line)
    return re.sub(r"\s+", " ", " ".join(kept)).strip(), comments


def _parse_date(value: Any, field_name: str, problems: list[str]) -> date | None:
    """Parse a ``YYYY/MM/DD`` string, appending a message on any failure."""
    if not isinstance(value, str):
        problems.append(
            f"{field_name}: expected a quoted YYYY/MM/DD string, got {type(value).__name__}. "
            "Unquoted dates are read by YAML as something else."
        )
        return None
    if not _DATE_PATTERN.match(value):
        problems.append(f"{field_name}: expected YYYY/MM/DD, got {value!r}.")
        return None
    try:
        return date(*(int(part) for part in value.split("/")))
    except ValueError as exc:
        problems.append(f"{field_name}: {value!r} is not a real date ({exc}).")
        return None


def _require_int(
    mapping: dict[str, Any],
    key: str,
    field_name: str,
    problems: list[str],
    *,
    minimum: int,
    maximum: int,
) -> int | None:
    """Pull a bounded integer out of a mapping, appending a message on failure."""
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


def _require_str(
    mapping: dict[str, Any], key: str, field_name: str, problems: list[str]
) -> str | None:
    """Pull a non-empty string out of a mapping, appending a message on failure."""
    if key not in mapping:
        problems.append(f"{field_name}: missing.")
        return None
    value = mapping[key]
    if not isinstance(value, str) or not value.strip():
        problems.append(f"{field_name}: expected a non-empty string, got {value!r}.")
        return None
    return value.strip()


def load_corpus_config(path: str | Path, *, require_query: bool = True) -> CorpusConfig:
    """Read and validate a corpus configuration file.

    Args:
        path: Path to ``corpus.yaml``.
        require_query: Insist on a non-empty query. Set to False only when the
            caller supplies its own query, as ``--query`` does while the search
            strategy is still being written. Every other field is still checked.

    Returns:
        The validated configuration.

    Raises:
        ConfigError: The file is missing, is not valid YAML, is not a mapping,
            or fails any field check. The message lists every problem at once.
    """
    path = Path(path)
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

    problems: list[str] = []

    version = _require_int(data, "version", "version", problems, minimum=1, maximum=10_000)

    # -- date range -------------------------------------------------------
    start_date = end_date = None
    date_range = data.get("date_range")
    if date_range is None:
        problems.append("date_range: missing.")
    elif not isinstance(date_range, dict):
        problems.append(f"date_range: expected a mapping, got {type(date_range).__name__}.")
    else:
        if "start" not in date_range:
            problems.append("date_range.start: missing.")
        else:
            start_date = _parse_date(date_range["start"], "date_range.start", problems)
        if "end" not in date_range:
            problems.append("date_range.end: missing.")
        else:
            end_date = _parse_date(date_range["end"], "date_range.end", problems)
        if start_date and end_date and start_date > end_date:
            problems.append(
                f"date_range: start ({start_date}) is after end ({end_date})."
            )

    # -- retrieval settings ----------------------------------------------
    retrieval = None
    settings = data.get("retrieval")
    if settings is None:
        problems.append("retrieval: missing.")
    elif not isinstance(settings, dict):
        problems.append(f"retrieval: expected a mapping, got {type(settings).__name__}.")
    else:
        db = _require_str(settings, "db", "retrieval.db", problems)
        if db is not None and db != "pubmed":
            problems.append(f"retrieval.db: only 'pubmed' is supported, got {db!r}.")
        tool = _require_str(settings, "tool", "retrieval.tool", problems)
        email = _require_str(settings, "email", "retrieval.email", problems)
        if email is not None and "@" not in email:
            problems.append(
                f"retrieval.email: {email!r} is not an address. NCBI requires a "
                "working contact on every request."
            )
        batch_size = _require_int(
            settings, "batch_size", "retrieval.batch_size", problems,
            minimum=1, maximum=MAX_BATCH_SIZE,
        )
        rps = _require_int(
            settings, "requests_per_second", "retrieval.requests_per_second", problems,
            minimum=1, maximum=MAX_REQUESTS_PER_SECOND,
        )
        if None not in (db, tool, email, batch_size, rps):
            retrieval = RetrievalSettings(
                db=db, tool=tool, email=email,
                batch_size=batch_size, requests_per_second=rps,
            )

    # -- query -------------------------------------------------------------
    query = ""
    raw_query = data.get("query")
    if raw_query is None:
        if require_query:
            problems.append("query: missing.")
    elif not isinstance(raw_query, str):
        problems.append(f"query: expected a string, got {type(raw_query).__name__}.")
    else:
        normalized, comments = normalize_query(raw_query)
        if not normalized and require_query:
            problems.append(
                "query: empty. The file holds only comments or blank lines; the "
                "search strategy has not been written yet."
                if comments
                else "query: empty."
            )
        query = normalized

    if problems:
        raise ConfigError(
            f"{path} is not usable. {len(problems)} problem(s):\n  - "
            + "\n  - ".join(problems)
        )

    assert version is not None and start_date and end_date and retrieval is not None
    return CorpusConfig(
        version=version,
        start_date=start_date,
        end_date=end_date,
        query=query,
        retrieval=retrieval,
        path=path,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        raw=data,
    )
