#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
import csv
from itertools import combinations, permutations
import json
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
TIE_ORDER = ("keep_all_nondominated", "dedup_equal_points")
TIE_KEEP = "keep_all_nondominated"
TIE_DEDUP = "dedup_equal_points"
LENS_ORDER = ("raw", "quotient")

SLICE_ALL = "all_monotone_inflationary"
SLICE_BOUNDED = "bounded_lift_le_1"
SLICE_STEP = "chain_step_family"

CELL_PKG_REWRITE = "cell_pkg_rewrite"
CELL_PKG_GATE = "cell_pkg_gate"
CELL_ACCT_GATE = "cell_acct_gate"
CELL_LENS = "cell_lens_protocol"
CELL_TIE = "cell_acct_tie_protocol"
CELL_PKG_MODE = "cell_pkg_mode_from_acct"

ORDER_REWRITE_GATE = "rewrite_then_gate"
ORDER_GATE_REWRITE = "gate_then_rewrite"

REQUIRED_CORES = (
    "baseline_raw",
    "lens_protocol_core",
    "accounting_core",
    "packaging_core",
    "combined_core",
    "chain_step_fallback",
)


@dataclass(frozen=True)
class Program:
    id: str
    cells: frozenset[str]


@dataclass(frozen=True)
class ProgramMetrics:
    raw_instability: float
    quotient_instability: float
    tie_policy_sensitivity: float
    pool_ratio_vs_baseline: float
    composite_raw: float
    interaction_gain: float
    flag_tie_suppression_artifact: bool
    flag_quotient_only_improvement: bool
    flag_hard_coded_packaging_choice: bool
    flag_excessive_pruning_collapse: bool
    survives_all_artifact_flags: bool


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

    def valid_choice(x: T, fx: T) -> bool:
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
            if not valid_choice(x, fx):
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
    return {name: WeightedBenchmark(v) for name, v in weights.items()}


def op_signature(op: FiniteMap[Hashable], ordered: list[Hashable]) -> str:
    idx = {x: i for i, x in enumerate(ordered)}
    return ",".join(str(idx[op.apply(x)]) for x in ordered)


def op_id(model_id: str, op: FiniteMap[Hashable], ordered: list[Hashable]) -> str:
    return f"{model_id}:({op_signature(op, ordered)})"


def dedup_equal_points(frontier: list[CandidateScore]) -> list[CandidateScore]:
    keep: dict[tuple[float, float], CandidateScore] = {}
    for cand in sorted(frontier, key=lambda c: c.id):
        key = (cand.yield_score, cand.cost_score)
        if key not in keep:
            keep[key] = cand
    return [keep[k] for k in sorted(keep.keys(), key=lambda x: (-x[0], x[1]))]


def jaccard_distance(a: set[str], b: set[str]) -> float:
    u = a | b
    if not u:
        return 0.0
    return 1.0 - (len(a & b) / len(u))


def mean_pairwise_jaccard(sets: list[set[str]]) -> float:
    if len(sets) < 2:
        return 0.0
    vals: list[float] = []
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            vals.append(jaccard_distance(sets[i], sets[j]))
    return sum(vals) / len(vals)


def permute_subset(s: frozenset[int], perm: tuple[int, ...]) -> frozenset[int]:
    return frozenset(perm[i] for i in s)


def canonical_symmetry_key(op: FiniteMap[frozenset[int]], ordered: list[frozenset[int]], n: int) -> str:
    perms = permutations(range(n))
    idx = {x: i for i, x in enumerate(ordered)}
    signatures: list[tuple[int, ...]] = []
    for perm in perms:
        inv = [0] * n
        for i, p in enumerate(perm):
            inv[p] = i
        inv_t = tuple(inv)
        sig: list[int] = []
        for s in ordered:
            pre = permute_subset(s, inv_t)
            mid = op.apply(pre)
            post = permute_subset(mid, perm)
            sig.append(idx[post])
        signatures.append(tuple(sig))
    best = min(signatures)
    return ",".join(str(v) for v in best)


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


