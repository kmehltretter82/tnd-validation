import TNDLib.Matching.Algorithm
import TNDLib.Matching.Cardinality

/-! Every receiver already tried by a proposer retains someone at least as good. -/

namespace TNDLib.Matching.Algorithm

/-- Once a proposer has tried a receiver, that receiver remains occupied by
someone it ranks at least as highly as that proposer. -/
def History (preferences : Preferences n) (state : State n) : Prop :=
  ∀ proposer receiver,
    (preferences.proposerRank proposer receiver).val < state.nextRank proposer →
    ∃ current, state.holding receiver = some current ∧
      (preferences.receiverRank receiver current).val ≤
        (preferences.receiverRank receiver proposer).val

/-- The empty state has no tried receiver. -/
theorem history_initial (preferences : Preferences n) : History preferences (initial n) :=
  fun _ _ tried => False.elim (Nat.not_lt_zero _ tried)

/-- Updating one receiver cannot worsen any previously occupied receiver's rank. -/
theorem advance_preserves_held_bound (preferences : Preferences n) (state : State n)
    (proposer receiver queried current : Fin n) (held : state.holding queried = some current) :
    ∃ winner, (advance preferences state proposer receiver).holding queried = some winner ∧
      (preferences.receiverRank queried winner).val ≤
        (preferences.receiverRank queried current).val :=
  if same : queried = receiver then
    Eq.mpr
      (congrArg (fun target =>
        ∃ winner, (advance preferences state proposer receiver).holding target = some winner ∧
          (preferences.receiverRank target winner).val ≤
            (preferences.receiverRank target current).val) same)
      (Exists.elim
        (Proposal.offer_preserves_rank (preferences.receiverRank receiver) proposer current)
        fun winner result =>
          ⟨winner,
            (ite_eq_left rfl).trans
              ((congrArg (Proposal.offer (preferences.receiverRank receiver) proposer)
                (same ▸ held)).trans result.1),
            result.2.1⟩)
  else
    ⟨current, (ite_eq_right same).trans held, Nat.le_refl _⟩

/-- Previously tried receivers keep dominating that proposer after any offer. -/
theorem history_old_advance (preferences : Preferences n) (state : State n)
    (history : History preferences state) (proposer receiver triedProposer triedReceiver : Fin n)
    (tried : (preferences.proposerRank triedProposer triedReceiver).val <
      state.nextRank triedProposer) :
    ∃ current, (advance preferences state proposer receiver).holding triedReceiver = some current ∧
      (preferences.receiverRank triedReceiver current).val ≤
        (preferences.receiverRank triedReceiver triedProposer).val :=
  Exists.elim (history triedProposer triedReceiver tried) fun incumbent previous =>
    Exists.elim
      (advance_preserves_held_bound preferences state proposer receiver
        triedReceiver incumbent previous.1)
      fun winner result => ⟨winner, result.1, Nat.le_trans result.2 previous.2⟩

/-- An offer retains someone at least as good as the new proposer. -/
theorem offer_candidate_bound (rank : Fin n → Fin n) (candidate : Fin n)
    (holding : Option (Fin n)) :
    ∃ winner, Proposal.offer rank candidate holding = some winner ∧
      (rank winner).val ≤ (rank candidate).val :=
  Option.rec ⟨candidate, rfl, Nat.le_refl _⟩
    (fun current =>
      ⟨Proposal.prefer rank candidate current, rfl,
        Proposal.preferRank_le_candidate rank candidate current⟩) holding

/-- The receiver just proposed to immediately satisfies the history bound. -/
theorem advance_new_bound (preferences : Preferences n) (state : State n)
    (proposer receiver : Fin n) :
    ∃ current, (advance preferences state proposer receiver).holding receiver = some current ∧
      (preferences.receiverRank receiver current).val ≤
        (preferences.receiverRank receiver proposer).val :=
  Exists.elim
    (offer_candidate_bound (preferences.receiverRank receiver) proposer (state.holding receiver))
    fun winner result => ⟨winner, (ite_eq_left rfl).trans result.1, result.2⟩

