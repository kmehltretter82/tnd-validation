import TNDLib.Cantor

/-! Certifying algorithms: length-2 pattern matching certificates and stream discrepancy certificates. -/

namespace TNDLib.Certifying

/-- Propositional specification of a length-2 boolean pattern `(p0, p1)` matching `text` at `pos`. -/
def MatchAt2 (text : Nat → Bool) (p0 p1 : Bool) (pos : Nat) : Prop :=
  text pos = p0 ∧ text (pos + 1) = p1

/-- Executable boolean checker for a length-2 pattern match at `pos`. -/
def checkMatchAt2 (text : Nat → Bool) (p0 p1 : Bool) (pos : Nat) : Bool :=
  if text pos = p0 then
    if text (pos + 1) = p1 then true else false
  else
    false

/-- Explicit mismatch certificate at offset `0` or `1` refuting a length-2 match at `pos`. -/
def MismatchWitness2 (text : Nat → Bool) (p0 p1 : Bool) (pos : Nat) (offset : Nat) : Prop :=
  (offset = 0 ∧ (text pos = p0 → False)) ∨ (offset = 1 ∧ (text (pos + 1) = p1 → False))

/-- Certificate that `candidate` differs from row `n` of `table` at diagonal position `n`. -/
def StreamDiscrepancyCert (table : Nat → Nat → Bool) (candidate : Nat → Bool) (n : Nat) : Prop :=
  TNDLib.Cantor.DiscrepancyWitness table candidate n

/-- Cantor's diagonal stream produces a valid discrepancy certificate at every row `n`. -/
theorem diagonalStreamCert (table : Nat → Nat → Bool) (n : Nat) :
    StreamDiscrepancyCert table (TNDLib.Cantor.diagonal table) n :=
  TNDLib.Cantor.diagonalDiscrepancy table n

end TNDLib.Certifying
