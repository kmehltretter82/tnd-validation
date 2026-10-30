import Init

/-! A recursive arithmetic construction with its witness specification. -/

namespace TNDLib.Nat

/-- The sum of all natural numbers from one through the input. -/
def sumTo : Nat → Nat
  | 0 => 0
  | n + 1 => sumTo n + (n + 1)

/-- The triangular sum bounds its final summand. -/
theorem leSumTo : (n : Nat) → n ≤ sumTo n
  | 0 => Nat.le_refl 0
  | n + 1 => Nat.le_add_left (n + 1) (sumTo n)

/-- The recurrence exposes an executable step of the sum. -/
theorem sumToSucc (n : Nat) : sumTo (n + 1) = sumTo n + (n + 1) := rfl

/-- Return the triangular sum together with its specification and lower bound. -/
def sumToWitness (n : Nat) : { s : Nat // s = sumTo n ∧ n ≤ s } :=
  ⟨sumTo n, rfl, leSumTo n⟩

end TNDLib.Nat
