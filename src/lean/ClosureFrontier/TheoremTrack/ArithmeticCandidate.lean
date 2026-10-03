import ClosureFrontier.TheoremTrack.Frontier
import Mathlib.Computability.Partrec

namespace ClosureFrontier.TheoremTrack

def AlignsOnConeWithCanonicalFamily {α : Type}
    (cone : Set α)
    (canon : Set (ExtensionOperator α))
    (op : ExtensionOperator α) : Prop :=
  ∃ opCanon, opCanon ∈ canon ∧ AgreeOnCone cone op opCanon

-- Arithmetic target lives under frozen P6 evaluation and P4 support indexing.
-- Effectivity is mathlib computability for the declared Primcodable encoding,
-- and monotonicity is the actual order law, rather than arbitrary record labels.
def ArithmeticCanonicalityTarget {α : Type} [Preorder α] [Primcodable α]
    (slice : FrozenSlice (ExtensionOperator α))
    (domain : Set (ExtensionOperator α))
    (cone : Set α)
    (canon : Set (ExtensionOperator α))
    (op : ExtensionOperator α) : Prop :=
  Computable op.fn ∧
    Monotone op.fn ∧
    FrontierEfficient slice domain op ∧
    AlignsOnConeWithCanonicalFamily cone canon op

abbrev arithmetic_canonicality_target_statement
    {α : Type} [Preorder α] [Primcodable α]
    (slice : FrozenSlice (ExtensionOperator α))
    (domain : Set (ExtensionOperator α))
    (cone : Set α)
    (canon : Set (ExtensionOperator α))
    (op : ExtensionOperator α) :
    Prop :=
  ArithmeticCanonicalityTarget slice domain cone canon op

end ClosureFrontier.TheoremTrack
