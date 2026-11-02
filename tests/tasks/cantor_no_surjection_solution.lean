import TNDLib

namespace TNDTask

theorem cantorNoSurjection (enum : Nat → Nat → Bool) (n : Nat) :
    (enum n = TNDLib.Cantor.diagonal enum) → False :=
  fun h => TNDLib.Cantor.diagonal_differ_at enum n (Eq.symm (congrFun h n))

end TNDTask
