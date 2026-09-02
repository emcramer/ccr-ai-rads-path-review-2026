"""Measure the rule-based classifier against an independently labeled sample.

The classifier in :mod:`trends.classify` is reproducible from the term
dictionaries alone and calls no model, which is the decision recorded in
``docs/DECISIONS.md``. The price of that decision is that its error rate is
unknown. This module measures it.

The design, also from ``docs/DECISIONS.md`` (2026-09-01, "Classifier validation
by LLM labeling with an author audit"):

1. Draw a **stratified** sample of about 200 papers. The themes differ in size
   by two orders of magnitude, so a simple random sample would carry perhaps
   one digital-twin paper and no clinical/FDA paper at all. One stratum holds
   papers the rules gave **no** theme, because a sample drawn only from labeled
   papers can measure precision and can never measure recall.
2. An agent labels the sample **blind**: the sheet it reads carries the title
   and the abstract and nothing else. Nothing in it reveals what the rules
   decided, and the row order is shuffled, so the stratum a paper came from
   cannot be inferred from its position.
3. Join the agent's labels to the rule labels and score the rules against them.
4. The author audits fifty of the labeled papers, and the three-way agreement
   is reported.

Two rounds have been run. **Round one measured `config/*.yaml` v2** and drove
seven dictionary fixes; **round two measures v3 on a fresh sample with a fresh
seed**, because a sample the patterns were fitted to no longer measures them.
Both rounds use the same six strata, so they are comparable.

Two numbers are produced for every category, and they answer different
questions.

**Raw counts** are what happened inside the sample: this many papers, this many
agreements. They are the honest denominator and every percentage in
``docs/validation.md`` is printed beside them.

**Weighted estimates** project the sample onto the corpus. Each stratum has a
known population :math:`N_h` and a known sample size :math:`n_h`, so a sampled
paper stands for :math:`N_h / n_h` corpus papers. The strata partition the
corpus, so the ratio estimator is unbiased. Its *variance* is another matter:
one false negative found in the no-theme stratum stands for hundreds of corpus
papers, and the weighted recall of a small theme is therefore a soft number.
The report says so wherever it prints one.

Command line
------------
Three subcommands, run in order::

    python -m trends.validate sample \\
        --labels data/processed/paper_labels.csv \\
        --records data/interim/records.parquet \\
        --output data/processed/validation/

    # ... an agent fills in agent_labels.csv, blind ...

    python -m trends.validate score \\
        --sample data/processed/validation/sample.csv \\
        --agent data/processed/validation/agent_labels.csv \\
        --labels data/processed/paper_labels.csv \\
        --output data/processed/validation/

    python -m trends.validate audit \\
        --joined data/processed/validation/joined_labels.csv \\
        --records data/interim/records.parquet \\
        --output data/processed/validation/

``sample`` writes ``sample.csv`` (the strata, the weights, and the seed) and
``blind_sheet.csv`` (PMID, title, abstract; nothing else). ``score`` writes
``joined_labels.csv``, ``agreement_themes.csv``, ``agreement_modalities.csv``
and ``agreement_report.txt``. ``audit`` writes ``audit_sheet.csv``.

Everything stochastic in this module goes through one seed, recorded in
``sample.csv`` and in the report.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Iterable, Sequence

import numpy as np
import pandas as pd

from .aggregate import MODALITY_KEYS, OTHER_MODALITY, THEME_KEYS

# --------------------------------------------------------------------------
# Sampling design
# --------------------------------------------------------------------------

#: Round one's seed, against dictionaries v2. Kept so the round-one draw in
#: ``data/processed/validation/round1/`` can still be reproduced.
ROUND_ONE_SEED: Final[int] = 20260902

#: The current seed, against dictionaries v3. A fresh seed is not decoration:
#: the v3 patterns were written after reading round one's 200 papers, so that
#: sample has been fitted to and can no longer measure them.
DEFAULT_SEED: Final[int] = 20260903

#: Modalities too rare to appear in a theme-stratified sample by chance.
#: Together they hold about 1,900 papers, 4.2% of the corpus; without a
#: stratum of their own a 200-paper draw would carry one or two.
RARE_MODALITIES: Final[tuple[str, ...]] = (
    "spatial_proteomics",
    "spatial_transcriptomics",
    "pathology_report",
    "radiology_report",
    "xray",
)

#: Strata that are not one of the four-or-more themes.
NON_THEME_STRATA: Final[tuple[str, ...]] = ("rare_modality", "no_theme")

#: Strata, in the order a paper is tested against them. The list is a
#: **priority order**, not a preference: a paper joins the first stratum it
#: qualifies for and no other, so the strata partition the corpus and the
#: weights are well defined. Rarity decides the order — the scarcest categories
#: are claimed first, or they would be swallowed by the large ones.
#:
#: Every theme in :data:`trends.aggregate.THEME_KEYS` must appear here.
#: :func:`check_theme_coverage` enforces that at draw time and
#: ``tests/test_validate.py`` enforces it at test time, because the failure it
#: prevents is silent: a theme missing from this list does not raise, it simply
#: falls into ``no_theme`` and is never measured. That is exactly what happened
#: when ``virtual_staining`` was added at config v7.
STRATUM_ORDER: Final[tuple[str, ...]] = (
    "virtual_staining",
    "digital_twins",
    "clinical_fda",
    "rare_modality",
    "foundation_models",
    "multimodal_integration",
    "no_theme",
)

#: Papers drawn from each stratum. Sums to 225.
DEFAULT_SAMPLE_SIZES: Final[dict[str, int]] = {
    "virtual_staining": 25,
    "digital_twins": 25,
    "clinical_fda": 25,
    "rare_modality": 20,
    "foundation_models": 40,
    "multimodal_integration": 40,
    "no_theme": 50,
}


def check_theme_coverage(stratum_order: Iterable[str] = STRATUM_ORDER) -> None:
    """Refuse to draw a sample that cannot measure every theme.

    A theme absent from :data:`STRATUM_ORDER` does not crash anything. Its
    papers quietly join ``no_theme``, the draw succeeds, the report prints, and
    the theme is simply never measured. Loud is better.
    """
    missing = [k for k in THEME_KEYS if k not in set(stratum_order)]
    if missing:
        raise ValidationError(
            "these themes have no stratum and would never be measured: "
            + ", ".join(missing)
            + ". Add them to STRATUM_ORDER and DEFAULT_SAMPLE_SIZES."
        )

#: Rows in the author's audit sheet, by where they came from. The two halves
#: are never averaged together: the agreement half estimates how often the
#: agent and the author agree, the disagreement half asks who was right when
#: the rules and the agent split.
DEFAULT_AUDIT_SIZES: Final[dict[str, int]] = {
    "random": 25,
    "disagreement": 25,
}

#: Columns the agent's label sheet must carry, beyond the label columns.
#:
#: ``other_datatype`` is separate from ``mod_other`` on purpose. ``mod_other``
#: is the composite the classifier assigns, by either of two routes;
#: ``other_datatype`` is only the positive half of it — "this paper uses a data
#: type outside the fifteen named rows". Without the second column the two
#: routes cannot be scored apart. See :func:`score_other_routes`.
AGENT_META_COLUMNS: Final[tuple[str, ...]] = (
    "pmid",
    "uncertain",
    "other_datatype",
    "note",
)


class ValidationError(ValueError):
    """A validation input is missing, malformed, or inconsistent."""


def theme_columns(prefix: str = "theme_") -> tuple[str, ...]:
    """Theme label column names, in canonical order."""
    return tuple(f"{prefix}{key}" for key in THEME_KEYS)


def modality_columns(prefix: str = "mod_") -> tuple[str, ...]:
    """Modality label column names, in canonical order."""
    return tuple(f"{prefix}{key}" for key in MODALITY_KEYS)


def assign_strata(
    labels: pd.DataFrame,
    *,
    rare_modalities: Sequence[str] = RARE_MODALITIES,
) -> pd.Series:
    """Assign every paper in ``labels`` to exactly one stratum.

    ``labels`` is ``paper_labels.csv`` as written by :mod:`trends.classify`.
    The returned series is indexed like ``labels`` and takes values from
    :data:`STRATUM_ORDER`.

    A paper carrying two themes lands in the rarer stratum, by the priority in
    :data:`STRATUM_ORDER`. That is not a claim that the rarer theme is the
    paper's real subject; it is only how the partition is made. Precision and
    recall are computed across the whole sample with the stratum weights, so a
    theme is never measured from its own stratum alone.
    """
    missing = [c for c in theme_columns() if c not in labels.columns]
    missing += [f"mod_{m}" for m in rare_modalities if f"mod_{m}" not in labels.columns]
    if missing:
        raise ValidationError(
            "paper_labels.csv is missing label columns: " + ", ".join(sorted(missing))
        )

    check_theme_coverage()
    rare_hit = labels[[f"mod_{m}" for m in rare_modalities]].sum(axis=1) > 0
    # Theme tests are derived from the canonical keys rather than written out,
    # so adding a theme to the dictionaries cannot leave one behind here.
    tests = {key: labels[f"theme_{key}"] == 1 for key in THEME_KEYS}
    tests["rare_modality"] = rare_hit

    strata = pd.Series("no_theme", index=labels.index, dtype=object)
    claimed = pd.Series(False, index=labels.index)
    for name in STRATUM_ORDER:
        if name == "no_theme":
            continue
        selected = tests[name] & ~claimed
        strata[selected] = name
        claimed |= selected
    return strata


#: Round three's seed. Targeted, not a full draw: only the categories a
#: dictionary change touched.
ROUND_THREE_SEED: Final[int] = 20260904

#: The targeted strata of round three. Each is defined by a **rule-positive**
#: condition, which is what makes the draw cheap: judging one category on a
#: paper the rules already flagged costs a fraction of a full 19-label read.
#: The price is stated rather than hidden -- a rule-positive stratum can measure
#: precision and can never measure recall, because it contains no paper the
#: rules called negative.
TARGETED_STRATA: Final[dict[str, str]] = {
    "digital_twins": "theme_digital_twins == 1",
    "genomics_with_histology": "mod_genomics == 1 and mod_he_histology == 1",
    "genomics_alone": "mod_genomics == 1 and mod_he_histology == 0",
    "multimodal_integration": "theme_multimodal_integration == 1",
    "clinical_data": "mod_clinical_data == 1",
    "spatial_proteomics": "mod_spatial_proteomics == 1",
}

#: Which category each targeted stratum is drawn to measure.
TARGETED_CATEGORY: Final[dict[str, str]] = {
    "digital_twins": "digital_twins",
    "genomics_with_histology": "genomics",
    "genomics_alone": "genomics",
    "multimodal_integration": "multimodal_integration",
    "clinical_data": "clinical_data",
    "spatial_proteomics": "spatial_proteomics",
}


def draw_targeted_sample(
    labels: pd.DataFrame,
    sizes: dict[str, int],
    *,
    seed: int = ROUND_THREE_SEED,
    exclude: Iterable[str] = (),
) -> SampleDesign:
    """Draw a per-category sample for a targeted round.

    Unlike :func:`draw_sample` the strata here **overlap** -- a paper can be
    both multimodal and genomics -- so a paper is assigned to the first stratum
    in ``sizes`` that claims it, and the populations are counted after that
    assignment. The weights are therefore weights within the drawn design, not
    a partition of the corpus, and no corpus-wide projection is available from
    this design. That is acceptable: a targeted round reports per-category
    rates and nothing else.

    ``exclude`` removes papers already read in an earlier round. Re-reading a
    paper whose labels the reader remembers is not an independent measurement.
    """
    excluded = {str(p) for p in exclude}
    frame = labels.copy()
    frame["pmid"] = frame["pmid"].astype(str)
    frame = frame.loc[~frame["pmid"].isin(excluded)]
    frame = frame.sort_values("pmid", kind="mergesort").reset_index(drop=True)

    unknown = set(sizes) - set(TARGETED_STRATA)
    if unknown:
        raise ValidationError("unknown stratum in sizes: " + ", ".join(sorted(unknown)))

    claimed = pd.Series(False, index=frame.index)
    strata = pd.Series("", index=frame.index, dtype=object)
    for name in sizes:
        condition = TARGETED_STRATA[name]
        mask = pd.Series(True, index=frame.index)
        for clause in condition.split(" and "):
            column, value = clause.split(" == ")
            mask &= frame[column] == int(value)
        selected = mask & ~claimed
        strata[selected] = name
        claimed |= selected
    frame["stratum"] = strata

    populations = {name: int((frame["stratum"] == name).sum()) for name in sizes}
    seeds = np.random.SeedSequence(seed).spawn(len(sizes))
    drawn: list[pd.DataFrame] = []
    realized: dict[str, int] = {}
    for child, name in zip(seeds, sizes):
        pool = frame.loc[frame["stratum"] == name]
        want = min(int(sizes[name]), len(pool))
        realized[name] = want
        if want == 0:
            continue
        rng = np.random.default_rng(child)
        picks = np.sort(rng.choice(len(pool), size=want, replace=False))
        drawn.append(pool.iloc[picks])

    if not drawn:
        raise ValidationError(
            "no papers qualified for any requested stratum: "
            + ", ".join(f"{k}={populations[k]}" for k in sizes)
        )
    sample = pd.concat(drawn, ignore_index=True)
    sample["category"] = sample["stratum"].map(TARGETED_CATEGORY)
    sample["n_population"] = sample["stratum"].map(populations)
    sample["n_sampled"] = sample["stratum"].map(realized)
    sample["weight"] = sample["n_population"] / sample["n_sampled"]
    return SampleDesign(
        frame=sample, seed=seed, populations=populations, sizes=realized
    )


@dataclass(frozen=True)
class SampleDesign:
    """A drawn sample, with everything needed to reproduce and weight it."""

    frame: pd.DataFrame
    seed: int
    populations: dict[str, int]
    sizes: dict[str, int]

    @property
    def n(self) -> int:
        """Papers drawn."""
        return len(self.frame)


def draw_sample(
    labels: pd.DataFrame,
    *,
    seed: int = DEFAULT_SEED,
    sizes: dict[str, int] | None = None,
) -> SampleDesign:
    """Draw the stratified sample.

    Reproducible from ``seed`` alone. The frame is sorted by PMID before the
    draw, and each stratum is drawn in the fixed order of
    :data:`STRATUM_ORDER` from its own child of one seeded generator, so a
    change to one stratum's size cannot shift another stratum's picks.

    A stratum smaller than its requested size is taken whole, and the shortfall
    is recorded rather than made up elsewhere.
    """
    sizes = dict(DEFAULT_SAMPLE_SIZES if sizes is None else sizes)
    unknown = set(sizes) - set(STRATUM_ORDER)
    if unknown:
        raise ValidationError("unknown stratum in sizes: " + ", ".join(sorted(unknown)))

    frame = labels.copy()
    frame["stratum"] = assign_strata(frame)
    frame = frame.sort_values("pmid", kind="mergesort").reset_index(drop=True)

    populations = {
        name: int((frame["stratum"] == name).sum()) for name in STRATUM_ORDER
    }
    seeds = np.random.SeedSequence(seed).spawn(len(STRATUM_ORDER))

    drawn: list[pd.DataFrame] = []
    realized: dict[str, int] = {}
    for child, name in zip(seeds, STRATUM_ORDER):
        pool = frame.loc[frame["stratum"] == name]
        want = min(int(sizes.get(name, 0)), len(pool))
        realized[name] = want
        if want == 0:
            continue
        rng = np.random.default_rng(child)
        picks = rng.choice(len(pool), size=want, replace=False)
        picks.sort()
        drawn.append(pool.iloc[picks])

    sample = pd.concat(drawn, ignore_index=True)
    sample["n_population"] = sample["stratum"].map(populations)
    sample["n_sampled"] = sample["stratum"].map(realized)
    sample["weight"] = sample["n_population"] / sample["n_sampled"]
    return SampleDesign(
        frame=sample, seed=seed, populations=populations, sizes=realized
    )


def blind_sheet(
    design: SampleDesign,
    records: pd.DataFrame,
    *,
    seed: int | None = None,
) -> pd.DataFrame:
    """Build the sheet the labeling agent reads.

    Title and abstract, and nothing else. No stratum, no rule label, no
    modality hint, and the rows are shuffled from the same seed so that
    position carries no information either. Anchoring on the machine's answer
    would make the measurement circular, and the cheapest defense against it is
    to make the machine's answer unavailable.
    """
    seed = design.seed if seed is None else seed
    needed = {"pmid", "title", "abstract"}
    if not needed <= set(records.columns):
        raise ValidationError(
            "record table is missing " + ", ".join(sorted(needed - set(records.columns)))
        )

    text = records.loc[:, ["pmid", "title", "abstract"]].copy()
    text["pmid"] = text["pmid"].astype(str)
    sheet = design.frame[["pmid"]].merge(text, on="pmid", how="left", validate="1:1")
    if sheet["title"].isna().any():
        lost = sheet.loc[sheet["title"].isna(), "pmid"].tolist()
        raise ValidationError("sampled PMIDs absent from the record table: " + ", ".join(lost))

    rng = np.random.default_rng(np.random.SeedSequence(seed).spawn(8)[-1])
    order = rng.permutation(len(sheet))
    sheet = sheet.iloc[order].reset_index(drop=True)
    sheet.insert(0, "item", np.arange(1, len(sheet) + 1))
    sheet["abstract"] = sheet["abstract"].fillna("")
    sheet["has_abstract"] = (sheet["abstract"].str.len() > 0).astype(int)
    return sheet


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------


def refresh_rule_labels(sample: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """Re-read the rule labels for an already-drawn sample.

    The sample design and the system under test are different things. The
    strata, the seed, the weights and the sampled PMIDs are fixed at the moment
    of the draw and stay fixed; the rule labels are whatever the current
    dictionaries say. When the dictionaries move under a sample that has
    already been labeled -- as they did between v3 and v5 -- this refreshes the
    labels without redrawing, so the agent's blind labels stay valid and only
    the system's answers change.

    Redrawing instead would be wrong twice: it would discard the labeling work,
    and it would change which papers are in the sample, because the strata are
    defined by the rule labels themselves.

    Fails if any sampled PMID has left the corpus, because a silently dropped
    paper would change a denominator without changing the report.
    """
    label_cols = list(theme_columns()) + list(modality_columns())
    missing = [c for c in label_cols if c not in labels.columns]
    if missing:
        raise ValidationError("label table is missing columns: " + ", ".join(missing))

    fresh = labels.loc[:, ["pmid", *label_cols]].copy()
    fresh["pmid"] = fresh["pmid"].astype(str)
    keep = [c for c in sample.columns if c not in label_cols]
    refreshed = sample.loc[:, keep].copy()
    refreshed["pmid"] = refreshed["pmid"].astype(str)
    merged = refreshed.merge(fresh, on="pmid", how="left", validate="1:1")
    lost = merged.loc[merged[label_cols[0]].isna(), "pmid"].tolist()
    if lost:
        raise ValidationError(
            "sampled PMIDs absent from the label table: " + ", ".join(lost)
        )
    merged[label_cols] = merged[label_cols].astype(int)
    return merged


def read_agent_labels(path: str | Path) -> pd.DataFrame:
    """Read the agent's label sheet and check its shape.

    Every theme and modality column must be present and hold 0 or 1. The
    ``uncertain`` flag marks a paper the labeler could not call from the
    abstract; those papers keep a best-guess label and are reported apart. A
    recorded doubt is data. A coin flip is noise.
    """
    frame = pd.read_csv(path, dtype={"pmid": str}, comment="#")
    wanted = list(AGENT_META_COLUMNS) + list(theme_columns()) + list(modality_columns())
    missing = [c for c in wanted if c not in frame.columns]
    if missing:
        raise ValidationError(
            "agent label sheet is missing columns: " + ", ".join(missing)
        )
    label_cols = list(theme_columns()) + list(modality_columns())
    bad = frame[label_cols].isin([0, 1]).all(axis=1)
    if not bad.all():
        raise ValidationError(
            "agent labels must be 0 or 1; offending PMIDs: "
            + ", ".join(frame.loc[~bad, "pmid"].astype(str).tolist())
        )
    if frame["pmid"].duplicated().any():
        raise ValidationError("agent label sheet repeats a PMID")
    return frame[wanted]


def join_labels(
    design_frame: pd.DataFrame,
    agent: pd.DataFrame,
    *,
    rule_prefix: str = "rule_",
    agent_prefix: str = "agent_",
) -> pd.DataFrame:
    """Join rule labels to agent labels, one row per sampled paper.

    The ``theme_`` and ``mod_`` prefixes are dropped on the way in, so a
    category is addressed by its bare key on both sides: ``rule_mri`` against
    ``agent_mri``. The two key sets are disjoint, so nothing collides.

    Fails loudly when the two sets of PMIDs differ. A silently dropped paper
    would change a denominator without changing the report.
    """
    sample_ids = set(design_frame["pmid"].astype(str))
    agent_ids = set(agent["pmid"].astype(str))
    if sample_ids != agent_ids:
        only_sample = sorted(sample_ids - agent_ids)
        only_agent = sorted(agent_ids - sample_ids)
        raise ValidationError(
            f"sample and agent sheets disagree: {len(only_sample)} unlabeled "
            f"({only_sample[:5]}), {len(only_agent)} extra ({only_agent[:5]})"
        )

    label_cols = list(theme_columns()) + list(modality_columns())
    bare = {c: c.split("_", 1)[1] for c in label_cols}
    rules = design_frame.loc[
        :, ["pmid", "stratum", "n_population", "n_sampled", "weight", *label_cols]
    ].copy()
    rules["pmid"] = rules["pmid"].astype(str)
    rules = rules.rename(columns={c: f"{rule_prefix}{bare[c]}" for c in label_cols})

    mine = agent.copy()
    mine["pmid"] = mine["pmid"].astype(str)
    mine = mine.rename(columns={c: f"{agent_prefix}{bare[c]}" for c in label_cols})
    mine = mine.rename(
        columns={
            "uncertain": "agent_uncertain",
            "note": "agent_note",
            "other_datatype": "agent_other_datatype",
        }
    )

    return rules.merge(mine, on="pmid", how="inner", validate="1:1")


def _rate(numerator: float, denominator: float) -> float:
    return float("nan") if denominator == 0 else numerator / denominator


def wilson_interval(successes: float, trials: float, z: float = 1.96) -> tuple[float, float]:
    """A 95% Wilson score interval for a proportion.

    Wilson rather than the normal approximation because the denominators here
    are small and the proportions sit near 0 and 1, where the normal interval
    runs outside [0, 1] and understates the uncertainty. 17 of 25 is 68%, and
    the honest statement of it is 68% (49-83%).

    Returns ``(nan, nan)`` on an empty denominator, which is what a rate with no
    cases deserves.
    """
    if trials <= 0:
        return (float("nan"), float("nan"))
    p = successes / trials
    z2 = z * z
    denominator = 1 + z2 / trials
    centre = (p + z2 / (2 * trials)) / denominator
    spread = (
        z * ((p * (1 - p) / trials + z2 / (4 * trials * trials)) ** 0.5)
    ) / denominator
    return (max(0.0, centre - spread), min(1.0, centre + spread))


def confusion(
    joined: pd.DataFrame,
    column: str,
    *,
    system_prefix: str = "rule_",
    reference_prefix: str = "agent_",
    weighted: bool = False,
) -> dict[str, float]:
    """Confusion counts for one category.

    ``system_prefix`` is the labeler under test, ``reference_prefix`` the
    reference. With ``weighted`` the counts are sums of stratum weights and
    estimate corpus totals; without it they are papers in the sample.
    """
    system = joined[f"{system_prefix}{column}"].to_numpy() == 1
    reference = joined[f"{reference_prefix}{column}"].to_numpy() == 1
    w = joined["weight"].to_numpy() if weighted else np.ones(len(joined))

    tp = float(w[system & reference].sum())
    fp = float(w[system & ~reference].sum())
    fn = float(w[~system & reference].sum())
    tn = float(w[~system & ~reference].sum())
    precision = _rate(tp, tp + fp)
    recall = _rate(tp, tp + fn)
    f1 = _rate(2 * precision * recall, precision + recall) if tp else (
        float("nan") if (tp + fp + fn) == 0 else 0.0
    )
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def agreement_table(
    joined: pd.DataFrame,
    columns: Sequence[str],
    *,
    system_prefix: str = "rule_",
    reference_prefix: str = "agent_",
) -> pd.DataFrame:
    """Raw and weighted confusion, precision, recall and F1 for each category.

    One row per category. Raw columns carry the sample counts and a 95% Wilson
    interval on each rate; ``est_`` columns carry the weighted corpus estimates.
    Read the raw counts first: an ``est_`` figure resting on one or two sampled
    papers is arithmetic, not evidence. The intervals exist because several
    categories here have denominators in the single digits, and a bare
    percentage off 25 papers invites a reader to believe it to the point.
    """
    rows = []
    for column in columns:
        raw = confusion(
            joined, column, system_prefix=system_prefix, reference_prefix=reference_prefix
        )
        est = confusion(
            joined,
            column,
            system_prefix=system_prefix,
            reference_prefix=reference_prefix,
            weighted=True,
        )
        p_lo, p_hi = wilson_interval(raw["tp"], raw["tp"] + raw["fp"])
        r_lo, r_hi = wilson_interval(raw["tp"], raw["tp"] + raw["fn"])
        rows.append(
            {
                "category": column,
                "tp": int(raw["tp"]),
                "fp": int(raw["fp"]),
                "fn": int(raw["fn"]),
                "tn": int(raw["tn"]),
                "n_system": int(raw["tp"] + raw["fp"]),
                "n_reference": int(raw["tp"] + raw["fn"]),
                "precision": raw["precision"],
                "precision_lo": p_lo,
                "precision_hi": p_hi,
                "recall": raw["recall"],
                "recall_lo": r_lo,
                "recall_hi": r_hi,
                "f1": raw["f1"],
                "est_precision": est["precision"],
                "est_recall": est["recall"],
                "est_f1": est["f1"],
                "est_papers_system": est["tp"] + est["fp"],
                "est_papers_reference": est["tp"] + est["fn"],
            }
        )
    return pd.DataFrame(rows)


def disagreements(
    joined: pd.DataFrame,
    columns: Sequence[str],
    *,
    system_prefix: str = "rule_",
    reference_prefix: str = "agent_",
) -> pd.DataFrame:
    """One row per paper and category where the two labelers disagree."""
    rows = []
    for _, paper in joined.iterrows():
        for column in columns:
            system = int(paper[f"{system_prefix}{column}"])
            reference = int(paper[f"{reference_prefix}{column}"])
            if system == reference:
                continue
            rows.append(
                {
                    "pmid": paper["pmid"],
                    "stratum": paper["stratum"],
                    "category": column,
                    "rule": system,
                    "agent": reference,
                    "kind": "false_positive" if system else "false_negative",
                    "agent_uncertain": int(paper.get("agent_uncertain", 0)),
                }
            )
    return pd.DataFrame(
        rows, columns=["pmid", "stratum", "category", "rule", "agent", "kind", "agent_uncertain"]
    )


#: How a disagreement came about. Every disagreement is coded into exactly one
#: of these, so that a term-level defect (fixable by editing a pattern) is never
#: confused with the structural limit of matching words in an abstract.
CAUSE_CODES: Final[dict[str, str]] = {
    "mention_not_use": (
        "The term is in the abstract and the paper does not do the thing: a "
        "modality named as background, comparator or reference standard, or a "
        "concept named in a closing forward-looking clause. Not fixable by "
        "editing a term list."
    ),
    "term_defect": (
        "The pattern matched something lexically different from what it meant: "
        "an acronym collision, architectural vocabulary, the wrong assay class. "
        "Fixable, and worth reporting to the dictionary owner."
    ),
    "rule_gap": (
        "The paper does the thing and says so in words no pattern covers. A "
        "recall gap, fixable by adding a pattern."
    ),
    "definition_boundary": (
        "Both readings are defensible and the two labelers drew the line "
        "differently. Not a defect in either; a definition the project has to "
        "settle."
    ),
    "agent_error": "On re-reading, the reference label was wrong.",
}

#: The one cause that no dictionary edit can remove.
STRUCTURAL_CAUSE: Final[str] = "mention_not_use"


def other_routes(pattern_hits: str | Path, pmids: Iterable[str]) -> pd.Series:
    """Which route assigned ``other`` to each paper.

    ``other`` is additive and reaches a paper two ways, and they mean opposite
    things. A **pattern** match is a positive claim: this paper uses a data type
    outside the fifteen named rows. The **fallback** is an admission: no named
    modality was found, so ``other`` stands in for "we could not tell". Pooled,
    the row's precision is uninterpretable — half of it would be scoring a claim
    and half an absence of one. ``pattern_hits.csv`` distinguishes them with
    ``role = "fallback"``, and this reads it.

    Returns a series indexed by PMID with values ``pattern``, ``fallback``,
    ``both``, or ``none``.
    """
    wanted = {str(p) for p in pmids}
    hits = pd.read_csv(
        pattern_hits,
        dtype={"pmid": str},
        usecols=["pmid", "category", "role", "category_matched"],
    )
    hits = hits[
        hits["pmid"].isin(wanted)
        & (hits["category"] == OTHER_MODALITY)
        & (hits["category_matched"] == 1)
    ]
    routes = {}
    for pmid in wanted:
        roles = set(hits.loc[hits["pmid"] == pmid, "role"])
        by_pattern = bool(roles - {"fallback"})
        by_fallback = "fallback" in roles
        routes[pmid] = (
            "both"
            if by_pattern and by_fallback
            else "pattern"
            if by_pattern
            else "fallback"
            if by_fallback
            else "none"
        )
    return pd.Series(routes, name="other_route")


def score_other_routes(joined: pd.DataFrame) -> pd.DataFrame:
    """Score the two ``other`` routes as the different claims they are.

    Requires ``other_route`` on ``joined`` (from :func:`other_routes`) and two
    reference columns the labeler must supply separately:

    ``agent_other_datatype``
        The positive claim. The paper uses a data type outside the named rows.
    ``agent_named_any``
        Derived: the labeler named at least one of the fourteen named
        modalities.

    The pattern route is scored against the positive claim. The fallback route
    is scored against its own claim, which is that no named modality is there:
    it is right when the labeler also found none.
    """
    named = [f"agent_{k}" for k in MODALITY_KEYS if k != OTHER_MODALITY]
    found_named = joined[named].sum(axis=1) > 0
    rows = []

    by_pattern = joined["other_route"].isin(["pattern", "both"])
    claimed = joined.loc[by_pattern, "agent_other_datatype"] == 1
    rows.append(
        {
            "route": "pattern",
            "claim": "uses a data type outside the named rows",
            "n": int(by_pattern.sum()),
            "correct": int(claimed.sum()),
            "precision": _rate(int(claimed.sum()), int(by_pattern.sum())),
        }
    )

    by_fallback = joined["other_route"] == "fallback"
    right = ~found_named.loc[by_fallback]
    rows.append(
        {
            "route": "fallback",
            "claim": "no named modality could be identified",
            "n": int(by_fallback.sum()),
            "correct": int(right.sum()),
            "precision": _rate(int(right.sum()), int(by_fallback.sum())),
        }
    )

    frame = pd.DataFrame(rows)
    lo_hi = [wilson_interval(r.correct, r.n) for r in frame.itertuples()]
    frame["lo"] = [x[0] for x in lo_hi]
    frame["hi"] = [x[1] for x in lo_hi]
    return frame


def read_causes(path: str | Path, splits: pd.DataFrame) -> pd.DataFrame:
    """Read the hand-coded cause of every disagreement and check the coding.

    The coding is a judgment and it is recorded in a file rather than inferred,
    so a reader can disagree with a specific line. This refuses a coding that
    misses a disagreement, invents one, or uses a code outside
    :data:`CAUSE_CODES` — a partial coding would put a denominator in the report
    that no longer matches the disagreements it claims to explain.
    """
    frame = pd.read_csv(path, dtype={"pmid": str}, comment="#")
    missing = [c for c in ("pmid", "category", "cause") if c not in frame.columns]
    if missing:
        raise ValidationError("cause file is missing columns: " + ", ".join(missing))
    bad = sorted(set(frame["cause"]) - set(CAUSE_CODES))
    if bad:
        raise ValidationError("unknown cause code: " + ", ".join(bad))

    coded = set(zip(frame["pmid"], frame["category"]))
    actual = set(zip(splits["pmid"].astype(str), splits["category"]))
    if coded != actual:
        raise ValidationError(
            f"cause coding does not match the disagreements: "
            f"{len(actual - coded)} uncoded, {len(coded - actual)} spurious"
        )
    return frame


def summarize_causes(causes: pd.DataFrame, splits: pd.DataFrame) -> pd.DataFrame:
    """Count disagreements by cause and direction, with a share of the total.

    The row that matters is :data:`STRUCTURAL_CAUSE`. Its share is the share of
    all disagreement that no edit to the term dictionaries can remove.
    """
    # ``kind`` is taken from the disagreements, not from the coding file, so a
    # miscopied direction in the coding cannot change the reported split.
    merged = causes.drop(columns=["kind"], errors="ignore").merge(
        splits[["pmid", "category", "kind"]].astype({"pmid": str}),
        on=["pmid", "category"],
        how="left",
    )
    table = (
        merged.groupby(["cause", "kind"]).size().unstack(fill_value=0).reset_index()
    )
    for column in ("false_positive", "false_negative"):
        if column not in table.columns:
            table[column] = 0
    table["total"] = table["false_positive"] + table["false_negative"]
    table["share"] = table["total"] / table["total"].sum()
    return table.sort_values("total", ascending=False).reset_index(drop=True)


def exact_match_rate(joined: pd.DataFrame, columns: Sequence[str]) -> pd.Series:
    """Share of papers whose full label set the two labelers agree on.

    Strict: every one of ``columns`` must match. Reported per stratum, because
    a corpus-wide average over a stratified sample would mean nothing.
    """
    same = pd.Series(True, index=joined.index)
    for column in columns:
        same &= joined[f"rule_{column}"] == joined[f"agent_{column}"]
    return same.groupby(joined["stratum"]).agg(["sum", "count", "mean"])


# --------------------------------------------------------------------------
# Audit sheet
# --------------------------------------------------------------------------


def build_audit_sheet(
    joined: pd.DataFrame,
    records: pd.DataFrame,
    *,
    seed: int = DEFAULT_SEED,
    sizes: dict[str, int] | None = None,
) -> pd.DataFrame:
    """Draw the fifty papers the author audits.

    Half are drawn at random from the labeled sample and estimate how often the
    author and the agent agree at all. Half are drawn from the papers where the
    rules and the agent disagreed, and ask who was right. The two halves have
    completely different base rates, so ``audit_stratum`` marks every row and
    the two must never be pooled into one percentage.

    A paper drawn into the random half is not offered again to the
    disagreement half.
    """
    sizes = dict(DEFAULT_AUDIT_SIZES if sizes is None else sizes)
    columns = list(THEME_KEYS) + list(MODALITY_KEYS)

    pool = joined.sort_values("pmid", kind="mergesort").reset_index(drop=True)
    conflict = pd.Series(False, index=pool.index)
    for column in columns:
        conflict |= pool[f"rule_{column}"] != pool[f"agent_{column}"]

    child_random, child_conflict = np.random.SeedSequence(seed + 1).spawn(2)

    n_random = min(sizes.get("random", 0), len(pool))
    rng = np.random.default_rng(child_random)
    random_idx = np.sort(rng.choice(len(pool), size=n_random, replace=False))

    remaining = pool.index.difference(pool.index[random_idx])
    conflict_pool = pool.loc[remaining][conflict.loc[remaining]]
    n_conflict = min(sizes.get("disagreement", 0), len(conflict_pool))
    rng = np.random.default_rng(child_conflict)
    conflict_idx = np.sort(rng.choice(len(conflict_pool), size=n_conflict, replace=False))

    chosen = pd.concat(
        [
            pool.iloc[random_idx].assign(audit_stratum="random"),
            conflict_pool.iloc[conflict_idx].assign(audit_stratum="disagreement"),
        ],
        ignore_index=True,
    )

    text = records.loc[:, ["pmid", "title", "abstract"]].copy()
    text["pmid"] = text["pmid"].astype(str)
    sheet = chosen.merge(text, on="pmid", how="left", validate="1:1")
    sheet["abstract"] = sheet["abstract"].fillna("")

    sheet["n_disagreements"] = sum(
        (sheet[f"rule_{c}"] != sheet[f"agent_{c}"]).astype(int) for c in columns
    )
    sheet["agent_themes"] = _label_string(sheet, "agent_", THEME_KEYS)
    sheet["rule_themes"] = _label_string(sheet, "rule_", THEME_KEYS)
    sheet["agent_modalities"] = _label_string(sheet, "agent_", MODALITY_KEYS)
    sheet["rule_modalities"] = _label_string(sheet, "rule_", MODALITY_KEYS)
    sheet["disagreed_on"] = _disagreement_string(sheet, columns)

    # Blank columns for the author. `author_themes` and `author_modalities`
    # take the same `+`-joined key strings the two label columns use, so the
    # author can copy one across and edit it rather than retyping.
    sheet["author_themes"] = ""
    sheet["author_modalities"] = ""
    sheet["author_verdict"] = ""
    sheet["author_note"] = ""

    ordered = [
        "audit_stratum",
        "pmid",
        "stratum",
        "n_disagreements",
        "disagreed_on",
        "title",
        "abstract",
        "agent_themes",
        "rule_themes",
        "agent_modalities",
        "rule_modalities",
        "agent_uncertain",
        "agent_note",
        "author_themes",
        "author_modalities",
        "author_verdict",
        "author_note",
    ]
    return sheet.loc[:, ordered].sort_values(
        ["audit_stratum", "pmid"], kind="mergesort"
    ).reset_index(drop=True)


def _label_string(frame: pd.DataFrame, prefix: str, keys: Sequence[str]) -> pd.Series:
    """Render a row's 0/1 label columns as a ``+``-joined key string."""

    def render(row: pd.Series) -> str:
        hits = [k for k in keys if int(row[f"{prefix}{k}"]) == 1]
        return "+".join(hits) if hits else "(none)"

    return frame.apply(render, axis=1)


