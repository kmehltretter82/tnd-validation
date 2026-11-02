import TNDLib

/-!
Mission L06 open task: the left argument is bounded above by the Lorenzen lattice join.
-/

namespace TNDTask

/-- Every natural number `a` is ordered below `join a b`. -/
theorem lorenzenLeJoinLeft (a b : Nat) : TNDLib.Lorenzen.LOrder a (TNDLib.Lorenzen.join a b) := by
  sorry

end TNDTask
