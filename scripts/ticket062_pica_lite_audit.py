#!/usr/bin/env python3
from __future__ import annotations

import csv
from dataclasses import dataclass
import json
from itertools import permutations
from pathlib import Path
import sys
from typing import Hashable, TypeVar

import yaml


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
    max_rank_lift_cost,
    moved_points_cost,
    pareto_frontier,
    total_rank_lift_cost,
)


T = TypeVar("T", bound=Hashable)

PROFILE_ORDER = ("uniform", "top_heavy", "bottom_heavy", "middle_heavy")
COST_ORDER = (
    "moved_points_cost",
    "total_rank_lift_cost",
    "average_rank_lift_cost",
    "normalized_total_rank_lift_cost",
)
TIE_KEEP = "keep_all_nondominated"
TIE_DEDUP = "dedup_equal_points"
SLICE_ALL = "all_monotone_inflationary"
SLICE_BOUNDED = "bounded_lift_le_1"
SLICE_STEP = "chain_step_family"

CELL_PKG_REWRITE = "cell_pkg_rewrite"
CELL_PKG_GATE = "cell_pkg_gate"
CELL_ACCT_GATE = "cell_acct_gate"
CELL_LENS = "cell_lens_protocol"
CELL_TIE = "cell_acct_tie_protocol"
CELL_PKG_MODE = "cell_pkg_mode_from_acct"


@dataclass(frozen=True)
class Program:
    program_id: str
    active_cells: frozenset[str]


@dataclass(frozen=True)
class CandidateEval:
    op_id: str
    op: FiniteMap[Hashable]
    moved_points: list[Hashable]
    yield_score: float
    cost_score: float


def element_key(poset: FinitePoset[T], x: T) -> tuple[int, str]:
    return (poset.rank_of(x), repr(x))


def op_signature(op: FiniteMap[Hashable], ordered: list[Hashable]) -> str:
    idx = {x: i for i, x in enumerate(ordered)}
    return ",".join(str(idx[op.apply(x)]) for x in ordered)


def operator_id(model_id: str, op: FiniteMap[Hashable], ordered: list[Hashable]) -> str:
    return f"{model_id}:({op_signature(op, ordered)})"


def enumerate_monotone_inflationary_maps(poset: FinitePoset[T], ordered: list[T]) -> list[FiniteMap[T]]:
    options: dict[T, list[T]] = {}
    for x in ordered:
        ys = [y for y in ordered if poset.leq(x, y)]
        ys.sort(key=lambda z: element_key(poset, z))
        options[x] = ys

    assigned: dict[T, T] = {}
    out: list[FiniteMap[T]] = []

    def valid(x: T, fx: T) -> bool:
        for y, fy in assigned.items():
            if poset.leq(x, y) and not poset.leq(fx, fy):
                return False
            if poset.leq(y, x) and not poset.leq(fy, fx):
                return False
        return True

    def backtrack(i: int) -> None:
        if i == len(ordered):
            out.append(FiniteMap(dict(assigned)))
            return
        x = ordered[i]
        for fx in options[x]:
            if not valid(x, fx):
                continue
            assigned[x] = fx
            backtrack(i + 1)
            del assigned[x]

    backtrack(0)
    return out


def is_step_family_chain(op: FiniteMap[int], top: int) -> bool:
    for k in range(top + 1):
        if all(op.apply(x) == min(top, x + k) for x in range(top + 1)):
            return True
    return False


def build_profiles(poset: FinitePoset[T], ordered: list[T]) -> dict[str, WeightedBenchmark[T]]:
    max_rank = max(poset.rank_of(x) for x in ordered)
    mid = max_rank / 2.0
    weights = {
        "uniform": {x: 1.0 for x in ordered},
        "top_heavy": {x: float(poset.rank_of(x) + 1) for x in ordered},
        "bottom_heavy": {x: float(max_rank - poset.rank_of(x) + 1) for x in ordered},
        "middle_heavy": {x: float(1.0 / (1.0 + abs(poset.rank_of(x) - mid))) for x in ordered},
    }
    return {name: WeightedBenchmark(w) for name, w in weights.items()}


