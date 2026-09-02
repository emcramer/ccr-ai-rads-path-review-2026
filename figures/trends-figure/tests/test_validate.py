"""Tests for :mod:`trends.validate`.

Two things here have to be true or the validation number means nothing.

**The draw must be reproducible from the seed.** ``docs/validation.md`` reports
a sample; a reader who cannot redraw it cannot check anything. So the seed is
pinned, and a test asserts that the same seed gives the same PMIDs and that a
different one does not.

**The arithmetic must be right.** Precision and recall are computed on
hand-built frames whose answers can be read off by eye, not on the real sample,
so a change to the scoring code fails here rather than silently moving a
published percentage.

Nothing in this file touches the corpus, the real labels, or the network.
"""

from __future__ import annotations

import pandas as pd
import pytest

from trends.aggregate import MODALITY_KEYS, THEME_KEYS
from trends.validate import (
    CAUSE_CODES,
    DEFAULT_SAMPLE_SIZES,
    NON_THEME_STRATA,
    DEFAULT_SEED,
    ROUND_ONE_SEED,
    ROUND_THREE_SEED,
    STRUCTURAL_CAUSE,
    TARGETED_CATEGORY,
    TARGETED_STRATA,
    RARE_MODALITIES,
    STRATUM_ORDER,
    SampleDesign,
    ValidationError,
    agreement_table,
    assign_strata,
    blind_sheet,
    build_audit_sheet,
    check_theme_coverage,
    confusion,
    disagreements,
    draw_sample,
    draw_targeted_sample,
    exact_match_rate,
    join_labels,
    modality_columns,
    other_routes,
    read_agent_labels,
    read_causes,
    refresh_rule_labels,
    score_other_routes,
    summarize_causes,
    wilson_interval,
    theme_columns,
)

LABEL_COLUMNS = list(theme_columns()) + list(modality_columns())


def make_labels(n: int = 600) -> pd.DataFrame:
    """A synthetic label table with every stratum populated.

    Deterministic and hand-shaped rather than random, so a stratum's size is a
    number this file states rather than one a generator happened to produce.
    """
    rows = []
    for i in range(n):
        row = {"pmid": f"{100000 + i}", "year": 2015 + i % 11}
        for column in LABEL_COLUMNS:
            row[column] = 0
        if i < 12:
            row["theme_digital_twins"] = 1
        elif i < 30:
            row["theme_clinical_fda"] = 1
        elif i < 60:
            row["mod_spatial_proteomics"] = 1
        elif i < 140:
            row["theme_foundation_models"] = 1
            row["mod_he_histology"] = 1
            row["mod_genomics"] = 1  # a genomics/histology co-occurrence
        elif i < 300:
            row["theme_multimodal_integration"] = 1
            row["mod_mri"] = 1
        else:
            row["mod_ct"] = 1
            row["mod_clinical_data"] = 1
            if i % 3 == 0:
                row["mod_genomics"] = 1  # genomics without histology
        rows.append(row)
    return pd.DataFrame(rows)


SIZES = {
    "digital_twins": 6,
    "clinical_fda": 9,
    "rare_modality": 10,
    "foundation_models": 20,
    "multimodal_integration": 20,
    "no_theme": 25,
}


# --------------------------------------------------------------------------
# Strata
# --------------------------------------------------------------------------


def test_strata_partition_the_corpus():
    labels = make_labels()
    strata = assign_strata(labels)
    assert len(strata) == len(labels)
    assert set(strata.unique()) <= set(STRATUM_ORDER)
    assert strata.value_counts().sum() == len(labels)


def test_priority_order_claims_the_rarest_stratum_first():
    """A paper carrying two themes joins the rarer one, and only that one."""
    labels = make_labels(10)
    labels[LABEL_COLUMNS] = 0
    labels.loc[0, "theme_digital_twins"] = 1
    labels.loc[0, "theme_multimodal_integration"] = 1
    labels.loc[1, "theme_clinical_fda"] = 1
    labels.loc[1, "theme_foundation_models"] = 1
    strata = assign_strata(labels)
    assert strata.iloc[0] == "digital_twins"
    assert strata.iloc[1] == "clinical_fda"


