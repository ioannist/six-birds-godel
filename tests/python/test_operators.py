from __future__ import annotations

from closure_frontier import FiniteMap, chain


def test_closure_operator_on_chain() -> None:
    c5 = chain(5)
    closure = FiniteMap({0: 2, 1: 2, 2: 2, 3: 3, 4: 4})
    assert closure.is_monotone(c5)
    assert closure.is_inflationary(c5)
    assert closure.is_idempotent()
    assert closure.is_closure_operator(c5)


def test_non_idempotent_extension_operator_and_iterates() -> None:
    c5 = chain(5)
    extension = FiniteMap({0: 1, 1: 2, 2: 3, 3: 4, 4: 4})
    assert extension.is_monotone(c5)
    assert extension.is_inflationary(c5)
    assert not extension.is_idempotent()

    second = extension.iterate(2)
    assert second.apply(0) == 2
    assert second.apply(2) == 4

    orbit = extension.orbit(0, max_steps=6, until_stable=True)
    assert orbit == [0, 1, 2, 3, 4, 4]
