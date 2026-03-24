#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
import csv
from itertools import permutations
import json
from pathlib import Path
import sys
from typing import Hashable, TypeVar


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
TIE_ORDER = (TIE_KEEP, TIE_DEDUP)
LENS_ORDER = ("raw", "quotient")

SURVIVOR_ID = "pair__cell_pkg_gate__cell_pkg_mode_from_acct"

PROGRAM_IDS = (
    "baseline_raw",
    "singleton__cell_pkg_gate",
    "singleton__cell_pkg_mode_from_acct",
    SURVIVOR_ID,
    "surrogate_closure_only",
    "surrogate_bounded_lift_le_1",
    "surrogate_bounded_lift_le_2",
)

SINGLETON_OR_SURROGATE = {
    "singleton__cell_pkg_gate",
    "singleton__cell_pkg_mode_from_acct",
    "surrogate_closure_only",
    "surrogate_bounded_lift_le_1",
    "surrogate_bounded_lift_le_2",
}


@dataclass(frozen=True)
class Context:
    model_id: str
    profile: str
    cost: str
    tie: str
    lens: str

    def key(self) -> str:
        return f"{self.model_id}|{self.profile}|{self.cost}|{self.tie}|{self.lens}"


def element_key(poset: FinitePoset[T], x: T) -> tuple[int, str]:
    return (poset.rank_of(x), repr(x))


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


def op_signature(op: FiniteMap[Hashable], ordered: list[Hashable]) -> str:
    idx = {x: i for i, x in enumerate(ordered)}
    return ",".join(str(idx[op.apply(x)]) for x in ordered)


def op_id(model_id: str, op: FiniteMap[Hashable], ordered: list[Hashable]) -> str:
    return f"{model_id}:({op_signature(op, ordered)})"


def dedup_equal_points(frontier: list[CandidateScore]) -> list[CandidateScore]:
    keep: dict[tuple[float, float], CandidateScore] = {}
    for c in sorted(frontier, key=lambda x: x.id):
        key = (c.yield_score, c.cost_score)
        if key not in keep:
            keep[key] = c
    return [keep[k] for k in sorted(keep.keys(), key=lambda p: (-p[0], p[1]))]


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


def permute_subset(s: frozenset[int], perm: tuple[int, ...]) -> frozenset[int]:
    return frozenset(perm[i] for i in s)


def canonical_symmetry_key(op: FiniteMap[frozenset[int]], ordered: list[frozenset[int]], n: int) -> str:
    idx = {x: i for i, x in enumerate(ordered)}
    signatures: list[tuple[int, ...]] = []
    for perm in permutations(range(n)):
        inv = [0] * n
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


def jaccard_distance(a: set[str], b: set[str]) -> float:
    u = a | b
    if not u:
        return 0.0
    return 1.0 - (len(a & b) / len(u))


def mean_pairwise_jaccard(sets: list[set[str]]) -> float:
    if len(sets) < 2:
        return 0.0
    vals = []
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            vals.append(jaccard_distance(sets[i], sets[j]))
    return sum(vals) / len(vals)


def choose_packaging_mode_state_dependent(
    base_pool: list[tuple[str, FiniteMap[Hashable]]],
    poset: FinitePoset[Hashable],
    profile: str,
    cost_name: str,
) -> str:
    if not base_pool:
        return "strict"
    moved_vals = [moved_points_cost(op) for _, op in base_pool]
    mean_moved = sum(moved_vals) / len(moved_vals)
    moved_ratio = mean_moved / max(1.0, float(poset.cardinality))
    non_idem_ratio = sum(1 for _, op in base_pool if not op.is_idempotent()) / len(base_pool)
    high_lift_ratio = sum(1 for _, op in base_pool if max_rank_lift_cost(op, poset) > 1.0) / len(base_pool)

    profile_signal = {
        "uniform": 0.45,
        "top_heavy": 0.75,
        "bottom_heavy": 0.25,
        "middle_heavy": 0.55,
    }[profile]
    cost_signal = {
        "moved_points_cost": 0.70,
        "total_rank_lift_cost": 0.60,
        "average_rank_lift_cost": 0.35,
        "normalized_total_rank_lift_cost": 0.50,
    }[cost_name]
    budget_state_signal = (profile_signal + cost_signal) / 2.0
    pool_signal = 0.50 * non_idem_ratio + 0.30 * high_lift_ratio + 0.20 * moved_ratio
    total_signal = 0.6 * pool_signal + 0.4 * budget_state_signal
    if total_signal >= 0.67:
        return "strict"
    if total_signal >= 0.40:
        return "balanced"
    return "raw"