def test_rare_modality_stratum_catches_every_rare_row():
    labels = make_labels(20)
    labels[LABEL_COLUMNS] = 0
    labels.loc[5, "mod_radiology_report"] = 1
    strata = assign_strata(labels)
    assert strata.iloc[5] == "rare_modality"


def test_missing_label_column_is_named_not_guessed():
    labels = make_labels(5).drop(columns=["theme_digital_twins"])
    with pytest.raises(ValidationError, match="theme_digital_twins"):
        assign_strata(labels)


# --------------------------------------------------------------------------
# The draw
# --------------------------------------------------------------------------


def test_same_seed_gives_the_same_papers():
    labels = make_labels()
    first = draw_sample(labels, seed=7, sizes=SIZES)
    second = draw_sample(labels, seed=7, sizes=SIZES)
    assert list(first.frame["pmid"]) == list(second.frame["pmid"])


def test_a_different_seed_gives_different_papers():
    labels = make_labels()
    first = draw_sample(labels, seed=7, sizes=SIZES)
    other = draw_sample(labels, seed=8, sizes=SIZES)
    assert set(first.frame["pmid"]) != set(other.frame["pmid"])


def test_row_order_of_the_input_does_not_change_the_draw():
    """The frame is sorted by PMID first, so an upstream re-sort is harmless."""
    labels = make_labels()
    shuffled = labels.iloc[::-1].reset_index(drop=True)
    assert list(draw_sample(labels, seed=7, sizes=SIZES).frame["pmid"]) == list(
        draw_sample(shuffled, seed=7, sizes=SIZES).frame["pmid"]
    )


def test_resizing_one_stratum_leaves_the_others_alone():
    """Each stratum draws from its own spawned generator, so the strata are
    independent. Without that, adding five digital-twin papers would silently
    replace the papers already labeled in every other stratum."""
    labels = make_labels()
    base = draw_sample(labels, seed=7, sizes=SIZES)
    bigger = draw_sample(labels, seed=7, sizes={**SIZES, "digital_twins": 10})
    for stratum in STRATUM_ORDER:
        if stratum == "digital_twins":
            continue
        a = set(base.frame.loc[base.frame["stratum"] == stratum, "pmid"])
        b = set(bigger.frame.loc[bigger.frame["stratum"] == stratum, "pmid"])
        assert a == b


def test_sizes_and_weights():
    labels = make_labels()
    design = draw_sample(labels, seed=7, sizes=SIZES)
    assert design.n == sum(SIZES.values())
    counts = design.frame["stratum"].value_counts().to_dict()
    assert counts == SIZES
    row = design.frame.iloc[0]
    assert row["weight"] == pytest.approx(row["n_population"] / row["n_sampled"])


def test_a_stratum_smaller_than_its_request_is_taken_whole():
    labels = make_labels()
    design = draw_sample(labels, seed=7, sizes={**SIZES, "digital_twins": 99})
    assert design.sizes["digital_twins"] == design.populations["digital_twins"] == 12


def test_default_sizes_cover_every_stratum():
    assert sum(DEFAULT_SAMPLE_SIZES.values()) == 225
    assert set(DEFAULT_SAMPLE_SIZES) == set(STRATUM_ORDER)


def test_every_canonical_theme_has_a_stratum():
    """The failure this guards is silent. A theme missing from STRATUM_ORDER
    does not raise: its papers join `no_theme` and are never measured. That is
    what happened when `virtual_staining` arrived at config v7."""
    for key in THEME_KEYS:
        assert key in STRATUM_ORDER, f"{key} has no stratum and cannot be measured"
    check_theme_coverage()


def test_a_theme_without_a_stratum_is_refused_by_name():
    short = tuple(s for s in STRATUM_ORDER if s != "virtual_staining")
    with pytest.raises(ValidationError, match="virtual_staining"):
        check_theme_coverage(short)


def test_the_non_theme_strata_are_not_themes():
    assert not set(NON_THEME_STRATA) & set(THEME_KEYS)
    assert set(STRATUM_ORDER) == set(THEME_KEYS) | set(NON_THEME_STRATA)


def test_unknown_stratum_is_refused():
    with pytest.raises(ValidationError, match="pathology_only"):
        draw_sample(make_labels(), seed=7, sizes={"pathology_only": 5})


# --------------------------------------------------------------------------
# The blind sheet
# --------------------------------------------------------------------------


