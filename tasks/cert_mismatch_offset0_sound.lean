import TNDLib

/-!
Mission M01 open task: an offset-0 character mismatch refutes a length-2 pattern match.
-/

namespace TNDTask

/-- A mismatch at offset `0` refutes `MatchAt2 text p0 p1 pos`. -/
theorem certMismatchOffset0Sound (text : Nat → Bool) (p0 p1 : Bool) (pos : Nat) :
    (text pos = p0 → False) → TNDLib.Certifying.MatchAt2 text p0 p1 pos → False := by
  sorry

end TNDTask
