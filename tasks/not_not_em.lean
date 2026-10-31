import TNDLib

namespace TNDTask

theorem notNotEm (p : Prop) : ¬¬(p ∨ ¬p) :=
  fun h => h (Or.inr (fun hp => h (Or.inl hp)))

end TNDTask
