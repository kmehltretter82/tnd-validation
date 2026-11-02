import Init

/-! Constructive diagonalization on binary streams (`Nat → Bool`) with explicit discrepancy witnesses. -/

namespace TNDLib.Cantor

/-- Negate a boolean value constructively. -/
def flip (b : Bool) : Bool :=
  Bool.casesOn b true false

/-- Construct the diagonal stream from a table of binary streams by flipping the diagonal entry. -/
def diagonal (enum : Nat → Nat → Bool) (n : Nat) : Bool :=
  flip (enum n n)

/-- Witness that two binary streams differ at index `n` because `f n` is the flipped value of `g n`. -/
def DiscrepancyAt (f g : Nat → Bool) (n : Nat) : Prop :=
  f n = flip (g n)

/-- Witness that a candidate binary stream differs from the `n`-th enumerated stream at index `n`. -/
def DiscrepancyWitness (enum : Nat → Nat → Bool) (candidate : Nat → Bool) (n : Nat) : Prop :=
  DiscrepancyAt candidate (enum n) n

/-- No boolean equals its flipped value. -/
theorem flip_ne_self (b : Bool) : (flip b = b) → False :=
  Bool.rec (motive := fun x => (flip x = x) → False)
    (fun h => Bool.noConfusion h)
    (fun h => Bool.noConfusion h)
    b

/-- The diagonal stream constructively satisfies the discrepancy witness at every index `n`. -/
theorem diagonalDiscrepancy (enum : Nat → Nat → Bool) (n : Nat) :
    DiscrepancyWitness enum (diagonal enum) n :=
  rfl

/-- The diagonal stream differs at index `n` from the `n`-th stream of the enumeration. -/
theorem diagonal_differ_at (enum : Nat → Nat → Bool) (n : Nat) :
    (diagonal enum n = enum n n) → False :=
  fun h => flip_ne_self (enum n n) h

end TNDLib.Cantor
