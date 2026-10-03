import ClosureFrontier.TheoremTrack.ArithmeticCandidate

namespace ClosureFrontier.TheoremTrack

theorem frontier_dominates_congr_right
    {α : Type}
    (slice : FrozenSlice (ExtensionOperator α))
    (cone : Set α)
    (hInv : SliceInvariantOnCone slice cone)
    (y op opCanon : ExtensionOperator α)
    (hAgree : AgreeOnCone cone op opCanon) :
    FrontierDominates slice y op ↔ FrontierDominates slice y opCanon := by
  rcases hInv op opCanon hAgree with ⟨hyield, hcost⟩
  unfold FrontierDominates
  simp [hyield, hcost]

theorem frontier_efficiency_transfer_to_cone_equivalent
    {α : Type}
    (slice : FrozenSlice (ExtensionOperator α))
    (domain : Set (ExtensionOperator α))
    (cone : Set α)
    (hInv : SliceInvariantOnCone slice cone)
    (op opCanon : ExtensionOperator α)
    (hEff : FrontierEfficient slice domain op)
    (hAgree : AgreeOnCone cone op opCanon)
    (hCanonMem : opCanon ∈ domain) :
    FrontierEfficient slice domain opCanon := by
  rcases hEff with ⟨_, hNoDomOp⟩
  refine ⟨hCanonMem, ?_⟩
  intro y hy hDomCanon
  have hEq : FrontierDominates slice y op ↔ FrontierDominates slice y opCanon :=
    frontier_dominates_congr_right slice cone hInv y op opCanon hAgree
  have hDomOp : FrontierDominates slice y op := (hEq).mpr hDomCanon
  exact hNoDomOp y hy hDomOp

theorem restricted_in_house_alignment_lemma
    {α : Type}
    (slice : FrozenSlice (ExtensionOperator α))
    (domain : Set (ExtensionOperator α))
    (cone : Set α)
    (canon : Set (ExtensionOperator α))
    (op : ExtensionOperator α)
    (hInv : SliceInvariantOnCone slice cone)
    (hEff : FrontierEfficient slice domain op)
    (hAlign : AlignsOnConeWithCanonicalFamily cone canon op)
    (hCanonInDomain : ∀ c, c ∈ canon → c ∈ domain) :
    ∃ c, c ∈ canon ∧ FrontierEfficient slice domain c ∧ AgreeOnCone cone op c := by
  rcases hAlign with ⟨c, hcCanon, hAgree⟩
  exact ⟨c, hcCanon,
    frontier_efficiency_transfer_to_cone_equivalent
      slice domain cone hInv op c hEff hAgree (hCanonInDomain c hcCanon), hAgree⟩

end ClosureFrontier.TheoremTrack
