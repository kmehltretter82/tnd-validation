import TNDLib

/-!
Mission M01 open task: pair the Cantor stream discrepancy certificate with its pointwise falsifier.
-/

namespace TNDTask

/-- The diagonal stream yields both a stream discrepancy certificate and a pointwise inequality at `n`. -/
theorem certCantorFalsifier (table : Nat → Nat → Bool) (n : Nat) :
    TNDLib.Certifying.StreamDiscrepancyCert table (TNDLib.Cantor.diagonal table) n ∧
      ((TNDLib.Cantor.diagonal table n = table n n) → False) := by
  sorry

end TNDTask
