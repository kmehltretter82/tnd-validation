import TNDLib.Matching.Basic

/-! Executable positive and negative cases for the stability certificate checker. -/

namespace TNDLib.Matching.Tests

/-- All participants rank opposite-side participants by their index. -/
def identityPreferences (n : Nat) : Preferences n :=
  ⟨fun _ i => i, fun _ i => i, fun _ {_ _} h => h, fun _ {_ _} h => h⟩

/-- Pair equal indices on the two sides. -/
def identityMatching (n : Nat) : PerfectMatching n :=
  ⟨id, id, fun _ => rfl, fun _ => rfl⟩

/-- Pair indices in opposite order on the two sides. -/
def reversedMatching (n : Nat) : PerfectMatching n :=
  ⟨Fin.rev, Fin.rev, Fin.rev_rev, Fin.rev_rev⟩

example : checkStable (identityPreferences 0) (identityMatching 0) = true := rfl

example : checkStable (identityPreferences 1) (identityMatching 1) = true := rfl

example : checkStable (identityPreferences 2) (identityMatching 2) = true := rfl

example : checkStable (identityPreferences 2) (reversedMatching 2) = false := rfl

/-- With common strict preferences the identity pairing is stable at size two. -/
theorem identityTwo_stable : Stable (identityPreferences 2) (identityMatching 2) :=
  (checkStable_eq_true_iff _ _).mp rfl

/-- With common strict preferences the crossed size-two pairing is unstable. -/
theorem reversedTwo_unstable : ¬ Stable (identityPreferences 2) (reversedMatching 2) :=
  fun h => Bool.noConfusion ((checkStable_eq_true_iff _ _).mpr h)

#print axioms TNDLib.Matching.checkStable_eq_true_iff
#print axioms identityTwo_stable
#print axioms reversedTwo_unstable

end TNDLib.Matching.Tests
