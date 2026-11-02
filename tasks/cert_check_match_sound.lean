import TNDLib

/-!
Mission M01 open task: soundness of the executable boolean matcher `checkMatchAt2`.
-/

namespace TNDTask

/-- When `checkMatchAt2` returns `true`, the propositional match specification `MatchAt2` holds. -/
theorem certCheckMatchSound (text : Nat → Bool) (p0 p1 : Bool) (pos : Nat) :
    TNDLib.Certifying.checkMatchAt2 text p0 p1 pos = true →
      TNDLib.Certifying.MatchAt2 text p0 p1 pos := by
  sorry

end TNDTask
