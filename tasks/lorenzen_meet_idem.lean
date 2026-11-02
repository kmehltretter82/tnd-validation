import TNDLib

/-!
Mission L06 open task: idempotence of the Lorenzen lattice meet on natural numbers.
-/

namespace TNDTask

/-- The lattice meet of any natural number with itself is that number. -/
theorem lorenzenMeetIdem (a : Nat) : TNDLib.Lorenzen.meet a a = a := by
  sorry

end TNDTask
