import Init

/-! Predicate logic and explicit witness data. -/

namespace TNDLib.Predicate

/-- Negating an existential gives pointwise negations constructively. -/
theorem notExists (p : α → Prop) : (¬∃ x, p x) ↔ ∀ x, ¬p x :=
  ⟨fun h x hx => h ⟨x, hx⟩, fun h ⟨x, hx⟩ => h x hx⟩

/-- A universal quantifier preserves conjunction. -/
theorem forallAnd (p q : α → Prop) :
    (∀ x, p x ∧ q x) ↔ (∀ x, p x) ∧ (∀ x, q x) :=
  ⟨fun h => ⟨fun x => (h x).1, fun x => (h x).2⟩,
   fun h x => ⟨h.1 x, h.2 x⟩⟩

/-- An existential distributes over disjunction without choosing an arbitrary witness. -/
theorem existsOr (p q : α → Prop) :
    (∃ x, p x ∨ q x) ↔ (∃ x, p x) ∨ (∃ x, q x) :=
  ⟨fun ⟨x, h⟩ => h.elim (fun hp => Or.inl ⟨x, hp⟩) (fun hq => Or.inr ⟨x, hq⟩),
   fun h => h.elim (fun ⟨x, hp⟩ => ⟨x, Or.inl hp⟩) (fun ⟨x, hq⟩ => ⟨x, Or.inr hq⟩)⟩

/-- Assemble a function from witness-producing data, not from existential propositions. -/
def assembleWitnesses (r : α → β → Prop) (w : (x : α) → { y : β // r x y }) :
    { f : α → β // ∀ x, r x (f x) } :=
  ⟨fun x => (w x).val, fun x => (w x).property⟩

end TNDLib.Predicate