def cost_value(cost_name: str, op: FiniteMap[Hashable], poset: FinitePoset[Hashable], ordered: list[Hashable]) -> float:
    if cost_name == "moved_points_cost":
        return moved_points_cost(op)
    if cost_name == "total_rank_lift_cost":
        return total_rank_lift_cost(op, poset)
    if cost_name == "average_rank_lift_cost":
        return average_rank_lift_cost(op, poset)
    if cost_name == "normalized_total_rank_lift_cost":
        max_total = float(sum(max(poset.rank_of(y) - poset.rank_of(x) for y in ordered) for x in ordered))
        total = total_rank_lift_cost(op, poset)
        return 0.0 if max_total <= 0 else total / max_total
    raise ValueError(f"unknown cost: {cost_name}")


def dedup_equal_points(frontier: list[CandidateScore]) -> list[CandidateScore]:
    keep: dict[tuple[float, float], CandidateScore] = {}
    for c in sorted(frontier, key=lambda item: item.id):
        key = (c.yield_score, c.cost_score)
        if key not in keep:
            keep[key] = c
    return [keep[k] for k in sorted(keep.keys(), key=lambda x: (-x[0], x[1]))]


def jaccard_distance(a: set[str], b: set[str]) -> float:
    union = a | b
    if not union:
        return 0.0
    return 1.0 - (len(a & b) / len(union))


def permutation_actions(n: int) -> list[tuple[int, ...]]:
    return list(permutations(range(n)))


def permute_subset(s: frozenset[int], perm: tuple[int, ...]) -> frozenset[int]:
    return frozenset(perm[i] for i in s)


def canonical_symmetry_key(op: FiniteMap[frozenset[int]], ordered: list[frozenset[int]], perms: list[tuple[int, ...]]) -> str:
    idx = {x: i for i, x in enumerate(ordered)}
    signatures: list[tuple[int, ...]] = []
    for perm in perms:
        inv = [0] * len(perm)
        for i, p in enumerate(perm):
            inv[p] = i
        inv_t = tuple(inv)
        sig = []
        for s in ordered:
            pre = permute_subset(s, inv_t)
            mid = op.apply(pre)
            post = permute_subset(mid, perm)
            sig.append(idx[post])
        signatures.append(tuple(sig))
    best = min(signatures)
    return ",".join(str(v) for v in best)


def load_programs(path: Path) -> list[Program]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "entries" not in data:
        raise ValueError("invalid program catalog")
    out: list[Program] = []
    for entry in data["entries"]:
        out.append(Program(program_id=entry["id"], active_cells=frozenset(entry.get("active_cells", []))))
    return out


def packaging_mode(program: Program, model_kind: str) -> str:
    if CELL_PKG_MODE not in program.active_cells:
        return "raw"
    if model_kind == "boolean":
        return "strict"
    return "balanced"