def _disagreement_string(frame: pd.DataFrame, keys: Sequence[str]) -> pd.Series:
    """Name the categories a row's two labelers split on, with the direction."""

    def render(row: pd.Series) -> str:
        parts = []
        for key in keys:
            rule, agent = int(row[f"rule_{key}"]), int(row[f"agent_{key}"])
            if rule != agent:
                parts.append(f"{key}:{'rule-only' if rule else 'agent-only'}")
        return "; ".join(parts) if parts else "(none)"

    return frame.apply(render, axis=1)


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------


def _pct(value: float) -> str:
    return "   n/a" if value != value else f"{value * 100:5.1f}%"


def _interval(value: float, low: float, high: float) -> str:
    """A rate and its 95% interval, or ``n/a`` when there were no cases."""
    if value != value:
        return "n/a"
    return f"{value * 100:.0f}% ({low * 100:.0f}-{high * 100:.0f}%)"


def format_report(
    design: SampleDesign,
    joined: pd.DataFrame,
    themes: pd.DataFrame,
    modalities: pd.DataFrame,
    *,
    routes: pd.DataFrame | None = None,
    causes: pd.DataFrame | None = None,
    min_denominator: int = 10,
) -> str:
    """The human-readable agreement report.

    Every percentage is printed beside the count it came from, and a rate
    resting on fewer than ``min_denominator`` cases is flagged with ``!``. That
    marker is the whole point of the column: several themes in this corpus have
    denominators in the single digits and no amount of decimal places changes
    that.
    """
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "CLASSIFIER AGREEMENT REPORT",
        "=" * 78,
        f"generated_utc   : {generated}",
        f"seed            : {design.seed}",
        f"sample          : {design.n} papers in {len(design.sizes)} strata",
        f"reference       : agent labels, blind to the rule labels",
        f"system          : rule-based classifier, config/*.yaml v2",
        "",
        "STRATA",
        "-" * 78,
        f"{'stratum':<24}{'population':>12}{'sampled':>9}{'weight':>10}",
    ]
    for name in STRATUM_ORDER:
        n_pop = design.populations.get(name, 0)
        n_draw = design.sizes.get(name, 0)
        weight = n_pop / n_draw if n_draw else float("nan")
        lines.append(f"{name:<24}{n_pop:>12,}{n_draw:>9}{weight:>10.1f}")
    lines.append(f"{'total':<24}{sum(design.populations.values()):>12,}{design.n:>9}")

    uncertain = int(joined["agent_uncertain"].sum())
    lines += [
        "",
        f"papers the agent flagged uncertain: {uncertain} of {len(joined)}",
        "",
    ]

    for title, table in (("THEMES", themes), ("MODALITIES", modalities)):
        lines += [
            title,
            "-" * 78,
            f"{'category':<24}{'TP':>4}{'FP':>4}{'FN':>4}"
            f"{'precision (95% CI)':>22}{'recall (95% CI)':>22}",
        ]
        for _, row in table.iterrows():
            thin = (
                "!"
                if row["n_reference"] < min_denominator
                or row["n_system"] < min_denominator
                else " "
            )
            lines.append(
                f"{row['category']:<24}{row['tp']:>4}{row['fp']:>4}{row['fn']:>4}"
                f"{_interval(row['precision'], row['precision_lo'], row['precision_hi']):>22}"
                f"{_interval(row['recall'], row['recall_lo'], row['recall_hi']):>22}"
                f" {thin}"
            )
        lines.append("")
    lines += [
        f"! marks a rate resting on fewer than {min_denominator} papers on one side.",
        "  Read the counts and the interval, not the percentage.",
        "  Intervals are 95% Wilson score intervals on the sample counts. They",
        "  cover sampling error only, not the risk that the reference labels are",
        "  themselves wrong.",
        "",
        "EXACT LABEL-SET AGREEMENT, per stratum",
        "-" * 78,
        "Every theme and every modality identical. A strict test: 19 binary",
        "labels must all match.",
    ]
    exact = exact_match_rate(joined, list(THEME_KEYS) + list(MODALITY_KEYS))
    for stratum, row in exact.iterrows():
        lines.append(
            f"{stratum:<24}{int(row['sum']):>5} of {int(row['count']):>3}   {_pct(row['mean'])}"
        )

    if routes is not None:
        lines += [
            "",
            "THE TWO ROUTES TO `other`",
            "-" * 78,
            "A pattern match claims an out-of-row data type. The fallback claims",
            "only that no named modality was found. Scored apart, because pooled",
            "they measure nothing.",
        ]
        for _, row in routes.iterrows():
            lines.append(
                f"{row['route']:<10}{row['correct']:>4} of {row['n']:>3}   "
                f"{_interval(row['precision'], row['lo'], row['hi'])}   {row['claim']}"
            )

    if causes is not None:
        total = int(causes["total"].sum())
        lines += [
            "",
            "WHY THEY DISAGREE",
            "-" * 78,
            f"Every one of the {total} disagreements coded into one cause.",
            f"{'cause':<22}{'FP':>5}{'FN':>5}{'total':>7}{'share':>8}",
        ]
        for _, row in causes.iterrows():
            lines.append(
                f"{row['cause']:<22}{int(row['false_positive']):>5}"
                f"{int(row['false_negative']):>5}{int(row['total']):>7}"
                f"{row['share'] * 100:>7.1f}%"
            )
        structural = causes.loc[causes["cause"] == STRUCTURAL_CAUSE, "share"]
        if len(structural):
            lines += [
                "",
                f"{float(structural.iloc[0]) * 100:.0f}% of all disagreement is "
                "mention-versus-use, which no",
                "edit to a term list can remove.",
            ]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------


