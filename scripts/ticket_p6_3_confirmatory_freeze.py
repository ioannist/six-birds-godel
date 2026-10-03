#!/usr/bin/env python3
from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent
P5_PROFILES = ROOT / "results" / "ticket-p5" / "program_profiles.csv"
P61_PROGRAM = ROOT / "results" / "ticket-p6-1" / "program_effect_sizes.csv"
P61_INTERACTION = ROOT / "results" / "ticket-p6-1" / "interaction_delta_table.csv"
P62_THRESHOLDS = ROOT / "results" / "ticket-p6-2" / "decision_thresholds.yaml"
P62_TRIGGER = ROOT / "results" / "ticket-p6-2" / "run_trigger_spec.yaml"

PRIMARY_NS = [64, 128]
OPTIONAL_NS = [256]
CONTROL_NS = [32]

CORE_CONFIGS = ["A14_only", "baseline", "full_action", "full_all"]
NEIGHBOR_CONFIGS = ["A13_A14", "A14_A19"]


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected mapping yaml: {path}")
    return data


def as_float(value: str) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def mean_abs_primary_delta(rows: list[dict[str, str]], config: str) -> tuple[float, int]:
    vals: list[float] = []
    min_count = 10**9
    for n in PRIMARY_NS:
        sub = [
            r
            for r in rows
            if r.get("config_name") == config and r.get("n") == str(n) and r.get("metric") == "frob_from_rank1"
        ]
        if not sub:
            continue
        d = as_float(sub[0].get("delta_vs_baseline", ""))
        c = int(sub[0].get("sample_count", "0") or 0)
        if d is not None:
            vals.append(abs(d))
            min_count = min(min_count, c)
    if len(vals) != len(PRIMARY_NS):
        return 0.0, 0
    return sum(vals) / len(vals), (0 if min_count == 10**9 else min_count)


