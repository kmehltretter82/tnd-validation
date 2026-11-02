import TNDLib

namespace TNDTask

theorem lorenzenOrderCancelLeft (c a b : Nat) :
    TNDLib.Lorenzen.LOrder (c + a) (c + b) → TNDLib.Lorenzen.LOrder a b :=
  fun h => Nat.le_of_add_le_add_left h

end TNDTask
