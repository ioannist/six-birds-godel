import json

import pytest

from closure_frontier import FiniteMap, chain
from closure_frontier.confirmatory import (
    CONFIGS, PRIMARY_SCALES, confirmatory_readiness, has_k4, read_exp112_audit,
)
from scripts import ticket063_interaction_anti_artifact_audit as toy
from scripts import ticket_p5_vendor_baseline_analysis as support
from closure_frontier.pica_data_bridge import _parse_jsonl


def summaries(candidate=0.3):
    delta = {"A14_only": candidate, "baseline": 0, "full_action": 0.4,
             "full_all": 0.3, "A13_A14": 0.25, "A14_A19": 0.1}
    return [{"config": config, "scale": scale, "seed_coverage_observed": 10,
             "anchor_k4_coverage_ratio": 1,
             "delta_vs_baseline_frob_from_rank1": delta[config]}
            for config in CONFIGS for scale in PRIMARY_SCALES]


def test_frozen_threshold_margin_uses_exact_decimal_inputs():
    result = confirmatory_readiness(summaries(), robustness_no_new_failures=True)
    # 0.30 - 0.25 meets the exact 0.05 margin, despite binary float subtraction.
    assert result["final_verdict"] == "theorem_ready"
    assert confirmatory_readiness(summaries())["final_verdict"] == "hybrid_ready"


def test_coverage_alone_cannot_pass_the_frozen_signal_rule():
    result = confirmatory_readiness(summaries(candidate=0.01))
    assert result["primary_coverage_complete"]
    assert result["final_verdict"] == "not_ready"


def test_hybrid_requires_its_frozen_comparator_or_robustness_condition():
    rows = summaries()
    for row in rows:
        if row["config"] == "A14_only":
            row["delta_vs_baseline_frob_from_rank1"] = 0.14 if row["scale"] == 64 else 0.5
    result = confirmatory_readiness(rows, robustness_no_new_failures=True)
    assert result["theorem_comparator_separation_pass"]
    assert not result["theorem_signal_pass"]
    assert result["final_verdict"] == "not_ready"
    assert confirmatory_readiness(rows)["final_verdict"] == "hybrid_ready"


def test_every_seed_needs_anchor_coverage():
    rows = summaries()
    rows[0]["anchor_k4_coverage_ratio"] = 0.9
    result = confirmatory_readiness(rows, robustness_no_new_failures=True)
    assert not result["primary_coverage_complete"]
    assert result["final_verdict"] == "not_ready"
    assert confirmatory_readiness(rows[:-1])["final_verdict"] == "not_ready"


def test_duplicate_summary_cells_are_rejected():
    rows = summaries()
    with pytest.raises(ValueError):
        confirmatory_readiness(rows + [rows[0]])


@pytest.mark.parametrize("defect", ["metric_missing", "metric_nan", "wrong_seed", "boolean_seed", "not_a_mapping"])
def test_audit_requires_a_real_metric_and_matching_job_identity(tmp_path, defect):
    audit = {"exp_id": "EXP-112", "config_name": "baseline", "seed": 0,
             "n": 64, "frob_from_rank1": 1.0}
    if defect == "metric_missing":
        del audit["frob_from_rank1"]
    elif defect == "metric_nan":
        audit["frob_from_rank1"] = float("nan")
    elif defect == "wrong_seed":
        audit["seed"] = 1
    elif defect == "boolean_seed":
        audit["seed"] = False
    else:
        audit = []
    path = tmp_path / "EXP-112_s0_n64_baseline.log"
    path.write_text("KEY_AUDIT_JSON " + json.dumps(audit) + "\n")
    assert read_exp112_audit(path) is None


def test_anchor_is_a_measurement_rather_than_a_label():
    assert not has_k4({"multi_scale_scan": [{"k": 4}]})
    assert not has_k4({"multi_scale_scan": [{"k": 4, "frob": float("nan")}]})
    assert has_k4({"multi_scale_scan": [{"k": 4, "frob": 1}]})


def test_rewrite_names_and_compares_the_resulting_map():
    poset = chain(3)
    original = FiniteMap({0: 1, 1: 2, 2: 2})
    pool = [(toy.op_id("C3", original, list(poset.elements)), original)]
    transformed = toy.transform_pool(pool, frozenset({toy.CELL_PKG_REWRITE}),
                                    poset, list(poset.elements), toy.ORDER_REWRITE_GATE, "raw")
    assert len(transformed) == 1
    operator_id, op = transformed[0]
    assert op.mapping == {0: 2, 1: 2, 2: 2}
    assert operator_id == toy.op_id("C3", op, list(poset.elements))
    assert operator_id != pool[0][0]


def test_surface_presence_cannot_establish_quantitative_effects():
    result = support.assess_toy_takeaways(
        [{"label": name} for name in ["baseline", "full_action", "full_all"]],
        [{"impact_proxy_score": 0}, {"impact_proxy_score": 1}],
        [{"surface_kind": "robustness", "headers": ["metric"]}], [],
    )
    assert result["supported_by_vendor"] == []


def test_nonmapping_jsonl_is_counted_as_a_parse_failure(tmp_path):
    path = tmp_path / "records.jsonl"
    path.write_text('{}\n[]\ninvalid\n')
    records, failures = _parse_jsonl(path)
    assert failures == 2
    assert [record["parsed"] for record in records] == [True, False, False]
