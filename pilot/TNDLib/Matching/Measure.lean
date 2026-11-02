import TNDLib.Matching.Algorithm
import TNDLib.Matching.Rank

/-! A finite proposal-count measure for the deferred-acceptance transition. -/

namespace TNDLib.Matching.Algorithm

/-- Sum a pointwise bounded natural-valued map over an explicit list. -/
theorem sumMapLeLengthMul (f : α → Nat) (limit : Nat) :
    ∀ xs : List α, (∀ x, x ∈ xs → f x ≤ limit) →
      (xs.map f).sum ≤ xs.length * limit
  | [], _ => Nat.le_of_eq (Nat.zero_mul limit).symm
  | a :: xs, bounded =>
    calc
      f a + (xs.map f).sum ≤ limit + xs.length * limit :=
        Nat.add_le_add (bounded a List.mem_cons_self)
          (sumMapLeLengthMul f limit xs fun x member =>
            bounded x (List.mem_cons_of_mem a member))
      _ = (a :: xs).length * limit :=
        (Nat.add_comm limit (xs.length * limit)).trans (Nat.succ_mul xs.length limit).symm

/-- The sum of an explicitly zero-valued finite map is zero. -/
theorem sumMapZero : ∀ xs : List α, (xs.map (fun _ => 0 : α → Nat)).sum = 0
  | [] => rfl
  | _ :: xs => (Nat.zero_add _).trans (sumMapZero xs)

/-- Updating an absent index does not change the sum over a list. -/
theorem sumIncrementOfAbsent [DecidableEq α] (f : α → Nat) (target : α) (xs : List α)
    (absent : target ∉ xs) :
    (xs.map (fun x => if x = target then f x + 1 else f x)).sum = (xs.map f).sum :=
  congrArg List.sum
    (List.map_congr_left fun x member =>
      ite_eq_right (fun same : x = target => absent (same ▸ member)))

/-- Incrementing one present index of a duplicate-free list increases its sum by one. -/
theorem sumIncrementOfMem [DecidableEq α] (f : α → Nat) (target : α) :
    ∀ xs : List α, xs.Nodup → target ∈ xs →
      (xs.map (fun x => if x = target then f x + 1 else f x)).sum = (xs.map f).sum + 1
  | [], _, present => False.elim (List.not_mem_nil present)
  | a :: xs, distinct, present =>
    if same : a = target then
      calc
        (if a = target then f a + 1 else f a) +
            (xs.map (fun x => if x = target then f x + 1 else f x)).sum =
            (f a + 1) + (xs.map (fun x => if x = target then f x + 1 else f x)).sum :=
          congrArg (fun value =>
            value + (xs.map (fun x => if x = target then f x + 1 else f x)).sum)
            (ite_eq_left same)
        _ = (f a + 1) + (xs.map f).sum :=
          congrArg (fun value => (f a + 1) + value)
            (sumIncrementOfAbsent f target xs fun member =>
              (List.nodup_cons.mp distinct).1 (same.symm ▸ member))
        _ = (f a + (xs.map f).sum) + 1 := Nat.add_right_comm _ _ _
    else
      calc
        (if a = target then f a + 1 else f a) +
            (xs.map (fun x => if x = target then f x + 1 else f x)).sum =
            f a + (xs.map (fun x => if x = target then f x + 1 else f x)).sum :=
          congrArg (fun value =>
            value + (xs.map (fun x => if x = target then f x + 1 else f x)).sum)
            (ite_eq_right same)
        _ = f a + ((xs.map f).sum + 1) :=
          congrArg (fun value => f a + value)
            (sumIncrementOfMem f target xs (List.nodup_cons.mp distinct).2
              ((List.mem_cons.mp present).elim
                (fun equality => False.elim (same equality.symm)) id))
        _ = (f a + (xs.map f).sum) + 1 := (Nat.add_assoc _ _ _).symm

/-- The number of preference ranks already tried, summed over all proposers. -/
def proposalCount (state : State n) : Nat :=
  ((Finite.enumerate n).map state.nextRank).sum

/-- The empty initial state has tried no ranks. -/
theorem proposalCount_initial (n : Nat) : proposalCount (initial n) = 0 :=
  sumMapZero (Finite.enumerate n)

/-- At most n ranks per proposer gives at most n*n proposals in total. -/
theorem proposalCount_le (state : State n) (bounded : ∀ p, state.nextRank p ≤ n) :
    proposalCount state ≤ n * n :=
  Nat.le_trans
    (sumMapLeLengthMul state.nextRank n (Finite.enumerate n) fun p _ => bounded p)
    (Nat.le_of_eq (congrArg (fun length => length * n) (Finite.lengthEnumerate n)))

/-- Every actual proposal increments the total number of tried ranks exactly once. -/
theorem proposalCount_advance (preferences : Preferences n) (state : State n)
    (proposer receiver : Fin n) :
    proposalCount (advance preferences state proposer receiver) = proposalCount state + 1 :=
  sumIncrementOfMem state.nextRank proposer (Finite.enumerate n)
    (nodupOfFnOfInjective id fun equality => equality) (Finite.memEnumerate proposer)

/-- An in-range proposal preserves the per-proposer bound on tried ranks. -/
theorem advance_bounded (preferences : Preferences n) (state : State n)
    (proposer receiver : Fin n) (bounded : ∀ p, state.nextRank p ≤ n)
    (untried : state.nextRank proposer < n) :
    ∀ p, (advance preferences state proposer receiver).nextRank p ≤ n :=
  fun p =>
    if same : p = proposer then
      Eq.mpr (congrArg (fun value => value ≤ n) (ite_eq_left same))
        (Eq.mpr (congrArg (fun index => state.nextRank index + 1 ≤ n) same)
          (Nat.succ_le_of_lt untried))
    else
      Eq.mpr (congrArg (fun value => value ≤ n) (ite_eq_right same)) (bounded p)

end TNDLib.Matching.Algorithm
