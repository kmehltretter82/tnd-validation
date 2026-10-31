import TNDLib

namespace TNDTask

theorem emOfDecidable (p : Prop) [d : Decidable p] : p ∨ ¬p :=
  Decidable.em p

end TNDTask
