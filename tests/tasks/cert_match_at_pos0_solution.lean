import TNDLib

namespace TNDTask

theorem certMatchAtPos0 (text : Nat → Bool) (p0 p1 : Bool) (pos : Nat) :
    TNDLib.Certifying.MatchAt2 text p0 p1 pos → text pos = p0 :=
  fun h => h.1

end TNDTask
