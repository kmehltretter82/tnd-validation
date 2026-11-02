import TNDLib

/-!
Mission M01 open task: project the second-character equality from a length-2 match specification.
-/

namespace TNDTask

/-- A length-2 pattern match at `pos` implies that `text (pos + 1)` equals `p1`. -/
theorem certMatchAtPos1 (text : Nat → Bool) (p0 p1 : Bool) (pos : Nat) :
    TNDLib.Certifying.MatchAt2 text p0 p1 pos → text (pos + 1) = p1 := by
  sorry

end TNDTask