/-- The incremented proposer's new rank interval adds exactly this receiver. -/
theorem history_advance_proposer (preferences : Preferences n) (state : State n)
    (history : History preferences state) (proposer receiver : Fin n)
    (offeredRank : (preferences.proposerRank proposer receiver).val = state.nextRank proposer)
    (queried : Fin n)
    (tried : (preferences.proposerRank proposer queried).val < state.nextRank proposer + 1) :
    ∃ current, (advance preferences state proposer receiver).holding queried = some current ∧
      (preferences.receiverRank queried current).val ≤
        (preferences.receiverRank queried proposer).val :=
  if before : (preferences.proposerRank proposer queried).val < state.nextRank proposer then
    history_old_advance preferences state history proposer receiver proposer queried before
  else
    let sameRank : preferences.proposerRank proposer queried =
        preferences.proposerRank proposer receiver :=
      Fin.ext
        ((Nat.le_antisymm (Nat.le_of_lt_succ tried) (Nat.le_of_not_gt before)).trans
          offeredRank.symm)
    let sameReceiver := preferences.proposerRank_injective proposer sameRank
    Eq.mpr
      (congrArg (fun target =>
        ∃ current, (advance preferences state proposer receiver).holding target = some current ∧
          (preferences.receiverRank target current).val ≤
            (preferences.receiverRank target proposer).val) sameReceiver)
      (advance_new_bound preferences state proposer receiver)

/-- A proposal at the next untried rank preserves the complete history invariant. -/
theorem history_advance (preferences : Preferences n) (state : State n)
    (history : History preferences state) (proposer receiver : Fin n)
    (offeredRank : (preferences.proposerRank proposer receiver).val = state.nextRank proposer) :
    History preferences (advance preferences state proposer receiver) :=
  fun queriedProposer queriedReceiver tried =>
    if same : queriedProposer = proposer then
      let nextEquality : (advance preferences state proposer receiver).nextRank queriedProposer =
          state.nextRank queriedProposer + 1 := ite_eq_left same
      let changed : (preferences.proposerRank queriedProposer queriedReceiver).val <
          state.nextRank queriedProposer + 1 := nextEquality ▸ tried
      Eq.mpr
        (congrArg (fun target =>
          ∃ current, (advance preferences state proposer receiver).holding queriedReceiver =
              some current ∧
            (preferences.receiverRank queriedReceiver current).val ≤
              (preferences.receiverRank queriedReceiver target).val) same)
        (history_advance_proposer preferences state history proposer receiver offeredRank
          queriedReceiver (same ▸ changed))
    else
      let nextEquality : (advance preferences state proposer receiver).nextRank queriedProposer =
          state.nextRank queriedProposer := ite_eq_right same
      history_old_advance preferences state history proposer receiver queriedProposer
        queriedReceiver (nextEquality ▸ tried)

/-- A free proposer cannot have tried every receiver in a consistent history. -/
theorem free_nextRank_lt (preferences : Preferences n) (state : State n)
    (history : History preferences state)
    (consistent : ∀ r₁ r₂ proposer,
      state.holding r₁ = some proposer → state.holding r₂ = some proposer → r₁ = r₂)
    (proposer : Fin n) (free : ∀ receiver, state.holding receiver ≠ some proposer) :
    state.nextRank proposer < n :=
  Nat.lt_of_not_ge fun exhausted =>
    Exists.elim (existsEmptyReceiverOfFree state.holding consistent proposer free)
      fun receiver empty =>
        Exists.elim
          (history proposer receiver
            (Nat.lt_of_lt_of_le (preferences.proposerRank proposer receiver).isLt exhausted))
          fun current occupied =>
            Option.some_ne_none current (occupied.1.symm.trans empty)

end TNDLib.Matching.Algorithm
