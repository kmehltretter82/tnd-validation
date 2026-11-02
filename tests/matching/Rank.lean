import TNDLib.Matching.Rank

namespace TNDLib.Matching.Tests

example : inverseRank (id : Fin 1 → Fin 1) 0 = 0 := rfl

example : inverseRank (id : Fin 3 → Fin 3) 2 = 2 := rfl

example : inverseRank (Fin.rev : Fin 3 → Fin 3) 0 = 2 := rfl

example : inverseRank (Fin.rev : Fin 3 → Fin 3) 2 = 0 := rfl

/-- An arbitrary-size inverse example uses injectivity, not a computed finite check. -/
theorem reverseRankInverse (rank : Fin n) :
    Fin.rev (inverseRank Fin.rev rank) = rank :=
  applyInverseRank _ (fun h => Fin.rev_inj.mp h) rank

#print axioms TNDLib.Matching.nodupLengthLeOfSubset
#print axioms TNDLib.Matching.nodupOfFnOfInjective
#print axioms TNDLib.Matching.surjectiveOfInjective
#print axioms TNDLib.Matching.applyInverseRank
#print axioms TNDLib.Matching.inverseRankApply
#print axioms reverseRankInverse

end TNDLib.Matching.Tests
