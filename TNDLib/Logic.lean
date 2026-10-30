import Init

/-! Elementary intuitionistic logic, with decidability assumptions kept explicit. -/

namespace TNDLib.Logic

/-- Conjunction distributes over a disjunction without deciding either side. -/
theorem andOrDistribute (P Q R : Prop) :
    (P ∧ (Q ∨ R)) ↔ (P ∧ Q) ∨ (P ∧ R) :=
  ⟨fun h => h.2.elim (fun q => Or.inl ⟨h.1, q⟩) (fun r => Or.inr ⟨h.1, r⟩),
   fun h => h.elim (fun pq => ⟨pq.1, Or.inl pq.2⟩) (fun pr => ⟨pr.1, Or.inr pr.2⟩)⟩

/-- The constructive De Morgan law for a disjunction. -/
theorem notOr (P Q : Prop) : ¬(P ∨ Q) ↔ (¬P ∧ ¬Q) :=
  ⟨fun h => ⟨fun p => h (Or.inl p), fun q => h (Or.inr q)⟩,
   fun h pq => pq.elim h.1 h.2⟩

/-- Excluded middle for a proposition supplied with an explicit decision procedure. -/
theorem decidableExcludedMiddle (P : Prop) [d : Decidable P] : P ∨ ¬P :=
  match d with
  | .isTrue h => Or.inl h
  | .isFalse h => Or.inr h

/-- The double negation of excluded middle needs no decision procedure. -/
theorem doubleNegatedExcludedMiddle (P : Prop) : ¬¬(P ∨ ¬P) :=
  fun h => h (Or.inr (fun p => h (Or.inl p)))

/-- Double-negation elimination uses the supplied decision procedure. -/
theorem decidableDoubleNegation (P : Prop) [d : Decidable P] : ¬¬P → P :=
  match d with
  | .isTrue h => fun _ => h
  | .isFalse h => fun hn => False.elim (hn h)

end TNDLib.Logic

