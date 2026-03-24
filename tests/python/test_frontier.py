from __future__ import annotations

from closure_frontier import CandidateScore, pareto_dominates, pareto_frontier


def test_pareto_dominance() -> None:
    a = CandidateScore(id="a", yield_score=0.8, cost_score=2.0)
    b = CandidateScore(id="b", yield_score=0.7, cost_score=3.0)
    assert pareto_dominates(a, b)
    assert not pareto_dominates(b, a)


def test_pareto_frontier_and_equal_points() -> None:
    c1 = CandidateScore(id="c1", yield_score=0.8, cost_score=2.0)
    c2 = CandidateScore(id="c2", yield_score=0.7, cost_score=3.0)
    c3 = CandidateScore(id="c3", yield_score=0.8, cost_score=2.0)
    c4 = CandidateScore(id="c4", yield_score=0.9, cost_score=4.0)
    frontier = pareto_frontier([c1, c2, c3, c4])
    frontier_ids = [candidate.id for candidate in frontier]
    assert "c2" not in frontier_ids
    assert set(frontier_ids) == {"c1", "c3", "c4"}
