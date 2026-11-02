import TNDLib

namespace TNDTask

theorem cantorDiagonalSpec (enum : Nat → Nat → Bool) (n : Nat) :
    TNDLib.Cantor.diagonal enum n = TNDLib.Cantor.flip (enum n n) :=
  rfl

end TNDTask
