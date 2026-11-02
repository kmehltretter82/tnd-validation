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

example : TNDLib.Cantor.flip true = false := rfl

example : TNDLib.Cantor.flip false = true := rfl

example : TNDLib.Cantor.diagonal (fun _ _ => false) 3 = true := rfl

example : TNDLib.Cantor.DiscrepancyWitness (fun _ _ => false) (TNDLib.Cantor.diagonal (fun _ _ => false)) 3 :=
  TNDLib.Cantor.diagonalDiscrepancy (fun _ _ => false) 3

example : (TNDLib.Cantor.diagonal (fun i j => decide (i = j)) 4 = true) → False :=
  TNDLib.Cantor.diagonal_differ_at (fun i j => decide (i = j)) 4

example : TNDLib.Lorenzen.meet 4 9 = 4 := rfl

example : TNDLib.Lorenzen.join 4 9 = 9 := rfl

example : TNDLib.Lorenzen.LOrder 3 7 :=
  TNDLib.Lorenzen.orderCancelLeft 5 3 7
    (Nat.le_succ_of_le (Nat.le_succ_of_le (Nat.le_succ_of_le (Nat.le_succ_of_le (Nat.le_refl 8)))))

example : TNDLib.Lorenzen.LOrder (TNDLib.Lorenzen.meet 6 2) 6 :=
  TNDLib.Lorenzen.meet_le_left 6 2

example : TNDLib.Lorenzen.LOrder 2 (TNDLib.Lorenzen.meet 6 2) :=
  TNDLib.Lorenzen.le_meet 2 6 2
    (Nat.le_succ_of_le (Nat.le_succ_of_le (Nat.le_succ_of_le (Nat.le_succ_of_le (Nat.le_refl 2)))))
    (Nat.le_refl 2)

example : TNDLib.Certifying.checkMatchAt2 (fun i => decide (i % 2 = 0)) true false 4 = true := rfl

example : TNDLib.Certifying.MatchAt2 (fun i => decide (i % 2 = 0)) true false 4 :=
  ⟨rfl, rfl⟩

example :
    TNDLib.Certifying.StreamDiscrepancyCert
      (fun i j => decide (i = j))
      (TNDLib.Cantor.diagonal (fun i j => decide (i = j)))
      2 :=
  TNDLib.Certifying.diagonalStreamCert (fun i j => decide (i = j)) 2

#eval show IO Unit from do
  unless (TNDLib.Nat.sumToWitness 5).val == 15 do
    throw (IO.userError "sumToWitness 5 did not execute to 15")
  unless (TNDLib.List.splitAt 2 [1, 2, 3]).val == ([1, 2], [3]) do
    throw (IO.userError "splitAt returned the wrong prefix or suffix")
  unless (TNDLib.Finite.select 6 (fun i => i.val % 2 = 0)).map Fin.val == [0, 2, 4] do
    throw (IO.userError "finite filtering returned the wrong indices")
  unless TNDLib.Algebra.product Nat.mul 1 [2, 3, 4] == 24 do
    throw (IO.userError "the list product did not execute to 24")
  unless TNDLib.Cantor.diagonal (fun i j => decide (i = j)) 5 == false do
    throw (IO.userError "diagonal stream returned the wrong bit")
  unless TNDLib.Lorenzen.meet 12 7 == 7 && TNDLib.Lorenzen.join 12 7 == 12 do
    throw (IO.userError "Lorenzen meet/join returned the wrong values")
  unless TNDLib.Certifying.checkMatchAt2 (fun i => decide (i % 2 = 0)) true false 4 == true do
    throw (IO.userError "checkMatchAt2 did not detect the concrete match")
