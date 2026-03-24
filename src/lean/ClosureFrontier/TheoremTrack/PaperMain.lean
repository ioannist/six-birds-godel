import ClosureFrontier.TheoremTrack.ExternalBoundary

namespace ClosureFrontier.TheoremTrack

-- Stable exported theorem surface for the paper's main conditional theorem.
theorem paper_main_conditional_arithmetic_frontier_canonicality
    {α : Type}
    (contract : ExternalDependencyContract α)
    (slice : FrozenSlice (ExtensionOperator α))
    (domain : Set (ExtensionOperator α))
    (cone : Set α)
    (canon : Set (ExtensionOperator α))
    (op : ExtensionOperator α)
    (hInv : SliceInvariantOnCone slice cone)
    (hRec : op.recursive)
    (hMono : op.monotone)
    (hEff : FrontierEfficient slice domain op)
    (hExt : ExternalContractHolds contract slice domain cone canon op) :
    ∃ c, c ∈ canon ∧ ArithmeticCanonicalityTarget slice domain cone canon c :=
  conditional_arithmetic_canonicality_lift contract slice domain cone canon op hInv hRec hMono hEff hExt

end ClosureFrontier.TheoremTrack
