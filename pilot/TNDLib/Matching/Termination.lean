import TNDLib.Matching.Progress
import TNDLib.Matching.History
import TNDLib.Matching.Measure
import TNDLib.Matching.Invariants

/-! Sufficient finite fuel for serial deferred acceptance. -/

namespace TNDLib.Matching.Algorithm

/-- The finite invariants carried by every valid deferred-acceptance state. -/
structure Valid (preferences : Preferences n) (state : State n) : Prop where
  bounded : ∀ proposer, state.nextRank proposer ≤ n
  consistent : Consistent state
  history : History preferences state
  assigned : AssignedBelow preferences state

/-- The empty state satisfies every invariant without a stable-existence premise. -/
theorem valid_initial (preferences : Preferences n) : Valid preferences (initial n) :=
  ⟨fun _ => Nat.zero_le n,
    consistent_initial n,
    history_initial preferences,
    assignedBelow_initial preferences⟩

def proposerStep (preferences : Preferences n) (state : State n)
    (proposer : Fin n) : StepResult n :=
  if state.nextRank proposer < n then
    match receiverAtRank preferences state proposer with
    | none => .invalid state proposer
    | some receiver => .advanced (advance preferences state proposer receiver)
  else .exhausted state proposer

/-- Exhausting free-proposer search is exactly the algorithm's completion branch. -/
theorem step_finished (preferences : Preferences n) (state : State n)
    (finished : findFree state = none) : step preferences state = .finished state :=
  congrArg (fun selected : Option (Fin n) =>
    match selected with
    | none => StepResult.finished state
    | some proposer => proposerStep preferences state proposer) finished

/-- A found free proposer and its in-range receiver produce the expected transition. -/
theorem step_advanced (preferences : Preferences n) (state : State n)
    (proposer receiver : Fin n) (found : findFree state = some proposer)
    (untried : state.nextRank proposer < n)
    (offered : receiverAtRank preferences state proposer = some receiver) :
    step preferences state = .advanced (advance preferences state proposer receiver) :=
  (congrArg (fun selected : Option (Fin n) =>
      match selected with
      | none => StepResult.finished state
      | some selectedProposer => proposerStep preferences state selectedProposer) found).trans
    ((ite_eq_left untried).trans
      (congrArg (fun selected : Option (Fin n) =>
        match selected with
        | none => StepResult.invalid state proposer
        | some target => StepResult.advanced (advance preferences state proposer target)) offered))

def continueRun (preferences : Preferences n) (fuel : Nat) : StepResult n → Outcome n
  | .advanced next => runFuel preferences fuel next
  | .finished final => .finished final
  | .invalid invalid proposer => .invalid invalid proposer
  | .exhausted exhausted proposer => .exhausted exhausted proposer

/-- One remaining interpreter step can report a completed state. -/
theorem runFuel_finished (preferences : Preferences n) (state : State n) (fuel : Nat)
    (finished : findFree state = none) :
    runFuel preferences (fuel + 1) state = .finished state :=
  congrArg (continueRun preferences fuel) (step_finished preferences state finished)

/-- One valid proposal consumes exactly one unit of interpreter fuel. -/
theorem runFuel_advanced (preferences : Preferences n) (state : State n) (fuel : Nat)
    (proposer receiver : Fin n) (found : findFree state = some proposer)
    (untried : state.nextRank proposer < n)
    (offered : receiverAtRank preferences state proposer = some receiver) :
    runFuel preferences (fuel + 1) state =
      runFuel preferences fuel (advance preferences state proposer receiver) :=
  congrArg (continueRun preferences fuel)
    (step_advanced preferences state proposer receiver found untried offered)

/-- Advancing the proposal count exactly compensates for one consumed fuel unit. -/
theorem fuelBound_advance (preferences : Preferences n) (state : State n)
    (proposer receiver : Fin n) (fuel : Nat)
    (bound : n * n < proposalCount state + (fuel + 1)) :
    n * n < proposalCount (advance preferences state proposer receiver) + fuel :=
  Eq.mpr
    (congrArg (fun count => n * n < count)
      ((congrArg (fun count => count + fuel)
        (proposalCount_advance preferences state proposer receiver)).trans
        ((Nat.add_right_comm (proposalCount state) 1 fuel).trans
          (Nat.add_assoc (proposalCount state) fuel 1)))) bound

/-- The actual proposal branch preserves every invariant in the state bundle. -/
theorem valid_advance (preferences : Preferences n) (state : State n)
    (valid : Valid preferences state) (proposer receiver : Fin n)
    (free : ∀ queried, state.holding queried ≠ some proposer)
    (untried : state.nextRank proposer < n)
    (offeredRank : (preferences.proposerRank proposer receiver).val = state.nextRank proposer) :
    Valid preferences (advance preferences state proposer receiver) :=
  ⟨advance_bounded preferences state proposer receiver valid.bounded untried,
    consistent_advance preferences state valid.consistent proposer receiver free,
    history_advance preferences state valid.history proposer receiver offeredRank,
    assignedBelow_advance preferences state valid.assigned proposer receiver free offeredRank⟩

/-- A valid state finishes whenever fuel exceeds its remaining proposal budget. -/
theorem runFuel_finishes (preferences : Preferences n) :
    ∀ (fuel : Nat) (state : State n), Valid preferences state →
      n * n < proposalCount state + fuel →
      ∃ final, runFuel preferences fuel state = .finished final ∧
        findFree final = none ∧ Valid preferences final
  | 0, state, valid, fuelBound =>
    False.elim (Nat.not_lt_of_ge (proposalCount_le state valid.bounded) fuelBound)
  | fuel + 1, state, valid, fuelBound =>
    match found : findFree state with
    | none => ⟨state, runFuel_finished preferences state fuel found, found, valid⟩
    | some proposer =>
      let free := findFree_sound state found
      let untried := free_nextRank_lt preferences state valid.history valid.consistent proposer free
      match offered : receiverAtRank preferences state proposer with
      | none => False.elim (receiverAtRank_ne_none preferences state proposer untried offered)
      | some receiver =>
        let nextValid := valid_advance preferences state valid proposer receiver free untried
          (receiverAtRank_sound preferences state proposer offered)
        Exists.elim
          (runFuel_finishes preferences fuel (advance preferences state proposer receiver)
            nextValid (fuelBound_advance preferences state proposer receiver fuel fuelBound))
          fun final result =>
            ⟨final,
              (runFuel_advanced preferences state fuel proposer receiver found untried offered).trans
                result.1,
              result.2⟩

/-- The executable default run always finishes with all invariants preserved. -/
theorem run_finishes (preferences : Preferences n) :
    ∃ final, run preferences = .finished final ∧ findFree final = none ∧
      Valid preferences final :=
  runFuel_finishes preferences (n * n + 1) (initial n) (valid_initial preferences)
    (Eq.mpr
      (congrArg (fun count => n * n < count + (n * n + 1)) (proposalCount_initial n))
      (Eq.mpr (congrArg (fun count => n * n < count) (Nat.zero_add (n * n + 1)))
        (Nat.lt_succ_self (n * n))))

end TNDLib.Matching.Algorithm
