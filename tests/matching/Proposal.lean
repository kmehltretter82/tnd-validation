import TNDLib.Matching.Proposal

namespace TNDLib.Matching.Proposal.Tests

example : offer (fun p : Fin 3 => p) (1 : Fin 3) none = some (1 : Fin 3) := rfl
example : offer (fun p : Fin 3 => p) ⟨0, Nat.zero_lt_succ 2⟩ (some ⟨2, Nat.lt_succ_self 2⟩) =
    some ⟨0, Nat.zero_lt_succ 2⟩ := rfl
example : offer (fun p : Fin 3 => p) ⟨2, Nat.lt_succ_self 2⟩ (some ⟨0, Nat.zero_lt_succ 2⟩) =
    some ⟨0, Nat.zero_lt_succ 2⟩ := rfl
example : offer (fun p : Fin 3 => p) (1 : Fin 3) (some (1 : Fin 3)) =
    some (1 : Fin 3) := rfl

#eval offer (fun p : Fin 3 => p) ⟨0, Nat.zero_lt_succ 2⟩ (some ⟨2, Nat.lt_succ_self 2⟩)
#print axioms offer_preserves_rank

end TNDLib.Matching.Proposal.Tests
