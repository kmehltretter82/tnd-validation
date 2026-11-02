import Init

/-!
Package M02: Lehmann, Sanders, and Walzer (2023/2025), ShockHash two-choice hashing
and pseudoforest 1-orientation certificates.
-/

namespace TNDPackage.M02ShockHash

/-- A finite two-choice hash table specification mapping each of `n` keys to two candidate slots in `Fin m`. -/
structure TwoChoiceHash (n m : Nat) where
  h0 : Fin n → Fin m
  h1 : Fin n → Fin m

/-- A 1-bit selector vector choosing between `h0` (`false`) and `h1` (`true`) for each key. -/
def SelectorBits (n : Nat) : Type :=
  Fin n → Bool

/-- Evaluates the chosen slot in `Fin m` for key `i` under two-choice hash `H` and selector bits `s`. -/
def selectedSlot {n m : Nat} (H : TwoChoiceHash n m) (s : SelectorBits n) (i : Fin n) : Fin m :=
  if s i = true then H.h1 i else H.h0 i

/-- Collision-free (injective) placement of keys into slots under selector bits `s`. -/
def CollisionFree {n m : Nat} (H : TwoChoiceHash n m) (s : SelectorBits n) : Prop :=
  ∀ i j : Fin n, selectedSlot H s i = selectedSlot H s j → i = j

/-- Pseudoforest 1-orientation certificate bundling selector bits and a reverse slot-owner witness map. -/
structure PseudoforestOrientationCert {n m : Nat} (H : TwoChoiceHash n m) where
  s : SelectorBits n
  slotOwner : Fin m → Option (Fin n)
  owner_correct : ∀ i : Fin n, slotOwner (selectedSlot H s i) = some i

/-- Soundness of a pseudoforest orientation certificate: certified slot selections are collision-free. -/
theorem orientation_cert_implies_collision_free {n m : Nat}
    (H : TwoChoiceHash n m) (cert : PseudoforestOrientationCert H) :
    CollisionFree H cert.s :=
  fun i j h =>
    Option.some.inj
      (Eq.trans
        (Eq.symm (cert.owner_correct i))
        (Eq.trans (congrArg cert.slotOwner h) (cert.owner_correct j)))

/-- Two-key non-collision specialization asserting that two selected slots are distinct. -/
def CollisionFreePair2 {m : Nat} (slot0 slot1 : Fin m) : Prop :=
  (slot0 = slot1) → False

end TNDPackage.M02ShockHash
