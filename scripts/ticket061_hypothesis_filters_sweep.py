#!/usr/bin/env python3
from __future__ import annotations

import csv
from dataclasses import dataclass
import json
from itertools import permutations
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

VARIANT_UNIQUE_TIE = "uniqueness_up_to_score_tie_quotient"
VARIANT_UNIQUE_SYMM = "uniqueness_up_to_symmetry"
VARIANT_BENCH_STABLE = "benchmark_stability_fixed_cost_tie"
VARIANT_COST_STABLE = "cost_stability_fixed_benchmark_tie"
VARIANT_STEP_CONTAIN = "chain_step_containment"
VARIANT_ORDER = (
    VARIANT_UNIQUE_TIE,
    VARIANT_UNIQUE_SYMM,
    VARIANT_BENCH_STABLE,
    VARIANT_COST_STABLE,
    VARIANT_STEP_CONTAIN,
)


@dataclass(frozen=True)
class SliceSpec:
    name: str
    applicable_to: str
    predicate: Callable[[FiniteMap[Hashable], dict[str, object]], bool]


def element_key(poset: FinitePoset[T], x: T) -> tuple[int, str]:
    return (poset.rank_of(x), repr(x))


def operator_id(model_id: str, ordered: list[T], op: FiniteMap[T]) -> str:
    index = {x: i for i, x in enumerate(ordered)}
    images = [str(index[op.apply(x)]) for x in ordered]
    return f"{model_id}:(" + ",".join(images) + ")"


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


def is_step_family_chain(op: FiniteMap[int], top: int) -> bool:
    for k in range(top + 1):
        if all(op.apply(x) == min(top, x + k) for x in range(top + 1)):
            return True
    return False


def dedup_equal_points(frontier: list[CandidateScore]) -> list[CandidateScore]:
    selected: dict[tuple[float, float], CandidateScore] = {}
    for cand in sorted(frontier, key=lambda c: c.id):
        key = (cand.yield_score, cand.cost_score)
        if key not in selected:
            selected[key] = cand
    return [selected[key] for key in sorted(selected.keys(), key=lambda k: (-k[0], k[1]))]


def compute_cost(
    cost_name: str,
    op: FiniteMap[Hashable],
    poset: FinitePoset[Hashable],
    ordered: list[Hashable],
) -> float:
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


def canonical_symmetry_key(
    op: FiniteMap[frozenset[int]],
    ordered: list[frozenset[int]],
    n: int,
) -> str:
    index = {x: i for i, x in enumerate(ordered)}
    signatures: list[tuple[int, ...]] = []
    for perm in permutations(range(n)):
        inv = [0] * n
        for i, p in enumerate(perm):
            inv[p] = i
        inv_t = tuple(inv)
        image_indices: list[int] = []
        for s in ordered:
            pre = permute_subset(s, inv_t)
            mid = op.apply(pre)
            post = permute_subset(mid, perm)
            image_indices.append(index[post])
        signatures.append(tuple(image_indices))
    best = min(signatures)
    return ",".join(str(v) for v in best)


def frontier_ids(
    candidates: list[CandidateScore],
    tie_mode: str,
) -> list[str]:
    f = pareto_frontier(candidates)
    if tie_mode == "dedup_equal_points":
        f = dedup_equal_points(f)
    return sorted(c.id for c in f)


