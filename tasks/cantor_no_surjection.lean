import TNDLib

/-!
Mission H01 open task: no row of an enumeration of binary streams equals the diagonal stream.
-/

namespace TNDTask

/-- No enumerated stream `enum n` is equal to `diagonal enum`. -/
theorem cantorNoSurjection (enum : Nat → Nat → Bool) (n : Nat) :
    (enum n = TNDLib.Cantor.diagonal enum) → False := by
  sorry

end TNDTask
