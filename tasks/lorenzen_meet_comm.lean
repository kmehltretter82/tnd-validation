import TNDLib

/-!
Mission L06 open task: commutativity of the Lorenzen lattice meet on natural numbers.
-/

namespace TNDTask

/-- The lattice meet on natural numbers is commutative. -/
theorem lorenzenMeetComm (a b : Nat) : TNDLib.Lorenzen.meet a b = TNDLib.Lorenzen.meet b a := by
  sorry

end TNDTask
