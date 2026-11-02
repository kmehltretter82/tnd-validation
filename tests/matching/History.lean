import TNDLib.Matching.History

namespace TNDLib.Matching.Algorithm.Tests

/-- Every participant ranks the other side by its index. -/
def preferences : Preferences 2 :=
  ⟨fun _ i => i, fun _ i => i, fun _ {_ _} equality => equality,
    fun _ {_ _} equality => equality⟩

def first : State 2 := advance preferences (initial 2) 0 0

def rejected : State 2 := advance preferences first 1 0

def completed : State 2 := advance preferences rejected 1 1

theorem first_history : History preferences first :=
  history_advance preferences (initial 2) (history_initial preferences) 0 0 rfl

theorem rejected_history : History preferences rejected :=
  history_advance preferences first first_history 1 0 rfl

theorem completed_history : History preferences completed :=
  history_advance preferences rejected rejected_history 1 1 rfl

example : rejected.holding 0 = some 0 := rfl

example : rejected.nextRank 1 = 1 := rfl

example : completed.holding 1 = some 1 := rfl

#print axioms TNDLib.Matching.Algorithm.history_initial
#print axioms TNDLib.Matching.Algorithm.history_advance
#print axioms TNDLib.Matching.Algorithm.free_nextRank_lt
#print axioms completed_history

end TNDLib.Matching.Algorithm.Tests
