import TNDLib

namespace TNDTask

theorem certMatchAtPos1 (text : Nat → Bool) (p0 p1 : Bool) (pos : Nat) :
    TNDLib.Certifying.MatchAt2 text p0 p1 pos → text (pos + 1) = p1 :=
  fun h => h.2

end TNDTask
