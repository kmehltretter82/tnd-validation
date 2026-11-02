import Init

/-!
Package H08: Perron (1951/1952), proof of Moessner's theorem via prefix sums
and Pascal binomial coefficients.
-/

namespace TNDPackage.H08PerronMoessner

/-- Partial sum `f 0 + f 1 + ... + f (n - 1)` of a sequence `f : Nat → Nat`. -/
def prefixSum (f : Nat → Nat) : Nat → Nat
  | 0 => 0
  | n + 1 => prefixSum f n + f n

/-- The `k`-th odd positive integer `2 * k + 1` remaining after the rank-2 Moessner sieve. -/
def oddTerm (k : Nat) : Nat :=
  2 * k + 1

/-- Standard recursive definition of the binomial coefficient `C(n, k)`. -/
def binom : Nat → Nat → Nat
  | 0, 0 => 1
  | 0, _ + 1 => 0
  | _ + 1, 0 => 1
  | n + 1, k + 1 => binom n k + binom n (k + 1)

/-- Pascal's additive recurrence `C(n + 1, k + 1) = C(n, k) + C(n, k + 1)`. -/
theorem pascal_step (n k : Nat) :
    binom (n + 1) (k + 1) = binom n k + binom n (k + 1) :=
  rfl

/-- Rank-2 Moessner step recurrence for the prefix sums of odd integers. -/
theorem moessner_rank2_step (n : Nat) :
    prefixSum oddTerm (n + 1) = prefixSum oddTerm n + (2 * n + 1) :=
  rfl

/-- Target specification for the rank-2 Moessner theorem: `prefixSum oddTerm n = n * n`. -/
def MoessnerRank2Squares : Prop :=
  ∀ n : Nat, prefixSum oddTerm n = n * n

end TNDPackage.H08PerronMoessner
