import Init

/-! A receiver retains the better of a new proposal and its current partner. -/

namespace TNDLib.Matching.Proposal

/-- Smaller ranks are preferred. Equality retains the existing partner. -/
def prefer (rank : Fin n → Fin n) (candidate current : Fin n) : Fin n :=
  ite ((rank candidate).val < (rank current).val) candidate current

/-- The transition either strictly improves the receiver's rank or retains it. -/
theorem preferSpec (rank : Fin n → Fin n) (candidate current : Fin n) :
    (prefer rank candidate current = candidate ∧
      (rank candidate).val < (rank current).val) ∨
    (prefer rank candidate current = current ∧
      ¬ (rank candidate).val < (rank current).val) :=
  Decidable.byCases
    (fun h => Or.inl ⟨ite_eq_left h, h⟩)
    (fun h => Or.inr ⟨ite_eq_right h, h⟩)

/-- A receiver's rank never worsens when it considers a proposal. -/
theorem preferRank_le_current (rank : Fin n → Fin n) (candidate current : Fin n) :
    (rank (prefer rank candidate current)).val ≤ (rank current).val :=
  Or.elim (preferSpec rank candidate current)
    (fun h => Eq.mpr (congrArg (fun winner => (rank winner).val ≤ (rank current).val) h.1)
      (Nat.le_of_lt h.2))
    (fun h => Eq.mpr (congrArg (fun winner => (rank winner).val ≤ (rank current).val) h.1)
      (Nat.le_refl (rank current).val))

/-- The retained partner is at least as good as the new candidate. -/
theorem preferRank_le_candidate (rank : Fin n → Fin n) (candidate current : Fin n) :
    (rank (prefer rank candidate current)).val ≤ (rank candidate).val :=
  Or.elim (preferSpec rank candidate current)
    (fun h => Eq.mpr (congrArg (fun winner => (rank winner).val ≤ (rank candidate).val) h.1)
      (Nat.le_refl (rank candidate).val))
    (fun h => Eq.mpr (congrArg (fun winner => (rank winner).val ≤ (rank candidate).val) h.1)
      (Nat.le_of_not_gt h.2))

/-- Tentatively hold a first proposal, or compare it with the existing partner. -/
def offer (rank : Fin n → Fin n) (candidate : Fin n) (holding : Option (Fin n)) :
    Option (Fin n) :=
  Option.elim holding (some candidate) (fun current => some (prefer rank candidate current))

/-- A receiver never becomes empty after receiving a proposal. -/
theorem offer_nonempty (rank : Fin n → Fin n) (candidate : Fin n)
    (holding : Option (Fin n)) : ∃ winner, offer rank candidate holding = some winner :=
  Option.rec ⟨candidate, rfl⟩ (fun current => ⟨prefer rank candidate current, rfl⟩) holding

/-- A previously held proposer is replaced only by an equally good or better one. -/
theorem offer_preserves_rank (rank : Fin n → Fin n) (candidate current : Fin n) :
    ∃ winner, offer rank candidate (some current) = some winner ∧
      (rank winner).val ≤ (rank current).val ∧
      (rank winner).val ≤ (rank candidate).val :=
  ⟨prefer rank candidate current, rfl,
    preferRank_le_current rank candidate current,
    preferRank_le_candidate rank candidate current⟩

end TNDLib.Matching.Proposal
