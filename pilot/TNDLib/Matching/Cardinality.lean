import TNDLib.Matching.Rank

/-! Finite cardinality consequences for consistent tentative holdings. -/

namespace TNDLib.Matching

/-- If some proposer is free, consistency forces an empty receiver on equally
sized sides. No decidability or existence of a final matching is assumed. -/
theorem existsEmptyReceiverOfFree (holdings : Fin n → Option (Fin n))
    (consistent : ∀ r₁ r₂ proposer,
      holdings r₁ = some proposer → holdings r₂ = some proposer → r₁ = r₂)
    (proposer : Fin n) (free : ∀ receiver, holdings receiver ≠ some proposer) :
    ∃ receiver, holdings receiver = none :=
  if found : (Finite.enumerate n).any (fun receiver => decide (holdings receiver = none)) = true then
    Exists.elim (List.any_eq_true.mp found) fun receiver witness =>
      ⟨receiver, of_decide_eq_true witness.2⟩
  else
    let occupied : ∀ receiver, holdings receiver ≠ none := fun receiver empty =>
      found (List.any_eq_true.mpr
        ⟨receiver, Finite.memEnumerate receiver, decide_eq_true empty⟩)
    let assigned : Fin n → Fin n := fun receiver => (holdings receiver).getD proposer
    let assigned_spec : ∀ receiver, holdings receiver = some (assigned receiver) :=
      fun receiver => (Option.getD_of_ne_none (occupied receiver) proposer).symm
    let injective : ∀ {r₁ r₂}, assigned r₁ = assigned r₂ → r₁ = r₂ :=
      fun {r₁ r₂} equality =>
        consistent r₁ r₂ (assigned r₁) (assigned_spec r₁)
          ((assigned_spec r₂).trans (congrArg some equality.symm))
    Exists.elim (surjectiveOfInjective assigned injective proposer) fun receiver equality =>
      False.elim (free receiver ((assigned_spec receiver).trans (congrArg some equality)))

/-- Search the explicit finite receiver set for an unoccupied receiver. -/
def findEmptyReceiver (holdings : Fin n → Option (Fin n)) : Option (Fin n) :=
  (Finite.enumerate n).find? fun receiver => decide (holdings receiver = none)

/-- Exhausting the finite search means every receiver is occupied. -/
theorem findEmptyReceiver_none_iff (holdings : Fin n → Option (Fin n)) :
    findEmptyReceiver holdings = none ↔ ∀ receiver, holdings receiver ≠ none :=
  ⟨fun exhausted receiver empty =>
      (List.find?_eq_none.mp exhausted receiver (Finite.memEnumerate receiver))
        (decide_eq_true empty),
    fun occupied => List.find?_eq_none.mpr fun receiver _ found =>
      occupied receiver (of_decide_eq_true found)⟩

/-- A found receiver really is unoccupied. -/
theorem findEmptyReceiver_some (holdings : Fin n → Option (Fin n)) (receiver : Fin n)
    (found : findEmptyReceiver holdings = some receiver) : holdings receiver = none :=
  of_decide_eq_true
    (List.find?_some (p := fun r => decide (holdings r = none)) found)

/-- Consistency and a free proposer guarantee that vacancy search succeeds. -/
theorem findEmptyReceiver_ne_none_of_free (holdings : Fin n → Option (Fin n))
    (consistent : ∀ r₁ r₂ proposer,
      holdings r₁ = some proposer → holdings r₂ = some proposer → r₁ = r₂)
    (proposer : Fin n) (free : ∀ receiver, holdings receiver ≠ some proposer) :
    findEmptyReceiver holdings ≠ none :=
  fun exhausted =>
    Exists.elim (existsEmptyReceiverOfFree holdings consistent proposer free)
      fun receiver empty => (findEmptyReceiver_none_iff holdings).mp exhausted receiver empty

end TNDLib.Matching
