from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class CandidateScore:
    id: str
    yield_score: float
    cost_score: float


def pareto_dominates(a: CandidateScore, b: CandidateScore) -> bool:
    no_worse = a.yield_score >= b.yield_score and a.cost_score <= b.cost_score
    strictly_better = a.yield_score > b.yield_score or a.cost_score < b.cost_score
    return no_worse and strictly_better


def pareto_frontier(candidates: Iterable[CandidateScore]) -> list[CandidateScore]:
    ordered = list(candidates)
    frontier: list[CandidateScore] = []
    for candidate in ordered:
        dominated = any(pareto_dominates(other, candidate) for other in ordered if other is not candidate)
        if not dominated:
            frontier.append(candidate)
    return frontier
