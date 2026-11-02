import TNDLib

/-!
Mission L06 open task: symmetry of Lorenzen relative primality.
-/

namespace TNDTask

/-- Relative primality in the Lorenzen lattice order is symmetric. -/
theorem lorenzenRelPrimeSymm (a b : Nat) :
    TNDLib.Lorenzen.RelPrime a b → TNDLib.Lorenzen.RelPrime b a := by
  sorry

end TNDTask
