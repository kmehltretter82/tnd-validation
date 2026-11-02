import TNDLib.Matching.Basic
import TNDLib.Matching.Proposal

/-!
An executable serial deferred-acceptance prototype. Its outcome explicitly
distinguishes completion from malformed/exhausted states and fuel exhaustion.
The generic termination/perfection/stability proof is separate work.
-/

namespace TNDLib.Matching.Algorithm

/-- Each receiver holds at most one proposer; each proposer tracks its next rank. -/
structure State (n : Nat) where
  holding : Fin n → Option (Fin n)
  nextRank : Fin n → Nat

/-- No proposals have been made and no receiver holds a proposer. -/
def initial (n : Nat) : State n :=
  ⟨fun _ => none, fun _ => 0⟩

/-- A proposer is free exactly when no receiver currently holds it. -/
def isFree (state : State n) (proposer : Fin n) : Bool :=
  (Finite.enumerate n).all fun receiver => decide (state.holding receiver ≠ some proposer)

/-- Select the first free proposer from the explicit finite enumeration. -/
def findFree (state : State n) : Option (Fin n) :=
  (Finite.enumerate n).find? (isFree state)

/-- Find the receiver at this proposer's next untried preference rank. -/
def receiverAtRank (preferences : Preferences n) (state : State n) (proposer : Fin n) :
    Option (Fin n) :=
  (Finite.enumerate n).find? fun receiver =>
    decide ((preferences.proposerRank proposer receiver).val = state.nextRank proposer)

/-- Process one specified proposal and mark its preference rank as tried. -/
def advance (preferences : Preferences n) (state : State n)
    (proposer receiver : Fin n) : State n :=
  ⟨fun other =>
      if other = receiver then
        Proposal.offer (preferences.receiverRank receiver) proposer (state.holding receiver)
      else state.holding other,
    fun other => if other = proposer then state.nextRank other + 1 else state.nextRank other⟩

/-- A step never silently treats a missing receiver or exhausted rank as completion. -/
inductive StepResult (n : Nat) where
  | advanced : State n → StepResult n
  | finished : State n → StepResult n
  | invalid : State n → Fin n → StepResult n
  | exhausted : State n → Fin n → StepResult n

/-- Make one proposal, or explicitly explain why no proposal is made. -/
def step (preferences : Preferences n) (state : State n) : StepResult n :=
  match findFree state with
  | none => .finished state
  | some proposer =>
    if state.nextRank proposer < n then
      match receiverAtRank preferences state proposer with
      | none => .invalid state proposer
      | some receiver => .advanced (advance preferences state proposer receiver)
    else .exhausted state proposer

/-- Prototype execution can finish, reject a state, or run out of its explicit fuel. -/
inductive Outcome (n : Nat) where
  | finished : State n → Outcome n
  | invalid : State n → Fin n → Outcome n
  | exhausted : State n → Fin n → Outcome n
  | fuelExhausted : State n → Outcome n

/-- A structurally terminating fuel interpreter; fuel exhaustion is not success. -/
def runFuel (preferences : Preferences n) : Nat → State n → Outcome n
  | 0, state => .fuelExhausted state
  | fuel + 1, state =>
    match step preferences state with
    | .advanced next => runFuel preferences fuel next
    | .finished final => .finished final
    | .invalid invalid proposer => .invalid invalid proposer
    | .exhausted exhausted proposer => .exhausted exhausted proposer

/-- Run from the empty state with a prospective proposal budget plus a completion check. -/
def run (preferences : Preferences n) : Outcome n :=
  runFuel preferences (n * n + 1) (initial n)

/-- Check the finished holder map against a known perfect matching. -/
def hasMatching (state : State n) (matching : PerfectMatching n) : Bool :=
  (Finite.enumerate n).all fun receiver =>
    decide (state.holding receiver = some (matching.inverse receiver))

/-- A finite observation for examples; incomplete outcomes are always rejected. -/
def outcomeHasMatching (outcome : Outcome n) (matching : PerfectMatching n) : Bool :=
  match outcome with
  | .finished state => hasMatching state matching
  | .invalid _ _ => false
  | .exhausted _ _ => false
  | .fuelExhausted _ => false

end TNDLib.Matching.Algorithm
