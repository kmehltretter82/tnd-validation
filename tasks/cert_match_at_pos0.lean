import TNDLib

/-!
Mission M01 open task: project the first-character equality from a length-2 match specification.
-/

namespace TNDTask

/-- A length-2 pattern match at `pos` implies that `text pos` equals `p0`. -/
theorem certMatchAtPos0 (text : Nat → Bool) (p0 p1 : Bool) (pos : Nat) :
    TNDLib.Certifying.MatchAt2 text p0 p1 pos → text pos = p0 := by
  sorry

end TNDTask
