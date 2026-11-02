import TNDLib.Matching.StableMatch

/-!
Computed constructor tests: exhaustive strict profiles at sizes zero, one, two,
and a fixed, reproducible collection of varied size-three profiles.
-/

namespace TNDLib.Matching.StableMatchTests

def identityPermutation (n : Nat) : PerfectMatching n :=
  ⟨id, id, fun _ => rfl, fun _ => rfl⟩

def reversePermutation (n : Nat) : PerfectMatching n :=
  ⟨Fin.rev, Fin.rev, Fin.rev_rev, Fin.rev_rev⟩

def commonPreferences (n : Nat) : Preferences n :=
  ⟨fun _ i => i, fun _ i => i, fun _ {_ _} h => h, fun _ {_ _} h => h⟩

def reassignmentPreferences (n : Nat) : Preferences n :=
  ⟨fun _ i => i, fun _ i => Fin.rev i, fun _ {_ _} h => h,
    fun _ {a b} same => (Fin.rev_rev a).symm.trans
      ((congrArg Fin.rev same).trans (Fin.rev_rev b))⟩

example : checkStable (commonPreferences 0) (stableMatch (commonPreferences 0)).val = true := rfl

example : checkStable (commonPreferences 1) (stableMatch (commonPreferences 1)).val = true := rfl

/-- Common preferences force a rejected proposer to continue to its next receiver. -/
example : List.ofFn (stableMatch (commonPreferences 2)).val.partner = [0, 1] := rfl

example : checkStable (commonPreferences 2) (stableMatch (commonPreferences 2)).val = true := rfl

example : checkStable (commonPreferences 2) (reversePermutation 2) = false := rfl

/-- The preferred second proposer displaces the first one at size two. -/
example : List.ofFn (stableMatch (reassignmentPreferences 2)).val.partner = [1, 0] := rfl

example : checkStable (reassignmentPreferences 2)
    (stableMatch (reassignmentPreferences 2)).val = true := rfl

/-- Repeated displacement produces the reversed pairing at size three. -/
example : List.ofFn (stableMatch (reassignmentPreferences 3)).val.partner = [2, 1, 0] := rfl

example : checkStable (reassignmentPreferences 3)
    (stableMatch (reassignmentPreferences 3)).val = true := rfl

/-- Compose two explicitly invertible finite permutations. -/
def composePermutation (left right : PerfectMatching n) : PerfectMatching n :=
  ⟨fun i => left.partner (right.partner i),
    fun i => right.inverse (left.inverse i),
    fun i =>
      (congrArg right.inverse (left.inverse_partner (right.partner i))).trans
        (right.inverse_partner i),
    fun i =>
      (congrArg left.partner (right.partner_inverse (left.inverse i))).trans
        (left.partner_inverse i)⟩

def cycleThree : Fin 3 → Fin 3 := Fin.cases 1 (Fin.cases 2 (Fin.cases 0 Fin.elim0))

def inverseCycleThree : Fin 3 → Fin 3 := Fin.cases 2 (Fin.cases 0 (Fin.cases 1 Fin.elim0))

def cyclicPermutation : PerfectMatching 3 :=
  ⟨cycleThree, inverseCycleThree,
    Fin.cases rfl (Fin.cases rfl (Fin.cases rfl (fun i => Fin.elim0 i))),
    Fin.cases rfl (Fin.cases rfl (Fin.cases rfl (fun i => Fin.elim0 i)))⟩

def permutationsThree : List (PerfectMatching 3) :=
  [identityPermutation 3,
    cyclicPermutation,
    composePermutation cyclicPermutation cyclicPermutation,
    reversePermutation 3,
    composePermutation cyclicPermutation (reversePermutation 3),
    composePermutation (composePermutation cyclicPermutation cyclicPermutation)
      (reversePermutation 3)]

example : permutationsThree.map (fun permutation => List.ofFn permutation.partner) =
    [[0, 1, 2], [1, 2, 0], [2, 0, 1], [2, 1, 0], [0, 2, 1], [1, 0, 2]] := rfl

/-- Enumerate all vectors over a finite explicit choice list. -/
def vectors (choices : List α) : (n : Nat) → List (Fin n → α)
  | 0 => [Fin.elim0]
  | n + 1 => choices.flatMap fun value =>
    (vectors choices n).map fun tail => Fin.cases value tail

/-- Every chosen rank row is a permutation, so all generated profiles are valid. -/
def preferencesFromRows (proposers receivers : Fin n → PerfectMatching n) : Preferences n :=
  ⟨fun p => (proposers p).partner, fun r => (receivers r).partner,
    fun p {a b} same => ((proposers p).inverse_partner a).symm.trans
      ((congrArg (proposers p).inverse same).trans ((proposers p).inverse_partner b)),
    fun r {a b} same => ((receivers r).inverse_partner a).symm.trans
      ((congrArg (receivers r).inverse same).trans ((receivers r).inverse_partner b))⟩

def profilesFromRows (rows : List (Fin n → PerfectMatching n)) : List (Preferences n) :=
  rows.flatMap fun proposers => rows.map (preferencesFromRows proposers)

def profilesZero : List (Preferences 0) :=
  profilesFromRows (vectors [] 0)

def profilesOne : List (Preferences 1) :=
  profilesFromRows (vectors [identityPermutation 1] 1)

def profilesTwo : List (Preferences 2) :=
  profilesFromRows (vectors [identityPermutation 2, reversePermutation 2] 2)

/-- There are two strict ranks per size-two row and four independent rows. -/
example : profilesZero.length = 1 := rfl
example : profilesOne.length = 1 := rfl
example : profilesTwo.length = 16 := rfl

/-- A deterministic sample uses every size-three proposer-row vector once. -/
def profilesThree : List (Preferences 3) :=
  let rows := vectors permutationsThree 3
  (List.range 216).map fun seed =>
    preferencesFromRows
      (rows[seed]?.getD (fun _ => identityPermutation 3))
      (rows[(seed * 37 + 11) % 216]?.getD (fun _ => identityPermutation 3))

example : profilesThree.length = 216 := rfl

/-- Independently inspect both directions of the computed pairing at runtime. -/
def checkBijection (matching : PerfectMatching n) : Bool :=
  (Finite.enumerate n).all (fun proposer =>
    decide (matching.inverse (matching.partner proposer) = proposer)) &&
  (Finite.enumerate n).all (fun receiver =>
    decide (matching.partner (matching.inverse receiver) = receiver))

def checkComputed (preferences : Preferences n) : Bool :=
  let matching := (stableMatch preferences).val
  checkBijection matching && checkStable preferences matching

def checkProfiles (name : String) (profiles : List (Preferences n)) : IO Unit := do
  for preferences in profiles do
    unless checkComputed preferences do
      throw (IO.userError (name ++ ": invalid computed matching"))
  IO.println (name ++ ": " ++ toString profiles.length ++ " profiles passed")

#eval do
  checkProfiles "n=0 exhaustive" profilesZero
  checkProfiles "n=1 exhaustive" profilesOne
  checkProfiles "n=2 exhaustive" profilesTwo
  checkProfiles "n=3 deterministic" profilesThree

#print axioms TNDLib.Matching.stableMatch
#print axioms TNDLib.Matching.existsStableMatching

end TNDLib.Matching.StableMatchTests
