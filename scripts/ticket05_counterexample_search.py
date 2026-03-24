#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Generic, Hashable, TypeVar


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "python"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from closure_frontier import (  # noqa: E402
    CandidateScore,
    FiniteMap,
    FinitePoset,
    WeightedBenchmark,
    boolean_lattice,
    chain,
    coverage_score,
    pareto_frontier,
    total_rank_lift_cost,
)


T = TypeVar("T", bound=Hashable)

PROFILE_UNIFORM = "uniform"
PROFILE_TOP_HEAVY = "top_heavy"
PROFILE_BOTTOM_HEAVY = "bottom_heavy"
PROFILE_ORDER = (PROFILE_UNIFORM, PROFILE_TOP_HEAVY, PROFILE_BOTTOM_HEAVY)


@dataclass(frozen=True)
class OperatorRecord(Generic[T]):
    op_id: str
    mapping_repr: dict[str, str]
    moved_points: list[str]
    moved_count: int
    cost_score: float
    is_step_family: bool | None
    yield_by_profile: dict[str, float]


def element_key(poset: FinitePoset[T], x: T) -> tuple[int, str]:
    return (poset.rank_of(x), repr(x))


def element_to_str(x: Hashable) -> str:
    if isinstance(x, frozenset):
        return "{" + ",".join(str(v) for v in sorted(x)) + "}"
    return str(x)


def build_profiles(poset: FinitePoset[T], ordered: list[T]) -> dict[str, WeightedBenchmark[T]]:
    max_rank = max(poset.rank_of(x) for x in ordered)
    uniform = {x: 1.0 for x in ordered}
    top_heavy = {x: float(poset.rank_of(x) + 1) for x in ordered}
    bottom_heavy = {x: float(max_rank - poset.rank_of(x) + 1) for x in ordered}
    return {
        PROFILE_UNIFORM: WeightedBenchmark(uniform),
        PROFILE_TOP_HEAVY: WeightedBenchmark(top_heavy),
        PROFILE_BOTTOM_HEAVY: WeightedBenchmark(bottom_heavy),
    }


def is_step_family_chain(op: FiniteMap[int], top: int) -> bool:
    for k in range(top + 1):
        if all(op.apply(x) == min(top, x + k) for x in range(top + 1)):
            return True
    return False


def enumerate_monotone_inflationary_maps(poset: FinitePoset[T], ordered: list[T]) -> list[FiniteMap[T]]:
    options: dict[T, list[T]] = {}
    for x in ordered:
        ys = [y for y in ordered if poset.leq(x, y)]
        ys.sort(key=lambda z: element_key(poset, z))
        options[x] = ys

    assigned: dict[T, T] = {}
    out: list[FiniteMap[T]] = []

    def valid_partial(x: T, fx: T) -> bool:
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
            if not valid_partial(x, fx):
                continue
            assigned[x] = fx
            backtrack(i + 1)
            del assigned[x]

    backtrack(0)
    return out


def operator_id(model_id: str, ordered: list[T], op: FiniteMap[T]) -> str:
    index = {x: i for i, x in enumerate(ordered)}
    image_indices = [str(index[op.apply(x)]) for x in ordered]
    return f"{model_id}:(" + ",".join(image_indices) + ")"


def evaluate_model(model_id: str, poset: FinitePoset[T], *, is_chain_model: bool) -> dict[str, object]:
    ordered = sorted(poset.elements, key=lambda x: element_key(poset, x))
    profiles = build_profiles(poset, ordered)
    operators = enumerate_monotone_inflationary_maps(poset, ordered)

    records: list[OperatorRecord[T]] = []
    candidates_by_profile: dict[str, list[CandidateScore]] = {name: [] for name in PROFILE_ORDER}

    top = None
    if is_chain_model:
        top = max(int(x) for x in ordered)

    for op in operators:
        moved = [x for x in ordered if op.apply(x) != x]
        moved_labels = [element_to_str(x) for x in moved]
        op_cost = total_rank_lift_cost(op, poset)
        yields = {
            profile: coverage_score(moved, benchmark)
            for profile, benchmark in profiles.items()
        }
        op_is_step = is_step_family_chain(op, top) if is_chain_model and top is not None else None
        op_id = operator_id(model_id, ordered, op)
        mapping_repr = {element_to_str(x): element_to_str(op.apply(x)) for x in ordered}
        records.append(
            OperatorRecord(
                op_id=op_id,
                mapping_repr=mapping_repr,
                moved_points=moved_labels,
                moved_count=len(moved_labels),
                cost_score=op_cost,
                is_step_family=op_is_step,
                yield_by_profile=yields,
            )
        )
        for profile in PROFILE_ORDER:
            candidates_by_profile[profile].append(
                CandidateScore(id=op_id, yield_score=yields[profile], cost_score=op_cost)
            )

    records_by_id = {rec.op_id: rec for rec in records}
    frontiers: dict[str, list[str]] = {}
    for profile in PROFILE_ORDER:
        frontier = pareto_frontier(candidates_by_profile[profile])
        frontiers[profile] = sorted(candidate.id for candidate in frontier)

    return {
        "model_id": model_id,
        "cardinality": poset.cardinality,
        "operator_count": len(operators),
        "profiles": list(PROFILE_ORDER),
        "frontiers": frontiers,
        "operators": [
            {
                "id": rec.op_id,
                "mapping": rec.mapping_repr,
                "moved_points": rec.moved_points,
                "moved_count": rec.moved_count,
                "yield_by_profile": rec.yield_by_profile,
                "cost_score": rec.cost_score,
                "is_step_family": rec.is_step_family,
            }
            for rec in sorted(records, key=lambda r: r.op_id)
        ],
        "records_by_id": records_by_id,
    }


