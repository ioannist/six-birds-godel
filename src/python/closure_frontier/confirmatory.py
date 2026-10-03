"""EXP-112 parsing and the numerical decision rules frozen in ticket P6.3.

These labels are empirical workflow decisions; none certifies a theorem.
"""
from __future__ import annotations

import json
import math
from fractions import Fraction
from pathlib import Path
import re
from typing import Any

CONFIGS = ("A14_only", "baseline", "full_action", "full_all", "A13_A14", "A14_A19")
PRIMARY_SCALES = (64, 128)
REQUIRED_SEEDS = frozenset(range(10))
LOG_PATTERN = re.compile(r"EXP-112_s(?P<seed>\d+)_n(?P<scale>\d+)_(?P<config>.+)\.log$")


def finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def read_exp112_audit(path: Path) -> dict[str, Any] | None:
    match = LOG_PATTERN.fullmatch(path.name)
    if match is None:
        return None
    for line in reversed(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        if not line.startswith("KEY_AUDIT_JSON "):
            continue
        try:
            audit = json.loads(line[len("KEY_AUDIT_JSON "):])
        except json.JSONDecodeError:
            return None
        if not isinstance(audit, dict):
            return None
        if (audit.get("exp_id") != "EXP-112"
                or audit.get("config_name") != match["config"]
                or type(audit.get("seed")) is not int
                or type(audit.get("n")) is not int
                or audit.get("seed") != int(match["seed"])
                or audit.get("n") != int(match["scale"])):
            return None
        metric = finite_number(audit.get("frob_from_rank1"))
        if metric is None or metric < 0:
            return None
        return audit
    return None


def has_k4(audit: dict[str, Any] | None) -> bool:
    if not isinstance(audit, dict) or not isinstance(audit.get("multi_scale_scan"), list):
        return False
    for entry in audit["multi_scale_scan"]:
        if not isinstance(entry, dict) or entry.get("k") != 4:
            continue
        metric = finite_number(entry.get("frob"))
        if metric is not None and metric >= 0:
            return True
    return False


def confirmatory_readiness(rows: list[dict[str, Any]], *,
                           robustness_no_new_failures: bool | None = None) -> dict[str, Any]:
    """Apply signal, comparator, and full seed/rung coverage gates to summaries."""
    cells: dict[tuple[str, int], dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("config")), int(row.get("scale", 0)))
        if key in cells:
            raise ValueError(f"duplicate confirmatory summary cell: {key}")
        cells[key] = row
    reasons = []
    comparable = True
    deltas: dict[str, list[Fraction]] = {config: [] for config in CONFIGS}
    for config in CONFIGS:
        for scale in PRIMARY_SCALES:
            row = cells.get((config, scale), {})
            seed_count = finite_number(row.get("seed_coverage_observed"))
            anchor = finite_number(row.get("anchor_k4_coverage_ratio"))
            delta = finite_number(row.get("delta_vs_baseline_frob_from_rank1"))
            if seed_count != len(REQUIRED_SEEDS) or anchor != 1.0 or delta is None:
                comparable = False
                reasons.append(f"incomplete_seed_rung_or_metric_coverage:{config}@{scale}")
            if delta is not None:
                # The summary's decimal scores define the decision inputs.
                deltas[config].append(Fraction(str(delta)))
    means_abs = {config: sum(map(abs, values)) / len(values)
                 for config, values in deltas.items() if len(values) == len(PRIMARY_SCALES)}
    candidate = deltas["A14_only"]
    signal = len(candidate) == 2 and any(delta > 0 for delta in candidate)
    hybrid_signal = signal and means_abs.get("A14_only", 0) >= Fraction("0.10")
    theorem_signal = len(candidate) == 2 and all(delta >= Fraction("0.15") for delta in candidate)
    neighbors = ("A13_A14", "A14_A19")
    neighbor_data = all(config in means_abs for config in neighbors)
    both_neighbors_match = neighbor_data and all(
        means_abs[config] >= means_abs.get("A14_only", 0) for config in neighbors)
    separation = neighbor_data and all(
        means_abs.get("A14_only", 0) - means_abs[config] >= Fraction("0.05") for config in neighbors)
    focus = comparable and signal and not both_neighbors_match
    theorem_ready = (focus and theorem_signal and separation
                     and robustness_no_new_failures is True)
    hybrid_condition = not separation or robustness_no_new_failures is not True
    hybrid_ready = focus and hybrid_signal and hybrid_condition and not theorem_ready
    if not theorem_signal:
        reasons.append("theorem_signal_below_threshold")
    if not separation:
        reasons.append("theorem_comparator_separation_below_threshold")
    if robustness_no_new_failures is not True:
        reasons.append("no_new_robustness_failures_not_established")
    return {
        "primary_coverage_complete": comparable,
        "final_verdict": "theorem_ready" if theorem_ready else "hybrid_ready" if hybrid_ready else "not_ready",
        "a14_only_remains_focus": focus,
        "primary_mean_abs_delta": {config: float(value) for config, value in means_abs.items()},
        "theorem_signal_pass": theorem_signal,
        "theorem_comparator_separation_pass": separation,
        "robustness_no_new_failures": robustness_no_new_failures,
        "decision_reasons": reasons,
        "decision_scope": "frozen empirical criteria; no theorem proof support",
    }
