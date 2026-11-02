import TNDLib.Matching.Basic

/-! Constructive finite ranking inversion by explicit bounded search. -/

namespace TNDLib.Matching

/-- Removing one unequal listed element preserves membership. -/
theorem memAppendOfMemInsert {x a : α} {front back : List α}
    (unequal : x ≠ a) (member : x ∈ front ++ a :: back) : x ∈ front ++ back :=
  List.mem_append.mpr
    ((List.mem_append.mp member).elim Or.inl fun tailMember =>
      (List.mem_cons.mp tailMember).elim
        (fun equality => False.elim (unequal equality)) Or.inr)

/-- Constructive finite cardinality without a nonconstructive equality instance. -/
theorem nodupLengthLeOfSubset :
    ∀ {xs ys : List α}, xs.Nodup → xs ⊆ ys → xs.length ≤ ys.length
  | [], _, _, _ => Nat.zero_le _
  | a :: xs, ys, distinct, subset =>
    let tailDistinct := (List.nodup_cons.mp distinct).2
    let absent := (List.nodup_cons.mp distinct).1
    let present := subset List.mem_cons_self
    Exists.elim (List.append_of_mem present) fun front split =>
      Exists.elim split fun back equality =>
        let tailSubset : xs ⊆ front ++ back := fun x member =>
          memAppendOfMemInsert (fun (same : x = a) => absent (same ▸ member))
            (equality ▸ subset (List.mem_cons_of_mem a member))
        Nat.le_trans
          (Nat.succ_le_succ (nodupLengthLeOfSubset tailDistinct tailSubset))
          (Nat.le_of_eq
            (calc
              (front ++ back).length + 1 = (front.length + back.length) + 1 :=
                congrArg Nat.succ List.length_append
              _ = front.length + (back.length + 1) := Nat.add_assoc _ _ _
              _ = (front ++ a :: back).length := (@List.length_append α front (a :: back)).symm
              _ = ys.length := congrArg List.length equality.symm))

/-- Enumerating an injective finite map produces no repeated output. -/
theorem nodupOfFnOfInjective (f : Fin n → α)
    (injective : ∀ {a b}, f a = f b → a = b) : (List.ofFn f).Nodup :=
  List.nodup_iff_eq_of_getElem_eq.mpr fun _ _ hi hj equality =>
    congrArg Fin.val
      (injective ((List.getElem_ofFn hi).symm.trans
        (equality.trans (List.getElem_ofFn hj))))

/-- Every rank is reached by an injective endomap of the explicit finite set. -/
theorem surjectiveOfInjective (f : Fin n → Fin n)
    (injective : ∀ {a b}, f a = f b → a = b) (target : Fin n) :
    ∃ source, f source = target :=
  if found : (List.ofFn f).any (fun value => decide (value = target)) = true then
    List.mem_ofFn.mp
      (Exists.elim (List.any_eq_true.mp found) fun _ witness =>
        (of_decide_eq_true witness.2) ▸ witness.1)
  else
    let absent : target ∉ List.ofFn f := fun member =>
      found (List.any_eq_true.mpr ⟨target, member, decide_eq_true rfl⟩)
    False.elim
      (Nat.not_succ_le_self n
        (calc
          n + 1 = (target :: List.ofFn f).length :=
            (congrArg Nat.succ List.length_ofFn).symm
          _ ≤ (Finite.enumerate n).length :=
            nodupLengthLeOfSubset
              (List.nodup_cons.mpr ⟨absent, nodupOfFnOfInjective f injective⟩)
              (fun x _ => Finite.memEnumerate x)
          _ = n := Finite.lengthEnumerate n))

/-- Search the finite domain for an input of the requested rank.
The fallback makes the function total for arbitrary maps; injectivity proves
that it is never used for a valid rank map. -/
def inverseRank (f : Fin n → Fin n) (target : Fin n) : Fin n :=
  ((Finite.enumerate n).find? fun source => decide (f source = target)).getD target

/-- Explicit finite search is a right inverse for every injective rank map. -/
theorem applyInverseRank (f : Fin n → Fin n)
    (injective : ∀ {a b}, f a = f b → a = b) (target : Fin n) :
    f (inverseRank f target) = target :=
  match found : (Finite.enumerate n).find? (fun source => decide (f source = target)) with
  | some source =>
    (congrArg f (congrArg (fun result => result.getD target) found)).trans
      (show f source = target from
        of_decide_eq_true
          (List.find?_some (p := fun x => decide (f x = target)) found))
  | none =>
    Exists.elim (surjectiveOfInjective f injective target) fun source equality =>
      False.elim
        ((List.find?_eq_none.mp found source (Finite.memEnumerate source))
          (decide_eq_true equality))

/-- Explicit finite search is also a left inverse for injective rank maps. -/
theorem inverseRankApply (f : Fin n → Fin n)
    (injective : ∀ {a b}, f a = f b → a = b) (source : Fin n) :
    inverseRank f (f source) = source :=
  injective (applyInverseRank f injective (f source))

end TNDLib.Matching
