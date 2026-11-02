import TNDLib

/-!
Mission H01 open task: unfold the pointwise specification of the Cantor diagonal stream.
-/

namespace TNDTask

/-- At index `n`, the diagonal stream equals the flipped diagonal entry `enum n n`. -/
theorem cantorDiagonalSpec (enum : Nat → Nat → Bool) (n : Nat) :
    TNDLib.Cantor.diagonal enum n = TNDLib.Cantor.flip (enum n n) := by
  sorry

end TNDTask