def load_cells() -> list[str]:
    path = ROOT / "data" / "pica_toy" / "cell_catalog.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = data.get("entries", [])
    out = [entry["id"] for entry in entries]
    required = {
        CELL_PKG_REWRITE,
        CELL_PKG_GATE,
        CELL_ACCT_GATE,
        CELL_LENS,
        CELL_TIE,
        CELL_PKG_MODE,
    }
    missing = required - set(out)
    if missing:
        raise ValueError(f"missing required cells in catalog: {sorted(missing)}")
    return out


def load_core_programs() -> dict[str, Program]:
    path = ROOT / "data" / "pica_toy" / "program_catalog.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = data.get("entries", [])
    out: dict[str, Program] = {}
    for entry in entries:
        pid = entry["id"]
        out[pid] = Program(id=pid, cells=frozenset(entry.get("active_cells", [])))
    for pid in REQUIRED_CORES:
        if pid not in out:
            raise ValueError(f"missing required program in catalog: {pid}")
    return out


def generate_programs(cells: list[str], cores: dict[str, Program]) -> dict[str, Program]:
    programs: dict[str, Program] = {}
    programs["baseline_raw"] = Program("baseline_raw", frozenset())
    for c in sorted(cells):
        programs[f"singleton__{c}"] = Program(f"singleton__{c}", frozenset({c}))
    for a, b in combinations(sorted(cells), 2):
        pid = f"pair__{a}__{b}"
        programs[pid] = Program(pid, frozenset({a, b}))
    for pid in ("lens_protocol_core", "accounting_core", "packaging_core", "combined_core", "chain_step_fallback"):
        programs[pid] = cores[pid]
    return programs


def choose_packaging_mode(
    cells: frozenset[str],
    pool: list[tuple[str, FiniteMap[Hashable]]],
    poset: FinitePoset[Hashable],
) -> str:
    if CELL_PKG_MODE not in cells:
        return "raw"
    if not pool:
        return "strict"
    moved_vals = [moved_points_cost(op) for _, op in pool]
    mean_moved = sum(moved_vals) / len(moved_vals)
    moved_ratio = mean_moved / max(1.0, float(poset.cardinality))
    non_idem_ratio = sum(1 for _, op in pool if not op.is_idempotent()) / len(pool)
    high_lift_ratio = sum(1 for _, op in pool if max_rank_lift_cost(op, poset) > 1.0) / len(pool)
    signal = 0.5 * non_idem_ratio + 0.3 * high_lift_ratio + 0.2 * moved_ratio
    if signal >= 0.66:
        return "strict"
    if signal >= 0.33:
        return "balanced"
    return "raw"


def filter_pool_by_slice(
    pool: list[tuple[str, FiniteMap[Hashable]]],
    slice_name: str,
    poset: FinitePoset[Hashable],
    step_map: dict[str, bool],
) -> list[tuple[str, FiniteMap[Hashable]]]:
    out: list[tuple[str, FiniteMap[Hashable]]] = []
    for oid, op in pool:
        if slice_name == SLICE_BOUNDED and max_rank_lift_cost(op, poset) > 1.0:
            continue
        if slice_name == SLICE_STEP and not step_map.get(oid, False):
            continue
        out.append((oid, op))
    return out


