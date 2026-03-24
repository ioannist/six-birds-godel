import ClosureFrontier.TheoremTrack.Core

namespace ClosureFrontier.TheoremTrack

structure BenchmarkProfile (α : Type) where
  yield : α → Rat

structure CostProfile (α : Type) where
  cost : α → Rat

structure ExtensionOperator (α : Type) where
  fn : α → α
  recursive : Prop
  monotone : Prop

-- P6 role in the current theorem track: frozen evaluation regime.
-- P4 appears here only as support/index bookkeeping, not as package change.
structure FrozenSlice (α : Type) where
  benchmark : BenchmarkProfile α
  cost : CostProfile α
  transformationClass : α → α → Prop
  tiePolicyFixed : Prop
  quotientRuleFixed : Prop
  stageIndex : Nat := 0

def FrontierDominates {α : Type}
    (slice : FrozenSlice α)
    (a b : α) : Prop :=
  slice.benchmark.yield a >= slice.benchmark.yield b ∧
    slice.cost.cost a <= slice.cost.cost b ∧
    (slice.benchmark.yield a > slice.benchmark.yield b ∨
      slice.cost.cost a < slice.cost.cost b)

def FrontierEfficient {α : Type}
    (slice : FrozenSlice α)
    (domain : Set α)
    (x : α) : Prop :=
  x ∈ domain ∧ ∀ y, y ∈ domain → ¬ FrontierDominates slice y x

def AgreeOnCone {α : Type}
    (cone : Set α)
    (a b : ExtensionOperator α) : Prop :=
  ∀ x, x ∈ cone → a.fn x = b.fn x

def SliceInvariantOnCone {α : Type}
    (slice : FrozenSlice (ExtensionOperator α))
    (cone : Set α) : Prop :=
  ∀ a b, AgreeOnCone cone a b →
    slice.benchmark.yield a = slice.benchmark.yield b ∧
    slice.cost.cost a = slice.cost.cost b

end ClosureFrontier.TheoremTrack
