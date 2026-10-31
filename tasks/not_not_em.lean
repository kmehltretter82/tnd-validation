import TNDLib

/-!
Approved starter task. This placeholder is a task statement, not part of the
certified TNDLib exports.
-/

namespace TNDTask

/-- Excluded middle cannot be refuted, even without assuming it. -/
theorem notNotEm (p : Prop) : ¬¬(p ∨ ¬p) := by
  sorry

end TNDTask
