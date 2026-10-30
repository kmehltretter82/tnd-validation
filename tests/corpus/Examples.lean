import TNDLib

/-!
Concrete regression examples for the initial corpus. These fixtures are deliberately
outside the certified root imports. The examples check small cases by kernel reduction;
the IO checks additionally exercise compiled execution.
-/

example : TNDLib.Nat.sumTo 0 = 0 := rfl

example : (TNDLib.Nat.sumToWitness 5).val = 15 := rfl

example : (TNDLib.List.splitAt 0 [1, 2, 3]).val = ([], [1, 2, 3]) := rfl

example : (TNDLib.List.splitAt 2 [1, 2, 3]).val = ([1, 2], [3]) := rfl

example : (TNDLib.List.splitAt 8 [1, 2, 3]).val = ([1, 2, 3], []) := rfl

example : (TNDLib.Finite.enumerate 0).map Fin.val = [] := rfl

example : (TNDLib.Finite.enumerate 4).map Fin.val = [0, 1, 2, 3] := rfl

example : (TNDLib.Finite.select 6 (fun i => i.val % 2 = 0)).map Fin.val = [0, 2, 4] := rfl

example : TNDLib.Algebra.product Nat.mul 1 [2, 3, 4] = 24 := rfl

example :
    TNDLib.Algebra.product Nat.add 0 ([1, 2] ++ [3, 4]) =
      TNDLib.Algebra.product Nat.add 0 [1, 2] + TNDLib.Algebra.product Nat.add 0 [3, 4] :=
  TNDLib.Algebra.productAppend Nat.add 0 Nat.add_assoc Nat.zero_add _ _

example :
    (TNDLib.Predicate.assembleWitnesses (fun x y : Nat => x ≤ y)
      (fun x => ⟨x, Nat.le_refl x⟩)).val 7 = 7 := rfl

#eval show IO Unit from do
  unless (TNDLib.Nat.sumToWitness 5).val == 15 do
    throw (IO.userError "sumToWitness 5 did not execute to 15")
  unless (TNDLib.List.splitAt 2 [1, 2, 3]).val == ([1, 2], [3]) do
    throw (IO.userError "splitAt returned the wrong prefix or suffix")
  unless (TNDLib.Finite.select 6 (fun i => i.val % 2 = 0)).map Fin.val == [0, 2, 4] do
    throw (IO.userError "finite filtering returned the wrong indices")
  unless TNDLib.Algebra.product Nat.mul 1 [2, 3, 4] == 24 do
    throw (IO.userError "the list product did not execute to 24")
