import TNDLib

namespace TNDTask

theorem lorenzenMeetIdem (a : Nat) : TNDLib.Lorenzen.meet a a = a :=
  ite_eq_left (Nat.le_refl a)

end TNDTask