def apply_program_filter(
    program_id: str,
    base_pool: list[tuple[str, FiniteMap[Hashable]]],
    poset: FinitePoset[Hashable],
    profile: str,
    cost_name: str,
) -> tuple[list[tuple[str, FiniteMap[Hashable]]], str]:
    mode = "raw"
    pool = list(base_pool)

    if program_id == "surrogate_closure_only":
        return [(oid, op) for oid, op in pool if op.is_idempotent()], mode
    if program_id == "surrogate_bounded_lift_le_1":
        return [(oid, op) for oid, op in pool if max_rank_lift_cost(op, poset) <= 1.0], mode
    if program_id == "surrogate_bounded_lift_le_2":
        return [(oid, op) for oid, op in pool if max_rank_lift_cost(op, poset) <= 2.0], mode
    if program_id == "baseline_raw":
        return pool, mode
    if program_id == "singleton__cell_pkg_mode_from_acct":
        mode = choose_packaging_mode_state_dependent(pool, poset, profile, cost_name)
        return pool, mode
    if program_id in {"singleton__cell_pkg_gate", SURVIVOR_ID}:
        if program_id == SURVIVOR_ID:
            mode = choose_packaging_mode_state_dependent(pool, poset, profile, cost_name)
        out: list[tuple[str, FiniteMap[Hashable]]] = []
        for oid, op in pool:
            if mode == "strict":
                keep = op.is_idempotent() and max_rank_lift_cost(op, poset) <= 1.0
            elif mode == "balanced":
                keep = op.is_idempotent() or max_rank_lift_cost(op, poset) <= 1.0
            else:
                keep = True
            if keep:
                out.append((oid, op))
        return out, mode
    raise ValueError(f"unknown program id: {program_id}")


def frontier_for_context(
    program_id: str,
    model_id: str,
    model_kind: str,
    poset: FinitePoset[Hashable],
    ordered: list[Hashable],
    base_pool: list[tuple[str, FiniteMap[Hashable]]],
    profile: str,
    cost_name: str,
    tie: str,
    lens: str,
    benchmarks: dict[str, WeightedBenchmark[Hashable]],
    sym_keys: dict[str, str],
) -> tuple[set[str], int, str]:
    filtered, mode = apply_program_filter(program_id, base_pool, poset, profile, cost_name)
    scored: list[CandidateScore] = []
    for oid, op in filtered:
        moved = [x for x in ordered if op.apply(x) != x]
        yld = coverage_score(moved, benchmarks[profile])
        cost = cost_value(cost_name, op, poset, ordered)
        scored.append(CandidateScore(id=oid, yield_score=yld, cost_score=cost))
    frontier = pareto_frontier(scored)
    if tie == TIE_DEDUP:
        frontier = dedup_equal_points(frontier)
    ids = {c.id for c in frontier}
    if lens == "quotient" and model_kind == "boolean":
        return {f"sym:{sym_keys[i]}" for i in ids}, len(filtered), mode
    return ids, len(filtered), mode


