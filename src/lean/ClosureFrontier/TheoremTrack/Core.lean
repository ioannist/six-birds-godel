import Mathlib.Data.Rat.Defs
import Mathlib.Logic.Function.Iterate

namespace ClosureFrontier.TheoremTrack

abbrev Score := Rat

structure ScoredCandidate where
  id : String
  yieldScore : Score
  costScore : Score
  deriving Repr, DecidableEq

abbrev CandidateSet := List ScoredCandidate

def WeakDominates (a b : ScoredCandidate) : Prop :=
  a.yieldScore >= b.yieldScore ∧ a.costScore <= b.costScore

def StrictlyBetterInOne (a b : ScoredCandidate) : Prop :=
  a.yieldScore > b.yieldScore ∨ a.costScore < b.costScore

def ParetoDominates (a b : ScoredCandidate) : Prop :=
  WeakDominates a b ∧ StrictlyBetterInOne a b

def Nondominated (s : CandidateSet) (x : ScoredCandidate) : Prop :=
  x ∈ s ∧ ∀ y ∈ s, ¬ ParetoDominates y x

-- P5 role in the current theorem track: fixed-package object.
structure ClosurePackage (α : Type) where
  op : α → α
  idempotent : ∀ x : α, op (op x) = op x

def MapGrowthWitness {α : Type} (op : α → α) (x : α) : Prop :=
  ∃ n : Nat, 1 ≤ n ∧ (op^[n + 1]) x ≠ (op^[n]) x

-- Persistent growth cannot be read inside a genuinely fixed P5 package.
def PersistentGrowthWitness {α : Type} (pkg : ClosurePackage α) (x : α) : Prop :=
  MapGrowthWitness pkg.op x

def PackageChanged {α : Type} (pkg pkg' : ClosurePackage α) : Prop :=
  pkg.op ≠ pkg'.op

def PackageChangeAt {α : Type} (pkg pkg' : ClosurePackage α) (x : α) : Prop :=
  pkg.op x ≠ pkg'.op x

-- A witness records an actual differing input, rather than a primitive-role tag.
structure PackageChangeWitness {α : Type} (pkg pkg' : ClosurePackage α) where
  point : α
  changed : PackageChangeAt pkg pkg' point

end ClosureFrontier.TheoremTrack
