from __future__ import annotations

from closure_frontier import (
    FiniteMap,
    WeightedBenchmark,
    average_rank_lift_cost,
    chain,
    coverage_score,
    max_rank_lift_cost,
    moved_points_cost,
    normalized_coverage_score,
    total_rank_lift_cost,
)


def test_weighted_coverage_scores() -> None:
    benchmark = WeightedBenchmark[str]({"a": 2.0, "b": 3.0, "c": 5.0})
    covered = {"a", "c"}
    assert coverage_score(covered, benchmark) == 7.0
    assert normalized_coverage_score(covered, benchmark) == 0.7


def test_normalized_coverage_zero_total_weight() -> None:
    benchmark = WeightedBenchmark[str]({"x": 0.0, "y": 0.0})
    assert coverage_score({"x"}, benchmark) == 0.0
    assert normalized_coverage_score({"x"}, benchmark) == 0.0


def test_operator_cost_functions() -> None:
    c5 = chain(5)
    extension = FiniteMap({0: 1, 1: 2, 2: 3, 3: 4, 4: 4})
    assert moved_points_cost(extension) == 4.0
    assert total_rank_lift_cost(extension, c5) == 4.0
    assert average_rank_lift_cost(extension, c5) == 0.8
    assert max_rank_lift_cost(extension, c5) == 1.0