def main() -> int:
    out_dir = ROOT / "results" / "ticket-06-1"
    out_dir.mkdir(parents=True, exist_ok=True)

    model_defs: list[tuple[str, FinitePoset[Hashable], str]] = []
    for n in range(2, 7):
        model_defs.append((f"C{n}", chain(n), "chain"))
    for n in range(1, 4):
        model_defs.append((f"B{n}", boolean_lattice(n), "boolean"))

    slices = (
        SliceSpec("all_monotone_inflationary", "both", lambda _op, _meta: True),
        SliceSpec("closure_only", "both", lambda op, _meta: op.is_idempotent()),
        SliceSpec("bounded_lift_le_1", "both", lambda op, meta: max_rank_lift_cost(op, meta["poset"]) <= 1.0),
        SliceSpec("bounded_lift_le_2", "both", lambda op, meta: max_rank_lift_cost(op, meta["poset"]) <= 2.0),
        SliceSpec("chain_step_family", "chain", lambda _op, meta: bool(meta["is_step"])),
    )

    # model -> slice -> context -> frontier ids
    frontier_map: dict[str, dict[str, dict[tuple[str, str, str], list[str]]]] = {}
    bool_symmetry_key: dict[str, dict[str, str]] = {}
    step_membership: dict[str, dict[str, bool]] = {}
    symmetry_summary: dict[str, object] = {"boolean_models": {}, "by_slice": {}}

    for model_id, poset, model_kind in model_defs:
        ordered = sorted(poset.elements, key=lambda x: element_key(poset, x))
        profiles = build_profiles(poset, ordered)
        all_maps = enumerate_monotone_inflationary_maps(poset, ordered)

        op_by_id: dict[str, FiniteMap[Hashable]] = {}
        is_step_by_id: dict[str, bool] = {}
        for op in all_maps:
            op_id = operator_id(model_id, ordered, op)
            op_by_id[op_id] = op
            if model_kind == "chain":
                is_step_by_id[op_id] = is_step_family_chain(op, int(max(ordered)))
            else:
                is_step_by_id[op_id] = False

        if model_kind == "boolean":
            n = int(model_id[1:])
            skeys: dict[str, str] = {}
            for op_id, op in op_by_id.items():
                skeys[op_id] = canonical_symmetry_key(op, ordered, n)
            bool_symmetry_key[model_id] = skeys
            class_count = len(set(skeys.values()))
            symmetry_summary["boolean_models"][model_id] = {
                "operator_count": len(op_by_id),
                "symmetry_class_count": class_count,
            }
        step_membership[model_id] = dict(is_step_by_id)

        frontier_map[model_id] = {}
        for sl in slices:
            if sl.applicable_to == "chain" and model_kind != "chain":
                continue
            if sl.applicable_to == "boolean" and model_kind != "boolean":
                continue

            pool = []
            for op_id, op in op_by_id.items():
                meta = {"poset": poset, "is_step": is_step_by_id[op_id]}
                if sl.predicate(op, meta):
                    pool.append(op_id)

            pool = sorted(pool)
            contexts: dict[tuple[str, str, str], list[str]] = {}
            for profile_name in PROFILE_ORDER:
                for cost_name in COST_ORDER:
                    cands: list[CandidateScore] = []
                    for op_id in pool:
                        op = op_by_id[op_id]
                        moved = [x for x in ordered if op.apply(x) != x]
                        yld = coverage_score(moved, profiles[profile_name])
                        cost = compute_cost(cost_name, op, poset, ordered)
                        cands.append(CandidateScore(id=op_id, yield_score=yld, cost_score=cost))
                    for tie_name in TIE_ORDER:
                        contexts[(profile_name, cost_name, tie_name)] = frontier_ids(cands, tie_name)
            frontier_map[model_id][sl.name] = contexts

    def applicable(model_kind: str, variant: str) -> bool:
        if variant == VARIANT_UNIQUE_SYMM:
            return model_kind == "boolean"
        if variant == VARIANT_STEP_CONTAIN:
            return model_kind == "chain"
        return True

    survival_rows: list[dict[str, str]] = []
    minimal_failures: dict[str, dict[str, object] | None] = {}

    for variant in VARIANT_ORDER:
        first_failure: dict[str, object] | None = None
        for sl in slices:
            failure: dict[str, object] | None = None
            checked_any = False
            for model_id, _poset, model_kind in model_defs:
                if sl.name not in frontier_map[model_id]:
                    continue
                if not applicable(model_kind, variant):
                    continue
                checked_any = True
                contexts = frontier_map[model_id][sl.name]

                if variant == VARIANT_UNIQUE_TIE:
                    for profile in PROFILE_ORDER:
                        for cost in COST_ORDER:
                            ids = contexts[(profile, cost, "dedup_equal_points")]
                            if len(ids) > 1:
                                failure = {
                                    "slice": sl.name,
                                    "model_id": model_id,
                                    "profile": profile,
                                    "cost": cost,
                                    "frontier_size": len(ids),
                                    "frontier_ids": ids,
                                }
                                break
                        if failure:
                            break

                elif variant == VARIANT_UNIQUE_SYMM:
                    skeys = bool_symmetry_key[model_id]
                    for profile in PROFILE_ORDER:
                        for cost in COST_ORDER:
                            ids = contexts[(profile, cost, "dedup_equal_points")]
                            classes = {skeys[op_id] for op_id in ids}
                            if len(classes) > 1:
                                failure = {
                                    "slice": sl.name,
                                    "model_id": model_id,
                                    "profile": profile,
                                    "cost": cost,
                                    "symmetry_class_count": len(classes),
                                    "frontier_ids": ids,
                                }
                                break
                        if failure:
                            break

                elif variant == VARIANT_BENCH_STABLE:
                    for cost in COST_ORDER:
                        for tie in TIE_ORDER:
                            sets = [set(contexts[(p, cost, tie)]) for p in PROFILE_ORDER]
                            if not all(s == sets[0] for s in sets[1:]):
                                failure = {
                                    "slice": sl.name,
                                    "model_id": model_id,
                                    "cost": cost,
                                    "tie": tie,
                                    "profiles": list(PROFILE_ORDER),
                                }
                                break
                        if failure:
                            break

                elif variant == VARIANT_COST_STABLE:
                    for profile in PROFILE_ORDER:
                        for tie in TIE_ORDER:
                            sets = [set(contexts[(profile, c, tie)]) for c in COST_ORDER]
                            if not all(s == sets[0] for s in sets[1:]):
                                failure = {
                                    "slice": sl.name,
                                    "model_id": model_id,
                                    "profile": profile,
                                    "tie": tie,
                                    "costs": list(COST_ORDER),
                                }
                                break
                        if failure:
                            break

                elif variant == VARIANT_STEP_CONTAIN:
                    for profile in PROFILE_ORDER:
                        for cost in COST_ORDER:
                            for tie in TIE_ORDER:
                                ids = contexts[(profile, cost, tie)]
                                non_step = [op_id for op_id in ids if not step_membership[model_id].get(op_id, False)]
                                if non_step:
                                    failure = {
                                        "slice": sl.name,
                                        "model_id": model_id,
                                        "profile": profile,
                                        "cost": cost,
                                        "tie": tie,
                                        "non_step_frontier_ids": non_step,
                                    }
                                    break
                            if failure:
                                break
                        if failure:
                            break
                else:
                    raise ValueError(f"unknown variant: {variant}")

                if failure:
                    break

            if not checked_any:
                status = "inconclusive_not_applicable"
            elif failure is None:
                status = "survives_on_searched_slice"
            else:
                status = "fails_with_minimal_failure"
                if first_failure is None:
                    first_failure = failure

            survival_rows.append(
                {
                    "variant": variant,
                    "slice": sl.name,
                    "status": status,
                    "minimal_failure": "" if failure is None else json.dumps(failure, sort_keys=True),
                }
            )

        minimal_failures[variant] = first_failure

    by_slice_symm: dict[str, dict[str, float]] = {}
    for sl in slices:
        vals = []
        for model_id, _poset, kind in model_defs:
            if kind != "boolean":
                continue
            if sl.name not in frontier_map[model_id]:
                continue
            contexts = frontier_map[model_id][sl.name]
            skeys = bool_symmetry_key[model_id]
            class_counts = []
            for profile in PROFILE_ORDER:
                for cost in COST_ORDER:
                    ids = contexts[(profile, cost, "dedup_equal_points")]
                    class_counts.append(len({skeys[i] for i in ids}))
            if class_counts:
                vals.extend(class_counts)
        if vals:
            by_slice_symm[sl.name] = {
                "mean_frontier_symmetry_classes": float(sum(vals) / len(vals)),
                "max_frontier_symmetry_classes": float(max(vals)),
            }
    symmetry_summary["by_slice"] = by_slice_symm

    matrix_path = out_dir / "variant_survival_matrix.csv"
    with matrix_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["variant", "slice", "status", "minimal_failure"])
        writer.writeheader()
        for row in survival_rows:
            writer.writerow(row)

    failures_path = out_dir / "minimal_failures.json"
    failures_path.write_text(json.dumps(minimal_failures, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    symmetry_path = out_dir / "symmetry_summary.json"
    symmetry_path.write_text(json.dumps(symmetry_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report_lines = [
        "# Ticket 6.1 Hypothesis Filters and Invariants Sweep",
        "",
        "## Variant outcomes",
    ]
    for row in survival_rows:
        report_lines.append(f"- {row['variant']} | {row['slice']} -> {row['status']}")
    report_lines.append("")
    report_lines.append("## Minimal failures")
    for variant in VARIANT_ORDER:
        entry = minimal_failures.get(variant)
        if entry is None:
            report_lines.append(f"- {variant}: none")
        else:
            report_lines.append(f"- {variant}: {json.dumps(entry, sort_keys=True)}")
    report_lines.append("")
    report_lines.append("## Applicability note")
    report_lines.append("- uniqueness_up_to_symmetry applies to Boolean models only.")
    report_lines.append("- chain_step_containment applies to chain models only.")
    (out_dir / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"wrote {matrix_path}")
    print(f"wrote {failures_path}")
    print(f"wrote {symmetry_path}")
    print(f"wrote {out_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
