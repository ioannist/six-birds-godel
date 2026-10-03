import ClosureFrontier
import Mathlib.Data.Fintype.Prod

namespace ClosureFrontier.StrengtheningReview
open TheoremTrack

-- Budget indexing: the initial application may change state without a switch.
def constantOne : ClosurePackage ℕ := ⟨fun _ => 1, fun _ => rfl⟩
def fixedPackages : ℕ → ClosurePackage ℕ := fun _ => constantOne

example : packageOrbit fixedPackages 0 0 = 0 ∧ packageOrbit fixedPackages 0 1 = 1 := by
  decide

example (n : ℕ) : packageSwitchCount fixedPackages n = 0 := by
  classical
  simp [packageSwitchCount, PackageChanged, fixedPackages]

example : orbitChangeCount fixedPackages 0 1 = 1 := by
  classical
  simp only [orbitChangeCount, Finset.range_one, Finset.filter_singleton]
  norm_num [packageOrbit, fixedPackages, constantOne]

example (n : ℕ) : orbitChangeCount alternatingPackages 0 (n + 1) =
    1 + packageSwitchCount alternatingPackages n := alternating_budget_sharp n

example : ∀ bound, ∃ t, bound ≤ t ∧
    PackageChanged (alternatingPackages t) (alternatingPackages (t + 1)) := by
  apply unbounded_changes_require_unbounded_switches alternatingPackages 0
  intro bound
  refine ⟨bound, le_rfl, ?_⟩
  rw [alternating_orbit_exact, alternating_orbit_exact]
  omega

def ident : ExtensionOperator ℕ := ⟨id⟩
def altered : ExtensionOperator ℕ := ⟨fun n => if n = 0 then 0 else n + 1⟩
def one : ExtensionOperator ℕ := ⟨fun _ => 1⟩
def support : Set ℕ := {0}

-- A proper canonical family can cover the cone-equivalence classes of its domain.
example : altered ≠ ident ∧ AgreeOnCone support altered ident := by
  constructor
  · intro h
    have hFn := congrArg (fun op : ExtensionOperator ℕ => op.fn 1) h
    norm_num [altered, ident] at hFn
  · intro x hx
    have hx0 : x = 0 := hx
    subst x
    simp [altered, ident]

example : ∀ slice : FrozenSlice (ExtensionOperator ℕ), SliceInvariantOnCone slice support →
    ∀ op, FrontierEfficient slice {ident, altered} op →
      ∃ c, c ∈ ({ident} : Set _) ∧ FrontierEfficient slice {ident, altered} c ∧
        AgreeOnCone support op c := by
  apply (universal_ledger_canonicality_iff_coverage {ident, altered} {ident} support
    (by intro x hx; simp only [Set.mem_singleton_iff] at hx; subst x; simp)).mpr
  intro op hop
  refine ⟨ident, Set.mem_singleton _, ?_⟩
  rcases hop with rfl | hop
  · exact agree_on_cone_refl _ _
  · have heq : op = altered := hop
    subst op
    intro x hx
    have hx0 : x = 0 := hx
    subst x
    simp [altered, ident]

-- An uncovered class yields a counterledger even with a nonempty domain and cone.
example : ∃ slice, SliceInvariantOnCone slice support ∧
    FrontierEfficient slice {ident, one} ident ∧
    ¬ AlignsOnConeWithCanonicalFamily support {one} ident := by
  apply uncovered_class_has_counterledger {ident, one} {one} support ident (by simp)
  rintro ⟨c, hc, hAgree⟩
  have heq : c = one := hc
  subst c
  have h := hAgree 0 (by simp [support])
  norm_num [ident, one] at h

-- A finite Boolean logical presentation exercises the proof interface. It is
-- explicitly NOT a model or formalization of EA, PA, or arithmetic consistency.
def boolPresentation : SentencePresentation Bool where
  conj := Bool.and
  impl := fun a b => !a || b
  top := true
  con := fun _ => false
  trueSentence := fun a => a = true
  consistent := fun a => a = true
  piClass := fun _ _ => True
  conj_left := by decide
  conj_right := by decide
  conj_intro := by decide
  impl_intro := by decide
  impl_elim := by decide
  le_top := by decide
  top_true := rfl
  true_consistent := fun _ h => h
  conj_computable := (Primrec.dom_bool₂ _).to_comp
  impl_computable := (Primrec.dom_bool₂ _).to_comp
  con_computable := Computable.const false
  con_monotone := monotone_const

-- The presentation itself is inhabited; the weak Walsh alternative is real.
example : WalshDichotomy boolPresentation id := by
  exact Or.inl ⟨true, rfl, fun _ _ => le_rfl⟩

theorem bool_walsh_fixture : WalshImportedLaw boolPresentation := by
  intro g _ hMono _
  cases hg : g true with
  | false =>
      right
      refine ⟨true, rfl, ?_⟩
      intro φ _
      have h := hMono (show φ ≤ true by cases φ <;> decide)
      rw [hg] at h
      exact le_trans (boolPresentation.conj_right φ (g φ)) h
  | true =>
      left
      refine ⟨true, rfl, ?_⟩
      intro φ _
      cases φ
      · cases g false <;> decide
      · rw [hg]

