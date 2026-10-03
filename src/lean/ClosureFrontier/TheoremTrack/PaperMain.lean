import ClosureFrontier.TheoremTrack.ExternalBoundary

namespace ClosureFrontier.TheoremTrack

-- Stable exported theorem surface, retaining agreement with the original input.
theorem paper_main_conditional_arithmetic_frontier_canonicality
    {α : Type} [Preorder α] [Primcodable α]
    (slice : FrozenSlice (ExtensionOperator α))
    (domain : Set (ExtensionOperator α))
    (cone : Set α)
    (canon : Set (ExtensionOperator α))
    (op : ExtensionOperator α)
    (hInv : SliceInvariantOnCone slice cone)
    (hRec : Computable op.fn)
    (hMono : Monotone op.fn)
    (hEff : FrontierEfficient slice domain op)
    (hExt : ExternalContractHolds slice domain cone canon op) :
    ∃ c, c ∈ canon ∧ ArithmeticCanonicalityTarget slice domain cone canon c ∧
      AgreeOnCone cone op c :=
  conditional_arithmetic_canonicality_lift slice domain cone canon op
    hInv hRec hMono hEff hExt

end ClosureFrontier.TheoremTrack