def summarize_conjectures(results: list[dict[str, object]]) -> tuple[dict[str, object], dict[str, object]]:
    c1_examples: list[dict[str, object]] = []
    c2_examples: list[dict[str, object]] = []
    c3_examples: list[dict[str, object]] = []

    for model in results:
        model_id = str(model["model_id"])
        fronts = model["frontiers"]
        assert isinstance(fronts, dict)

        for profile in PROFILE_ORDER:
            frontier_ids = list(fronts[profile])
            if len(frontier_ids) != 1:
                c1_examples.append(
                    {
                        "model_id": model_id,
                        "profile": profile,
                        "frontier_size": len(frontier_ids),
                        "frontier_ids": frontier_ids,
                    }
                )

        u = set(fronts[PROFILE_UNIFORM])
        t = set(fronts[PROFILE_TOP_HEAVY])
        b = set(fronts[PROFILE_BOTTOM_HEAVY])
        if not (u == t == b):
            c2_examples.append(
                {
                    "model_id": model_id,
                    "uniform": sorted(u),
                    "top_heavy": sorted(t),
                    "bottom_heavy": sorted(b),
                }
            )

        if model_id.startswith("C"):
            records_by_id = model["records_by_id"]
            assert isinstance(records_by_id, dict)
            frontier_all = set(u) | set(t) | set(b)
            non_step = []
            for op_id in sorted(frontier_all):
                rec = records_by_id[op_id]
                assert isinstance(rec, OperatorRecord)
                if rec.is_step_family is False:
                    non_step.append(op_id)
            if non_step:
                c3_examples.append(
                    {
                        "model_id": model_id,
                        "non_step_frontier_ids": non_step,
                    }
                )

    def pick_minimal(examples: list[dict[str, object]]) -> dict[str, object] | None:
        if not examples:
            return None
        return sorted(examples, key=lambda ex: str(ex["model_id"]))[0]

    catalog = {
        "conjecture_uniqueness": {
            "tested": True,
            "counterexample_found": bool(c1_examples),
            "examples": c1_examples,
        },
        "conjecture_reweighting_stability": {
            "tested": True,
            "counterexample_found": bool(c2_examples),
            "examples": c2_examples,
        },
        "conjecture_chain_step_family": {
            "tested": True,
            "counterexample_found": bool(c3_examples),
            "examples": c3_examples,
        },
    }

    minimal = {
        "conjecture_uniqueness": pick_minimal(c1_examples),
        "conjecture_reweighting_stability": pick_minimal(c2_examples),
        "conjecture_chain_step_family": pick_minimal(c3_examples),
    }
    return catalog, minimal


def write_report(
    output_path: Path,
    model_summaries: list[dict[str, object]],
    catalog: dict[str, object],
    minimal: dict[str, object],
) -> None:
    lines: list[str] = []
    lines.append("# Ticket 05 Counterexample Search")
    lines.append("")
    lines.append("## Search Space")
    total_ops = 0
    for model in model_summaries:
        model_id = str(model["model_id"])
        op_count = int(model["operator_count"])
        total_ops += op_count
        lines.append(f"- {model_id}: {op_count} monotone inflationary self-maps")
    lines.append(f"- Total operators checked: {total_ops}")
    lines.append("")
    lines.append("## Conjecture Outcomes")
    entries = [
        ("Uniqueness", "conjecture_uniqueness"),
        ("Reweighting stability", "conjecture_reweighting_stability"),
        ("Canonical step-family on chains", "conjecture_chain_step_family"),
    ]
    for label, key in entries:
        info = catalog[key]
        assert isinstance(info, dict)
        found = bool(info["counterexample_found"])
        status = "counterexample found" if found else "none found in searched space"
        lines.append(f"- {label}: {status}")
    lines.append("")
    lines.append("## Minimal Examples")
    for label, key in entries:
        example = minimal[key]
        if example is None:
            lines.append(f"- {label}: none found")
        else:
            lines.append(f"- {label}: {json.dumps(example, sort_keys=True)}")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    output_dir = ROOT / "results" / "ticket-05"
    output_dir.mkdir(parents=True, exist_ok=True)

    model_defs: list[tuple[str, FinitePoset[Hashable], bool]] = []
    for n in range(2, 7):
        model_defs.append((f"C{n}", chain(n), True))
    for n in range(1, 4):
        model_defs.append((f"B{n}", boolean_lattice(n), False))

    model_summaries: list[dict[str, object]] = []
    for model_id, poset, is_chain_model in model_defs:
        model_summaries.append(evaluate_model(model_id, poset, is_chain_model=is_chain_model))

    catalog, minimal = summarize_conjectures(model_summaries)

    catalog_out = {
        "search_scope": {
            "chains": ["C2", "C3", "C4", "C5", "C6"],
            "boolean_lattices": ["B1", "B2", "B3"],
            "profiles": list(PROFILE_ORDER),
            "exhaustive": True,
        },
        "models": [
            {
                "model_id": model["model_id"],
                "cardinality": model["cardinality"],
                "operator_count": model["operator_count"],
                "frontiers": model["frontiers"],
                "operators": model["operators"],
            }
            for model in model_summaries
        ],
        "conjecture_outcomes": catalog,
    }

    (output_dir / "counterexample_catalog.json").write_text(
        json.dumps(catalog_out, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "minimal_examples.json").write_text(
        json.dumps(minimal, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_report(output_dir / "report.md", model_summaries, catalog, minimal)

    print(f"wrote {output_dir / 'counterexample_catalog.json'}")
    print(f"wrote {output_dir / 'minimal_examples.json'}")
    print(f"wrote {output_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