def make_records(labels: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "pmid": labels["pmid"],
            "title": ["title " + p for p in labels["pmid"]],
            "abstract": ["abstract " + p for p in labels["pmid"]],
        }
    )


def test_blind_sheet_leaks_nothing():
    """No label, no stratum, no weight. This is the whole point of the file:
    a labeler who can see the rules' answer is not an independent reference."""
    labels = make_labels()
    design = draw_sample(labels, seed=7, sizes=SIZES)
    sheet = blind_sheet(design, make_records(labels))
    assert set(sheet.columns) == {"item", "pmid", "title", "abstract", "has_abstract"}
    assert len(sheet) == design.n


def test_blind_sheet_is_shuffled_so_position_carries_nothing():
    labels = make_labels()
    design = draw_sample(labels, seed=7, sizes=SIZES)
    sheet = blind_sheet(design, make_records(labels))
    assert list(sheet["pmid"]) != list(design.frame["pmid"])
    assert set(sheet["pmid"]) == set(design.frame["pmid"])


def test_blind_sheet_refuses_a_pmid_it_has_no_text_for():
    labels = make_labels()
    design = draw_sample(labels, seed=7, sizes=SIZES)
    records = make_records(labels).iloc[5:]
    with pytest.raises(ValidationError, match="absent from the record table"):
        blind_sheet(design, records)


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------


def scored_frame() -> pd.DataFrame:
    """Four papers, two strata, one category, every cell of the matrix used.

    Weights are 10 and 1, so a weighted figure differs visibly from a raw one.
    """
    return pd.DataFrame(
        {
            "pmid": ["1", "2", "3", "4"],
            "stratum": ["a", "a", "b", "b"],
            "weight": [10.0, 10.0, 1.0, 1.0],
            "rule_mri": [1, 1, 0, 0],
            "agent_mri": [1, 0, 1, 0],
            "agent_uncertain": [0, 0, 0, 0],
        }
    )


def test_confusion_counts():
    counts = confusion(scored_frame(), "mri")
    assert (counts["tp"], counts["fp"], counts["fn"], counts["tn"]) == (1, 1, 1, 1)
    assert counts["precision"] == pytest.approx(0.5)
    assert counts["recall"] == pytest.approx(0.5)
    assert counts["f1"] == pytest.approx(0.5)


def test_weighted_confusion_uses_the_stratum_weights():
    counts = confusion(scored_frame(), "mri", weighted=True)
    assert (counts["tp"], counts["fp"], counts["fn"]) == (10.0, 10.0, 1.0)
    assert counts["precision"] == pytest.approx(0.5)
    assert counts["recall"] == pytest.approx(10 / 11)


def test_precision_is_nan_when_the_system_never_fired():
    frame = scored_frame()
    frame["rule_mri"] = 0
    counts = confusion(frame, "mri")
    assert counts["precision"] != counts["precision"]  # NaN
    assert counts["recall"] == pytest.approx(0.0)


def test_f1_is_zero_when_the_two_labelers_never_agree():
    frame = scored_frame()
    frame["rule_mri"] = [1, 1, 0, 0]
    frame["agent_mri"] = [0, 0, 1, 1]
    counts = confusion(frame, "mri")
    assert counts["tp"] == 0
    assert counts["f1"] == pytest.approx(0.0)


def test_agreement_table_reports_both_denominators():
    table = agreement_table(scored_frame(), ["mri"]).iloc[0]
    assert table["n_system"] == 2
    assert table["n_reference"] == 2
    assert table["precision"] == pytest.approx(0.5)
    assert table["est_recall"] == pytest.approx(10 / 11)


def test_exact_match_rate_is_reported_per_stratum():
    frame = scored_frame()
    rates = exact_match_rate(frame, ["mri"])
    assert rates.loc["a", "sum"] == 1
    assert rates.loc["b", "mean"] == pytest.approx(0.5)


# --------------------------------------------------------------------------
# Joining and reading
# --------------------------------------------------------------------------


def agent_sheet(labels: pd.DataFrame) -> pd.DataFrame:
    frame = labels.loc[:, ["pmid", *LABEL_COLUMNS]].copy()
    frame["uncertain"] = 0
    frame["other_datatype"] = frame["mod_other"]
    frame["note"] = ""
    return frame


