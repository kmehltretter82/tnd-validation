import TNDLib.Matching.Measure

/-! Proposal counts include rejected proposals as well as accepted proposals. -/

namespace TNDLib.Matching.Algorithm.MeasureTests

def commonPreferences (n : Nat) : Preferences n :=
  ⟨fun _ i => i, fun _ i => i, fun _ {_ _} h => h, fun _ {_ _} h => h⟩

def afterFirst : State 2 := advance (commonPreferences 2) (initial 2) 0 0

def afterRejection : State 2 := advance (commonPreferences 2) afterFirst 1 0

example : proposalCount afterFirst = 1 := rfl

example : afterRejection.holding 0 = some 0 := rfl

example : proposalCount afterRejection = 2 := rfl

example : proposalCount (advance (commonPreferences 2) afterRejection 1 1) = 3 := rfl

example (n : Nat) : proposalCount (initial n) = 0 := proposalCount_initial n

example (preferences : Preferences n) (state : State n) (proposer receiver : Fin n)
    (bounded : ∀ p, state.nextRank p ≤ n) (untried : state.nextRank proposer < n) :
    proposalCount (advance preferences state proposer receiver) ≤ n * n :=
  proposalCount_le _ (advance_bounded preferences state proposer receiver bounded untried)

#print axioms TNDLib.Matching.Algorithm.proposalCount_initial
#print axioms TNDLib.Matching.Algorithm.proposalCount_le
#print axioms TNDLib.Matching.Algorithm.proposalCount_advance
#print axioms TNDLib.Matching.Algorithm.advance_bounded

end TNDLib.Matching.Algorithm.MeasureTests
