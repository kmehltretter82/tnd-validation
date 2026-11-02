import Init

/-!
Package L03: Ackermann (1927/1928), original 3-variable hierarchy `φ(a, b, n)`
and initial-value helper `α(a, n)`.
-/

namespace TNDPackage.L03Ackermann

/-- Ackermann's initial-value helper `α(a, n)`: `0` at `n = 0`, `1` at `n = 1`, and `a` for `n ≥ 2`. -/
def ackAlpha (a n : Nat) : Nat :=
  Nat.casesOn n 0 (fun m => Nat.casesOn m 1 (fun _ => a))

/-- Ackermann's original 1928 3-variable hierarchy `φ(a, b, n)` defined via structural `Nat.rec`. -/
def ackPhi (a b n : Nat) : Nat :=
  (Nat.rec (motive := fun _ => Nat → Nat)
    (fun x => a + x)
    (fun k prev => fun x => Nat.rec (motive := fun _ => Nat) (ackAlpha a k) (fun _ acc => prev acc) x)
    n) b

/-- Level-0 identity: `φ(a, b, 0) = a + b`. -/
theorem ackPhi_level0 (a b : Nat) : ackPhi a b 0 = a + b :=
  rfl

/-- Level-1 base value: `φ(a, 0, 1) = 0`. -/
theorem ackPhi_level1_zero (a : Nat) : ackPhi a 0 1 = 0 :=
  rfl

/-- Level-2 base value: `φ(a, 0, 2) = 1`. -/
theorem ackPhi_level2_zero (a : Nat) : ackPhi a 0 2 = 1 :=
  rfl

/-- Level-3 base value: `φ(a, 0, 3) = a`. -/
theorem ackPhi_level3_zero (a : Nat) : ackPhi a 0 3 = a :=
  rfl

/-- Target specification for level 1: `φ(a, b, 1) = a * b` for all `a, b : Nat`. -/
def AckLevel1Spec : Prop :=
  ∀ a b : Nat, ackPhi a b 1 = a * b

end TNDPackage.L03Ackermann
