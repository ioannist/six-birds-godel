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
      calc
        (pkg.op^[Nat.succ n + 1]) x
            = pkg.op ((pkg.op^[n + 1]) x) := by rw [Function.iterate_succ_apply']
        _ = pkg.op (pkg.op x) := by rw [ih]
        _ = pkg.op x := pkg.idempotent x

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
  simp [hsat1, hsat0]

-- Growth is observed by applying a second package to the first package's result.
-- Idempotence yields a concrete point at which the package maps must differ.
theorem persistent_growth_witness_implies_package_change
    {α : Type}
    (pkg pkg' : ClosurePackage α)
    (x : α)
    (hGrowth : pkg'.op (pkg.op x) ≠ pkg.op x) :
    PackageChanged pkg pkg' ∧ PackageChangeAt pkg pkg' (pkg.op x) ∧
      Nonempty (PackageChangeWitness pkg pkg') := by
  have hAt : PackageChangeAt pkg pkg' (pkg.op x) := by
    unfold PackageChangeAt
    rw [pkg.idempotent]
    exact Ne.symm hGrowth
  refine ⟨?_, hAt, ⟨⟨pkg.op x, hAt⟩⟩⟩
  intro hSame
  exact hAt (congrFun hSame (pkg.op x))

theorem bridge_candidate_holds_in_frozen_idempotent_setting
    {α : Type}
    (pkg : ClosurePackage α)
    (x : α) :
    ¬ PersistentGrowthWitness pkg x :=
  frozen_package_no_persistent_growth pkg x

-- This scopes the no-go precisely: a fixed non-idempotent map is not excluded.
theorem idempotent_iff_no_persistent_growth {α : Type} (op : α → α) :
    (∀ x, op (op x) = op x) ↔ ∀ x, ¬ MapGrowthWitness op x := by
  constructor
  · intro h x
    exact frozen_package_no_persistent_growth ⟨op, h⟩ x
  · intro h x
    by_contra hneq
    exact h x ⟨1, by decide, by simpa using hneq⟩

theorem package_changed_iff_witness {α : Type} (pkg pkg' : ClosurePackage α) :
    PackageChanged pkg pkg' ↔ Nonempty (PackageChangeWitness pkg pkg') := by
  classical
  constructor
  · intro hChanged
    have hNotAll : ¬ ∀ x, pkg.op x = pkg'.op x := fun h => hChanged (funext h)
    rcases not_forall.mp hNotAll with ⟨x, hx⟩
    exact ⟨⟨x, hx⟩⟩
  · rintro ⟨w⟩ hSame
    exact w.changed (congrFun hSame w.point)

theorem pareto_dominates_irrefl (x : ScoredCandidate) : ¬ ParetoDominates x x := by
  simp [ParetoDominates, WeakDominates, StrictlyBetterInOne]

theorem pareto_dominates_trans {a b c : ScoredCandidate}
    (hab : ParetoDominates a b) (hbc : ParetoDominates b c) : ParetoDominates a c := by
  rcases hab with ⟨⟨hay, hac⟩, hstrict⟩
  rcases hbc with ⟨⟨hby, hbcost⟩, _⟩
  refine ⟨⟨le_trans hby hay, le_trans hac hbcost⟩, ?_⟩
  rcases hstrict with hy | hk
  · exact Or.inl (lt_of_le_of_lt hby hy)
  · exact Or.inr (lt_of_lt_of_le hk hbcost)

theorem finite_nondominated_exists
    (s : CandidateSet)
    (h_nonempty : s ≠ []) :
    ∃ x, Nondominated s x := by
  classical
  induction s with
  | nil => exact (h_nonempty rfl).elim
  | cons a tail ih =>
      by_cases htail : tail = []
      · subst tail
        exact ⟨a, by simp [Nondominated, pareto_dominates_irrefl]⟩
      · rcases ih htail with ⟨x, hxmem, hxmax⟩
        by_cases hax : ParetoDominates a x
        · refine ⟨a, by simp, ?_⟩
          intro y hy hyDom
          rcases List.mem_cons.mp hy with rfl | hytail
          · exact pareto_dominates_irrefl y hyDom
          · exact hxmax y hytail (pareto_dominates_trans hyDom hax)
        · refine ⟨x, List.mem_cons_of_mem a hxmem, ?_⟩
          intro y hy
          rcases List.mem_cons.mp hy with rfl | hytail
          · exact hax
          · exact hxmax y hytail

end ClosureFrontier.TheoremTrack
