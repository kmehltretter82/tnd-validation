import TNDLib.Matching.Algorithm

/-! Reduction tests for rejection, reassignment, and explicit incomplete outcomes. -/

namespace TNDLib.Matching.Algorithm.Tests

def commonPreferences (n : Nat) : Preferences n :=
  ⟨fun _ i => i, fun _ i => i, fun _ {_ _} h => h, fun _ {_ _} h => h⟩

def identityMatching (n : Nat) : PerfectMatching n :=
  ⟨id, id, fun _ => rfl, fun _ => rfl⟩

def reverseMatching (n : Nat) : PerfectMatching n :=
  ⟨Fin.rev, Fin.rev, Fin.rev_rev, Fin.rev_rev⟩

/-- Both proposers prefer receiver zero; receivers prefer the larger proposer. -/
def reassignmentPreferences (n : Nat) : Preferences n :=
  ⟨fun _ i => i, fun _ i => Fin.rev i, fun _ {_ _} h => h,
    fun _ {a b} h => (Fin.rev_rev a).symm.trans
      ((congrArg Fin.rev h).trans (Fin.rev_rev b))⟩

example : outcomeHasMatching (run (commonPreferences 0)) (identityMatching 0) = true := rfl

example : outcomeHasMatching (run (commonPreferences 1)) (identityMatching 1) = true := rfl

/-- Proposer one is rejected by receiver zero, then proposes to receiver one. -/
example : outcomeHasMatching (run (commonPreferences 2)) (identityMatching 2) = true := rfl

example : checkStable (commonPreferences 2) (identityMatching 2) = true := rfl

def firstCommonProposal : State 2 := advance (commonPreferences 2) (initial 2) 0 0

example : (advance (commonPreferences 2) firstCommonProposal 1 0).holding 0 = some 0 := rfl

example : (advance (commonPreferences 2) firstCommonProposal 1 0).nextRank 1 = 1 := rfl

/-- Receiver zero replaces proposer zero with proposer one; zero moves to receiver one. -/
example : outcomeHasMatching (run (reassignmentPreferences 2)) (reverseMatching 2) = true := rfl

example : checkStable (reassignmentPreferences 2) (reverseMatching 2) = true := rfl

def firstReassignmentProposal : State 2 :=
  advance (reassignmentPreferences 2) (initial 2) 0 0

example : (advance (reassignmentPreferences 2) firstReassignmentProposal 1 0).holding 0 =
    some 1 := rfl

example : isFree (advance (reassignmentPreferences 2) firstReassignmentProposal 1 0) 0 =
    true := rfl

example : outcomeHasMatching
    (runFuel (commonPreferences 2) 1 (initial 2)) (identityMatching 2) = false := rfl

example : step (commonPreferences 1) ⟨fun _ => none, fun _ => 1⟩ =
    .exhausted ⟨fun _ => none, fun _ => 1⟩ 0 := rfl

#print axioms TNDLib.Matching.Algorithm.run
#print axioms TNDLib.Matching.Algorithm.outcomeHasMatching

end TNDLib.Matching.Algorithm.Tests
