import ClosureFrontier.TheoremTrack.Candidates
import Mathlib.Data.Finset.Card
import Mathlib.Data.Finset.Range

namespace ClosureFrontier.TheoremTrack

-- The state recurrence is fixed: no exogenous inputs are inserted between steps.
def packageOrbit {α : Type} (packages : ℕ → ClosurePackage α) (x : α) : ℕ → α
  | 0 => x
  | t + 1 => (packages t).op (packageOrbit packages x t)

theorem orbit_change_requires_switch {α : Type}
    (packages : ℕ → ClosurePackage α) (x : α) (t : ℕ)
    (h : packageOrbit packages x (t + 2) ≠ packageOrbit packages x (t + 1)) :
    PackageChanged (packages t) (packages (t + 1)) ∧
      PackageChangeAt (packages t) (packages (t + 1))
        (packageOrbit packages x (t + 1)) := by
  have hid : (packages t).op (packageOrbit packages x (t + 1)) =
      packageOrbit packages x (t + 1) := (packages t).idempotent _
  have hAt : PackageChangeAt (packages t) (packages (t + 1))
      (packageOrbit packages x (t + 1)) := by
    unfold PackageChangeAt
    rw [hid]
    exact Ne.symm h
  exact ⟨fun hSame => hAt (congrFun hSame _), hAt⟩

noncomputable def orbitChangeCount {α : Type}
    (packages : ℕ → ClosurePackage α) (x : α) (horizon : ℕ) : ℕ := by
  classical
  exact ((Finset.range horizon).filter fun t =>
    packageOrbit packages x (t + 1) ≠ packageOrbit packages x t).card

noncomputable def packageSwitchCount {α : Type}
    (packages : ℕ → ClosurePackage α) (horizon : ℕ) : ℕ := by
  classical
  exact ((Finset.range horizon).filter fun t =>
    PackageChanged (packages t) (packages (t + 1))).card

