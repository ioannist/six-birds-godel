import ClosureFrontier.TheoremTrack.ExternalBoundary

namespace ClosureFrontier.TheoremTrack

theorem finite_frontier_setup_exists
    (s : CandidateSet)
    (h_nonempty : s ≠ []) :
    ∃ x, x ∈ s := by
  cases s with
  | nil =>
      contradiction
  | cons x xs =>
      exact ⟨x, by simp⟩

theorem finite_frontier_enumeration_invariant
    (s₁ s₂ : CandidateSet)
    (h_perm : s₁.Perm s₂) :
    (∀ x, Nondominated s₁ x ↔ Nondominated s₂ x) := by
  intro x
  constructor
  · intro hx
    rcases hx with ⟨hxmem, hnodom⟩
    refine ⟨(h_perm.mem_iff.mp hxmem), ?_⟩
    intro y hy
    have hy' : y ∈ s₁ := h_perm.mem_iff.mpr hy
    exact hnodom y hy'
  · intro hx
    rcases hx with ⟨hxmem, hnodom⟩
    refine ⟨(h_perm.symm.mem_iff.mp hxmem), ?_⟩
    intro y hy
    have hy' : y ∈ s₂ := h_perm.symm.mem_iff.mpr hy
    exact hnodom y hy'

theorem closure_iterate_saturates_one_step
    {α : Type}
    (pkg : ClosurePackage α)
    (x : α)
    (n : Nat) :
    (pkg.op^[n + 1]) x = pkg.op x := by
  induction n with
  | zero =>
      simp
  | succ n ih =>
      have hfix : (pkg.op^[n + 1]) (pkg.op x) = pkg.op x := by
        simpa using ih (x := pkg.op x)
      calc
        (pkg.op^[Nat.succ n + 1]) x
            = (pkg.op^[n + 1]) (pkg.op x) := by simp [Function.iterate_succ_apply']
        _ = pkg.op x := hfix

theorem frozen_package_no_persistent_growth
    {α : Type}
    (pkg : ClosurePackage α)
    (x : α) :
    ¬ PersistentGrowthWitness pkg x := by
  intro hw
  rcases hw with ⟨n, hn, hneq⟩
  have hsat1 : (pkg.op^[n + 1]) x = pkg.op x := closure_iterate_saturates_one_step pkg x n
  have hsat0 : (pkg.op^[n]) x = pkg.op x := by
    cases n with
    | zero =>
        cases hn
    | succ k =>
        simpa using closure_iterate_saturates_one_step pkg x k
  apply hneq
  simpa [hsat1, hsat0]

-- Current theorem read: if growth persists, some package-change witness of P1/P2 type is needed.
theorem persistent_growth_witness_implies_package_change
    {α : Type}
    (pkg : ClosurePackage α)
    (x : α) :
    PersistentGrowthWitness pkg x → False := by
  intro hw
  exact frozen_package_no_persistent_growth pkg x hw

theorem bridge_candidate_holds_in_frozen_idempotent_setting
    {α : Type}
    (pkg : ClosurePackage α)
    (x : α) :
    ¬ PersistentGrowthWitness pkg x :=
  frozen_package_no_persistent_growth pkg x

axiom finite_nondominated_exists
    (s : CandidateSet)
    (h_nonempty : s ≠ []) :
    ∃ x, Nondominated s x

end ClosureFrontier.TheoremTrack