def test_join_refuses_a_partly_labeled_sample():
    labels = make_labels()
    design = draw_sample(labels, seed=7, sizes=SIZES)
    partial = agent_sheet(design.frame).iloc[:-1]
    with pytest.raises(ValidationError, match="disagree"):
        join_labels(design.frame, partial)


def test_join_puts_both_labelers_side_by_side():
    labels = make_labels()
    design = draw_sample(labels, seed=7, sizes=SIZES)
    joined = join_labels(design.frame, agent_sheet(design.frame))
    assert len(joined) == design.n
    for key in list(THEME_KEYS) + list(MODALITY_KEYS):
        assert f"rule_{key}" in joined.columns
        assert f"agent_{key}" in joined.columns
    assert "weight" in joined.columns


def test_agent_sheet_must_be_binary(tmp_path):
    labels = make_labels(3)
    frame = agent_sheet(labels)
    frame.loc[1, "theme_digital_twins"] = 2
    path = tmp_path / "agent.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(ValidationError, match="must be 0 or 1"):
        read_agent_labels(path)


def test_agent_sheet_must_not_repeat_a_paper(tmp_path):
    labels = make_labels(3)
    frame = pd.concat([agent_sheet(labels), agent_sheet(labels).iloc[:1]])
    path = tmp_path / "agent.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(ValidationError, match="repeats a PMID"):
        read_agent_labels(path)


def test_agent_sheet_must_carry_every_category(tmp_path):
    labels = make_labels(3)
    frame = agent_sheet(labels).drop(columns=["mod_pet"])
    path = tmp_path / "agent.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(ValidationError, match="mod_pet"):
        read_agent_labels(path)


# --------------------------------------------------------------------------
# The audit sheet
# --------------------------------------------------------------------------


def joined_with_disagreements() -> pd.DataFrame:
    labels = make_labels()
    design = draw_sample(labels, seed=7, sizes=SIZES)
    agent = agent_sheet(design.frame)
    # Flip one modality on every third paper, so a disagreement pool exists.
    flip = agent.index[::3]
    agent.loc[flip, "mod_ct"] = 1 - agent.loc[flip, "mod_ct"]
    return join_labels(design.frame, agent)


def test_audit_sheet_splits_the_two_halves_and_never_pools_them():
    joined = joined_with_disagreements()
    sheet = build_audit_sheet(
        joined, make_records(make_labels()), seed=7, sizes={"random": 10, "disagreement": 10}
    )
    assert len(sheet) == 20
    assert sheet["audit_stratum"].value_counts().to_dict() == {
        "random": 10,
        "disagreement": 10,
    }
    assert not sheet["pmid"].duplicated().any()


def test_every_disagreement_row_actually_disagrees():
    joined = joined_with_disagreements()
    sheet = build_audit_sheet(
        joined, make_records(make_labels()), seed=7, sizes={"random": 10, "disagreement": 10}
    )
    conflicts = sheet.loc[sheet["audit_stratum"] == "disagreement"]
    assert (conflicts["n_disagreements"] > 0).all()
    assert (conflicts["disagreed_on"] != "(none)").all()


def test_audit_sheet_leaves_the_author_columns_blank():
    joined = joined_with_disagreements()
    sheet = build_audit_sheet(
        joined, make_records(make_labels()), seed=7, sizes={"random": 10, "disagreement": 10}
    )
    for column in ("author_themes", "author_modalities", "author_verdict", "author_note"):
        assert (sheet[column] == "").all()
    assert {"title", "abstract"} <= set(sheet.columns)


def test_audit_sheet_is_reproducible():
    joined = joined_with_disagreements()
    records = make_records(make_labels())
    sizes = {"random": 10, "disagreement": 10}
    first = build_audit_sheet(joined, records, seed=7, sizes=sizes)
    second = build_audit_sheet(joined, records, seed=7, sizes=sizes)
    assert list(first["pmid"]) == list(second["pmid"])


def test_sample_design_reports_its_own_size():
    labels = make_labels()
    design = draw_sample(labels, seed=7, sizes=SIZES)
    assert isinstance(design, SampleDesign)
    assert design.n == len(design.frame)


# --------------------------------------------------------------------------
# Round two: intervals, the two `other` routes, and cause coding
# --------------------------------------------------------------------------


