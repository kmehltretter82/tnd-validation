import TNDLib

namespace TNDTask

theorem cantorDiscrepancyNe (f g : Nat → Bool) (n : Nat) :
    TNDLib.Cantor.DiscrepancyAt f g n → (f n = g n) → False :=
  fun h1 h2 => TNDLib.Cantor.flip_ne_self (g n) (Eq.trans (Eq.symm h1) h2)

end TNDTask