example : ∃ θ, boolPresentation.trueSentence θ ∧
    AgreeModuloCone {φ | φ ≤ θ} (extensionBy boolPresentation (fun _ => false))
      (extensionBy boolPresentation boolPresentation.con) := by
  apply walsh_restricted_canonicalization boolPresentation bool_walsh_fixture
    (fun _ => false) (Computable.const false) monotone_const ⟨0, fun _ => trivial⟩
  · intro φ hφ
    have heq : φ = true := hφ
    subst φ
    decide
  · intro φ
    cases φ <;> decide

-- The guarded construction retains its negative control outside the support.
example : ¬ boolPresentation.top ∈
      ({φ | φ ≤ boolPresentation.con boolPresentation.top} : Set Bool) ∧
    ¬ SentenceEquivalent
      ((extensionBy boolPresentation
        (guardedConsistency boolPresentation (boolPresentation.con boolPresentation.top))).fn
          boolPresentation.top)
      ((extensionBy boolPresentation boolPresentation.con).fn boolPresentation.top) :=
  guarded_disagrees_outside_support boolPresentation (by decide)

-- Nonconstant ledger: canonical score 1, identity score 0, and real domination.
example : (consistencyProbeSlice boolPresentation true).benchmark.yield
      (extensionBy boolPresentation boolPresentation.con) = 1 ∧
    (consistencyProbeSlice boolPresentation true).benchmark.yield ⟨id⟩ = 0 ∧
    FrontierDominates (consistencyProbeSlice boolPresentation true)
      (extensionBy boolPresentation boolPresentation.con) ⟨id⟩ :=
  consistency_probe_separates_identity boolPresentation true (by decide)

-- Provable equivalence can hold for distinct codes; no quotient computability
-- or equality of the original codes is needed by the arithmetic bridge.
def coarseNat : Preorder ℕ where
  le := fun a b => a % 2 = b % 2
  lt := fun _ _ => False
  le_refl := fun _ => rfl
  le_trans := fun _ _ _ h k => h.trans k
  lt_iff_le_not_ge := by
    intro a b
    constructor
    · intro h; exact h.elim
    · intro h; exact h.2 h.1.symm

example : @SentenceEquivalent ℕ coarseNat 0 2 ∧ (0 : ℕ) ≠ 2 := by
  change ((0 : ℕ) % 2 = 2 % 2 ∧ (2 : ℕ) % 2 = 0 % 2) ∧ (0 : ℕ) ≠ 2
  decide

-- A three-world finite modal fixture makes truth of the guard coexist with
-- unprovability of both consistency steps. It checks the joint premises needed
-- by the concrete construction, while remaining explicitly separate from EA.
abbrev ModalProfile := Bool × Bool × Bool

def modalPresentation : SentencePresentation ModalProfile where
  conj := fun a b => (a.1 && b.1, a.2.1 && b.2.1, a.2.2 && b.2.2)
  impl := fun a b => (!a.1 || b.1, !a.2.1 || b.2.1, !a.2.2 || b.2.2)
  top := (true, true, true)
  con := fun a => (a.2.1 || a.2.2, a.2.2, false)
  trueSentence := fun a => a.1 = true
  consistent := fun a => a.1 = true ∨ a.2.1 = true ∨ a.2.2 = true
  piClass := fun _ _ => True
  conj_left := by decide
  conj_right := by decide
  conj_intro := by decide
  impl_intro := by decide
  impl_elim := by decide
  le_top := by decide
  top_true := rfl
  true_consistent := fun _ h => Or.inl h
  conj_computable := (Primrec.dom_finite _).to_comp
  impl_computable := (Primrec.dom_finite _).to_comp
  con_computable := (Primrec.dom_finite _).to_comp
  con_monotone := by decide

example : modalPresentation.trueSentence (modalPresentation.con modalPresentation.top) ∧
    ¬ modalPresentation.top ≤ modalPresentation.con modalPresentation.top ∧
    ¬ modalPresentation.con modalPresentation.top ≤
      modalPresentation.con (modalPresentation.con modalPresentation.top) := by
  change (true = true) ∧ ¬(true, true, true) ≤ (true, true, false) ∧
    ¬(true, true, false) ≤ (true, false, false)
  decide

-- Instantiate the entire frontier example with an inhabited true support,
-- actual computable maps, a nonconstant invariant ledger, and a dominated control.
example : ∃ θ : ModalProfile, modalPresentation.trueSentence θ ∧
    AgreeModuloCone {φ | φ ≤ θ}
      (extensionBy modalPresentation (guardedConsistency modalPresentation θ))
      (extensionBy modalPresentation modalPresentation.con) ∧
    FrontierEfficient (consistencyProbeSlice modalPresentation θ)
      {extensionBy modalPresentation (guardedConsistency modalPresentation θ),
        extensionBy modalPresentation modalPresentation.con, ⟨id⟩}
      (extensionBy modalPresentation (guardedConsistency modalPresentation θ)) ∧
    FrontierDominates (consistencyProbeSlice modalPresentation θ)
      (extensionBy modalPresentation modalPresentation.con) ⟨id⟩ := by
  let θ := modalPresentation.con modalPresentation.top
  have h := guarded_consistency_frontier_instance modalPresentation θ
    (show true = true from rfl) (by decide)
  exact ⟨θ, h.1, h.2.2.2.2.2.1, h.2.2.2.2.2.2.2.1, h.2.2.2.2.2.2.2.2.2⟩

end ClosureFrontier.StrengtheningReview
