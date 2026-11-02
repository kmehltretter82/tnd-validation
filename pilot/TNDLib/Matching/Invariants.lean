import TNDLib.Matching.Algorithm

/-! Consistency and proposal-cursor bounds for the serial proposal transition. -/

namespace TNDLib.Matching.Algorithm

/-- No proposer is held by two different receivers. -/
def Consistent (state : State n) : Prop :=
  ∀ receiver₁ receiver₂ proposer,
    state.holding receiver₁ = some proposer →
    state.holding receiver₂ = some proposer → receiver₁ = receiver₂

/-- Every held pair has already been proposed to. -/
def AssignedBelow (preferences : Preferences n) (state : State n) : Prop :=
  ∀ receiver proposer, state.holding receiver = some proposer →
    (preferences.proposerRank proposer receiver).val < state.nextRank proposer

/-- An accepted holder is either the new proposer or the previous holder. -/
theorem offer_eq_some_cases (rank : Fin n → Fin n) (candidate winner : Fin n)
    (holding : Option (Fin n)) :
    Proposal.offer rank candidate holding = some winner →
      winner = candidate ∨ holding = some winner :=
  Option.rec
    (fun held => Or.inl (Option.some.inj held).symm)
    (fun current held =>
      Or.elim (Proposal.preferSpec rank candidate current)
        (fun preferred => Or.inl ((Option.some.inj held).symm.trans preferred.1))
        (fun retained => Or.inr
          (congrArg some (retained.1.symm.trans (Option.some.inj held))))) holding

/-- A changed holder is the new proposer at the receiver receiving this offer. -/
theorem advance_holding_cases (preferences : Preferences n) (state : State n)
    (proposer receiver queried holder : Fin n)
    (held : (advance preferences state proposer receiver).holding queried = some holder) :
    (queried = receiver ∧ holder = proposer) ∨ state.holding queried = some holder :=
  if same : queried = receiver then
    Or.elim
      (offer_eq_some_cases (preferences.receiverRank receiver) proposer holder
        (state.holding receiver) ((ite_eq_left same).symm.trans held))
      (fun newHolder => Or.inl ⟨same, newHolder⟩)
      (fun oldHolder => Or.inr
        (Eq.mpr (congrArg (fun target => state.holding target = some holder) same) oldHolder))
  else Or.inr ((ite_eq_right same).symm.trans held)

/-- Offering a free proposer preserves uniqueness of tentative partners. -/
theorem consistent_advance (preferences : Preferences n) (state : State n)
    (consistent : Consistent state) (proposer receiver : Fin n)
    (free : ∀ queried, state.holding queried ≠ some proposer) :
    Consistent (advance preferences state proposer receiver) :=
  fun receiver₁ receiver₂ holder held₁ held₂ =>
    Or.elim (advance_holding_cases preferences state proposer receiver receiver₁ holder held₁)
      (fun new₁ =>
        Or.elim
          (advance_holding_cases preferences state proposer receiver receiver₂ holder held₂)
          (fun new₂ => new₁.1.trans new₂.1.symm)
          (fun old₂ => False.elim (free receiver₂ (new₁.2 ▸ old₂))))
      (fun old₁ =>
        Or.elim
          (advance_holding_cases preferences state proposer receiver receiver₂ holder held₂)
          (fun new₂ => False.elim (free receiver₁ (new₂.2 ▸ old₁)))
          (fun old₂ => consistent receiver₁ receiver₂ holder old₁ old₂))

/-- The empty initial state cannot hold a proposer twice. -/
theorem consistent_initial (n : Nat) : Consistent (initial n) :=
  fun _ _ proposer held => False.elim (Option.some_ne_none proposer held.symm)

/-- The empty initial state has no assigned pair. -/
theorem assignedBelow_initial (preferences : Preferences n) :
    AssignedBelow preferences (initial n) :=
  fun _ proposer held => False.elim (Option.some_ne_none proposer held.symm)

/-- A proposal transition never decreases a proposer's next-rank cursor. -/
theorem advance_nextRank_le (preferences : Preferences n) (state : State n)
    (proposer receiver queried : Fin n) :
    state.nextRank queried ≤ (advance preferences state proposer receiver).nextRank queried :=
  if same : queried = proposer then
    Eq.mpr
      (congrArg (fun counter => state.nextRank queried ≤ counter) (ite_eq_left same))
      (Nat.le_succ _)
  else
    Eq.mpr
      (congrArg (fun counter => state.nextRank queried ≤ counter) (ite_eq_right same))
      (Nat.le_refl _)

/-- Advancing the cursor records both a retained old pair and the newly held pair. -/
theorem assignedBelow_advance (preferences : Preferences n) (state : State n)
    (assigned : AssignedBelow preferences state) (proposer receiver : Fin n)
    (_free : ∀ queried, state.holding queried ≠ some proposer)
    (offeredRank : (preferences.proposerRank proposer receiver).val = state.nextRank proposer) :
    AssignedBelow preferences (advance preferences state proposer receiver) :=
  fun queried holder held =>
    Or.elim (advance_holding_cases preferences state proposer receiver queried holder held)
      (fun newHolder =>
        Eq.mpr
          (congrArg (fun target =>
            (preferences.proposerRank target queried).val <
              (advance preferences state proposer receiver).nextRank target) newHolder.2)
          (Eq.mpr
            (congrArg (fun target =>
              (preferences.proposerRank proposer target).val <
                (advance preferences state proposer receiver).nextRank proposer) newHolder.1)
            (Eq.mpr
              (congrArg (fun counter =>
                (preferences.proposerRank proposer receiver).val < counter)
                (ite_eq_left rfl))
              (Nat.lt_succ_of_le (Nat.le_of_eq offeredRank)))))
      (fun oldHolder =>
        Nat.lt_of_lt_of_le (assigned queried holder oldHolder)
          (advance_nextRank_le preferences state proposer receiver holder))

end TNDLib.Matching.Algorithm
