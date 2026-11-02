import TNDLib

namespace TNDTask

theorem cantorDiagonalDiscrepancy (enum : Nat → Nat → Bool) (n : Nat) :
    TNDLib.Cantor.DiscrepancyWitness enum (TNDLib.Cantor.diagonal enum) n :=
  rfl

end TNDTask
