#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict
import csv
import json
import math
from pathlib import Path
import sys
from typing import Callable, Hashable, TypeVar


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "python"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from closure_frontier import (  # noqa: E402
    CandidateScore,
    FiniteMap,
    FinitePoset,
    WeightedBenchmark,
    average_rank_lift_cost,
    boolean_lattice,
    chain,
    coverage_score,
    moved_points_cost,
    pareto_frontier,
    total_rank_lift_cost,
)


T = TypeVar("T", bound=Hashable)

PROFILE_UNIFORM = "uniform"
PROFILE_TOP = "top_heavy"
PROFILE_BOTTOM = "bottom_heavy"
PROFILE_MIDDLE = "middle_heavy"
PROFILE_ORDER = (PROFILE_UNIFORM, PROFILE_TOP, PROFILE_BOTTOM, PROFILE_MIDDLE)

COST_MOVED = "moved_points_cost"
COST_TOTAL = "total_rank_lift_cost"
COST_AVG = "average_rank_lift_cost"
COST_NORM = "normalized_total_rank_lift_cost"
COST_ORDER = (COST_MOVED, COST_TOTAL, COST_AVG, COST_NORM)

TIE_KEEP = "keep_all_nondominated"
TIE_DEDUP = "dedup_equal_points"
TIE_ORDER = (TIE_KEEP, TIE_DEDUP)

FAMILY_CHAIN_ALL = "chain_all_monotone_inflationary"
FAMILY_CHAIN_CLOSURE = "chain_closure_only"
FAMILY_CHAIN_STEP = "chain_step_family"
FAMILY_BOOL_ALL = "boolean_all_monotone_inflationary"


def element_key(poset: FinitePoset[T], x: T) -> tuple[int, str]:
    return (poset.rank_of(x), repr(x))


def element_to_str(x: Hashable) -> str:
    if isinstance(x, frozenset):
        return "{" + ",".join(str(v) for v in sorted(x)) + "}"
    return str(x)


def operator_id(model_id: str, ordered: list[T], op: FiniteMap[T]) -> str:
    index = {x: i for i, x in enumerate(ordered)}
    image_indices = [str(index[op.apply(x)]) for x in ordered]
    return f"{model_id}:(" + ",".join(image_indices) + ")"


def enumerate_monotone_inflationary_maps(poset: FinitePoset[T], ordered: list[T]) -> list[FiniteMap[T]]:
    options: dict[T, list[T]] = {}
    for x in ordered:
        candidates = [y for y in ordered if poset.leq(x, y)]
        candidates.sort(key=lambda z: element_key(poset, z))
        options[x] = candidates

    assigned: dict[T, T] = {}
    maps: list[FiniteMap[T]] = []

    def is_valid_choice(x: T, fx: T) -> bool:
        for y, fy in assigned.items():
            if poset.leq(x, y) and not poset.leq(fx, fy):
                return False
            if poset.leq(y, x) and not poset.leq(fy, fx):
                return False
        return True

    def backtrack(i: int) -> None:
        if i == len(ordered):
            maps.append(FiniteMap(dict(assigned)))
            return
        x = ordered[i]
        for fx in options[x]:
            if not is_valid_choice(x, fx):
                continue
            assigned[x] = fx
            backtrack(i + 1)
            del assigned[x]

    backtrack(0)
    return maps


def is_step_family_chain(op: FiniteMap[int], top: int) -> bool:
    for k in range(top + 1):
        if all(op.apply(x) == min(top, x + k) for x in range(top + 1)):
            return True
    return False


def build_profiles(poset: FinitePoset[T], ordered: list[T]) -> dict[str, dict[T, float]]:
    max_rank = max(poset.rank_of(x) for x in ordered)
    mid = max_rank / 2.0
    return {
        PROFILE_UNIFORM: {x: 1.0 for x in ordered},
        PROFILE_TOP: {x: float(poset.rank_of(x) + 1) for x in ordered},
        PROFILE_BOTTOM: {x: float(max_rank - poset.rank_of(x) + 1) for x in ordered},
        PROFILE_MIDDLE: {
            x: float(1.0 / (1.0 + abs(poset.rank_of(x) - mid)))
            for x in ordered
        },
    }


def dedup_equal_points(candidates: list[CandidateScore]) -> list[CandidateScore]:
    best_by_point: dict[tuple[float, float], CandidateScore] = {}
    for candidate in sorted(candidates, key=lambda c: c.id):
        key = (candidate.yield_score, candidate.cost_score)
        if key not in best_by_point:
            best_by_point[key] = candidate
    return [best_by_point[key] for key in sorted(best_by_point.keys(), key=lambda p: (-p[0], p[1]))]


