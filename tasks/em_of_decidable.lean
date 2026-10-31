import TNDLib

/-!
Approved starter task. This placeholder is a task statement, not part of the
certified TNDLib exports.
-/

namespace TNDTask

/-- A decision procedure for a proposition yields excluded middle for it. -/
theorem emOfDecidable (p : Prop) [d : Decidable p] : p ∨ ¬p := by
  sorry

end TNDTask
