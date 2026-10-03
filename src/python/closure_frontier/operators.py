from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Generic, Hashable, Mapping, TypeVar

from .finite_posets import FinitePoset


T = TypeVar("T", bound=Hashable)


@dataclass(frozen=True)
class FiniteMap(Generic[T]):
    """Total self-map on a finite domain."""

    mapping: Mapping[T, T]

    def __post_init__(self) -> None:
        object.__setattr__(self, "mapping", MappingProxyType(dict(self.mapping)))
        if not self.mapping:
            raise ValueError("mapping must be non-empty")
        domain = set(self.mapping.keys())
        codomain = set(self.mapping.values())
        if not codomain.issubset(domain):
            raise ValueError("mapping must map into its own domain")

    @property
    def domain(self) -> frozenset[T]:
        return frozenset(self.mapping.keys())

    def apply(self, x: T) -> T:
        try:
            return self.mapping[x]
        except KeyError as exc:
            raise ValueError(f"point not in domain: {x}") from exc

    def __call__(self, x: T) -> T:
        return self.apply(x)

    def compose(self, other: FiniteMap[T]) -> FiniteMap[T]:
        if self.domain != other.domain:
            raise ValueError("maps must have the same domain for composition")
        composed = {x: self.apply(other.apply(x)) for x in self.mapping}
        return FiniteMap(mapping=composed)

    def iterate(self, k: int) -> FiniteMap[T]:
        if k < 0:
            raise ValueError("k must be non-negative")
        if k == 0:
            return FiniteMap(mapping={x: x for x in self.mapping})
        result = FiniteMap(mapping=dict(self.mapping))
        for _ in range(1, k):
            result = self.compose(result)
        return result

    def orbit(self, x: T, *, max_steps: int, until_stable: bool = False) -> list[T]:
        if max_steps < 0:
            raise ValueError("max_steps must be non-negative")
        if x not in self.domain:
            raise ValueError(f"point not in domain: {x}")
        values = [x]
        current = x
        for _ in range(max_steps):
            nxt = self.apply(current)
            values.append(nxt)
            if until_stable and nxt == current:
                break
            current = nxt
        return values

    def is_idempotent(self) -> bool:
        for x in self.mapping:
            if self.apply(self.apply(x)) != self.apply(x):
                return False
        return True

    def is_monotone(self, poset: FinitePoset[T]) -> bool:
        domain = self.domain
        if domain != poset.rank_domain:
            raise ValueError("map domain must match poset elements")
        for x in self.mapping:
            for y in self.mapping:
                if poset.leq(x, y) and not poset.leq(self.apply(x), self.apply(y)):
                    return False
        return True

    def is_inflationary(self, poset: FinitePoset[T]) -> bool:
        domain = self.domain
        if domain != poset.rank_domain:
            raise ValueError("map domain must match poset elements")
        for x in self.mapping:
            if not poset.leq(x, self.apply(x)):
                return False
        return True

    def is_closure_operator(self, poset: FinitePoset[T]) -> bool:
        return self.is_monotone(poset) and self.is_inflationary(poset) and self.is_idempotent()
