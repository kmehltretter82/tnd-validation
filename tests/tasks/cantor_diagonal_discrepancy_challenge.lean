import TNDLib

/-!
Mission H01 calibration challenge: Cantor diagonal stream discrepancy witness.
-/

namespace TNDTask

/-- The diagonal stream constructively satisfies the discrepancy witness at every index `n`. -/
theorem cantorDiagonalDiscrepancy (enum : Nat → Nat → Bool) (n : Nat) :
    TNDLib.Cantor.DiscrepancyWitness enum (TNDLib.Cantor.diagonal enum) n := by
  sorry

end TNDTask