theorem package_switch_budget {α : Type}
    (packages : ℕ → ClosurePackage α) (x : α) (horizon : ℕ) :
    orbitChangeCount packages x (horizon + 1) ≤
      1 + packageSwitchCount packages horizon := by
  classical
  let changed := (Finset.range (horizon + 1)).filter fun t =>
    packageOrbit packages x (t + 1) ≠ packageOrbit packages x t
  let switched := (Finset.range horizon).filter fun t =>
    PackageChanged (packages t) (packages (t + 1))
  have hmap : Set.MapsTo (fun t : ℕ => t - 1) (↑(changed.erase 0) : Set ℕ)
      (↑switched : Set ℕ) := by
    intro t ht
    change t ∈ changed.erase 0 at ht
    change t - 1 ∈ switched
    have ht' := Finset.mem_erase.mp ht
    have hchanged := Finset.mem_filter.mp ht'.2
    have hlt := Finset.mem_range.mp hchanged.1
    cases t with
    | zero => exact (ht'.1 rfl).elim
    | succ t =>
      apply Finset.mem_filter.mpr
      refine ⟨Finset.mem_range.mpr (by omega), ?_⟩
      exact (orbit_change_requires_switch packages x t hchanged.2).1
  have hinj : Set.InjOn (fun t : ℕ => t - 1) (↑(changed.erase 0) : Set ℕ) := by
    intro a ha b hb hab
    change a ∈ changed.erase 0 at ha
    change b ∈ changed.erase 0 at hb
    change a - 1 = b - 1 at hab
    have ha0 := (Finset.mem_erase.mp ha).1
    have hb0 := (Finset.mem_erase.mp hb).1
    omega
  have hcard := Finset.card_le_card_of_injOn (fun t : ℕ => t - 1) hmap hinj
  have herase := Finset.pred_card_le_card_erase (s := changed) (a := 0)
  change changed.card ≤ 1 + switched.card
  omega

theorem unbounded_changes_require_unbounded_switches {α : Type}
    (packages : ℕ → ClosurePackage α) (x : α)
    (h : ∀ bound, ∃ t, bound ≤ t ∧
      packageOrbit packages x (t + 1) ≠ packageOrbit packages x t) :
    ∀ bound, ∃ t, bound ≤ t ∧ PackageChanged (packages t) (packages (t + 1)) := by
  intro bound
  rcases h (bound + 1) with ⟨t, ht, hg⟩
  cases t with
  | zero => omega
  | succ t => exact ⟨t, by omega, (orbit_change_requires_switch packages x t hg).1⟩

-- Two closures round upward respectively to odd and even integers.
def oddRound (n : ℕ) : ℕ := 2 * (n / 2) + 1
def evenRound (n : ℕ) : ℕ := 2 * ((n + 1) / 2)

theorem odd_round_laws : Monotone oddRound ∧ (∀ n, n ≤ oddRound n) ∧
    (∀ n, oddRound (oddRound n) = oddRound n) := by
  refine ⟨?_, ?_, ?_⟩
  · intro a b hab
    unfold oddRound
    have hd := Nat.div_le_div_right (c := 2) hab
    omega
  · intro n
    unfold oddRound
    omega
  · intro n
    unfold oddRound
    omega

theorem even_round_laws : Monotone evenRound ∧ (∀ n, n ≤ evenRound n) ∧
    (∀ n, evenRound (evenRound n) = evenRound n) := by
  refine ⟨?_, ?_, ?_⟩
  · intro a b hab
    unfold evenRound
    have hd := Nat.div_le_div_right (c := 2) (show a + 1 ≤ b + 1 by omega)
    omega
  · intro n
    unfold evenRound
    omega
  · intro n
    unfold evenRound
    omega

theorem odd_round_computable : Computable oddRound :=
  (Primrec.nat_add.comp
    (Primrec.nat_mul.comp (Primrec.const 2)
      (Primrec.nat_div.comp Primrec.id (Primrec.const 2)))
    (Primrec.const 1)).to_comp

theorem even_round_computable : Computable evenRound :=
  (Primrec.nat_mul.comp (Primrec.const 2)
    (Primrec.nat_div.comp
      (Primrec.nat_add.comp Primrec.id (Primrec.const 1)) (Primrec.const 2))).to_comp

def oddPackage : ClosurePackage ℕ := ⟨oddRound, odd_round_laws.2.2⟩
def evenPackage : ClosurePackage ℕ := ⟨evenRound, even_round_laws.2.2⟩

def alternatingPackages (t : ℕ) : ClosurePackage ℕ :=
  if t % 2 = 0 then oddPackage else evenPackage

theorem alternating_orbit_exact (t : ℕ) : packageOrbit alternatingPackages 0 t = t := by
  induction t with
  | zero => rfl
  | succ t ih =>
      simp only [packageOrbit, ih, alternatingPackages]
      split_ifs with heven
      · change oddRound t = t + 1
        unfold oddRound
        omega
      · change evenRound t = t + 1
        unfold evenRound
        omega

theorem alternating_orbit_unbounded :
    ∀ bound, ∃ t, bound < packageOrbit alternatingPackages 0 t := by
  intro bound
  exact ⟨bound + 1, by rw [alternating_orbit_exact]; omega⟩

theorem alternating_uses_two_packages (t : ℕ) :
    alternatingPackages t = oddPackage ∨ alternatingPackages t = evenPackage := by
  unfold alternatingPackages
  split_ifs <;> simp

theorem alternating_switches_every_step (t : ℕ) :
    PackageChanged (alternatingPackages t) (alternatingPackages (t + 1)) := by
  apply (orbit_change_requires_switch alternatingPackages 0 t ?_).1
  rw [alternating_orbit_exact, alternating_orbit_exact]
  omega

theorem alternating_budget_sharp (horizon : ℕ) :
    orbitChangeCount alternatingPackages 0 (horizon + 1) =
      1 + packageSwitchCount alternatingPackages horizon := by
  classical
  have hCount : ∀ n, orbitChangeCount alternatingPackages 0 n = n := by
    intro n
    simp [orbitChangeCount, alternating_orbit_exact]
  have hSwitch : packageSwitchCount alternatingPackages horizon = horizon := by
    simp [packageSwitchCount, alternating_switches_every_step]
  rw [hCount, hSwitch]
  omega

end ClosureFrontier.TheoremTrack
