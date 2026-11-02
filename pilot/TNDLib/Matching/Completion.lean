import TNDLib.Matching.Algorithm
import TNDLib.Matching.Rank
import TNDLib.Matching.History

/-! Decode a completed finite holder state into executable perfect-matching data. -/

namespace TNDLib.Matching.Algorithm

/-- Search for the receiver holding a proposer. Completion proves the fallback unused. -/
def chosenReceiver (state : State n) (proposer : Fin n) : Fin n :=
  ((Finite.enumerate n).find? fun receiver =>
    decide (state.holding receiver = some proposer)).getD proposer

/-- If no proposer is free, the finite search locates each proposer's actual receiver. -/
theorem holdsChosenReceiver (state : State n) (finished : findFree state = none)
    (proposer : Fin n) : state.holding (chosenReceiver state proposer) = some proposer :=
  match found : (Finite.enumerate n).find?
      (fun receiver => decide (state.holding receiver = some proposer)) with
  | some _receiver =>
    (congrArg state.holding (congrArg (fun result => result.getD proposer) found)).trans
      (of_decide_eq_true (List.find?_some (p := fun receiver => decide (state.holding receiver = some proposer)) found))
  | none =>
    False.elim
      ((List.find?_eq_none.mp finished proposer (Finite.memEnumerate proposer))
        (List.all_eq_true.mpr fun receiver _ =>
          decide_eq_true fun equality =>
            (List.find?_eq_none.mp found receiver (Finite.memEnumerate receiver))
              (decide_eq_true equality)))

/-- Two distinct proposers cannot be assigned the same receiver by the completed search. -/
theorem chosenReceiver_injective (state : State n) (finished : findFree state = none)
    {a b : Fin n} (same : chosenReceiver state a = chosenReceiver state b) : a = b :=
  Option.some.inj ((holdsChosenReceiver state finished a).symm.trans
    ((congrArg state.holding same).trans (holdsChosenReceiver state finished b)))

/-- Decode completed holdings as explicit bijective matching data. -/
def matchingOfFinished (state : State n) (finished : findFree state = none) :
    PerfectMatching n :=
  ⟨chosenReceiver state, inverseRank (chosenReceiver state),
    inverseRankApply (chosenReceiver state) (chosenReceiver_injective state finished),
    applyInverseRank (chosenReceiver state) (chosenReceiver_injective state finished)⟩

/-- The decoded receiver-side partner is exactly the proposer held by that receiver. -/
theorem holdsMatchingInverse (state : State n) (finished : findFree state = none)
    (receiver : Fin n) :
    state.holding receiver = some ((matchingOfFinished state finished).inverse receiver) :=
  (congrArg state.holding
    (applyInverseRank (chosenReceiver state)
      (chosenReceiver_injective state finished) receiver)).symm.trans
    (holdsChosenReceiver state finished (inverseRank (chosenReceiver state) receiver))

/-- Completion and the proposal-history invariants rule out every blocking pair. -/
theorem matchingStableOfHistory (preferences : Preferences n) (state : State n)
    (finished : findFree state = none) (history : History preferences state)
    (assigned : ∀ receiver proposer, state.holding receiver = some proposer →
      (preferences.proposerRank proposer receiver).val < state.nextRank proposer) :
    Stable preferences (matchingOfFinished state finished) :=
  fun proposer receiver blocking =>
    Exists.elim
      (history proposer receiver
        (Nat.lt_trans blocking.2.1
          (assigned (chosenReceiver state proposer) proposer
            (holdsChosenReceiver state finished proposer))))
      fun _held bound =>
        Nat.not_lt_of_ge
          (Eq.mpr
            (congrArg
              (fun incumbent => (preferences.receiverRank receiver incumbent).val ≤
                (preferences.receiverRank receiver proposer).val)
              (Option.some.inj ((holdsMatchingInverse state finished receiver).symm.trans bound.1)))
            bound.2)
          blocking.2.2

end TNDLib.Matching.Algorithm
