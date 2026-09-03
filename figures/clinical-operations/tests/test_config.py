"""Configuration integrity.

Two groups of checks.

The first is the **version ledger**, ported from ``../trends-figure``. A config
file's ``version`` is what a run manifest records, and it is the only thing that
ties a published count back to the rule that produced it. That guarantee breaks
silently when a file is edited without the version moving: the manifest still
names a version, but the version no longer means what it meant. In the sibling
project this happened three times in one day and was caught each time by hand.
``config/VERSIONS.json`` freezes each version to a hash and these tests make it
bite.

The second group checks the **oncology rule itself** — that every code carries
the evidence the schema promises, that no code is classified twice, and that the
exclusion lists are complete enough to audit. A rule nobody can check is not
better than no rule.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]

#: Config files the ledger governs.
LEDGERED_CONFIGS: tuple[str, ...] = ("source.yaml", "oncology_codes.yaml")

#: The ledger itself, inside the config directory.
LEDGER_NAME = "VERSIONS.json"

#: Shortest hash prefix the ledger may record and still be checkable.
_MIN_HASH_PREFIX = 8

#: Domains a category may claim.
VALID_DOMAINS = {"radiology", "pathology"}

#: Tiers a category may claim.
VALID_TIERS = {"oncology"}


def file_digest(path: Path) -> str:
    """SHA-256 of a file's raw bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# The config version ledger
# --------------------------------------------------------------------------


def _keep_duplicate_pairs(pairs: list[tuple[str, object]]) -> list[tuple[str, object]]:
    """``object_pairs_hook`` that preserves repeated keys instead of collapsing them.

    ``json.load`` keeps the last of a repeated key, which would hide exactly the
    mistake this checks for.
    """
    return pairs


def _entry_hash(value: object) -> str | None:
    """Pull the hash out of a ledger entry.

    Accepts a bare string, or a mapping carrying the hash under ``sha256``,
    ``hash``, or ``digest``. Returns ``None`` when no hash can be read, which the
    caller treats as "not recorded" rather than as a violation.
    """
    if isinstance(value, list):  # a nested object, from the pairs hook
        value = dict(value)
    if isinstance(value, str):
        text = value.strip()
    elif isinstance(value, dict):
        for key in ("sha256", "hash", "digest"):
            found = value.get(key)
            if isinstance(found, str):
                text = found.strip()
                break
        else:
            return None
    else:
        return None
    text = text.rstrip("….").strip()
    if len(text) < _MIN_HASH_PREFIX or any(c not in "0123456789abcdefABCDEF" for c in text):
        return None
    return text.lower()


def _file_sections(raw: list) -> list[tuple[str, list]]:
    """Return the ``(filename, versions)`` sections of a parsed ledger.

    Keys beginning with ``_`` are commentary — the ledger carries its own README
    and a provenance note — and are skipped.
    """
    pairs = [item for item in raw if isinstance(item, (list, tuple)) and len(item) == 2]
    for key, value in pairs:
        if key == "files" and isinstance(value, list):
            pairs = [item for item in value if isinstance(item, (list, tuple)) and len(item) == 2]
            break
    return [
        (str(key), value)
        for key, value in pairs
        if not str(key).startswith("_") and isinstance(value, list)
    ]