def frontier_with_tie_mode(candidates: list[CandidateScore], tie_mode: str) -> list[CandidateScore]:
    frontier = pareto_frontier(candidates)
    if tie_mode == TIE_KEEP:
        return sorted(frontier, key=lambda c: c.id)
    if tie_mode == TIE_DEDUP:
        return sorted(dedup_equal_points(frontier), key=lambda c: c.id)
    raise ValueError(f"unknown tie mode: {tie_mode}")


def jaccard_distance(a: set[str], b: set[str]) -> float:
    union = a | b
    if not union:
        return 0.0
    inter = a & b
    return 1.0 - (len(inter) / len(union))


def write_svg_bar_plot(
    path: Path,
    title: str,
    items: list[tuple[str, float]],
    *,
    width: int = 1000,
    height: int = 540,
) -> None:
    margin_left = 280
    margin_top = 50
    margin_bottom = 40
    bar_gap = 8
    usable_w = width - margin_left - 40
    usable_h = height - margin_top - margin_bottom
    count = max(1, len(items))
    bar_h = max(10, (usable_h - bar_gap * (count - 1)) // count)
    max_val = max((value for _, value in items), default=1.0)
    if max_val <= 0:
        max_val = 1.0

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text x="{margin_left}" y="28" font-size="18" font-family="monospace">{title}</text>',
    ]
    y = margin_top
    for label, value in items:
        bar_w = int((value / max_val) * usable_w)
        lines.append(f'<text x="10" y="{y + bar_h - 2}" font-size="12" font-family="monospace">{label}</text>')
        lines.append(
            f'<rect x="{margin_left}" y="{y}" width="{bar_w}" height="{bar_h}" fill="#3c78d8"/>'
        )
        lines.append(
            f'<text x="{margin_left + bar_w + 6}" y="{y + bar_h - 2}" font-size="12" font-family="monospace">{value:.4f}</text>'
        )
        y += bar_h + bar_gap
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    out_dir = ROOT / "results" / "ticket-06"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Ensure ticket-05 artifacts are present after .gitignore carry-forward fix.
    ticket05_script = ROOT / "scripts" / "ticket05_counterexample_search.py"
    if ticket05_script.is_file():
        code = __import__("subprocess").run([sys.executable, str(ticket05_script)], cwd=ROOT).returncode
        if code != 0:
            raise SystemExit("ticket05 regeneration failed")

    model_defs: list[tuple[str, FinitePoset[Hashable], bool]] = []
    for n in range(2, 7):
        model_defs.append((f"C{n}", chain(n), True))
    for n in range(1, 4):
        model_defs.append((f"B{n}", boolean_lattice(n), False))

    raw_rows: list[dict[str, object]] = []
    frequency_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    frequency_totals: dict[str, int] = defaultdict(int)

    bench_sensitivity_values: dict[str, list[float]] = defaultdict(list)
    cost_sensitivity_values: dict[str, list[float]] = defaultdict(list)
    tie_change_counts: dict[str, int] = defaultdict(int)
    tie_total_counts: dict[str, int] = defaultdict(int)

    family_operator_totals: dict[str, int] = defaultdict(int)

    for model_id, poset, is_chain_model in model_defs:
        ordered = sorted(poset.elements, key=lambda x: element_key(poset, x))
        profiles = build_profiles(poset, ordered)
        benchmarks = {name: WeightedBenchmark(weights) for name, weights in profiles.items()}
        all_maps = enumerate_monotone_inflationary_maps(poset, ordered)

        step_ids: set[str] = set()
        closure_ids: set[str] = set()
        map_id_to_map: dict[str, FiniteMap[Hashable]] = {}
        for op in all_maps:
            op_id = operator_id(model_id, ordered, op)
            map_id_to_map[op_id] = op
            if op.is_idempotent():
                closure_ids.add(op_id)
            if is_chain_model and is_step_family_chain(op, int(max(ordered))):
                step_ids.add(op_id)

        family_to_ids: dict[str, list[str]] = {}
        all_ids = sorted(map_id_to_map.keys())
        if is_chain_model:
            family_to_ids[FAMILY_CHAIN_ALL] = all_ids
            family_to_ids[FAMILY_CHAIN_CLOSURE] = sorted(closure_ids)
            family_to_ids[FAMILY_CHAIN_STEP] = sorted(step_ids)
        else:
            family_to_ids[FAMILY_BOOL_ALL] = all_ids

        for family_name, operator_ids in family_to_ids.items():
            family_operator_totals[family_name] += len(operator_ids)
            if not operator_ids:
                continue

            score_cache: dict[tuple[str, str], list[CandidateScore]] = {}
            for profile_name in PROFILE_ORDER:
                for cost_name in COST_ORDER:
                    cands: list[CandidateScore] = []
                    for op_id in operator_ids:
                        op = map_id_to_map[op_id]
                        moved = [x for x in ordered if op.apply(x) != x]
                        yld = coverage_score(moved, benchmarks[profile_name])
                        if cost_name == COST_MOVED:
                            cost = moved_points_cost(op)
                        elif cost_name == COST_TOTAL:
                            cost = total_rank_lift_cost(op, poset)
                        elif cost_name == COST_AVG:
                            cost = average_rank_lift_cost(op, poset)
                        elif cost_name == COST_NORM:
                            max_total_lift = float(sum(max(poset.rank_of(y) - poset.rank_of(x) for y in ordered) for x in ordered))
                            total_lift = total_rank_lift_cost(op, poset)
                            cost = 0.0 if max_total_lift <= 0.0 else total_lift / max_total_lift
                        else:
                            raise ValueError(f"unknown cost: {cost_name}")
                        cands.append(CandidateScore(id=op_id, yield_score=yld, cost_score=cost))
                    score_cache[(profile_name, cost_name)] = cands

            frontier_sets: dict[tuple[str, str, str], set[str]] = {}
            for profile_name in PROFILE_ORDER:
                for cost_name in COST_ORDER:
                    cands = score_cache[(profile_name, cost_name)]
                    for tie_mode in TIE_ORDER:
                        frontier = frontier_with_tie_mode(cands, tie_mode)
                        frontier_ids = [cand.id for cand in frontier]
                        frontier_sets[(profile_name, cost_name, tie_mode)] = set(frontier_ids)

                        frequency_totals[family_name] += 1
                        for op_id in frontier_ids:
                            frequency_counts[family_name][op_id] += 1

                        raw_rows.append(
                            {
                                "model_id": model_id,
                                "family": family_name,
                                "profile": profile_name,
                                "cost": cost_name,
                                "tie_mode": tie_mode,
                                "operator_pool_size": len(operator_ids),
                                "frontier_size": len(frontier_ids),
                                "frontier_ids": ";".join(sorted(frontier_ids)),
                            }
                        )

            for cost_name in COST_ORDER:
                for tie_mode in TIE_ORDER:
                    sets = [frontier_sets[(profile, cost_name, tie_mode)] for profile in PROFILE_ORDER]
                    distances: list[float] = []
                    for i in range(len(sets)):
                        for j in range(i + 1, len(sets)):
                            distances.append(jaccard_distance(sets[i], sets[j]))
                    if distances:
                        bench_sensitivity_values[family_name].append(sum(distances) / len(distances))

            for profile_name in PROFILE_ORDER:
                for tie_mode in TIE_ORDER:
                    sets = [frontier_sets[(profile_name, cost, tie_mode)] for cost in COST_ORDER]
                    distances = []
                    for i in range(len(sets)):
                        for j in range(i + 1, len(sets)):
                            distances.append(jaccard_distance(sets[i], sets[j]))
                    if distances:
                        cost_sensitivity_values[family_name].append(sum(distances) / len(distances))

            for profile_name in PROFILE_ORDER:
                for cost_name in COST_ORDER:
                    s_keep = frontier_sets[(profile_name, cost_name, TIE_KEEP)]
                    s_dedup = frontier_sets[(profile_name, cost_name, TIE_DEDUP)]
                    tie_total_counts[family_name] += 1
                    if s_keep != s_dedup:
                        tie_change_counts[family_name] += 1

    raw_csv_path = out_dir / "raw_frontier_data.csv"
    fieldnames = [
        "model_id",
        "family",
        "profile",
        "cost",
        "tie_mode",
        "operator_pool_size",
        "frontier_size",
        "frontier_ids",
    ]
    with raw_csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in raw_rows:
            writer.writerow(row)

    family_summary: dict[str, dict[str, object]] = {}
    for family in sorted(frequency_totals.keys()):
        total_runs = frequency_totals[family]
        op_freq = []
        for op_id, count in frequency_counts[family].items():
            freq = 0.0 if total_runs == 0 else count / total_runs
            op_freq.append({"operator_id": op_id, "count": count, "frequency": freq})
        op_freq.sort(key=lambda r: (-float(r["frequency"]), str(r["operator_id"])))

        b_vals = bench_sensitivity_values.get(family, [])
        c_vals = cost_sensitivity_values.get(family, [])
        tie_total = tie_total_counts.get(family, 0)
        tie_changes = tie_change_counts.get(family, 0)
        tie_rate = 0.0 if tie_total == 0 else tie_changes / tie_total

        family_summary[family] = {
            "operator_pool_count": family_operator_totals.get(family, 0),
            "frontier_runs": total_runs,
            "benchmark_sensitivity_score": 0.0 if not b_vals else sum(b_vals) / len(b_vals),
            "cost_sensitivity_score": 0.0 if not c_vals else sum(c_vals) / len(c_vals),
            "tie_frontier_change_count": tie_changes,
            "tie_frontier_total_count": tie_total,
            "tie_frontier_change_rate": tie_rate,
            "frontier_appearance_frequency": op_freq,
        }

    summary = {
        "definitions": {
            "benchmark_sensitivity_score": "mean pairwise Jaccard distance of frontier sets across benchmark profiles, fixing family/model/cost/tie.",
            "cost_sensitivity_score": "mean pairwise Jaccard distance of frontier sets across cost choices, fixing family/model/benchmark/tie.",
            "tie_frontier_change_count": "number of benchmark-cost settings where frontier set differs between tie modes.",
        },
        "search_scope": {
            "chains": ["C2", "C3", "C4", "C5", "C6"],
            "boolean_lattices": ["B1", "B2", "B3"],
            "operator_families": [FAMILY_CHAIN_ALL, FAMILY_CHAIN_CLOSURE, FAMILY_CHAIN_STEP, FAMILY_BOOL_ALL],
            "benchmark_profiles": list(PROFILE_ORDER),
            "cost_choices": list(COST_ORDER),
            "tie_modes": list(TIE_ORDER),
            "deterministic": True,
            "exhaustive_within_family": True,
        },
        "family_summary": family_summary,
    }
    summary_path = out_dir / "sensitivity_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    freq_items: list[tuple[str, float]] = []
    for family in sorted(family_summary.keys()):
        top = family_summary[family]["frontier_appearance_frequency"]
        assert isinstance(top, list)
        for entry in top[:3]:
            assert isinstance(entry, dict)
            freq_items.append((f"{family} | {entry['operator_id']}", float(entry["frequency"])))
    write_svg_bar_plot(out_dir / "frequency_plot.svg", "Top Frontier Appearance Frequencies", freq_items[:12])

    sens_items = []
    for family in sorted(family_summary.keys()):
        info = family_summary[family]
        sens_items.append((f"{family} | benchmark", float(info["benchmark_sensitivity_score"])))
        sens_items.append((f"{family} | cost", float(info["cost_sensitivity_score"])))
        sens_items.append((f"{family} | tie-change-rate", float(info["tie_frontier_change_rate"])))
    write_svg_bar_plot(out_dir / "sensitivity_plot.svg", "Sensitivity Metrics by Family", sens_items)

    report_lines = [
        "# Ticket 06 Robustness and Sensitivity Audit",
        "",
        "## Setup",
        "- Models: chains C2..C6 and Boolean lattices B1..B3.",
        "- Families: chain all monotone inflationary, chain closure-only, chain step-family, Boolean all monotone inflationary.",
        f"- Benchmarks: {', '.join(PROFILE_ORDER)}.",
        f"- Costs: {', '.join(COST_ORDER)}.",
        f"- Tie modes: {', '.join(TIE_ORDER)}.",
        "",
        "## Family Metrics",
    ]
    for family in sorted(family_summary.keys()):
        info = family_summary[family]
        report_lines.append(
            "- "
            + f"{family}: benchmark_sensitivity={float(info['benchmark_sensitivity_score']):.4f}, "
            + f"cost_sensitivity={float(info['cost_sensitivity_score']):.4f}, "
            + f"tie_change_rate={float(info['tie_frontier_change_rate']):.4f}."
        )
    report_lines.append("")
    report_lines.append("## Notes")
    report_lines.append("- All runs were deterministic and exhaustive within each listed family.")
    report_lines.append("- Raw frontier rows and per-operator frequencies are in CSV/JSON outputs.")
    (out_dir / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"wrote {raw_csv_path}")
    print(f"wrote {summary_path}")
    print(f"wrote {out_dir / 'report.md'}")
    print(f"wrote {out_dir / 'frequency_plot.svg'}")
    print(f"wrote {out_dir / 'sensitivity_plot.svg'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
