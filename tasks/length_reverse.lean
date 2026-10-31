import TNDLib

/-!
Approved starter task. This placeholder is a task statement, not part of the
certified TNDLib exports.
-/

universe u

namespace TNDTask

/-- Reversing a list preserves its length. -/
theorem lengthReverse {α : Type u} (l : List α) : l.reverse.length = l.length := by
  sorry

end TNDTask
