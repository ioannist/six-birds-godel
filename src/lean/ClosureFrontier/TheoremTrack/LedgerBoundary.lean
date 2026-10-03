import ClosureFrontier.TheoremTrack.Alignment

namespace ClosureFrontier.TheoremTrack

theorem agree_on_cone_refl {α : Type} (cone : Set α) (a : ExtensionOperator α) :
    AgreeOnCone cone a a := fun _ _ => rfl

theorem agree_on_cone_symm {α : Type} {cone : Set α} {a b : ExtensionOperator α}
    (h : AgreeOnCone cone a b) : AgreeOnCone cone b a := fun x hx => (h x hx).symm

theorem agree_on_cone_trans {α : Type} {cone : Set α} {a b c : ExtensionOperator α}
    (hab : AgreeOnCone cone a b) (hbc : AgreeOnCone cone b c) :
    AgreeOnCone cone a c := fun x hx => (hab x hx).trans (hbc x hx)

-- All invariant real ledgers are allowed here. No computable-ledger restriction.
noncomputable def classIndicatorSlice {α : Type}
    (cone : Set α) (target : ExtensionOperator α) : FrozenSlice (ExtensionOperator α) := by
  classical
  exact { benchmark := ⟨fun op => if AgreeOnCone cone target op then 1 else 0⟩
          cost := ⟨fun _ => 0⟩
          transformationClass := fun _ _ => True }

theorem class_indicator_invariant {α : Type} (cone : Set α) (target : ExtensionOperator α) :
    SliceInvariantOnCone (classIndicatorSlice cone target) cone := by
  classical
  intro a b hab
  have hiff : AgreeOnCone cone target a ↔ AgreeOnCone cone target b :=
    ⟨fun ha => agree_on_cone_trans ha hab,
     fun hb => agree_on_cone_trans hb (agree_on_cone_symm hab)⟩
  exact ⟨by simp [classIndicatorSlice, hiff], rfl⟩

theorem class_indicator_target_efficient {α : Type} (cone : Set α)
    (domain : Set (ExtensionOperator α)) (target : ExtensionOperator α) (h : target ∈ domain) :
    FrontierEfficient (classIndicatorSlice cone target) domain target := by
  classical
  refine ⟨h, ?_⟩
  intro y _
  by_cases hy : AgreeOnCone cone target y
  · simp [FrontierDominates, classIndicatorSlice, agree_on_cone_refl, hy]
  · simp [FrontierDominates, classIndicatorSlice, agree_on_cone_refl, hy]

-- Equivalence of universal selection and class coverage. Requiring the
-- representative to be efficient as well does not alter this characterization.
theorem universal_ledger_canonicality_iff_coverage {α : Type}
    (domain canon : Set (ExtensionOperator α)) (cone : Set α)
    (hCanon : canon ⊆ domain) :
    (∀ slice : FrozenSlice (ExtensionOperator α), SliceInvariantOnCone slice cone →
      ∀ op, FrontierEfficient slice domain op →
        ∃ c, c ∈ canon ∧ FrontierEfficient slice domain c ∧ AgreeOnCone cone op c) ↔
      ∀ op, op ∈ domain → AlignsOnConeWithCanonicalFamily cone canon op := by
  constructor
  · intro h op hop
    rcases h (classIndicatorSlice cone op) (class_indicator_invariant cone op) op
      (class_indicator_target_efficient cone domain op hop) with ⟨c, hc, _, hAgree⟩
    exact ⟨c, hc, hAgree⟩
  · intro h slice hInv op hEff
    exact restricted_in_house_alignment_lemma slice domain cone canon op hInv hEff
      (h op hEff.1) (fun _ hc => hCanon hc)

theorem uncovered_class_has_counterledger {α : Type}
    (domain canon : Set (ExtensionOperator α)) (cone : Set α)
    (op : ExtensionOperator α) (hop : op ∈ domain)
    (hMissing : ¬ AlignsOnConeWithCanonicalFamily cone canon op) :
    ∃ slice, SliceInvariantOnCone slice cone ∧ FrontierEfficient slice domain op ∧
      ¬ AlignsOnConeWithCanonicalFamily cone canon op :=
  ⟨classIndicatorSlice cone op, class_indicator_invariant cone op,
    class_indicator_target_efficient cone domain op hop, hMissing⟩

end ClosureFrontier.TheoremTrack
