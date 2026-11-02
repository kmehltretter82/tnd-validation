import Init

/-! Lorenzen-style constructive lattice-ordered natural numbers with explicit meet, join, and relative primality. -/

namespace TNDLib.Lorenzen

/-- Constructive order relation on natural numbers. -/
def LOrder (a b : Nat) : Prop :=
  a ≤ b

/-- Constructive lattice meet (minimum) on natural numbers. -/
def meet (a b : Nat) : Nat :=
  if a ≤ b then a else b

/-- Constructive lattice join (maximum) on natural numbers. -/
def join (a b : Nat) : Nat :=
  if a ≤ b then b else a

/-- Constructive relative primality in the lattice order with respect to `0`. -/
def RelPrime (a b : Nat) : Prop :=
  ∀ x : Nat, LOrder x a → LOrder x b → LOrder x 0

/-- Left additive cancellation for the constructive order. -/
theorem orderCancelLeft (c a b : Nat) : LOrder (c + a) (c + b) → LOrder a b :=
  fun h => Nat.le_of_add_le_add_left h

/-- Transport an order bound along an equality on the left operand. -/
theorem lorder_of_eq_left (m a b : Nat) (hm : m = a) (h : LOrder a b) : LOrder m b :=
  Eq.rec (motive := fun k _ => LOrder k b) h (Eq.symm hm)

/-- Transport an order bound along an equality on the right operand. -/
theorem lorder_of_eq_right (a m b : Nat) (hm : m = b) (h : LOrder a b) : LOrder a m :=
  Eq.rec (motive := fun k _ => LOrder a k) h (Eq.symm hm)

/-- The meet of `a` and `b` is bounded above by `a`. -/
theorem meet_le_left (a b : Nat) : LOrder (meet a b) a :=
  if h : a ≤ b then
    lorder_of_eq_left (meet a b) a a (ite_eq_left h) (Nat.le_refl a)
  else
    lorder_of_eq_left (meet a b) b a (ite_eq_right h) (Nat.le_of_not_le h)

/-- The meet of `a` and `b` is bounded above by `b`. -/
theorem meet_le_right (a b : Nat) : LOrder (meet a b) b :=
  if h : a ≤ b then
    lorder_of_eq_left (meet a b) a b (ite_eq_left h) h
  else
    lorder_of_eq_left (meet a b) b b (ite_eq_right h) (Nat.le_refl b)

/-- Any common lower bound of `a` and `b` is bounded above by `meet a b`. -/
theorem le_meet (x a b : Nat) : LOrder x a → LOrder x b → LOrder x (meet a b) :=
  fun hxa hxb =>
    if h : a ≤ b then
      lorder_of_eq_right x (meet a b) a (ite_eq_left h) hxa
    else
      lorder_of_eq_right x (meet a b) b (ite_eq_right h) hxb

end TNDLib.Lorenzen
