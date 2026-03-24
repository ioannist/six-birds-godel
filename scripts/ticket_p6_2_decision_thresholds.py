#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent
P61_PROGRAM = ROOT / "results" / "ticket-p6-1" / "program_effect_sizes.csv"
P61_CELL = ROOT / "results" / "ticket-p6-1" / "cell_effect_sizes.csv"
P61_INTERACTION = ROOT / "results" / "ticket-p6-1" / "interaction_delta_table.csv"
T6_ROBUSTNESS = ROOT / "vendors" / "six-birds-pica" / "paper" / "figdata" / "T6_robustness.csv"

CANDIDATE = "A14_only"
PRIMARY_NS = {64, 128}
EXTENDED_NS = {256}
CONTROL_N = 32


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def as_float(text: str) -> float | None:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def main() -> int:
    out_dir = ROOT / "results" / "ticket-p6-2"
    out_dir.mkdir(parents=True, exist_ok=True)

    program_rows = load_csv(P61_PROGRAM)
    cell_rows = load_csv(P61_CELL)
    interaction_rows = load_csv(P61_INTERACTION)
    robust_rows = load_csv(T6_ROBUSTNESS)

    # Focus metrics for candidate A14_only on frob_from_rank1.
    prog = [
        r
        for r in program_rows
        if r.get("config_name") == CANDIDATE and r.get("metric") == "frob_from_rank1"
    ]
    delta_by_n: dict[int, float] = {}
    for r in prog:
        n = int(r["n"])
        d = as_float(r.get("delta_vs_baseline", ""))
        if d is not None:
            delta_by_n[n] = d

    primary_deltas = [abs(delta_by_n[n]) for n in sorted(PRIMARY_NS) if n in delta_by_n]
    control_delta = abs(delta_by_n.get(CONTROL_N, 0.0))
    extended_deltas = [abs(delta_by_n[n]) for n in sorted(EXTENDED_NS) if n in delta_by_n]

    # Comparator separation from interaction table.
    inter = [
        r
        for r in interaction_rows
        if r.get("config_name") == CANDIDATE and r.get("comparison_status") == "resolved"
    ]
    interaction_by_n: dict[int, float] = {}
    comparator_labels: set[str] = set()
    for r in inter:
        n = int(r["n"])
        v = as_float(r.get("interaction_delta_abs_shift", ""))
        if v is not None:
            interaction_by_n[n] = abs(v)
            label = (r.get("closest_simpler_config") or "").strip()
            if label:
                comparator_labels.add(label)
    primary_interaction = [interaction_by_n[n] for n in sorted(PRIMARY_NS) if n in interaction_by_n]

    # LOO ablation support at primary n.
    core_loo = [r for r in cell_rows if r.get("n_tier") == "core" and r.get("metric") == "frob_from_rank1"]
    core_loo_count = len(core_loo)

    # Robustness blockers.
    robust_fail = sum(1 for r in robust_rows if (r.get("result_status") or "").strip() == "FAIL")
    robust_partial = sum(1 for r in robust_rows if (r.get("result_status") or "").strip() == "PARTIAL")

    # Low-scale dependence flag: true if primary signal is weak while control is stronger.
    primary_mean = mean(primary_deltas)
    low_scale_dependence = bool(primary_deltas) and (primary_mean < 0.10 and control_delta > primary_mean)

    thresholds = {
        "version": "0.1.0",
        "scale_policy": {
            "control_only": [32],
            "primary_decision": [64, 128],
            "extended_if_available": [256],
        },
        "candidate_surface": CANDIDATE,
        "criteria": {
            "interaction_signal_strength": {
                "theorem_ready": "abs(delta_vs_baseline_frob) >= 0.15 at n=64 and n=128",
                "hybrid_ready": "mean abs(delta_vs_baseline_frob) over n in {64,128} >= 0.10",
            },
            "comparator_separation": {
                "theorem_ready": "resolved strict comparator at n=64 and n=128 with abs(interaction_delta_abs_shift) >= 0.10",
                "hybrid_ready": "resolved strict comparator at >=1 primary n with abs(interaction_delta_abs_shift) >= 0.10",
            },
            "robustness": {
                "theorem_ready": "robustness FAIL count == 0 and PARTIAL count <= 1",
                "hybrid_ready": "robustness FAIL count <= 1 and PARTIAL count <= 3",
            },
            "ablation_support": {
                "theorem_ready": "primary-regime LOO effect rows >= 80",
                "hybrid_ready": "primary-regime LOO effect rows >= 40",
            },
            "low_scale_dependence": {
                "theorem_ready": "False",
                "hybrid_ready": "False",
            },
        },
    }

    crit_signal_theorem = all(abs(delta_by_n.get(n, 0.0)) >= 0.15 for n in PRIMARY_NS)
    crit_signal_hybrid = primary_mean >= 0.10

    crit_sep_theorem = all(interaction_by_n.get(n, 0.0) >= 0.10 for n in PRIMARY_NS)
    crit_sep_hybrid = any(interaction_by_n.get(n, 0.0) >= 0.10 for n in PRIMARY_NS)

    crit_rob_theorem = robust_fail == 0 and robust_partial <= 1
    crit_rob_hybrid = robust_fail <= 1 and robust_partial <= 3

    crit_abl_theorem = core_loo_count >= 80
    crit_abl_hybrid = core_loo_count >= 40

    crit_low_theorem = not low_scale_dependence
    crit_low_hybrid = not low_scale_dependence

    theorem_ready = all([crit_signal_theorem, crit_sep_theorem, crit_rob_theorem, crit_abl_theorem, crit_low_theorem])
    hybrid_ready = all([crit_signal_hybrid, crit_sep_hybrid, crit_rob_hybrid, crit_abl_hybrid, crit_low_hybrid])
    overall_status = "theorem_ready" if theorem_ready else ("hybrid_ready" if hybrid_ready else "not_ready")

    matrix_rows: list[dict[str, Any]] = [
        {
            "dimension": "interaction_signal_strength",
            "observed": f"primary_abs_deltas={','.join(f'{x:.6f}' for x in primary_deltas)}; control_abs_delta={control_delta:.6f}",
            "theorem_threshold": ">=0.15 at both n=64 and n=128",
            "hybrid_threshold": "mean >=0.10 across n=64,128",
            "theorem_pass": int(crit_signal_theorem),
            "hybrid_pass": int(crit_signal_hybrid),
        },
        {
            "dimension": "comparator_separation",
            "observed": f"primary_interaction={','.join(f'{x:.6f}' for x in primary_interaction)}; comparators={','.join(sorted(comparator_labels))}",
            "theorem_threshold": "resolved comparator >=0.10 at n=64 and n=128",
            "hybrid_threshold": "resolved comparator >=0.10 at >=1 primary n",
            "theorem_pass": int(crit_sep_theorem),
            "hybrid_pass": int(crit_sep_hybrid),
        },
        {
            "dimension": "robustness_across_shipped_scales",
            "observed": f"robustness_fail={robust_fail}; robustness_partial={robust_partial}",
            "theorem_threshold": "fail=0 and partial<=1",
            "hybrid_threshold": "fail<=1 and partial<=3",
            "theorem_pass": int(crit_rob_theorem),
            "hybrid_pass": int(crit_rob_hybrid),
        },
        {
            "dimension": "ablation_support",
            "observed": f"core_loo_effect_rows={core_loo_count}",
            "theorem_threshold": ">=80",
            "hybrid_threshold": ">=40",
            "theorem_pass": int(crit_abl_theorem),
            "hybrid_pass": int(crit_abl_hybrid),
        },
        {
            "dimension": "low_scale_dependence_only",
            "observed": str(low_scale_dependence),
            "theorem_threshold": "False",
            "hybrid_threshold": "False",
            "theorem_pass": int(crit_low_theorem),
            "hybrid_pass": int(crit_low_hybrid),
        },
        {
            "dimension": "overall_decision_status",
            "observed": overall_status,
            "theorem_threshold": "all theorem criteria true",
            "hybrid_threshold": "all hybrid criteria true",
            "theorem_pass": int(theorem_ready),
            "hybrid_pass": int(hybrid_ready),
        },
    ]

    run_needed = not theorem_ready
    run_trigger = {
        "trigger_id": "ticket_p6_2_minimal_trigger",
        "version": "0.1.0",
        "theorem_ready": theorem_ready,
        "hybrid_ready": hybrid_ready,
        "new_run_needed": run_needed,
        "smallest_trigger": {
            "label": "a14_only_vs_baseline_primary_regime_confirmatory",
            "cost_class": "cheap_new_run",
            "target_configs": ["baseline", "A14_only", "full_action", "full_all"],
            "target_comparators": ["baseline", "full_action", "full_all"],
            "target_scales": [64, 128],
            "optional_scale": [256],
            "exact_ambiguity_resolved": "Closes theorem-threshold robustness/comparator-separation gap under primary regime without relying on n=32.",
            "note": "Only execute if theorem-ready status is required now; hybrid-ready already clears shipped thresholds.",
        }
        if run_needed
        else {
            "label": "none",
            "cost_class": "none",
            "target_configs": [],
            "target_comparators": [],
            "target_scales": [],
            "optional_scale": [],
            "exact_ambiguity_resolved": "No run needed.",
            "note": "Shipped data clears theorem-ready thresholds.",
        },
    }

    report_lines = [
        "# Ticket P6.2 Decision-Threshold Closure",
        "",
        "## Decision outcome",
        f"- theorem_ready: {'yes' if theorem_ready else 'no'}",
        f"- hybrid_ready: {'yes' if hybrid_ready else 'no'}",
        f"- overall_status: {overall_status}",
        "",
        "## Candidate focus",
        f"- candidate surface: {CANDIDATE}",
        f"- primary-regime abs deltas (n=64,128): {', '.join(f'{x:.6f}' for x in primary_deltas)}",
        f"- comparator labels used: {', '.join(sorted(comparator_labels)) if comparator_labels else 'none'}",
        "",
        "## Run trigger",
        f"- new_run_needed: {'yes' if run_needed else 'no'}",
        f"- smallest_trigger: {run_trigger['smallest_trigger']['label']}",
        "",
        "## Scale discipline",
        "- n=32 is treated as control-only and is not decision-driving.",
        "- readiness is centered on n=64 and n=128, with n=256 as supplementary when available.",
    ]

    (out_dir / "decision_thresholds.yaml").write_text(yaml.safe_dump(thresholds, sort_keys=False), encoding="utf-8")
    write_csv(out_dir / "readiness_matrix.csv", matrix_rows)
    (out_dir / "run_trigger_spec.yaml").write_text(yaml.safe_dump(run_trigger, sort_keys=False), encoding="utf-8")
    (out_dir / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"wrote {out_dir / 'decision_thresholds.yaml'}")
    print(f"wrote {out_dir / 'readiness_matrix.csv'}")
    print(f"wrote {out_dir / 'run_trigger_spec.yaml'}")
    print(f"wrote {out_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
