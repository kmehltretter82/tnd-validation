import TNDLib

namespace TNDTask

theorem certCantorFalsifier (table : Nat → Nat → Bool) (n : Nat) :
    TNDLib.Certifying.StreamDiscrepancyCert table (TNDLib.Cantor.diagonal table) n ∧
      ((TNDLib.Cantor.diagonal table n = table n n) → False) :=
  ⟨TNDLib.Certifying.diagonalStreamCert table n, TNDLib.Cantor.diagonal_differ_at table n⟩

end TNDTask