def test_wilson_interval_brackets_the_point_estimate():
    low, high = wilson_interval(17, 25)
    assert low < 17 / 25 < high
    assert (round(low, 2), round(high, 2)) == (0.48, 0.83)


def test_wilson_interval_is_wider_on_fewer_cases():
    narrow = wilson_interval(80, 100)
    wide = wilson_interval(8, 10)
    assert (wide[1] - wide[0]) > (narrow[1] - narrow[0])


def test_wilson_interval_stays_inside_the_unit_interval():
    """The reason for Wilson rather than the normal approximation: at 7 of 7
    the normal interval runs above 1, which is not a probability."""
    low, high = wilson_interval(7, 7)
    assert 0.0 <= low <= 1.0 and high == 1.0
    assert low > 0.5


def test_wilson_interval_of_an_empty_denominator_is_not_a_number():
    low, high = wilson_interval(0, 0)
    assert low != low and high != high


def test_agreement_table_carries_the_intervals():
    row = agreement_table(scored_frame(), ["mri"]).iloc[0]
    assert row["precision_lo"] < row["precision"] < row["precision_hi"]
    assert row["recall_lo"] < row["recall"] < row["recall_hi"]


def test_other_routes_reads_the_fallback_marker(tmp_path):
    """`role = "fallback"` is what tells an admission from a claim."""
    hits = pd.DataFrame(
        {
            "pmid": ["1", "2", "2", "3", "4"],
            "category": ["other", "other", "other", "other", "mri"],
            "role": ["include", "fallback", "include", "fallback", "include"],
            "category_matched": [1, 1, 1, 1, 1],
        }
    )
    path = tmp_path / "hits.csv"
    hits.to_csv(path, index=False)
    routes = other_routes(path, ["1", "2", "3", "4", "5"])
    assert routes["1"] == "pattern"
    assert routes["2"] == "both"
    assert routes["3"] == "fallback"
    assert routes["4"] == "none"  # only a modality hit, no `other`
    assert routes["5"] == "none"  # not in the hits table at all


def test_the_two_other_routes_are_scored_against_different_claims():
    """Pooled they measure nothing: the pattern route asserts a data type, the
    fallback only asserts an absence. This checks they are scored apart."""
    frame = pd.DataFrame(
        {
            "pmid": ["1", "2", "3", "4"],
            "stratum": ["a"] * 4,
            "weight": [1.0] * 4,
            "other_route": ["pattern", "pattern", "fallback", "fallback"],
            "agent_other_datatype": [1, 0, 0, 0],
            "agent_uncertain": [0, 0, 0, 0],
        }
    )
    for key in MODALITY_KEYS:
        frame[f"agent_{key}"] = 0
    frame.loc[3, "agent_mri"] = 1  # a named modality the rules missed
    routes = score_other_routes(frame).set_index("route")
    assert routes.loc["pattern", "n"] == 2
    assert routes.loc["pattern", "correct"] == 1
    assert routes.loc["fallback", "n"] == 2
    assert routes.loc["fallback", "correct"] == 1


def causes_frame(splits: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "pmid": splits["pmid"].astype(str),
            "category": splits["category"],
            "cause": ["mention_not_use"] * len(splits),
        }
    )


def test_cause_coding_must_cover_every_disagreement(tmp_path):
    joined = joined_with_disagreements()
    splits = disagreements(joined, list(THEME_KEYS) + list(MODALITY_KEYS))
    partial = causes_frame(splits).iloc[:-1]
    path = tmp_path / "causes.csv"
    partial.to_csv(path, index=False)
    with pytest.raises(ValidationError, match="1 uncoded"):
        read_causes(path, splits)


def test_cause_coding_refuses_an_unknown_code(tmp_path):
    joined = joined_with_disagreements()
    splits = disagreements(joined, list(THEME_KEYS) + list(MODALITY_KEYS))
    frame = causes_frame(splits)
    frame.loc[0, "cause"] = "vibes"
    path = tmp_path / "causes.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(ValidationError, match="unknown cause code: vibes"):
        read_causes(path, splits)


