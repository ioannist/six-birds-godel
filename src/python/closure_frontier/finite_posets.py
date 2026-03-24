from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Callable, Generic, Hashable, TypeVar


T = TypeVar("T", bound=Hashable)


@dataclass(frozen=True)
class FinitePoset(Generic[T]):
    """Finite poset with explicit element set and order predicate."""

    elements: tuple[T, ...]
    leq_fn: Callable[[T, T], bool]
    rank: dict[T, int] | None = None

    def __post_init__(self) -> None:
        unique = dict.fromkeys(self.elements)
        if len(unique) != len(self.elements):
            raise ValueError("elements must be unique")
        if not self.elements:
            raise ValueError("elements must be non-empty")
        if self.rank is not None:
            rank_keys = set(self.rank.keys())
            element_keys = set(self.elements)
            if rank_keys != element_keys:
                raise ValueError("rank map must cover exactly the poset elements")
        self.validate_order()

    @property
    def cardinality(self) -> int:
        return len(self.elements)

    def leq(self, x: T, y: T) -> bool:
        if x not in self.rank_domain or y not in self.rank_domain:
            raise ValueError("x and y must be elements of the poset")
        return bool(self.leq_fn(x, y))

    @property
    def rank_domain(self) -> frozenset[T]:
        return frozenset(self.elements)

    def rank_of(self, x: T) -> int:
        if self.rank is None:
            raise ValueError("poset has no rank map")
        if x not in self.rank:
            raise ValueError(f"missing rank for element: {x}")
        return self.rank[x]

    def validate_order(self) -> None:
        elems = self.elements
        for x in elems:
            if not self.leq_fn(x, x):
                raise ValueError("order is not reflexive")
        for x in elems:
            for y in elems:
                if self.leq_fn(x, y) and self.leq_fn(y, x) and x != y:
                    raise ValueError("order is not antisymmetric")
        for x in elems:
            for y in elems:
                for z in elems:
                    if self.leq_fn(x, y) and self.leq_fn(y, z) and not self.leq_fn(x, z):
                        raise ValueError("order is not transitive")


def chain(n: int) -> FinitePoset[int]:
    """Construct the chain C_n on elements 0, ..., n-1."""
    if n <= 0:
        raise ValueError("n must be positive")
    elements = tuple(range(n))
    rank = {x: x for x in elements}
    return FinitePoset(elements=elements, leq_fn=lambda x, y: x <= y, rank=rank)


def boolean_lattice(n: int) -> FinitePoset[frozenset[int]]:
    """Construct the Boolean lattice B_n ordered by subset inclusion."""
    if n < 0:
        raise ValueError("n must be non-negative")
    base = tuple(range(n))
    elems: list[frozenset[int]] = []
    for size in range(n + 1):
        for combo in combinations(base, size):
            elems.append(frozenset(combo))
    rank = {x: len(x) for x in elems}
    return FinitePoset(elements=tuple(elems), leq_fn=lambda x, y: x.issubset(y), rank=rank)
