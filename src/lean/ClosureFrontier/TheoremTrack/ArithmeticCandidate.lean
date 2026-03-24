import ClosureFrontier.TheoremTrack.Frontier

namespace ClosureFrontier.TheoremTrack

def AlignsOnConeWithCanonicalFamily {α : Type}
    (cone : Set α)
    (canon : Set (ExtensionOperator α))
    (op : ExtensionOperator α) : Prop :=
  op ∈ canon ∨ ∃ opCanon, opCanon ∈ canon ∧ ∀ x, x ∈ cone → op.fn x = opCanon.fn x

-- Arithmetic target lives under frozen P6 evaluation and P4 support indexing.
def ArithmeticCanonicalityTarget {α : Type}
    (slice : FrozenSlice (ExtensionOperator α))
    (domain : Set (ExtensionOperator α))
    (cone : Set α)
    (canon : Set (ExtensionOperator α))
    (op : ExtensionOperator α) : Prop :=
  op.recursive ∧
    op.monotone ∧
    FrontierEfficient slice domain op ∧
    AlignsOnConeWithCanonicalFamily cone canon op

theorem arithmetic_canonicality_target_statement
    {α : Type}
    (slice : FrozenSlice (ExtensionOperator α))
    (domain : Set (ExtensionOperator α))
    (cone : Set α)
    (canon : Set (ExtensionOperator α))
    (op : ExtensionOperator α) :
    Prop :=
  ArithmeticCanonicalityTarget slice domain cone canon op

end ClosureFrontier.TheoremTrack
