import Init

/-! A list split that carries its length bound and recombination proof. -/

namespace TNDLib.List

/-- Split a list into a prefix of at most `n` elements and its remaining suffix. -/
def splitAt (n : Nat) (xs : List α) :
    { pair : List α × List α // pair.1 ++ pair.2 = xs ∧ pair.1.length ≤ n } :=
  ⟨(xs.take n, xs.drop n), List.take_append_drop n xs, List.length_take_le n xs⟩

/-- The first component is the usual prefix operation. -/
theorem splitAtPrefix (n : Nat) (xs : List α) : (splitAt n xs).val.1 = xs.take n := rfl

/-- The second component is the remaining suffix. -/
theorem splitAtSuffix (n : Nat) (xs : List α) : (splitAt n xs).val.2 = xs.drop n := rfl

/-- Recombining the returned parts preserves every input element in order. -/
theorem splitAtRecombine (n : Nat) (xs : List α) :
    (splitAt n xs).val.1 ++ (splitAt n xs).val.2 = xs :=
  (splitAt n xs).property.1

/-- The returned prefix respects the requested bound even for a short input. -/
theorem splitAtLength (n : Nat) (xs : List α) : (splitAt n xs).val.1.length ≤ n :=
  (splitAt n xs).property.2

end TNDLib.List
