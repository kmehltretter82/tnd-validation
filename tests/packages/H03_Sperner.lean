import Init

/-!
Package H03: Sperner (1927/1928), subset antichains and middle binomial coefficient bound.
-/

namespace TNDPackage.H03Sperner

/-- Characteristic bitvector representing a subset of `{0, ..., n - 1}`. -/
def BitSubset (n : Nat) : Type :=
  Fin n → Bool

/-- Pointwise subset inclusion `A ⊆ B` on `BitSubset n`. -/
def SubsetLe {n : Nat} (A B : BitSubset n) : Prop :=
  ∀ i : Fin n, A i = true → B i = true

/-- Mutual non-containment (incomparability) of two subsets `A` and `B`. -/
def Incomparable {n : Nat} (A B : BitSubset n) : Prop :=
  (SubsetLe A B → False) ∧ (SubsetLe B A → False)

/-- Pairwise antichain condition on a list of subsets of `Fin n`. -/
def PairwiseAntichain {n : Nat} : List (BitSubset n) → Prop
  | [] => True
  | A :: F => (∀ B : BitSubset n, B ∈ F → Incomparable A B) ∧ PairwiseAntichain F

/-- Middle binomial coefficient `C(n, n / 2)`. -/
def middleBinom (n : Nat) : Nat :=
  Nat.sub
    ((Nat.rec (motive := fun _ => Nat → Nat)
        (fun k => Nat.casesOn k 1 (fun _ => 0))
        (fun _ prev => fun k => Nat.casesOn k 1 (fun k' => prev k' + prev (k' + 1)))
        n) (Nat.div n 2))
    1 + 1

/-- Target specification of Sperner's theorem: every pairwise antichain `F` has length at most `middleBinom n`. -/
def SpernerBoundSpec (n : Nat) : Prop :=
  ∀ F : List (BitSubset n), PairwiseAntichain F → F.length ≤ middleBinom n

/-- Any singleton family `[A]` is a valid pairwise antichain and satisfies `[A].length ≤ middleBinom n`. -/
theorem singleton_antichain_bound {n : Nat} (A : BitSubset n) :
    PairwiseAntichain [A] ∧ [A].length ≤ middleBinom n :=
  ⟨⟨fun _ h => False.elim (List.not_mem_nil h), True.intro⟩,
   Nat.le_add_left 1 _⟩

end TNDPackage.H03Sperner
