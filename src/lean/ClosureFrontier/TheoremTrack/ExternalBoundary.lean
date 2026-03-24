import ClosureFrontier.TheoremTrack.Alignment

namespace ClosureFrontier.TheoremTrack

structure ExternalDependencyContract (α : Type) where
  canonicalFamilyClosedInDomain :
    Set (ExtensionOperator α) → Set (ExtensionOperator α) → Prop
  coneCanonicalization :
    FrozenSlice (ExtensionOperator α) →
      Set (ExtensionOperator α) →
      Set α →
      Set (ExtensionOperator α) →
      ExtensionOperator α → Prop

def ExternalContractHolds {α : Type}
    (contract : ExternalDependencyContract α)
    (slice : FrozenSlice (ExtensionOperator α))
    (domain : Set (ExtensionOperator α))
    (cone : Set α)
    (canon : Set (ExtensionOperator α))
    (op : ExtensionOperator α) : Prop :=
  contract.canonicalFamilyClosedInDomain canon domain ∧
    contract.coneCanonicalization slice domain cone canon op

-- External arithmetic boundary: explicit theorem parameters only, no hidden axioms.
theorem conditional_arithmetic_canonicality_lift
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
    ∃ c, c ∈ canon ∧ ArithmeticCanonicalityTarget slice domain cone canon c := by
  rcases hExt with ⟨hCanonClosed, hCanonAlign⟩
  have hCanonInDomain : ∀ c, c ∈ canon → c ∈ domain := by
    intro c hc
    exact hCanonClosed canon domain hc
  rcases restricted_in_house_alignment_lemma slice domain cone canon op hInv hEff hCanonAlign hCanonInDomain with
    ⟨c, hcCanon, hcEff⟩
  refine ⟨c, hcCanon, ?_⟩
  exact ⟨hRec, hMono, hcEff, Or.inl hcCanon⟩

end ClosureFrontier.TheoremTrack
