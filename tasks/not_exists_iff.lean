import TNDLib

/-!
Approved starter task. This placeholder is a task statement, not part of the
certified TNDLib exports.
-/

universe u

namespace TNDTask

/-- No witness exists exactly when every candidate fails. -/
theorem notExistsIff {α : Type u} (p : α → Prop) : (¬∃ x, p x) ↔ ∀ x, ¬p x := by
  sorry

end TNDTask