def _read_labels(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path, comment="#", dtype={"pmid": str})
    if "pmid" not in frame.columns:
        raise ValidationError(f"{path} has no pmid column")
    return frame


def _read_records(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix == ".parquet":
        frame = pd.read_parquet(path, columns=["pmid", "title", "abstract"])
    else:
        frame = pd.read_csv(path, dtype={"pmid": str}, usecols=["pmid", "title", "abstract"])
    frame["pmid"] = frame["pmid"].astype(str)
    return frame.drop_duplicates("pmid")


def _write(frame: pd.DataFrame, path: Path, header: Iterable[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        for line in header:
            handle.write(f"# {line}\n")
        frame.to_csv(handle, index=False)
    return path


def cmd_sample(args: argparse.Namespace) -> int:
    labels = _read_labels(args.labels)
    records = _read_records(args.records)
    design = draw_sample(labels, seed=args.seed)
    sheet = blind_sheet(design, records)

    out = Path(args.output)
    header = [
        "file: sample.csv",
        f"seed: {design.seed}",
        f"labels: {args.labels}",
        f"strata: {json.dumps(design.sizes)}",
        f"populations: {json.dumps(design.populations)}",
    ]
    _write(design.frame, out / "sample.csv", header)
    _write(
        sheet,
        out / "blind_sheet.csv",
        [
            "file: blind_sheet.csv",
            "The labeling sheet. Title and abstract only: no rule label, no",
            "stratum, and the row order is shuffled from the seed.",
            f"seed: {design.seed}",
        ],
    )
    print(f"{design.n} papers drawn, seed {design.seed}")
    for name in STRATUM_ORDER:
        print(f"  {name:<24}{design.sizes.get(name, 0):>4} of {design.populations.get(name, 0):>7,}")
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    sample = pd.read_csv(args.sample, comment="#", dtype={"pmid": str})
    if args.labels:
        sample = refresh_rule_labels(sample, _read_labels(args.labels))
    agent = read_agent_labels(args.agent)
    joined = join_labels(sample, agent)

    populations = {
        name: int(sample.loc[sample["stratum"] == name, "n_population"].iloc[0])
        if (sample["stratum"] == name).any()
        else 0
        for name in STRATUM_ORDER
    }
    sizes = {name: int((sample["stratum"] == name).sum()) for name in STRATUM_ORDER}
    design = SampleDesign(
        frame=sample, seed=args.seed, populations=populations, sizes=sizes
    )

    if args.pattern_hits:
        joined = joined.join(
            other_routes(args.pattern_hits, joined["pmid"]), on="pmid"
        )

    themes = agreement_table(joined, THEME_KEYS)
    modalities = agreement_table(joined, MODALITY_KEYS)
    splits = disagreements(joined, list(THEME_KEYS) + list(MODALITY_KEYS))

    routes = (
        score_other_routes(joined) if "other_route" in joined.columns else None
    )
    causes = None
    if args.causes and Path(args.causes).exists():
        causes = summarize_causes(read_causes(args.causes, splits), splits)

    out = Path(args.output)
    _write(joined, out / "joined_labels.csv", ["file: joined_labels.csv", f"seed: {args.seed}"])
    _write(themes, out / "agreement_themes.csv", ["file: agreement_themes.csv"])
    _write(modalities, out / "agreement_modalities.csv", ["file: agreement_modalities.csv"])
    _write(splits, out / "disagreements.csv", ["file: disagreements.csv"])
    if routes is not None:
        _write(
            routes,
            out / "other_routes.csv",
            [
                "file: other_routes.csv",
                "The two routes to `other` scored as the different claims they",
                "are: a pattern match asserts an out-of-row data type, the",
                "fallback admits that no named modality was found.",
            ],
        )
    if causes is not None:
        _write(causes, out / "cause_summary.csv", ["file: cause_summary.csv"])
    report = format_report(design, joined, themes, modalities, routes=routes, causes=causes)
    (out / "agreement_report.txt").write_text(report, encoding="utf-8")
    print(report)
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    joined = pd.read_csv(args.joined, comment="#", dtype={"pmid": str})
    records = _read_records(args.records)
    sheet = build_audit_sheet(joined, records, seed=args.seed)
    out = Path(args.output)
    _write(
        sheet,
        out / "audit_sheet.csv",
        [
            "file: audit_sheet.csv",
            "50 rows for the author. audit_stratum says which half a row came",
            "from: `random` estimates agent-author agreement, `disagreement`",
            "asks who was right. Never average the two.",
            "Fill in author_themes, author_modalities, author_verdict,",
            "author_note. Instructions: docs/validation.md.",
            f"seed: {args.seed}",
        ],
    )
    print(sheet["audit_stratum"].value_counts().to_string())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m trends.validate",
        description="Draw, score, and audit the classifier validation sample.",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="random seed")
    subs = parser.add_subparsers(dest="command", required=True)

    p = subs.add_parser("sample", help="draw the stratified sample and the blind sheet")
    p.add_argument("--labels", default="data/processed/paper_labels.csv")
    p.add_argument("--records", default="data/interim/records.parquet")
    p.add_argument("--output", default="data/processed/validation/")
    p.set_defaults(func=cmd_sample)

    p = subs.add_parser("score", help="score the rules against the agent labels")
    p.add_argument("--sample", default="data/processed/validation/sample.csv")
    p.add_argument("--agent", default="data/processed/validation/agent_labels.csv")
    p.add_argument("--output", default="data/processed/validation/")
    p.add_argument(
        "--pattern-hits",
        default="data/processed/pattern_hits.csv",
        help="provenance table, read only to split the two `other` routes",
    )
    p.add_argument(
        "--causes",
        default="data/processed/validation/disagreement_causes.csv",
        help="hand-coded cause per disagreement; skipped when absent",
    )
    p.add_argument(
        "--labels",
        default=None,
        help=(
            "re-read the rule labels for the already-drawn sample from this "
            "table, keeping the draw. Use after the dictionaries change under "
            "a sample that has already been labeled."
        ),
    )
    p.set_defaults(func=cmd_score)

    p = subs.add_parser("audit", help="build the author's 50-row audit sheet")
    p.add_argument("--joined", default="data/processed/validation/joined_labels.csv")
    p.add_argument("--records", default="data/interim/records.parquet")
    p.add_argument("--output", default="data/processed/validation/")
    p.set_defaults(func=cmd_audit)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except ValidationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
