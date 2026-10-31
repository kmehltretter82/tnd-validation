import TNDLib

/-!
Approved starter task. This placeholder is a task statement, not part of the
certified TNDLib exports.
-/

namespace TNDTask

/-- The first hit of the library's bounded search is a genuine witness. -/
theorem selectHeadWitness {n : Nat} (p : Fin n → Prop) [DecidablePred p] (h : ∃ i, p i) :
    ∃ i, (TNDLib.Finite.select n p).head? = some i ∧ p i := by
  sorry

end TNDTask