def score_operator_set(
    model_id: str,
    model_kind: str,
    poset: FinitePoset[Hashable],
    ordered: list[Hashable],
    slice_name: str,
    base_ops: list[FiniteMap[Hashable]],
    is_step_map: dict[str, bool],
    sym_key_map: dict[str, str],
    program: Program,
    benchmarks: dict[str, WeightedBenchmark[Hashable]],
) -> tuple[dict[tuple[str, str, str], set[str]], int]:
    mode = packaging_mode(program, model_kind)

    # base slice filtering
    pool = []
    for op in base_ops:
        op_id = operator_id(model_id, op, ordered)
        if slice_name == SLICE_BOUNDED and max_rank_lift_cost(op, poset) > 1.0:
            continue
        if slice_name == SLICE_STEP and not is_step_map[op_id]:
            continue
        pool.append((op_id, op))

    # interaction-aware rewrite/gating
    by_sig: dict[str, tuple[str, FiniteMap[Hashable]]] = {}
    budget = max(1.0, float(poset.cardinality // 2))
    for op_id, op in pool:
        transformed = op
        if CELL_PKG_REWRITE in program.active_cells and not transformed.is_idempotent():
            transformed = transformed.iterate(len(ordered))

        keep = True
        if CELL_PKG_GATE in program.active_cells:
            max_lift = max_rank_lift_cost(transformed, poset)
            if mode == "strict":
                keep = transformed.is_idempotent() and max_lift <= 1.0
            elif mode == "balanced":
                keep = transformed.is_idempotent() or max_lift <= 1.0
        if keep and CELL_ACCT_GATE in program.active_cells:
            keep = moved_points_cost(transformed) <= budget
        if not keep:
            continue

        sid = op_signature(transformed, ordered)
        representative = by_sig.get(sid)
        if representative is None or op_id < representative[0]:
            by_sig[sid] = (op_id, transformed)

    candidates = [(rep_id, op) for rep_id, op in by_sig.values()]

    tie_modes = [TIE_DEDUP] if CELL_TIE in program.active_cells else [TIE_KEEP, TIE_DEDUP]

    out: dict[tuple[str, str, str], set[str]] = {}
    for profile in PROFILE_ORDER:
        for cost_name in COST_ORDER:
            scored: list[CandidateScore] = []
            for rep_id, op in candidates:
                moved = [x for x in ordered if op.apply(x) != x]
                yld = coverage_score(moved, benchmarks[profile])
                cost = cost_value(cost_name, op, poset, ordered)
                scored.append(CandidateScore(id=rep_id, yield_score=yld, cost_score=cost))
            frontier = pareto_frontier(scored)
            for tie in tie_modes:
                frontier_use = frontier
                if tie == TIE_DEDUP:
                    frontier_use = dedup_equal_points(frontier_use)
                ids = [c.id for c in frontier_use]
                if CELL_LENS in program.active_cells and model_kind == "boolean":
                    ids = sorted({f"sym:{sym_key_map[i]}" for i in ids})
                else:
                    ids = sorted(ids)
                out[(profile, cost_name, tie)] = set(ids)
            if TIE_KEEP not in tie_modes:
                out[(profile, cost_name, TIE_KEEP)] = set(out[(profile, cost_name, TIE_DEDUP)])

    return out, len(candidates)


def mean_pairwise_jaccard(sets: list[set[str]]) -> float:
    if len(sets) < 2:
        return 0.0
    dists: list[float] = []
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            dists.append(jaccard_distance(sets[i], sets[j]))
    return sum(dists) / len(dists)


def main() -> int:
    programs = load_programs(ROOT / "data" / "pica_toy" / "program_catalog.yaml")
    out_dir = ROOT / "results" / "ticket-06-2"
    out_dir.mkdir(parents=True, exist_ok=True)

    model_defs: list[tuple[str, FinitePoset[Hashable], str]] = []
    for n in range(3, 7):
        model_defs.append((f"C{n}", chain(n), "chain"))
    for n in range(1, 4):
        model_defs.append((f"B{n}", boolean_lattice(n), "boolean"))

    rows: list[dict[str, object]] = []
    by_program_values: dict[str, list[float]] = {}
    by_program_pool: dict[str, list[float]] = {}

    for model_id, poset, model_kind in model_defs:
        ordered = sorted(poset.elements, key=lambda x: element_key(poset, x))
        base_ops = enumerate_monotone_inflationary_maps(poset, ordered)
        benchmarks = build_profiles(poset, ordered)

        is_step: dict[str, bool] = {}
        for op in base_ops:
            op_id = operator_id(model_id, op, ordered)
            if model_kind == "chain":
                is_step[op_id] = is_step_family_chain(op, int(max(ordered)))
            else:
                is_step[op_id] = False

        sym_key_map: dict[str, str] = {}
        if model_kind == "boolean":
            perms = permutation_actions(int(model_id[1:]))
            for op in base_ops:
                op_id = operator_id(model_id, op, ordered)
                sym_key_map[op_id] = canonical_symmetry_key(op, ordered, perms)

        slice_names = [SLICE_ALL, SLICE_BOUNDED]
        if model_kind == "chain":
            slice_names.append(SLICE_STEP)

        for slice_name in slice_names:
            program_metrics: dict[str, tuple[float, float, float, int]] = {}
            for program in programs:
                if program.program_id == "chain_step_fallback" and model_kind != "chain":
                    continue
                frontier_map, pool_size = score_operator_set(
                    model_id=model_id,
                    model_kind=model_kind,
                    poset=poset,
                    ordered=ordered,
                    slice_name=slice_name,
                    base_ops=base_ops,
                    is_step_map=is_step,
                    sym_key_map=sym_key_map,
                    program=program,
                    benchmarks=benchmarks,
                )

                bench_vals = []
                for cost in COST_ORDER:
                    for tie in (TIE_KEEP, TIE_DEDUP):
                        sets = [frontier_map[(profile, cost, tie)] for profile in PROFILE_ORDER]
                        bench_vals.append(mean_pairwise_jaccard(sets))
                bench_stability = sum(bench_vals) / len(bench_vals) if bench_vals else 0.0

                cost_vals = []
                for profile in PROFILE_ORDER:
                    for tie in (TIE_KEEP, TIE_DEDUP):
                        sets = [frontier_map[(profile, cost, tie)] for cost in COST_ORDER]
                        cost_vals.append(mean_pairwise_jaccard(sets))
                cost_stability = sum(cost_vals) / len(cost_vals) if cost_vals else 0.0

                tie_change = 0
                tie_total = 0
                for profile in PROFILE_ORDER:
                    for cost in COST_ORDER:
                        tie_total += 1
                        if frontier_map[(profile, cost, TIE_KEEP)] != frontier_map[(profile, cost, TIE_DEDUP)]:
                            tie_change += 1
                tie_sens = 0.0 if tie_total == 0 else tie_change / tie_total
                instability = bench_stability + cost_stability + tie_sens
                program_metrics[program.program_id] = (bench_stability, cost_stability, tie_sens, pool_size)

                rows.append(
                    {
                        "model_id": model_id,
                        "model_kind": model_kind,
                        "slice": slice_name,
                        "program_id": program.program_id,
                        "benchmark_stability": round(bench_stability, 6),
                        "cost_stability": round(cost_stability, 6),
                        "tie_sensitivity": round(tie_sens, 6),
                        "instability_total": round(instability, 6),
                        "candidate_pool_size": pool_size,
                    }
                )

                by_program_values.setdefault(program.program_id, []).append(instability)
                by_program_pool.setdefault(program.program_id, []).append(float(pool_size))

            if "baseline_raw" in program_metrics:
                base_instability = sum(program_metrics["baseline_raw"][:3])
                for prog_id, metrics in program_metrics.items():
                    delta = sum(metrics[:3]) - base_instability
                    for row in reversed(rows):
                        if row["model_id"] == model_id and row["slice"] == slice_name and row["program_id"] == prog_id:
                            row["delta_vs_baseline"] = round(delta, 6)
                            break

    csv_path = out_dir / "program_stability.csv"
    fields = [
        "model_id",
        "model_kind",
        "slice",
        "program_id",
        "benchmark_stability",
        "cost_stability",
        "tie_sensitivity",
        "instability_total",
        "candidate_pool_size",
        "delta_vs_baseline",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            if "delta_vs_baseline" not in row:
                row["delta_vs_baseline"] = 0.0
            writer.writerow(row)

    program_summary: dict[str, dict[str, float]] = {}
    for prog_id, vals in by_program_values.items():
        mean_inst = sum(vals) / len(vals)
        mean_pool = sum(by_program_pool[prog_id]) / len(by_program_pool[prog_id])
        program_summary[prog_id] = {
            "mean_instability_total": mean_inst,
            "mean_candidate_pool_size": mean_pool,
        }

    baseline_mean = program_summary["baseline_raw"]["mean_instability_total"]
    baseline_pool = program_summary["baseline_raw"]["mean_candidate_pool_size"]

    ablation: dict[str, object] = {
        "baseline_raw_mean_instability": baseline_mean,
        "combined_core_mean_instability": program_summary.get("combined_core", {}).get("mean_instability_total", 0.0),
        "program_summary": program_summary,
        "improves_over_baseline_programs": sorted(
            [
                pid
                for pid, info in program_summary.items()
                if info["mean_instability_total"] < baseline_mean
            ]
        ),
        "ablation_cell_importance": {},
    }

    loo = {
        CELL_PKG_REWRITE: "combined_minus_pkg_rewrite",
        CELL_PKG_GATE: "combined_minus_pkg_gate",
        CELL_ACCT_GATE: "combined_minus_acct_gate",
        CELL_LENS: "combined_minus_lens_protocol",
        CELL_TIE: "combined_minus_acct_tie_protocol",
        CELL_PKG_MODE: "combined_minus_pkg_mode_from_acct",
    }
    combined = program_summary.get("combined_core", {}).get("mean_instability_total")
    if combined is not None:
        for cell_id, prog_id in loo.items():
            if prog_id in program_summary:
                delta = program_summary[prog_id]["mean_instability_total"] - combined
                ablation["ablation_cell_importance"][cell_id] = {
                    "delta_instability_when_removed": delta
                }

    collapse_flags: dict[str, bool] = {}
    for pid, info in program_summary.items():
        ratio = 0.0 if baseline_pool <= 0 else info["mean_candidate_pool_size"] / baseline_pool
        collapse_flags[pid] = ratio < 0.2
        info["pool_ratio_vs_baseline"] = ratio
    ablation["possible_trivial_collapse_flags"] = collapse_flags

    ablation_path = out_dir / "ablation_effects.json"
    ablation_path.write_text(json.dumps(ablation, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    improves = ablation["improves_over_baseline_programs"]
    report_lines = [
        "# Ticket 6.2 PICA-lite Interaction Audit",
        "",
        "## Core answer",
        f"- Any program improving over baseline_raw: {'yes' if improves else 'no'}.",
        f"- Improving programs: {', '.join(improves) if improves else 'none'}.",
        "",
        "## Ablation signal",
    ]
    cell_importance = ablation["ablation_cell_importance"]
    if isinstance(cell_importance, dict) and cell_importance:
        ranked = sorted(
            cell_importance.items(),
            key=lambda kv: float(kv[1]["delta_instability_when_removed"]),
            reverse=True,
        )
        for cell_id, info in ranked:
            report_lines.append(
                f"- {cell_id}: delta_instability_when_removed={float(info['delta_instability_when_removed']):.6f}"
            )
    else:
        report_lines.append("- no ablation data available")
    report_lines.append("")
    report_lines.append("## Trivial-collapse check")
    for pid in sorted(program_summary):
        ratio = float(program_summary[pid]["pool_ratio_vs_baseline"])
        collapse = collapse_flags[pid]
        report_lines.append(f"- {pid}: pool_ratio_vs_baseline={ratio:.4f}, possible_trivial_collapse={collapse}")
    report_lines.append("")
    report_lines.append("## Interpretation")
    report_lines.append("- Improvements are interaction-profile dependent and evaluated against baseline_raw.")
    report_lines.append("- Collapse flags indicate where stability gains may come mostly from heavy candidate pruning.")
    (out_dir / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"wrote {csv_path}")
    print(f"wrote {ablation_path}")
    print(f"wrote {out_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
