import TNDLib

namespace TNDTask

theorem selectHeadWitness {n : Nat} (p : Fin n → Prop) [DecidablePred p] (h : ∃ i, p i) :
    ∃ i, (TNDLib.Finite.select n p).head? = some i ∧ p i :=
  Exists.elim h (fun i hi =>
    Exists.elim (List.exists_cons_of_ne_nil
        (List.ne_nil_of_mem ((TNDLib.Finite.memSelect p i).mpr hi))) (fun x hx =>
      Exists.elim hx (fun _ he =>
        Exists.intro x (And.intro (Eq.trans (congrArg List.head? he) rfl)
          ((TNDLib.Finite.memSelect p x).mp
            (Eq.mpr (congrArg (fun l => x ∈ l) he) List.mem_cons_self))))))

end TNDTask
