from fractions import Fraction
from itertools import product
import math

import pytest

from closure_frontier import (
    CandidateScore, FiniteMap, FinitePoset, WeightedBenchmark, boolean_lattice, chain,
    coverage_score, pareto_frontier,
)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_values_cannot_enter_a_frontier(value: float) -> None:
    with pytest.raises(ValueError):
        CandidateScore("bad-yield", value, 0)
    with pytest.raises(ValueError):
        CandidateScore("bad-cost", 0, value)
    with pytest.raises(ValueError):
        WeightedBenchmark({"x": value})


def test_total_weight_overflow_is_rejected() -> None:
    with pytest.raises(ValueError):
        WeightedBenchmark({"x": 1e308, "y": 1e308})


def test_validated_maps_and_ledgers_keep_their_input_snapshot() -> None:
    mapping = {0: 1, 1: 1}
    op = FiniteMap(mapping)
    mapping[0] = 3
    assert op(0) == 1
    with pytest.raises(TypeError):
        op.mapping[0] = 3
    weights = {"x": 1.0}
    benchmark = WeightedBenchmark(weights)
    weights["x"] = math.nan
    assert coverage_score(["x"], benchmark) == 1.0
    with pytest.raises(TypeError):
        benchmark.weights["x"] = math.nan
    with pytest.raises(ValueError):
        op.orbit(2, max_steps=0)


def test_validated_order_and_rank_keep_their_input_snapshot() -> None:
    relation = {(0, 0), (0, 1), (1, 1)}
    ranks = {0: 0, 1: 1}
    poset = FinitePoset((0, 1), lambda x, y: (x, y) in relation, ranks)
    relation.add((1, 0))
    ranks[0] = 99
    assert not poset.leq(1, 0)
    assert poset.rank_of(0) == 0
    for invalid_rank in [{0: 0, 1: 0}, {0: 0, 1: -1}, {0: 0, 1: 1.5}]:
        with pytest.raises(ValueError):
            FinitePoset((0, 1), lambda x, y: x <= y, invalid_rank)


@pytest.mark.parametrize(
    "poset,expected_count",
    [(chain(2), 2), (chain(3), 5), (chain(4), 14), (chain(5), 42),
     (chain(6), 132), (boolean_lattice(1), 2), (boolean_lattice(2), 9),
     (boolean_lattice(3), 216)],
)
def test_toy_frontiers_against_independent_rational_enumeration(poset, expected_count) -> None:
    # Enumerate the entire product, independent of the ticket backtracking code.
    elements = poset.elements
    options = [[y for y in elements if poset.leq(x, y)] for x in elements]
    maps = []
    for images in product(*options):
        mapping = dict(zip(elements, images))
        if all(not poset.leq(x, y) or poset.leq(mapping[x], mapping[y])
               for x in elements for y in elements):
            maps.append(mapping)
    assert len(maps) == expected_count
    ranks = [poset.rank_of(x) for x in elements]
    max_rank = max(ranks)
    middle = Fraction(max_rank, 2)
    profiles = [
        [Fraction(1) for _ in elements],
        [Fraction(r + 1) for r in ranks],
        [Fraction(max_rank - r + 1) for r in ranks],
        [1 / (1 + abs(r - middle)) for r in ranks],
    ]
    max_total_lift = sum(max_rank - r for r in ranks)
    for weights in profiles:
        benchmark = WeightedBenchmark(dict(zip(elements, map(float, weights))))
        points = []
        computed_yields = []
        for mapping in maps:
            moved = sum(mapping[x] != x for x in elements)
            total_lift = sum(poset.rank_of(mapping[x]) - poset.rank_of(x) for x in elements)
            yld = sum(w for x, w in zip(elements, weights) if mapping[x] != x)
            points.append((yld, [Fraction(moved), Fraction(total_lift),
                Fraction(total_lift, len(elements)), Fraction(total_lift, max_total_lift)]))
            computed_yields.append(coverage_score(
                [x for x in elements if mapping[x] != x], benchmark))
        for cost_index in range(4):
            exact = [
                i for i, (yld, costs) in enumerate(points)
                if not any(oy >= yld and oc[cost_index] <= costs[cost_index]
                    and (oy > yld or oc[cost_index] < costs[cost_index])
                    for oy, oc in points)
            ]
            candidates = [CandidateScore(str(i), computed_yields[i], float(costs[cost_index]))
                          for i, (yld, costs) in enumerate(points)]
            assert [int(c.id) for c in pareto_frontier(candidates)] == exact
