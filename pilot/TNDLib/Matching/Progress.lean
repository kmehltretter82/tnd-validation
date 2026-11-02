import TNDLib.Matching.Algorithm
import TNDLib.Matching.Rank

/-! Constructive meaning and success of finite proposal lookup. -/

namespace TNDLib.Matching.Algorithm

/-- The finite executable predicate checks exactly that a proposer is unheld. -/
theorem isFree_eq_true_iff (state : State n) (proposer : Fin n) :
    isFree state proposer = true ↔ ∀ receiver, state.holding receiver ≠ some proposer :=
  ⟨fun free receiver =>
      of_decide_eq_true ((List.all_eq_true.mp free) receiver (Finite.memEnumerate receiver)),
    fun free => List.all_eq_true.mpr fun receiver _ => decide_eq_true (free receiver)⟩

/-- A free proposer returned by finite search really is unheld. -/
theorem findFree_sound (state : State n) {proposer : Fin n}
    (found : findFree state = some proposer) :
    ∀ receiver, state.holding receiver ≠ some proposer :=
  (isFree_eq_true_iff state proposer).mp
    (List.find?_some (p := isFree state) found)

/-- A valid untried rank always names an actual receiver. -/
theorem receiverAtRank_ne_none (preferences : Preferences n) (state : State n)
    (proposer : Fin n) (untried : state.nextRank proposer < n) :
    receiverAtRank preferences state proposer ≠ none :=
  fun missing =>
    Exists.elim
      (surjectiveOfInjective (preferences.proposerRank proposer)
        (preferences.proposerRank_injective proposer) ⟨state.nextRank proposer, untried⟩)
      fun receiver equality =>
        (List.find?_eq_none.mp missing receiver (Finite.memEnumerate receiver))
          (decide_eq_true (congrArg Fin.val equality))

/-- A receiver returned by lookup has exactly the next untried preference rank. -/
theorem receiverAtRank_sound (preferences : Preferences n) (state : State n)
    (proposer : Fin n) {receiver : Fin n}
    (found : receiverAtRank preferences state proposer = some receiver) :
    (preferences.proposerRank proposer receiver).val = state.nextRank proposer :=
  of_decide_eq_true
    (List.find?_some
      (p := fun receiver => decide
        ((preferences.proposerRank proposer receiver).val = state.nextRank proposer)) found)

/-- Every offered receiver enters the tried prefix, whether it accepts or rejects. -/
theorem offeredReceiver_tried (preferences : Preferences n) (state : State n)
    (proposer receiver : Fin n)
    (offeredRank : (preferences.proposerRank proposer receiver).val = state.nextRank proposer) :
    (preferences.proposerRank proposer receiver).val <
      (advance preferences state proposer receiver).nextRank proposer :=
  Eq.mpr
    (congrArg (fun counter => (preferences.proposerRank proposer receiver).val < counter)
      (ite_eq_left rfl))
    (Nat.lt_succ_of_le (Nat.le_of_eq offeredRank))

/-- Lookup cannot return a receiver in the proposer's previously tried prefix. -/
theorem nextReceiver_not_tried (preferences : Preferences n) (state : State n)
    (proposer : Fin n) {receiver : Fin n}
    (found : receiverAtRank preferences state proposer = some receiver)
    (previous : Fin n)
    (tried : (preferences.proposerRank proposer previous).val < state.nextRank proposer) :
    previous ≠ receiver :=
  fun same =>
    Nat.ne_of_lt tried
      ((congrArg (fun chosen => (preferences.proposerRank proposer chosen).val) same).trans
        (receiverAtRank_sound preferences state proposer found))

end TNDLib.Matching.Algorithm
