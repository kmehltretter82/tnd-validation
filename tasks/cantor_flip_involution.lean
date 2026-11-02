import TNDLib

/-!
Mission H01 open task: flipping a boolean value twice restores the original boolean.
-/

namespace TNDTask

/-- Flipping a boolean twice is the identity operation. -/
theorem cantorFlipInvolution (b : Bool) : TNDLib.Cantor.flip (TNDLib.Cantor.flip b) = b := by
  sorry

end TNDTask
