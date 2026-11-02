import TNDLib.Matching.Completion
import TNDLib.Matching.Termination

/-! A total executable stable-matching constructor for finite strict complete preferences. -/

namespace TNDLib.Matching.Algorithm

/-- Any actual completed run carries the invariants established by total termination. -/
theorem finishedValid (preferences : Preferences n) (state : State n)
    (observed : run preferences = Outcome.finished state) :
    findFree state = none ∧ Valid preferences state :=
  Exists.elim (run_finishes preferences) fun _witness result =>
    Eq.mp
      (congrArg (fun final => findFree final = none ∧ Valid preferences final)
        (Outcome.finished.inj (result.1.symm.trans observed)))
      result.2

/-- Compute a perfect stable matching, with correctness for every valid input size. -/
def stableMatch (preferences : Preferences n) :
    { matching : PerfectMatching n // Stable preferences matching } :=
  match observed : run preferences with
  | .finished state =>
    let valid := finishedValid preferences state observed
    ⟨matchingOfFinished state valid.1,
      matchingStableOfHistory preferences state valid.1 valid.2.history valid.2.assigned⟩
  | .invalid _ _ =>
    False.elim (Exists.elim (run_finishes preferences) fun _ result =>
      Outcome.noConfusion rfl (heq_of_eq (result.1.symm.trans observed)))
  | .exhausted _ _ =>
    False.elim (Exists.elim (run_finishes preferences) fun _ result =>
      Outcome.noConfusion rfl (heq_of_eq (result.1.symm.trans observed)))
  | .fuelExhausted _ =>
    False.elim (Exists.elim (run_finishes preferences) fun _ result =>
      Outcome.noConfusion rfl (heq_of_eq (result.1.symm.trans observed)))

end TNDLib.Matching.Algorithm

namespace TNDLib.Matching

/-- Constructive finite stable existence, returned as executable matching data. -/
def stableMatch (preferences : Preferences n) :
    { matching : PerfectMatching n // Stable preferences matching } :=
  Algorithm.stableMatch preferences

/-- The matching computed by the constructor is stable. -/
theorem stableMatch_stable (preferences : Preferences n) :
    Stable preferences (stableMatch preferences).val :=
  (stableMatch preferences).property

/-- Finite strict complete preference profiles always admit a stable perfect matching. -/
theorem existsStableMatching (preferences : Preferences n) :
    ∃ matching : PerfectMatching n, Stable preferences matching :=
  ⟨(stableMatch preferences).val, stableMatch_stable preferences⟩

end TNDLib.Matching
