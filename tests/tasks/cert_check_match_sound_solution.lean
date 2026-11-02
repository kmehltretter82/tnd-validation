import TNDLib

namespace TNDTask

theorem certCheckMatchSound (text : Nat → Bool) (p0 p1 : Bool) (pos : Nat) :
    TNDLib.Certifying.checkMatchAt2 text p0 p1 pos = true →
      TNDLib.Certifying.MatchAt2 text p0 p1 pos :=
  fun h =>
    if h0 : text pos = p0 then
      if h1 : text (pos + 1) = p1 then
        ⟨h0, h1⟩
      else
        Bool.noConfusion (Eq.trans (Eq.symm (Eq.trans (ite_eq_left h0) (ite_eq_right h1))) h)
    else
      Bool.noConfusion (Eq.trans (Eq.symm (ite_eq_right h0)) h)

end TNDTask
