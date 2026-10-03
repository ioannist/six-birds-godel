import ClosureFrontier.TheoremTrack.Alignment

namespace ClosureFrontier.TheoremTrack

-- These are proofs of the named conditions, not arbitrary proposition labels.
-- No arithmetic encoding or literature discharge is asserted by this interface.
structure ExternalDependencyContract {α : Type} [Preorder α] [Primcodable α]
    (slice : FrozenSlice (ExtensionOperator α))
    (domain : Set (ExtensionOperator α))
    (cone : Set α)
    (canon : Set (ExtensionOperator α))
    (op : ExtensionOperator α) : Prop where
  canonicalFamilyClosedInDomain : ∀ c, c ∈ canon → c ∈ domain
  canonicalFamilyAdmissible : ∀ c, c ∈ canon → Computable c.fn ∧ Monotone c.fn
  coneCanonicalization : Computable op.fn → Monotone op.fn →
    FrontierEfficient slice domain op → AlignsOnConeWithCanonicalFamily cone canon op

abbrev ExternalContractHolds {α : Type} [Preorder α] [Primcodable α]
    (slice : FrozenSlice (ExtensionOperator α))
    (domain : Set (ExtensionOperator α))
    (cone : Set α)
    (canon : Set (ExtensionOperator α))
    (op : ExtensionOperator α) : Prop :=
  ExternalDependencyContract slice domain cone canon op

-- Cone agreement transports the ledger, not global effectivity or monotonicity.
-- Those properties must be supplied for the canonical family itself.
theorem conditional_arithmetic_canonicality_lift
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
      AgreeOnCone cone op c := by
  rcases restricted_in_house_alignment_lemma slice domain cone canon op hInv hEff
      (hExt.coneCanonicalization hRec hMono hEff)
      hExt.canonicalFamilyClosedInDomain with ⟨c, hcCanon, hcEff, hcAgree⟩
  rcases hExt.canonicalFamilyAdmissible c hcCanon with ⟨hcRec, hcMono⟩
  exact ⟨c, hcCanon, ⟨hcRec, hcMono, hcEff, c, hcCanon, fun _ _ => rfl⟩, hcAgree⟩

end ClosureFrontier.TheoremTrack
