import ClosureFrontier.TheoremTrack.ExternalBoundary

namespace ClosureFrontier.TheoremTrack

abbrev P5FixedPackage (α : Type) := ClosurePackage α
abbrev P6FrozenEvaluation (α : Type) := FrozenSlice α
abbrev P4StageIndex := Nat

-- Mechanism labels alone do not witness a difference between package maps.
inductive PackageChangeMechanism where
  | rewriteP1
  | gatingP2

inductive DiagnosticOnlyTag where
  | protocolMismatchP3

end ClosureFrontier.TheoremTrack