def transform_pool(
    pool: list[tuple[str, FiniteMap[Hashable]]],
    cells: frozenset[str],
    poset: FinitePoset[Hashable],
    ordered: list[Hashable],
    order_mode: str,
    packaging_mode: str,
) -> list[tuple[str, FiniteMap[Hashable]]]:
    budget_cap = float(max(1, poset.cardinality // 2))
    if packaging_mode == "strict":
        budget_cap = max(1.0, float(poset.cardinality // 3))
    elif packaging_mode == "balanced":
        budget_cap = max(1.0, float((poset.cardinality + 1) // 2))

    def rewrite(op: FiniteMap[Hashable]) -> FiniteMap[Hashable]:
        if CELL_PKG_REWRITE in cells and not op.is_idempotent():
            return op.iterate(len(ordered))
        return op

    def gate(op: FiniteMap[Hashable]) -> bool:
        keep = True
        if CELL_PKG_GATE in cells:
            lift = max_rank_lift_cost(op, poset)
            if packaging_mode == "strict":
                keep = op.is_idempotent() and lift <= 1.0
            elif packaging_mode == "balanced":
                keep = op.is_idempotent() or lift <= 1.0
        if keep and CELL_ACCT_GATE in cells:
            keep = moved_points_cost(op) <= budget_cap
        return keep

    out: list[tuple[str, FiniteMap[Hashable]]] = []
    for oid, op in pool:
        current = op
        if order_mode == ORDER_REWRITE_GATE:
            current = rewrite(current)
            if not gate(current):
                continue
        elif order_mode == ORDER_GATE_REWRITE:
            if not gate(current):
                continue
            current = rewrite(current)
        else:
            raise ValueError(f"unknown order_mode: {order_mode}")
        out.append((oid, current))

    # Deduplicate transformed operators by mapping signature.
    by_sig: dict[str, tuple[str, FiniteMap[Hashable]]] = {}
    for oid, op in out:
        sig = op_signature(op, ordered)
        chosen = by_sig.get(sig)
        if chosen is None or oid < chosen[0]:
            by_sig[sig] = (oid, op)
    reduced = sorted(by_sig.values(), key=lambda item: item[0])

    # Lens cell can optionally perform symmetry-level representative compression on boolean models.
    if CELL_LENS in cells and ordered and isinstance(ordered[0], frozenset):
        n = max(len(s) for s in ordered) if ordered else 0
        if n > 0:
            rep_by_sym: dict[str, tuple[str, FiniteMap[Hashable]]] = {}
            ordered_bool = [x for x in ordered if isinstance(x, frozenset)]
            for oid, op in reduced:
                key = canonical_symmetry_key(op, ordered_bool, n)  # type: ignore[arg-type]
                prev = rep_by_sym.get(key)
                if prev is None or oid < prev[0]:
                    rep_by_sym[key] = (oid, op)
            reduced = sorted(rep_by_sym.values(), key=lambda item: item[0])
    return reduced


def frontier_sets_for_program(
    model_id: str,
    model_kind: str,
    poset: FinitePoset[Hashable],
    ordered: list[Hashable],
    base_pool: list[tuple[str, FiniteMap[Hashable]]],
    program: Program,
    sym_key_map: dict[str, str],
    order_mode: str,
) -> tuple[dict[tuple[str, str, str, str], set[str]], int, str]:
    slice_pool = list(base_pool)
    packaging_mode = choose_packaging_mode(program.cells, slice_pool, poset)
    transformed_pool = transform_pool(
        slice_pool,
        program.cells,
        poset,
        ordered,
        order_mode,
        packaging_mode,
    )
    profiles = build_profiles(poset, ordered)

    out: dict[tuple[str, str, str, str], set[str]] = {}
    tie_epsilon = 1e-6 if CELL_TIE in program.cells else 0.0
    for profile in PROFILE_ORDER:
        for cost_name in COST_ORDER:
            scored: list[CandidateScore] = []
            for oid, op in transformed_pool:
                moved = [x for x in ordered if op.apply(x) != x]
                yld = coverage_score(moved, profiles[profile])
                cost = cost_value(cost_name, op, poset, ordered)
                if tie_epsilon > 0.0:
                    cost += tie_epsilon * moved_points_cost(op)
                scored.append(CandidateScore(id=oid, yield_score=yld, cost_score=cost))
            frontier = pareto_frontier(scored)
            frontier_map = {
                TIE_KEEP: list(frontier),
                TIE_DEDUP: dedup_equal_points(frontier),
            }
            for tie_mode in TIE_ORDER:
                ids_raw = sorted(c.id for c in frontier_map[tie_mode])
                raw_set = set(ids_raw)
                out[(profile, cost_name, tie_mode, "raw")] = raw_set
                if model_kind == "boolean":
                    out[(profile, cost_name, tie_mode, "quotient")] = {f"sym:{sym_key_map[i]}" for i in raw_set}
                else:
                    out[(profile, cost_name, tie_mode, "quotient")] = set(raw_set)

    return out, len(transformed_pool), packaging_mode


def compute_instability_metrics(frontiers: dict[tuple[str, str, str, str], set[str]], lens: str) -> tuple[float, float, float]:
    bench_vals: list[float] = []
    for cost_name in COST_ORDER:
        for tie in TIE_ORDER:
            sets = [frontiers[(profile, cost_name, tie, lens)] for profile in PROFILE_ORDER]
            bench_vals.append(mean_pairwise_jaccard(sets))
    bench_instability = sum(bench_vals) / len(bench_vals) if bench_vals else 0.0

    cost_vals: list[float] = []
    for profile in PROFILE_ORDER:
        for tie in TIE_ORDER:
            sets = [frontiers[(profile, cost_name, tie, lens)] for cost_name in COST_ORDER]
            cost_vals.append(mean_pairwise_jaccard(sets))
    cost_instability = sum(cost_vals) / len(cost_vals) if cost_vals else 0.0

    tie_vals: list[float] = []
    for profile in PROFILE_ORDER:
        for cost_name in COST_ORDER:
            a = frontiers[(profile, cost_name, TIE_KEEP, lens)]
            b = frontiers[(profile, cost_name, TIE_DEDUP, lens)]
            tie_vals.append(jaccard_distance(a, b))
    tie_sensitivity = sum(tie_vals) / len(tie_vals) if tie_vals else 0.0

    instability = bench_instability + cost_instability
    return instability, tie_sensitivity, bench_instability + cost_instability + tie_sensitivity


def main() -> int:
    cells = load_cells()
    core_programs = load_core_programs()
    programs = generate_programs(cells, core_programs)

    out_dir = ROOT / "results" / "ticket-06-3"
    out_dir.mkdir(parents=True, exist_ok=True)

    model_defs: list[tuple[str, FinitePoset[Hashable], str]] = []
    for n in range(3, 7):
        model_defs.append((f"C{n}", chain(n), "chain"))
    for n in range(1, 4):
        model_defs.append((f"B{n}", boolean_lattice(n), "boolean"))

    rows: list[dict[str, object]] = []
    baseline_pool_sizes: dict[tuple[str, str], int] = {}
    program_packaging_modes: dict[str, set[str]] = {pid: set() for pid in programs}

    # For order sensitivity
    order_sensitivity: dict[str, dict[str, object]] = {}

    for model_id, poset, model_kind in model_defs:
        ordered = sorted(poset.elements, key=lambda x: element_key(poset, x))
        all_maps = enumerate_monotone_inflationary_maps(poset, ordered)
        base_pairs = [(op_id(model_id, op, ordered), op) for op in all_maps]

        step_map: dict[str, bool] = {}
        for oid, op in base_pairs:
            if model_kind == "chain":
                step_map[oid] = is_step_family_chain(op, int(max(ordered)))
            else:
                step_map[oid] = False

        sym_key_map: dict[str, str] = {}
        if model_kind == "boolean":
            n = int(model_id[1:])
            ordered_bool = [x for x in ordered if isinstance(x, frozenset)]
            for oid, op in base_pairs:
                sym_key_map[oid] = canonical_symmetry_key(op, ordered_bool, n)  # type: ignore[arg-type]

        slices = [SLICE_ALL, SLICE_BOUNDED]
        if model_kind == "chain":
            slices.append(SLICE_STEP)

        for slice_name in slices:
            slice_pool = filter_pool_by_slice(base_pairs, slice_name, poset, step_map)
            # baseline sizing per model/slice for pruning ratio
            _, base_pool_size, _ = frontier_sets_for_program(
                model_id,
                model_kind,
                poset,
                ordered,
                slice_pool,
                programs["baseline_raw"],
                sym_key_map,
                ORDER_REWRITE_GATE,
            )
            baseline_pool_sizes[(model_id, slice_name)] = base_pool_size

            for pid, program in programs.items():
                if pid == "chain_step_fallback" and model_kind != "chain":
                    continue
                frontiers, pool_size, p_mode = frontier_sets_for_program(
                    model_id,
                    model_kind,
                    poset,
                    ordered,
                    slice_pool,
                    program,
                    sym_key_map,
                    ORDER_REWRITE_GATE,
                )
                program_packaging_modes[pid].add(p_mode)
                raw_instability, tie_raw, raw_composite = compute_instability_metrics(frontiers, "raw")
                quotient_instability, tie_quot, _quot_comp = compute_instability_metrics(frontiers, "quotient")
                tie_avg = (tie_raw + tie_quot) / 2.0
                baseline_pool = baseline_pool_sizes[(model_id, slice_name)]
                ratio = 0.0 if baseline_pool == 0 else pool_size / baseline_pool

                rows.append(
                    {
                        "program_id": pid,
                        "model_id": model_id,
                        "slice": slice_name,
                        "raw_instability": round(raw_instability, 6),
                        "quotient_instability": round(quotient_instability, 6),
                        "tie_policy_sensitivity": round(tie_avg, 6),
                        "candidate_pool_ratio_vs_baseline": round(ratio, 6),
                        "raw_composite": round(raw_composite, 6),
                    }
                )

                # Order-sensitivity check only for programs containing both rewrite and gate cells.
                if CELL_PKG_REWRITE in program.cells and CELL_PKG_GATE in program.cells:
                    alt_frontiers, _alt_pool_size, _alt_mode = frontier_sets_for_program(
                        model_id,
                        model_kind,
                        poset,
                        ordered,
                        slice_pool,
                        program,
                        sym_key_map,
                        ORDER_GATE_REWRITE,
                    )
                    changed = 0
                    total = 0
                    samples: list[dict[str, str]] = []
                    for key, base_set in frontiers.items():
                        total += 1
                        other_set = alt_frontiers[key]
                        if base_set != other_set:
                            changed += 1
                            if len(samples) < 5:
                                profile, cost_name, tie_mode, lens = key
                                samples.append(
                                    {
                                        "model_id": model_id,
                                        "slice": slice_name,
                                        "profile": profile,
                                        "cost": cost_name,
                                        "tie": tie_mode,
                                        "lens": lens,
                                    }
                                )
                    key_id = f"{pid}|{model_id}|{slice_name}"
                    order_sensitivity[key_id] = {
                        "program_id": pid,
                        "model_id": model_id,
                        "slice": slice_name,
                        "changed_contexts": changed,
                        "total_contexts": total,
                        "changed": changed > 0,
                        "sample_changed_contexts": samples,
                    }

    # Aggregate to program-level metrics.
    by_program: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        by_program.setdefault(str(row["program_id"]), []).append(row)

    agg_base: dict[str, dict[str, float]] = {}
    for pid, vals in by_program.items():
        def mean(field: str) -> float:
            return sum(float(v[field]) for v in vals) / len(vals)
        agg_base[pid] = {
            "raw_instability": mean("raw_instability"),
            "quotient_instability": mean("quotient_instability"),
            "tie_policy_sensitivity": mean("tie_policy_sensitivity"),
            "candidate_pool_ratio_vs_baseline": mean("candidate_pool_ratio_vs_baseline"),
            "raw_composite": mean("raw_composite"),
        }

    baseline = agg_base["baseline_raw"]
    baseline_raw = baseline["raw_instability"]
    baseline_quot = baseline["quotient_instability"]
    baseline_tie = baseline["tie_policy_sensitivity"]
    baseline_comp = baseline["raw_composite"]

    # Interaction gain over best proper subset among analyzed programs.
    subset_map = {pid: programs[pid].cells for pid in programs}
    interaction_gain: dict[str, float] = {}
    for pid, cells_set in subset_map.items():
        if len(cells_set) <= 1:
            interaction_gain[pid] = 0.0
            continue
        candidates = []
        for qid, qcells in subset_map.items():
            if qid == pid:
                continue
            if qcells < cells_set:  # strict subset
                candidates.append(agg_base[qid]["raw_composite"])
        if not candidates:
            interaction_gain[pid] = 0.0
        else:
            interaction_gain[pid] = min(candidates) - agg_base[pid]["raw_composite"]

    # Artifact flags and final table.
    final_metrics: dict[str, ProgramMetrics] = {}
    for pid, metrics in agg_base.items():
        raw_improve = baseline_raw - metrics["raw_instability"]
        quot_improve = baseline_quot - metrics["quotient_instability"]
        tie_improve = baseline_tie - metrics["tie_policy_sensitivity"]
        comp_improve = baseline_comp - metrics["raw_composite"]

        tie_suppression_artifact = comp_improve > 0 and tie_improve > 0 and raw_improve <= 0.1 * comp_improve
        quotient_only_improvement = quot_improve > 0 and raw_improve <= 0
        hard_coded_packaging_choice = (
            CELL_PKG_MODE in programs[pid].cells and len(program_packaging_modes.get(pid, set())) <= 1
        )
        excessive_pruning = metrics["candidate_pool_ratio_vs_baseline"] < 0.2
        survives = not (tie_suppression_artifact or quotient_only_improvement or hard_coded_packaging_choice or excessive_pruning)

        final_metrics[pid] = ProgramMetrics(
            raw_instability=metrics["raw_instability"],
            quotient_instability=metrics["quotient_instability"],
            tie_policy_sensitivity=metrics["tie_policy_sensitivity"],
            pool_ratio_vs_baseline=metrics["candidate_pool_ratio_vs_baseline"],
            composite_raw=metrics["raw_composite"],
            interaction_gain=interaction_gain[pid],
            flag_tie_suppression_artifact=tie_suppression_artifact,
            flag_quotient_only_improvement=quotient_only_improvement,
            flag_hard_coded_packaging_choice=hard_coded_packaging_choice,
            flag_excessive_pruning_collapse=excessive_pruning,
            survives_all_artifact_flags=survives,
        )

    # Write program_synergy.csv
    synergy_path = out_dir / "program_synergy.csv"
    with synergy_path.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "program_id",
            "cell_count",
            "raw_instability",
            "quotient_instability",
            "tie_policy_sensitivity",
            "candidate_pool_ratio_vs_baseline",
            "interaction_gain",
            "flag_tie_suppression_artifact",
            "flag_quotient_only_improvement",
            "flag_hard_coded_packaging_choice",
            "flag_excessive_pruning_collapse",
            "survives_all_artifact_flags",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for pid in sorted(final_metrics):
            m = final_metrics[pid]
            writer.writerow(
                {
                    "program_id": pid,
                    "cell_count": len(programs[pid].cells),
                    "raw_instability": round(m.raw_instability, 8),
                    "quotient_instability": round(m.quotient_instability, 8),
                    "tie_policy_sensitivity": round(m.tie_policy_sensitivity, 8),
                    "candidate_pool_ratio_vs_baseline": round(m.pool_ratio_vs_baseline, 8),
                    "interaction_gain": round(m.interaction_gain, 8),
                    "flag_tie_suppression_artifact": m.flag_tie_suppression_artifact,
                    "flag_quotient_only_improvement": m.flag_quotient_only_improvement,
                    "flag_hard_coded_packaging_choice": m.flag_hard_coded_packaging_choice,
                    "flag_excessive_pruning_collapse": m.flag_excessive_pruning_collapse,
                    "survives_all_artifact_flags": m.survives_all_artifact_flags,
                }
            )

    # Write anti_artifact_summary.json
    improving_raw = sorted([pid for pid, m in final_metrics.items() if m.raw_instability < baseline_raw])
    surviving = sorted([pid for pid, m in final_metrics.items() if m.survives_all_artifact_flags])
    positive_interaction = sorted([pid for pid, m in final_metrics.items() if m.interaction_gain > 0])

    best_candidate = None
    eligible = [pid for pid in final_metrics if final_metrics[pid].survives_all_artifact_flags]
    if eligible:
        best_candidate = min(eligible, key=lambda pid: final_metrics[pid].composite_raw)
    else:
        best_candidate = min(final_metrics.keys(), key=lambda pid: final_metrics[pid].composite_raw)

    summary = {
        "baseline_raw": {
            "raw_instability": baseline_raw,
            "quotient_instability": baseline_quot,
            "tie_policy_sensitivity": baseline_tie,
            "raw_composite": baseline_comp,
        },
        "program_metrics": {
            pid: {
                "cells": sorted(programs[pid].cells),
                "raw_instability": m.raw_instability,
                "quotient_instability": m.quotient_instability,
                "tie_policy_sensitivity": m.tie_policy_sensitivity,
                "candidate_pool_ratio_vs_baseline": m.pool_ratio_vs_baseline,
                "interaction_gain": m.interaction_gain,
                "flag_tie_suppression_artifact": m.flag_tie_suppression_artifact,
                "flag_quotient_only_improvement": m.flag_quotient_only_improvement,
                "flag_hard_coded_packaging_choice": m.flag_hard_coded_packaging_choice,
                "flag_excessive_pruning_collapse": m.flag_excessive_pruning_collapse,
                "survives_all_artifact_flags": m.survives_all_artifact_flags,
            }
            for pid, m in sorted(final_metrics.items())
        },
        "improving_programs_on_raw_instability": improving_raw,
        "programs_with_positive_interaction_gain": positive_interaction,
        "programs_surviving_all_artifact_flags": surviving,
        "best_program_after_anti_artifact_audit": best_candidate,
        "notes": {
            "tie_policy_externalized": True,
            "lens_axis_externalized": True,
            "packaging_mode_state_dependent": True,
        },
    }
    anti_path = out_dir / "anti_artifact_summary.json"
    anti_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    order_summary = {
        "execution_orders_compared": [ORDER_REWRITE_GATE, ORDER_GATE_REWRITE],
        "programs_checked": sorted(
            {
                programs[str(v["program_id"])].id
                for v in order_sensitivity.values()
            }
        ),
        "details": order_sensitivity,
        "any_order_sensitivity_detected": any(bool(v["changed"]) for v in order_sensitivity.values()),
    }
    order_path = out_dir / "order_sensitivity.json"
    order_path.write_text(json.dumps(order_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report_lines = [
        "# Ticket 6.3 Interaction Nontriviality and Anti-Artifact Audit",
        "",
        "## Core answers",
        f"- Any raw-stability improvement over baseline: {'yes' if improving_raw else 'no'}.",
        f"- Programs surviving all artifact flags: {', '.join(surviving) if surviving else 'none'}.",
        f"- Any positive multi-cell interaction gain: {'yes' if positive_interaction else 'no'}.",
        f"- Best candidate after anti-artifact checks: {best_candidate}.",
        "",
        "## Artifact distinction",
        "- tie-suppression artifact, quotient-only improvement, hard-coded packaging, and excessive pruning are flagged per program in anti_artifact_summary.json.",
        "",
        "## Order sensitivity",
        f"- Detected: {order_summary['any_order_sensitivity_detected']}.",
        "- Detailed changed contexts are in order_sensitivity.json.",
    ]
    report_path = out_dir / "report.md"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"wrote {synergy_path}")
    print(f"wrote {anti_path}")
    print(f"wrote {order_path}")
    print(f"wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
