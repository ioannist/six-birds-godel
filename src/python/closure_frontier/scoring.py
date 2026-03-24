from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Hashable, Iterable, TypeVar

from .finite_posets import FinitePoset
from .operators import FiniteMap


T = TypeVar("T", bound=Hashable)


@dataclass(frozen=True)
class WeightedBenchmark(Generic[T]):
    """Weighted finite benchmark family."""

    weights: dict[T, float]

    def __post_init__(self) -> None:
        if not self.weights:
            raise ValueError("weights must be non-empty")
        for token, weight in self.weights.items():
            if weight < 0.0:
                raise ValueError(f"weight must be non-negative: {token}")

    @property
    def total_weight(self) -> float:
        return float(sum(self.weights.values()))


def coverage_score(covered: Iterable[T], benchmark: WeightedBenchmark[T]) -> float:
    covered_set = set(covered)
    return float(sum(weight for token, weight in benchmark.weights.items() if token in covered_set))


def normalized_coverage_score(covered: Iterable[T], benchmark: WeightedBenchmark[T]) -> float:
    total = benchmark.total_weight
    if total <= 0.0:
        return 0.0
    return coverage_score(covered, benchmark) / total


def moved_points_cost(op: FiniteMap[T]) -> float:
    return float(sum(1 for x in op.mapping if op.apply(x) != x))


def total_rank_lift_cost(op: FiniteMap[T], poset: FinitePoset[T]) -> float:
    if op.domain != poset.rank_domain:
        raise ValueError("map domain must match poset elements")
    total = 0.0
    for x in op.mapping:
        lift = poset.rank_of(op.apply(x)) - poset.rank_of(x)
        total += float(max(0, lift))
    return total


def average_rank_lift_cost(op: FiniteMap[T], poset: FinitePoset[T]) -> float:
    return total_rank_lift_cost(op, poset) / float(len(op.mapping))


def max_rank_lift_cost(op: FiniteMap[T], poset: FinitePoset[T]) -> float:
    if op.domain != poset.rank_domain:
        raise ValueError("map domain must match poset elements")
    return float(max(max(0, poset.rank_of(op.apply(x)) - poset.rank_of(x)) for x in op.mapping))
