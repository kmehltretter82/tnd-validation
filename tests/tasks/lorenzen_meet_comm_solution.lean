import TNDLib

namespace TNDTask

theorem lorenzenMeetComm (a b : Nat) : TNDLib.Lorenzen.meet a b = TNDLib.Lorenzen.meet b a :=
  if hab : a ≤ b then
    if hba : b ≤ a then
      Eq.trans (ite_eq_left hab) (Eq.trans (Nat.le_antisymm hab hba) (Eq.symm (ite_eq_left hba)))
    else
      Eq.trans (ite_eq_left hab) (Eq.symm (ite_eq_right hba))
  else
    Eq.trans (ite_eq_right hab) (Eq.symm (ite_eq_left (Nat.le_of_not_le hab)))

end TNDTask
