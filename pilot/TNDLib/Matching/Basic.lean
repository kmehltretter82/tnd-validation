import TNDLib.Finite

/-!
Finite strict complete preferences and a constructive stability certificate checker.
The two sides of the market are each `Fin n`; lower ranks are preferred.
-/

namespace TNDLib.Matching

/-- Explicit strict complete rankings: each row assigns distinct finite ranks. -/
structure Preferences (n : Nat) where
  proposerRank : Fin n → Fin n → Fin n
  receiverRank : Fin n → Fin n → Fin n
  proposerRank_injective : ∀ p, ∀ {a b}, proposerRank p a = proposerRank p b → a = b
  receiverRank_injective : ∀ r, ∀ {a b}, receiverRank r a = receiverRank r b → a = b

/-- A pairing of every participant, with an explicit inverse on the other side. -/
structure PerfectMatching (n : Nat) where
  partner : Fin n → Fin n
  inverse : Fin n → Fin n
  inverse_partner : ∀ p, inverse (partner p) = p
  partner_inverse : ∀ r, partner (inverse r) = r

/-- An unmatched pair whose members both prefer one another to their partners. -/
def BlockingPair (preferences : Preferences n) (matching : PerfectMatching n)
    (proposer receiver : Fin n) : Prop :=
  matching.partner proposer ≠ receiver ∧
  preferences.proposerRank proposer receiver <
    preferences.proposerRank proposer (matching.partner proposer) ∧
  preferences.receiverRank receiver proposer <
    preferences.receiverRank receiver (matching.inverse receiver)

/-- Blocking is decidable from the explicit finite rankings. -/
def blockingPairDecidable (preferences : Preferences n) (matching : PerfectMatching n)
    (proposer receiver : Fin n) : Decidable (BlockingPair preferences matching proposer receiver) :=
  inferInstanceAs (Decidable
    (matching.partner proposer ≠ receiver ∧
      preferences.proposerRank proposer receiver <
        preferences.proposerRank proposer (matching.partner proposer) ∧
      preferences.receiverRank receiver proposer <
        preferences.receiverRank receiver (matching.inverse receiver)))

/-- Stability rules out every blocking pair. -/
def Stable (preferences : Preferences n) (matching : PerfectMatching n) : Prop :=
  ∀ proposer receiver, ¬ BlockingPair preferences matching proposer receiver

/-- Enumerate both finite sides and check every potential blocking pair. -/
def checkStable (preferences : Preferences n) (matching : PerfectMatching n) : Bool :=
  (Finite.enumerate n).all fun proposer =>
    (Finite.enumerate n).all fun receiver =>
      @decide (¬ BlockingPair preferences matching proposer receiver)
        (@instDecidableNot (BlockingPair preferences matching proposer receiver)
          (blockingPairDecidable preferences matching proposer receiver))

/-- The executable checker accepts exactly the stable perfect matchings. -/
theorem checkStable_eq_true_iff (preferences : Preferences n) (matching : PerfectMatching n) :
    checkStable preferences matching = true ↔ Stable preferences matching :=
  ⟨fun h proposer receiver =>
      @of_decide_eq_true (¬ BlockingPair preferences matching proposer receiver)
        (@instDecidableNot (BlockingPair preferences matching proposer receiver)
          (blockingPairDecidable preferences matching proposer receiver))
        ((List.all_eq_true.mp
          ((List.all_eq_true.mp h) proposer (Finite.memEnumerate proposer)))
          receiver (Finite.memEnumerate receiver)),
    fun h => List.all_eq_true.mpr fun proposer _ =>
      List.all_eq_true.mpr fun receiver _ =>
        @decide_eq_true (¬ BlockingPair preferences matching proposer receiver)
          (@instDecidableNot (BlockingPair preferences matching proposer receiver)
            (blockingPairDecidable preferences matching proposer receiver))
          (h proposer receiver)⟩

end TNDLib.Matching
