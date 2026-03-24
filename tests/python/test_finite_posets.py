from __future__ import annotations

from closure_frontier import boolean_lattice, chain


def test_chain_construction_and_order() -> None:
    c5 = chain(5)
    assert c5.cardinality == 5
    assert c5.leq(0, 4)
    assert not c5.leq(4, 0)
    assert c5.rank_of(3) == 3


def test_boolean_lattice_construction_and_order() -> None:
    b3 = boolean_lattice(3)
    assert b3.cardinality == 8
    a = frozenset({0, 2})
    b = frozenset({0, 1, 2})
    assert b3.leq(a, b)
    assert not b3.leq(b, a)
    assert b3.rank_of(a) == 2
