import ClosureFrontier.TheoremTrack.ExternalBoundary

namespace ClosureFrontier.TheoremTrack

abbrev P5FixedPackage (α : Type) := ClosurePackage α
abbrev P6FrozenEvaluation (α : Type) := FrozenSlice α
abbrev P4StageIndex := Nat

inductive PackageChangeWitness where
  | rewriteP1
  | gatingP2

inductive DiagnosticOnlyTag where
  | protocolMismatchP3

end ClosureFrontier.TheoremTrack
