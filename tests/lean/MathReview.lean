import ClosureFrontier

namespace ClosureFrontier.MathReview
open TheoremTrack

def identityOp : ExtensionOperator ℕ := ⟨id⟩
def badOp : ExtensionOperator ℕ := ⟨fun n => cond n.bodd 2 0⟩
def zeroCone : Set ℕ := {0}
def zeroSlice : FrozenSlice (ExtensionOperator ℕ) where
  benchmark := ⟨fun _ => 0⟩
  cost := ⟨fun _ => 0⟩
  transformationClass := fun _ _ => True

theorem zero_slice_invariant : SliceInvariantOnCone zeroSlice zeroCone := by
  intro _ _ _
  exact ⟨rfl, rfl⟩

theorem zero_slice_efficient (op : ExtensionOperator ℕ) (domain : Set (ExtensionOperator ℕ))
    (h : op ∈ domain) : FrontierEfficient zeroSlice domain op := by
  refine ⟨h, ?_⟩
  intro y _
  simp [FrontierDominates, zeroSlice]

theorem bad_op_computable : Computable badOp.fn :=
  Computable.cond Computable.nat_bodd (Computable.const 2) (Computable.const 0)

theorem bad_op_not_monotone : ¬ Monotone badOp.fn := by
  intro h
  have hh := h (show (1 : ℕ) ≤ 2 by decide)
  change (2 : ℕ) ≤ 0 at hh
  exact (by decide : ¬ (2 : ℕ) ≤ 0) hh

def distinguishingSlice : FrozenSlice (ExtensionOperator ℕ) where
  benchmark := ⟨fun op => if op.fn 1 = 1 then 1 else 0⟩
  cost := ⟨fun _ => 0⟩
  transformationClass := fun _ _ => True

theorem cone_invariance_is_necessary :
    AgreeOnCone zeroCone identityOp badOp ∧
    FrontierEfficient distinguishingSlice Set.univ identityOp ∧
    FrontierDominates distinguishingSlice identityOp badOp ∧
    ¬ SliceInvariantOnCone distinguishingSlice zeroCone := by
  have hAgree : AgreeOnCone zeroCone identityOp badOp := by
    intro x hx
    have hx0 : x = 0 := hx
    subst x
    rfl
  have hDom : FrontierDominates distinguishingSlice identityOp badOp := by
    norm_num [FrontierDominates, distinguishingSlice, identityOp, badOp]
  refine ⟨hAgree, ⟨Set.mem_univ _, ?_⟩, hDom, ?_⟩
  · intro y _
    by_cases hy : y.fn 1 = 1
    · simp [FrontierDominates, distinguishingSlice, identityOp, hy]
    · simp [FrontierDominates, distinguishingSlice, identityOp, hy]
  · intro hInv
    have hScores := (hInv identityOp badOp hAgree).1
    norm_num [distinguishingSlice, identityOp, badOp] at hScores

-- Frontier efficiency alone supplies no representative in an arbitrary family.
example : FrontierEfficient zeroSlice Set.univ identityOp ∧
    ¬ AlignsOnConeWithCanonicalFamily zeroCone ∅ identityOp := by
  exact ⟨zero_slice_efficient identityOp Set.univ (Set.mem_univ _), by
    simp [AlignsOnConeWithCanonicalFamily]⟩

-- The old, two-item semantic contract holds here, but its desired target fails.
-- Both maps are computable; the cone is nonempty; the input is monotone/efficient.
theorem canonical_admissibility_is_necessary :
    Computable identityOp.fn ∧ Monotone identityOp.fn ∧
    SliceInvariantOnCone zeroSlice zeroCone ∧
    FrontierEfficient zeroSlice Set.univ identityOp ∧
    (∀ c : ExtensionOperator ℕ, c ∈ ({badOp} : Set _) → c ∈ (Set.univ : Set _)) ∧
    AlignsOnConeWithCanonicalFamily zeroCone {badOp} identityOp ∧
    ¬ (∃ c, c ∈ ({badOp} : Set _) ∧
      ArithmeticCanonicalityTarget zeroSlice Set.univ zeroCone {badOp} c) := by
  refine ⟨Computable.id, monotone_id, zero_slice_invariant,
    zero_slice_efficient identityOp Set.univ (Set.mem_univ _),
    (fun _ _ => Set.mem_univ _), ?_, ?_⟩
  · refine ⟨badOp, Set.mem_singleton _, ?_⟩
    intro x hx
    have hx0 : x = 0 := hx
    subst x
    rfl
  · rintro ⟨c, hc, hTarget⟩
    have hcEq : c = badOp := hc
    subst c
    exact bad_op_not_monotone hTarget.2.1

-- An inhabited model of the corrected contract, using actual computability.
theorem identity_contract :
    ExternalContractHolds zeroSlice {identityOp} zeroCone {identityOp} identityOp := by
  refine ⟨(fun _ hc => hc), ?_, ?_⟩
  · intro c hc
    have hcEq : c = identityOp := hc
    subst c
    exact ⟨Computable.id, monotone_id⟩
  · intro _ _ _
    exact ⟨identityOp, Set.mem_singleton _, fun _ _ => rfl⟩

example : ∃ c, c ∈ ({identityOp} : Set _) ∧
    ArithmeticCanonicalityTarget zeroSlice {identityOp} zeroCone {identityOp} c ∧
    AgreeOnCone zeroCone identityOp c :=
  paper_main_conditional_arithmetic_frontier_canonicality
    zeroSlice {identityOp} zeroCone {identityOp} identityOp zero_slice_invariant
    Computable.id monotone_id
    (zero_slice_efficient identityOp {identityOp} (Set.mem_singleton _)) identity_contract

-- Actual package changes exist, and the strengthened bridge returns their input.
def packageZero : ClosurePackage ℕ := ⟨fun _ => 0, fun _ => rfl⟩
def packageOne : ClosurePackage ℕ := ⟨fun _ => 1, fun _ => rfl⟩
example : PackageChanged packageZero packageOne ∧
    PackageChangeAt packageZero packageOne (packageZero.op 3) ∧
    Nonempty (PackageChangeWitness packageZero packageOne) :=
  persistent_growth_witness_implies_package_change packageZero packageOne 3 (by decide)

-- A fixed non-idempotent map can grow, so growth alone cannot certify change.
example : ((Nat.succ^[2]) 0 ≠ (Nat.succ^[1]) 0) ∧
    ¬ (∀ x : ℕ, Nat.succ (Nat.succ x) = Nat.succ x) := by
  constructor
  · decide
  · intro h
    have hh := h 0
    omega

example : ¬ ∃ x, Nondominated [] x := by simp [Nondominated]
example : ∃ x, Nondominated [⟨"a", 1, 1⟩, ⟨"b", 1, 1⟩] x :=
  finite_nondominated_exists _ (by simp)

end ClosureFrontier.MathReview
