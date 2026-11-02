import TNDLib

namespace TNDTask

theorem certMismatchOffset0Sound (text : Nat → Bool) (p0 p1 : Bool) (pos : Nat) :
    (text pos = p0 → False) → TNDLib.Certifying.MatchAt2 text p0 p1 pos → False :=
  fun hne hm => hne hm.1

end TNDTask
