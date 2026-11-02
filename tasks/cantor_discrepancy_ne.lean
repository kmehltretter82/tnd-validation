import TNDLib

/-!
Mission H01 open task: an explicit discrepancy witness at `n` refutes equality at `n`.
-/

namespace TNDTask

/-- Two binary streams with a discrepancy witness at `n` cannot agree at `n`. -/
theorem cantorDiscrepancyNe (f g : Nat → Bool) (n : Nat) :
    TNDLib.Cantor.DiscrepancyAt f g n → (f n = g n) → False := by
  sorry

end TNDTask