def main() -> int:
    out_dir = ROOT / "results" / "ticket-06-4"
    out_dir.mkdir(parents=True, exist_ok=True)

    model_defs: list[tuple[str, FinitePoset[Hashable], str]] = []
    for n in range(3, 7):
        model_defs.append((f"C{n}", chain(n), "chain"))
    for n in range(1, 4):
        model_defs.append((f"B{n}", boolean_lattice(n), "boolean"))

    contexts: list[Context] = []
    frontier_sets: dict[str, dict[str, set[str]]] = {pid: {} for pid in PROGRAM_IDS}
    pool_ratios: dict[str, list[float]] = {pid: [] for pid in PROGRAM_IDS}
    mode_counter: dict[str, int] = {"raw": 0, "balanced": 0, "strict": 0}
    total_mode_contexts = 0

    for model_id, poset, model_kind in model_defs:
        ordered = sorted(poset.elements, key=lambda x: element_key(poset, x))
        all_ops = enumerate_monotone_inflationary_maps(poset, ordered)
        base_pool = [(op_id(model_id, op, ordered), op) for op in all_ops]
        base_size = len(base_pool)
        benchmarks = build_profiles(poset, ordered)
        sym_keys: dict[str, str] = {}
        if model_kind == "boolean":
            n = int(model_id[1:])
            ordered_bool = [x for x in ordered if isinstance(x, frozenset)]
            for oid, op in base_pool:
                sym_keys[oid] = canonical_symmetry_key(op, ordered_bool, n)  # type: ignore[arg-type]

        for profile in PROFILE_ORDER:
            for cost_name in COST_ORDER:
                for tie in TIE_ORDER:
                    for lens in LENS_ORDER:
                        ctx = Context(model_id=model_id, profile=profile, cost=cost_name, tie=tie, lens=lens)
                        contexts.append(ctx)
                        key = ctx.key()
                        for pid in PROGRAM_IDS:
                            frontier, pool_size, mode = frontier_for_context(
                                program_id=pid,
                                model_id=model_id,
                                model_kind=model_kind,
                                poset=poset,
                                ordered=ordered,
                                base_pool=base_pool,
                                profile=profile,
                                cost_name=cost_name,
                                tie=tie,
                                lens=lens,
                                benchmarks=benchmarks,
                                sym_keys=sym_keys,
                            )
                            frontier_sets[pid][key] = frontier
                            ratio = 0.0 if base_size == 0 else pool_size / base_size
                            pool_ratios[pid].append(ratio)
                            if pid == SURVIVOR_ID:
                                mode_counter[mode] = mode_counter.get(mode, 0) + 1
                                total_mode_contexts += 1

    # Instability metrics by program on raw lens.
    instability: dict[str, float] = {}
    for pid in PROGRAM_IDS:
        bench_vals: list[float] = []
        cost_vals: list[float] = []
        tie_vals: list[float] = []
        for model_id, _p, _k in model_defs:
            # benchmark instability: vary benchmark, fix cost/tie.
            for cost_name in COST_ORDER:
                for tie in TIE_ORDER:
                    sets = [
                        frontier_sets[pid][Context(model_id, profile, cost_name, tie, "raw").key()]
                        for profile in PROFILE_ORDER
                    ]
                    bench_vals.append(mean_pairwise_jaccard(sets))
            # cost instability: vary cost, fix benchmark/tie.
            for profile in PROFILE_ORDER:
                for tie in TIE_ORDER:
                    sets = [
                        frontier_sets[pid][Context(model_id, profile, cost_name, tie, "raw").key()]
                        for cost_name in COST_ORDER
                    ]
                    cost_vals.append(mean_pairwise_jaccard(sets))
            # tie sensitivity: keep vs dedup, fix benchmark/cost.
            for profile in PROFILE_ORDER:
                for cost_name in COST_ORDER:
                    a = frontier_sets[pid][Context(model_id, profile, cost_name, TIE_KEEP, "raw").key()]
                    b = frontier_sets[pid][Context(model_id, profile, cost_name, TIE_DEDUP, "raw").key()]
                    tie_vals.append(jaccard_distance(a, b))
        bench = sum(bench_vals) / len(bench_vals) if bench_vals else 0.0
        cost = sum(cost_vals) / len(cost_vals) if cost_vals else 0.0
        tie = sum(tie_vals) / len(tie_vals) if tie_vals else 0.0
        instability[pid] = bench + cost + tie

    # Behavioral equivalence to survivor.
    total_contexts = len(contexts)
    equivalence: dict[str, float] = {}
    eq_count: dict[str, int] = {}
    for pid in PROGRAM_IDS:
        if pid == SURVIVOR_ID:
            continue
        matches = 0
        for ctx in contexts:
            key = ctx.key()
            if frontier_sets[pid][key] == frontier_sets[SURVIVOR_ID][key]:
                matches += 1
        eq_count[pid] = matches
        equivalence[pid] = matches / total_contexts if total_contexts > 0 else 0.0

    # Write comparison CSV.
    csv_path = out_dir / "survivor_comparison.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "comparator_id",
            "equivalence_rate_to_survivor",
            "matching_contexts",
            "total_contexts",
            "mean_raw_instability",
            "mean_pool_ratio_vs_baseline",
            "relative_instability_gap_vs_survivor",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        survivor_instability = instability[SURVIVOR_ID]
        for pid in [p for p in PROGRAM_IDS if p != SURVIVOR_ID]:
            comp_inst = instability[pid]
            rel_gap = 0.0 if comp_inst == 0 else (comp_inst - survivor_instability) / comp_inst
            writer.writerow(
                {
                    "comparator_id": pid,
                    "equivalence_rate_to_survivor": round(equivalence[pid], 8),
                    "matching_contexts": eq_count[pid],
                    "total_contexts": total_contexts,
                    "mean_raw_instability": round(comp_inst, 8),
                    "mean_pool_ratio_vs_baseline": round(sum(pool_ratios[pid]) / len(pool_ratios[pid]), 8),
                    "relative_instability_gap_vs_survivor": round(rel_gap, 8),
                }
            )

    mode_usage = {
        "total_contexts": total_mode_contexts,
        "mode_counts": mode_counter,
        "mode_frequencies": {
            mode: (count / total_mode_contexts if total_mode_contexts > 0 else 0.0)
            for mode, count in mode_counter.items()
        },
    }
    mode_path = out_dir / "mode_usage.json"
    mode_path.write_text(json.dumps(mode_usage, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    survivor_instability = instability[SURVIVOR_ID]
    best_singleton_or_surrogate = min(SINGLETON_OR_SURROGATE, key=lambda pid: instability[pid])
    best_comp_inst = instability[best_singleton_or_surrogate]
    relative_improvement = 0.0 if best_comp_inst == 0 else (best_comp_inst - survivor_instability) / best_comp_inst
    survivor_ratio = sum(pool_ratios[SURVIVOR_ID]) / len(pool_ratios[SURVIVOR_ID])

    max_equiv = max(equivalence[pid] for pid in equivalence) if equivalence else 0.0
    mode_freq = mode_usage["mode_frequencies"]
    active_modes = [m for m, p in mode_freq.items() if p >= 0.10]

    checks = {
        "equivalence_check": max_equiv <= 0.90,
        "mode_diversity_check": len(active_modes) >= 2,
        "pool_ratio_floor_check": survivor_ratio >= 0.70,
        "relative_improvement_check": relative_improvement >= 0.05,
    }
    nontrivial = all(checks.values())

    closest_simpler = max(equivalence.items(), key=lambda item: item[1])[0] if equivalence else "none"

    summary = {
        "survivor_id": SURVIVOR_ID,
        "mean_raw_instability": survivor_instability,
        "mean_pool_ratio_vs_baseline": survivor_ratio,
        "best_singleton_or_surrogate": best_singleton_or_surrogate,
        "best_singleton_or_surrogate_instability": best_comp_inst,
        "relative_improvement_vs_best_singleton_or_surrogate": relative_improvement,
        "equivalence_rates_to_survivor": equivalence,
        "max_equivalence_rate": max_equiv,
        "checks": checks,
        "nontriviality_floor_cleared": nontrivial,
        "closest_simpler_explanation": closest_simpler,
        "mode_usage": mode_usage,
        "theorem_ready_slice_found": nontrivial,
    }
    summary_path = out_dir / "nontriviality_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report_lines = [
        "# Ticket 6.4 Survivor Isolation and Nontriviality Floor",
        "",
        f"- Nontriviality floor cleared: {nontrivial}.",
        f"- Closest simpler explanation: {closest_simpler}.",
        f"- Theorem-ready slice found: {nontrivial}.",
    ]
    report_lines.append("")
    report_lines.append("## Check outcomes")
    for k, v in checks.items():
        report_lines.append(f"- {k}: {v}")
    report_lines.append("")
    report_lines.append("## Mode usage")
    for mode in ("raw", "balanced", "strict"):
        count = mode_counter.get(mode, 0)
        freq = mode_usage["mode_frequencies"][mode]
        report_lines.append(f"- {mode}: count={count}, freq={freq:.6f}")
    report_path = out_dir / "report.md"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"wrote {csv_path}")
    print(f"wrote {mode_path}")
    print(f"wrote {summary_path}")
    print(f"wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