def test_cause_summary_shares_sum_to_one_and_split_by_direction():
    joined = joined_with_disagreements()
    splits = disagreements(joined, list(THEME_KEYS) + list(MODALITY_KEYS))
    causes = causes_frame(splits)
    causes.loc[causes.index[:3], "cause"] = "term_defect"
    summary = summarize_causes(causes, splits)
    assert summary["share"].sum() == pytest.approx(1.0)
    assert summary["total"].sum() == len(splits)
    assert set(summary.columns) >= {"cause", "false_positive", "false_negative"}


def test_the_structural_cause_is_a_known_code():
    assert STRUCTURAL_CAUSE in CAUSE_CODES


def test_the_two_rounds_used_different_seeds():
    """A sample the patterns were fitted to cannot measure them."""
    assert DEFAULT_SEED != ROUND_ONE_SEED


# --------------------------------------------------------------------------
# Round three: refreshing labels under a moved dictionary, targeted draws
# --------------------------------------------------------------------------


def test_refresh_keeps_the_draw_and_swaps_the_labels():
    """The sample design and the system under test are different things. When
    the dictionaries move under a sample that has already been labeled, the
    draw must survive and only the rule labels change."""
    labels = make_labels()
    design = draw_sample(labels, seed=7, sizes=SIZES)
    moved = labels.copy()
    moved["theme_digital_twins"] = 0  # the category was rewritten away
    refreshed = refresh_rule_labels(design.frame, moved)
    assert list(refreshed["pmid"]) == list(design.frame["pmid"])
    assert list(refreshed["stratum"]) == list(design.frame["stratum"])
    assert list(refreshed["weight"]) == list(design.frame["weight"])
    assert refreshed["theme_digital_twins"].sum() == 0
    assert design.frame["theme_digital_twins"].sum() > 0


def test_refuse_to_refresh_when_a_sampled_paper_has_left_the_corpus():
    labels = make_labels()
    design = draw_sample(labels, seed=7, sizes=SIZES)
    shrunk = labels.iloc[5:]
    with pytest.raises(ValidationError, match="absent from the label table"):
        refresh_rule_labels(design.frame, shrunk)


def test_refresh_needs_the_label_columns():
    labels = make_labels()
    design = draw_sample(labels, seed=7, sizes=SIZES)
    with pytest.raises(ValidationError, match="mod_pet"):
        refresh_rule_labels(design.frame, labels.drop(columns=["mod_pet"]))


def test_targeted_draw_is_reproducible_and_excludes_prior_rounds():
    labels = make_labels()
    sizes = {"digital_twins": 5, "clinical_data": 5}
    already = list(labels["pmid"][300:350])
    first = draw_targeted_sample(labels, sizes, seed=11, exclude=already)
    second = draw_targeted_sample(labels, sizes, seed=11, exclude=already)
    assert list(first.frame["pmid"]) == list(second.frame["pmid"])
    assert not set(first.frame["pmid"]) & set(already)


def test_targeted_strata_overlap_so_a_paper_is_claimed_once():
    """Unlike the six-stratum design these conditions overlap, so the order of
    ``sizes`` decides who claims a paper. It must still claim it only once."""
    labels = make_labels()
    labels["mod_genomics"] = 1  # every paper now qualifies for two strata
    labels["mod_clinical_data"] = 1
    sizes = {"genomics_alone": 5, "clinical_data": 5}
    design = draw_targeted_sample(labels, sizes, seed=11)
    assert not design.frame["pmid"].duplicated().any()
    assert set(design.frame["stratum"]) <= set(sizes)


def test_targeted_draw_labels_each_row_with_the_category_it_measures():
    labels = make_labels()
    design = draw_targeted_sample(labels, {"genomics_with_histology": 5}, seed=11)
    assert set(design.frame["category"]) == {"genomics"}


def test_targeted_draw_refuses_an_unknown_stratum():
    with pytest.raises(ValidationError, match="pathology_only"):
        draw_targeted_sample(make_labels(), {"pathology_only": 5}, seed=11)


def test_every_targeted_stratum_names_the_category_it_measures():
    assert set(TARGETED_STRATA) == set(TARGETED_CATEGORY)
    for category in TARGETED_CATEGORY.values():
        assert category in set(THEME_KEYS) | set(MODALITY_KEYS)


def test_the_three_rounds_used_three_different_seeds():
    assert len({ROUND_ONE_SEED, DEFAULT_SEED, ROUND_THREE_SEED}) == 3