def interaction_primary_mean(rows: list[dict[str, str]], config: str) -> tuple[float, str]:
    vals: list[float] = []
    comparator = ""
    for n in PRIMARY_NS:
        sub = [r for r in rows if r.get("config_name") == config and r.get("n") == str(n)]
        if not sub:
            continue
        r = sub[0]
        v = as_float(r.get("interaction_delta_abs_shift", ""))
        if v is not None:
            vals.append(v)
        cmp_lbl = (r.get("closest_simpler_config") or "").strip()
        if cmp_lbl:
            comparator = cmp_lbl
    return (sum(vals) / len(vals) if vals else 0.0), comparator


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    out_dir = ROOT / "results" / "ticket-p6-3"
    out_dir.mkdir(parents=True, exist_ok=True)

    p5 = load_csv(P5_PROFILES)
    p61_prog = load_csv(P61_PROGRAM)
    p61_inter = load_csv(P61_INTERACTION)
    p62_thresholds = load_yaml(P62_THRESHOLDS)
    p62_trigger = load_yaml(P62_TRIGGER)

    profile_by_label = {r.get("label", ""): r for r in p5}
    configs = CORE_CONFIGS + NEIGHBOR_CONFIGS

    comparator_rows: list[dict[str, Any]] = []
    included: list[str] = []
    for cfg in configs:
        profile = profile_by_label.get(cfg)
        support_class = profile.get("support_class", "missing") if profile else "missing"
        support_score = profile.get("support_score", "") if profile else ""
        kind = profile.get("program_kind", "") if profile else ""
        primary_mean_abs, primary_min_count = mean_abs_primary_delta(p61_prog, cfg)
        inter_mean, simpler = interaction_primary_mean(p61_inter, cfg)

        include = False
        reason = ""
        if cfg in CORE_CONFIGS:
            include = True
            reason = "core anchor/control config"
        else:
            if support_class in {"strong_surface_support", "moderate_surface_support"} and primary_min_count >= 10:
                include = True
                reason = "nearest supported neighbor with primary-regime coverage"
            else:
                include = False
                reason = "insufficient shipped support for credible challenge control"

        if include:
            included.append(cfg)

        comparator_rows.append(
            {
                "config": cfg,
                "program_kind": kind,
                "support_class": support_class,
                "support_score": support_score,
                "primary_mean_abs_delta_vs_baseline_frob": round(primary_mean_abs, 8),
                "primary_min_sample_count": primary_min_count,
                "primary_mean_interaction_delta": round(inter_mean, 8),
                "closest_simpler_comparator_seen": simpler,
                "include_in_confirmatory_run": "yes" if include else "no",
                "include_reason": reason,
            }
        )

    # Decide if A14_only remains best narrow candidate against neighbor set.
    candidate_mean, _ = mean_abs_primary_delta(p61_prog, "A14_only")
    a13_mean, _ = mean_abs_primary_delta(p61_prog, "A13_A14")
    a19_mean, _ = mean_abs_primary_delta(p61_prog, "A14_A19")
    a14_still_target = candidate_mean >= max(a13_mean, a19_mean)

    # Freeze confirmatory protocol.
    confirmatory_protocol = {
        "protocol_id": "ticket_p6_3_confirmatory_freeze",
        "version": "0.1.0",
        "target_hypothesis": "A14_only is the strongest narrow interaction candidate once hardened against nearest shipped comparators.",
        "candidate_target": "A14_only",
        "candidate_target_retained": bool(a14_still_target),
        "scale_policy": {
            "primary_regime": PRIMARY_NS,
            "optional_extension": OPTIONAL_NS,
            "control_only": CONTROL_NS,
            "decision_note": "n=32 is non-decision-driving.",
        },
        "frozen_comparator_set": included,
        "metric_bundle": {
            "primary_metric": {
                "name": "delta_vs_baseline_frob_from_rank1",
                "definition": "Per-(config,n) mean(frob_from_rank1) - mean_baseline(frob_from_rank1), evaluated at n=64 and n=128.",
                "decision_aggregation": "primary_mean_abs = mean(|delta| over n in {64,128})",
            },
            "secondary_metric": {
                "name": "primary_regime_seed_coverage_and_anchor_scan",
                "definition": "Each (config,n) in primary regime must have seed_count >= 10 and anchor rung support at k=4 logged for decision metrics.",
                "purpose": "Prevents fragile conclusions from thin or non-comparable slices.",
            },
        },
        "minimal_run_budget": {
            "configs": included,
            "primary_scales": PRIMARY_NS,
            "optional_scale": OPTIONAL_NS,
            "n256_required": False,
            "minimum_seed_footprint": "10 seeds per (config,n) for n in {64,128}; optional 5+ seeds at n=256 if extension is run.",
            "minimum_scan_rung_footprint": "k_rung=4 required for all primary (config,n); optional mini-check at k_rung in {2,8} for sensitivity.",
            "cost_class": "cheap_new_run",
        },
        "lineage": {
            "source_thresholds": "results/ticket-p6-2/decision_thresholds.yaml",
            "source_trigger": "results/ticket-p6-2/run_trigger_spec.yaml",
        },
    }

    decision_logic = {
        "decision_logic_id": "ticket_p6_3_decision_logic",
        "version": "0.1.0",
        "theorem_ready_upgrade_if": [
            "A14_only has delta_vs_baseline_frob >= 0.15 at n=64 and n=128.",
            "A14_only exceeds A13_A14 and A14_A19 on primary_mean_abs(delta_vs_baseline_frob) by >= 0.05.",
            "Secondary metric passes: seed_count >=10 per primary (config,n) and anchor k_rung=4 coverage complete.",
            "No new robustness FAILs are introduced in confirmatory reporting slice.",
        ],
        "hybrid_only_if": [
            "A14_only improves over baseline on at least one primary n and primary_mean_abs(delta) >= 0.10.",
            "But theorem comparator-separation margin (>=0.05 vs both nearest neighbors) is not met, or robustness remains partial.",
        ],
        "falsify_a14_focus_if": [
            "A14_only fails to beat baseline at both primary n (64 and 128).",
            "Or both nearest neighbors (A13_A14 and A14_A19) match/exceed A14_only on primary_mean_abs(delta_vs_baseline_frob).",
            "Or confirmatory slice fails minimum seed/rung comparability, making A14_only non-credible as a focus target.",
        ],
        "decision_outputs": ["theorem_ready", "hybrid_ready", "not_ready"],
        "n32_guardrail": "No upgrade decision may be made from n=32-only evidence.",
    }

    report_lines = [
        "# Ticket P6.3 Confirmatory Freeze",
        "",
        "## Target check",
        f"- A14_only remains right confirmatory target: {'yes' if a14_still_target else 'no'}",
        f"- comparator set frozen: {', '.join(included)}",
        "",
        "## Metric freeze",
        "- primary: delta_vs_baseline_frob_from_rank1 on n=64,128",
        "- secondary: seed coverage + anchor k_rung=4 comparability",
        "",
        "## Budget freeze",
        "- primary scales: n=64,128",
        "- n=256: optional extension, not required for trigger closure",
        "- minimum seeds: 10 per (config,n) at primary scales",
        "",
        "## Decision hardening",
        "- theorem upgrade, hybrid-only retention, and A14-only falsification conditions are explicitly machine-readable in decision_logic.yaml",
        "- no run executed in this ticket",
    ]

    (out_dir / "confirmatory_protocol.yaml").write_text(
        yaml.safe_dump(confirmatory_protocol, sort_keys=False), encoding="utf-8"
    )
    write_csv(out_dir / "comparator_table.csv", comparator_rows)
    (out_dir / "decision_logic.yaml").write_text(
        yaml.safe_dump(decision_logic, sort_keys=False), encoding="utf-8"
    )
    (out_dir / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"wrote {out_dir / 'confirmatory_protocol.yaml'}")
    print(f"wrote {out_dir / 'comparator_table.csv'}")
    print(f"wrote {out_dir / 'decision_logic.yaml'}")
    print(f"wrote {out_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
