import TNDLib

namespace TNDTask

theorem lorenzenLeJoinLeft (a b : Nat) : TNDLib.Lorenzen.LOrder a (TNDLib.Lorenzen.join a b) :=
  if h : a ≤ b then
    TNDLib.Lorenzen.lorder_of_eq_right a (TNDLib.Lorenzen.join a b) b (ite_eq_left h) h
  else
    TNDLib.Lorenzen.lorder_of_eq_right a (TNDLib.Lorenzen.join a b) a (ite_eq_right h) (Nat.le_refl a)

end TNDTask
