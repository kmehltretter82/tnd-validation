import TNDLib

universe u

namespace TNDTask

theorem notExistsIff {α : Type u} (p : α → Prop) : (¬∃ x, p x) ↔ ∀ x, ¬p x :=
  Iff.intro (fun h x hx => h (Exists.intro x hx)) (fun h e => Exists.elim e h)

end TNDTask
