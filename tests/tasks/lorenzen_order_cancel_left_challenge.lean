import TNDLib

/-!
Mission L06 calibration challenge: left additive cancellation for the Lorenzen lattice order.
-/

namespace TNDTask

/-- Left additive cancellation in `TNDLib.Lorenzen.LOrder`. -/
theorem lorenzenOrderCancelLeft (c a b : Nat) :
    TNDLib.Lorenzen.LOrder (c + a) (c + b) → TNDLib.Lorenzen.LOrder a b := by
  sorry

end TNDTask