def _parse_ledger(path: Path) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Read ``VERSIONS.json``.

    Returns the recorded hashes as ``{filename: {version: hash}}``, and a list of
    reuse problems: a version written twice with different hashes.
    """
    raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_keep_duplicate_pairs)
    entries: dict[str, dict[str, str]] = {}
    problems: list[str] = []
    for filename, versions in _file_sections(raw):
        recorded: dict[str, str] = {}
        for item in versions:
            if not (isinstance(item, (list, tuple)) and len(item) == 2):
                continue
            version, value = item
            digest = _entry_hash(value)
            if digest is None:
                continue
            version = str(version)
            if version in recorded and recorded[version] != digest:
                problems.append(
                    f"{path} records {filename} version {version} twice, with different "
                    f"hashes ({recorded[version][:12]}… and {digest[:12]}…). A version is "
                    "frozen once. Give the later content a new version number and append "
                    "it as a new entry; never re-point an existing one."
                )
            recorded[version] = digest
        entries[filename] = recorded
    return entries, problems


def _hash_mismatches(config_dir: Path, entries: dict[str, dict[str, str]]) -> list[str]:
    """Compare each config file on disk with the hash its own version froze."""
    problems: list[str] = []
    for filename in LEDGERED_CONFIGS:
        path = config_dir / filename
        recorded = entries.get(filename)
        if not path.exists() or not recorded:
            continue
        version = str(yaml.safe_load(path.read_text(encoding="utf-8")).get("version"))
        expected = recorded.get(version)
        if expected is None:
            continue
        actual = file_digest(path)
        if not actual.startswith(expected):
            problems.append(
                f"config/{filename} says version {version}, and {LEDGER_NAME} froze "
                f"version {version} at {expected[:12]}…, but the file now hashes to "
                f"{actual[:12]}…. The file was edited without the version moving, so "
                f"every manifest naming {filename} v{version} is now ambiguous. Fix it by "
                f"bumping `version` in config/{filename} and appending the new version "
                f"and its hash to config/{LEDGER_NAME} — not by editing the hash recorded "
                "for the existing version."
            )
    return problems


def test_config_files_match_the_version_ledger():
    """A config file may not change without its version moving."""
    config = PROJECT_ROOT / "config"
    ledger = config / LEDGER_NAME
    if not ledger.exists():
        pytest.skip(f"config/{LEDGER_NAME} does not exist yet")
    entries, _ = _parse_ledger(ledger)
    problems = _hash_mismatches(config, entries)
    assert not problems, "\n\n".join(problems)


def test_the_version_ledger_never_reuses_a_version():
    """The ledger is append-only: one version, one hash, forever."""
    config = PROJECT_ROOT / "config"
    ledger = config / LEDGER_NAME
    if not ledger.exists():
        pytest.skip(f"config/{LEDGER_NAME} does not exist yet")
    _, problems = _parse_ledger(ledger)
    assert not problems, "\n\n".join(problems)


def _unrecorded_current_versions(
    config_dir: Path, entries: dict[str, dict[str, str]]
) -> list[str]:
    """Return configs whose CURRENT version the ledger does not record.

    ``_hash_mismatches`` deliberately skips a version the ledger has never seen,
    on the principle that an unrecorded version is not evidence of tampering.
    That leaves a hole: bumping ``version`` and forgetting to append the new
    hash passes every other check, and the config is then unguarded at exactly
    the moment it changed. This closes it.
    """
    problems: list[str] = []
    for filename in LEDGERED_CONFIGS:
        path = config_dir / filename
        if not path.exists():
            continue
        version = str(yaml.safe_load(path.read_text(encoding="utf-8")).get("version"))
        recorded = entries.get(filename) or {}
        if version not in recorded:
            problems.append(
                f"config/{filename} declares version {version}, which {LEDGER_NAME} "
                f"does not record (it has {sorted(recorded) or 'nothing'}). Bumping a "
                "version without appending its hash leaves the file unguarded from "
                f"that point on. Append `\"{version}\": \"<sha256>\"` under "
                f"files.{filename}, using: shasum -a 256 config/{filename}"
            )
    return problems


def test_the_ledger_records_each_config_current_version():
    """Every governed config's live version must be frozen to a hash.

    This is the check that makes the ledger complete. Without it the guard only
    catches editing-without-bumping, and bumping-without-ledgering slips through.
    """
    config = PROJECT_ROOT / "config"
    ledger = config / LEDGER_NAME
    if not ledger.exists():
        pytest.skip(f"config/{LEDGER_NAME} does not exist yet")
    entries, _ = _parse_ledger(ledger)
    problems = _unrecorded_current_versions(config, entries)
    assert not problems, "\n\n".join(problems)


def test_the_completeness_guard_catches_a_bump_without_a_ledger_entry(tmp_path):
    """The hole this closes, demonstrated.

    v1 is ledgered; the file is edited and bumped to v2; the ledger is not
    appended to. Every other check passes and this one must not.
    """
    config = tmp_path / "config"
    config.mkdir()
    path = config / "source.yaml"
    path.write_text("version: 1\ndevice_list: {}\n", encoding="utf-8")
    entries = {"source.yaml": {"1": file_digest(path)}}

    path.write_text("version: 2\ndevice_list: {a: 1}\n", encoding="utf-8")

    assert _hash_mismatches(config, entries) == [], "the hash guard alone lets this pass"
    problems = _unrecorded_current_versions(config, entries)
    assert len(problems) == 1
    assert "does not record" in problems[0]


# -- the guard's own tests, so it is not itself taken on trust ----------------


def test_the_ledger_guard_catches_an_edit_without_a_bump(tmp_path):
    """The mistake this exists to catch: content moves, version does not."""
    config = tmp_path / "config"
    config.mkdir()
    path = config / "source.yaml"
    path.write_text("version: 1\ndevice_list: {}\n", encoding="utf-8")
    frozen = file_digest(path)

    # Edit the file but leave `version` alone — the breach.
    path.write_text("version: 1\ndevice_list: {a: 1}\n", encoding="utf-8")

    problems = _hash_mismatches(config, {"source.yaml": {"1": frozen}})
    assert len(problems) == 1
    assert "was edited without the version moving" in problems[0]


def test_the_ledger_guard_passes_a_change_followed_by_a_bump(tmp_path):
    """The legitimate case: edit the file, bump the version, append an entry."""
    config = tmp_path / "config"
    config.mkdir()
    path = config / "source.yaml"
    path.write_text("version: 1\ndevice_list: {}\n", encoding="utf-8")
    first = file_digest(path)

    path.write_text("version: 2\ndevice_list: {a: 1}\n", encoding="utf-8")
    second = file_digest(path)

    problems = _hash_mismatches(config, {"source.yaml": {"1": first, "2": second}})
    assert problems == []


def test_the_reuse_guard_catches_a_repointed_version(tmp_path):
    """A version written twice with different hashes is a reuse."""
    ledger = tmp_path / LEDGER_NAME
    ledger.write_text(
        '{"files": {"source.yaml": {"1": "%s", "1": "%s"}}}'
        % ("a" * 64, "b" * 64),
        encoding="utf-8",
    )
    _, problems = _parse_ledger(ledger)
    assert len(problems) == 1
    assert "twice, with different hashes" in problems[0]


# --------------------------------------------------------------------------
# The oncology rule
# --------------------------------------------------------------------------


def _counted_codes(config: dict) -> dict[str, str]:
    """Every counted product code mapped to the category that claims it."""
    found: dict[str, str] = {}
    for key, category in config["categories"].items():
        for entry in category["codes"]:
            found[entry["code"]] = key
    return found


def _excluded_codes(config: dict) -> dict[str, str]:
    """Every excluded product code mapped to the exclusion group that holds it."""
    found: dict[str, str] = {}
    for key, group in config.get("excluded", {}).items():
        for entry in group["codes"]:
            found[entry["code"]] = key
    return found


def test_no_product_code_is_classified_twice(oncology_config):
    """A code belongs to exactly one category, and is never both counted and excluded.

    Two categories claiming one code would double-count every device under it.
    """
    counted: dict[str, list[str]] = {}
    for key, category in oncology_config["categories"].items():
        for entry in category["codes"]:
            counted.setdefault(entry["code"], []).append(key)

    duplicated = {code: keys for code, keys in counted.items() if len(keys) > 1}
    assert not duplicated, f"codes claimed by more than one category: {duplicated}"

    both = set(counted) & set(_excluded_codes(oncology_config))
    assert not both, (
        f"codes that are both counted and excluded: {sorted(both)}. A code is counted "
        "or excluded, never both."
    )


def test_every_category_declares_a_valid_domain_and_tier(oncology_config):
    """Downstream code groups by these values; a typo would silently drop a series."""
    problems = []
    for key, category in oncology_config["categories"].items():
        if category.get("domain") not in VALID_DOMAINS:
            problems.append(f"{key}: domain {category.get('domain')!r} not in {VALID_DOMAINS}")
        if category.get("tier") not in VALID_TIERS:
            problems.append(f"{key}: tier {category.get('tier')!r} not in {VALID_TIERS}")
        if not category.get("label"):
            problems.append(f"{key}: no label, which the figure axes need")
    assert not problems, "\n".join(problems)


def test_every_counted_code_records_its_evidence(oncology_config):
    """A counted code carries FDA's own words for why it counts.

    This is the whole basis of the rule's auditability. A code with an empty
    definition is a code a reader cannot check.
    """
    problems = []
    for key, category in oncology_config["categories"].items():
        for entry in category["codes"]:
            code = entry.get("code")
            if not entry.get("device_name"):
                problems.append(f"{key}/{code}: no device_name")
            definition = (entry.get("definition") or "").strip()
            if len(definition) < 40:
                problems.append(
                    f"{key}/{code}: definition is missing or too short to be evidence "
                    f"({len(definition)} chars). Record what FDA says the device type is "
                    "for, or say explicitly that openFDA returns no definition and why "
                    "the code is counted anyway."
                )
    assert not problems, "\n".join(problems)


def test_every_excluded_code_records_a_reason(oncology_config):
    """An exclusion a reader cannot interrogate is indistinguishable from an oversight."""
    problems = []
    for key, group in oncology_config.get("excluded", {}).items():
        if not group.get("reason"):
            problems.append(f"exclusion group {key!r} has no reason")
        for entry in group["codes"]:
            if not (entry.get("why") or "").strip():
                problems.append(f"{key}/{entry.get('code')}: no `why`")
            if entry.get("n") is None:
                problems.append(
                    f"{key}/{entry.get('code')}: no `n`. The device count is what tells a "
                    "reader how much the exclusion costs."
                )
    assert not problems, "\n".join(problems)


def test_every_override_records_why_the_lookup_is_wrong(oncology_config):
    """An override contradicts the authoritative source, so it must justify itself."""
    for code, override in oncology_config.get("overrides", {}).items():
        assert override.get("domain") in VALID_DOMAINS, f"{code}: bad domain"
        assert override.get("tier") in VALID_TIERS, f"{code}: bad tier"
        reason = (override.get("reason") or "").strip()
        assert len(reason) > 80, (
            f"override for {code} does not explain why openFDA's record is not "
            "trustworthy for this device. An unexplained override is a silent "
            "correction of the source."
        )


def test_overridden_codes_are_also_classified(oncology_config):
    """An override adjusts a classification; it does not create one out of nothing."""
    counted = _counted_codes(oncology_config)
    for code in oncology_config.get("overrides", {}):
        assert code in counted, (
            f"{code} has an override but appears in no category. The override would "
            "have nothing to attach to."
        )


def test_the_qfm_exclusion_is_documented(oncology_config):
    """QFM is the exclusion most likely to be undone by someone reading code names.

    Its device-type name reads oncologic and its devices are not. If a later edit
    moves it into a counted category, the radiology total jumps by 39 and the
    figure silently overstates the comparison. This test is a tripwire on that
    specific mistake, and it points at the reasoning rather than just failing.
    """
    counted = _counted_codes(oncology_config)
    assert "QFM" not in counted, (
        "QFM has been moved into a counted category. Before accepting that change, read "
        "the devices authorized under it: pneumothorax and pulmonary-embolism triage, "
        "vertebral compression fracture, aneurysm and trauma triage. One of 39 is "
        "oncologic. Its name says 'Lesions'; its devices are acute-care findings. See "
        "docs/DECISIONS.md, 2026-09-03."
    )
    excluded = _excluded_codes(oncology_config)
    assert excluded.get("QFM") == "not_oncology"


def test_all_nine_pathology_codes_are_counted(oncology_config):
    """Every pathology authorization on the FDA AI list is oncologic.

    Nothing is lost to the conservative rule on the pathology side, which is what
    lets the figure claim the gap is understated rather than overstated. If a
    pathology code ever moves to `excluded`, that claim needs revisiting.
    """
    counted = _counted_codes(oncology_config)
    pathology_codes = {
        code for code, key in counted.items()
        if oncology_config["categories"][key]["domain"] == "pathology"
    }
    assert pathology_codes == {
        "QPN", "SFH", "QKQ", "QYV", "PZM", "PQP", "MNM", "NMN"
    }, (
        "The set of counted pathology codes has changed. The figure's claim that the "
        "radiology-to-pathology gap is understated depends on every pathology "
        "authorization being counted."
    )
