import Init

/-! Finite enumeration with explicit, constructive decision procedures. -/

namespace TNDLib.Finite

/-- Enumerate the inhabitants of an explicitly bounded finite type. -/
def enumerate (n : Nat) : List (Fin n) := List.ofFn id

/-- Every bounded index occurs in its explicit enumeration. -/
theorem memEnumerate (i : Fin n) : i ∈ enumerate n :=
  List.mem_ofFn.mpr ⟨i, rfl⟩

/-- The enumeration has exactly the requested number of entries. -/
theorem lengthEnumerate (n : Nat) : (enumerate n).length = n := List.length_ofFn

/-- Enumerate the solutions of a predicate supplied with a decision procedure. -/
def select (n : Nat) (p : Fin n → Prop) [DecidablePred p] : List (Fin n) :=
  (enumerate n).filter (fun i => decide (p i))

/-- Finite filtering returns exactly the indices satisfying the predicate. -/
theorem memSelect (p : Fin n → Prop) [DecidablePred p] (i : Fin n) :
    i ∈ select n p ↔ p i :=
  List.mem_filter.trans
    ⟨fun h => of_decide_eq_true h.2, fun hp => ⟨memEnumerate i, decide_eq_true hp⟩⟩

end TNDLib.Finite
