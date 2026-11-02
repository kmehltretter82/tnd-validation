# Stable matching: source-to-statement map

Reviewed on 2026-11-01. This document specifies the selected mathematical
claim, maps it to the implemented arbitrary-size Lean constructor, and records
the remaining audit boundaries. The formal proof is implemented and compiles;
source-admission integration and production certification remain separate.

## Primary source and selected surface

D. Gale and L. S. Shapley, *College Admissions and the Stability of Marriage*,
The American Mathematical Monthly 69(1), 1962, pp. 9–15.
[Publisher record](https://doi.org/10.1080/00029890.1962.11989827).
[University-hosted primary-paper copy](https://iqua.ece.toronto.edu/baochun/ece1771f/papers/Gale-Shapley-1962.pdf).

The inspected seven-page PDF has SHA-256
`3971ec3e3b048b6ace92248fcc8fa8f021808ca76cbc09d439275b8c0a07bb41`.
Printed page numbers, rather than PDF-viewer indices, are used below. The
paper's text and scans are not included in the library repository.

| Source location | Selected content |
| --- | --- |
| Section 2, p. 9 | Preference rankings have no ties. |
| Section 3, p. 11 | Equal finite populations; everyone ranks the opposite population. |
| Section 3, p. 11 | Instability is mutual strict improvement by an unmatched pair. |
| Theorem 1, p. 12 | A stable marriage exists for each such preference profile. |
| Proof, pp. 12–13 | An iterative proposal construction establishes the theorem. |

The pilot selects Theorem 1 and the definitions needed to state it. The
college-admissions model, optimality theorem, unequal populations, incomplete
preferences, and ties are outside this claim. The published theorem has an
informal domain; the following is TND's explicit formal specification of that
domain. Renaming the populations to proposers and receivers has no
mathematical effect.

## Formal domain and conclusion

For every `n : Nat`, let both participant sets be explicit copies of `Fin n`.
This encodes equal cardinality without a noncomputable choice of enumeration.
The two roles remain distinct through the argument positions and field names,
even when both are represented by `Fin n`.

For each participant, preferences are a permutation of ranks `0, ..., n-1`.
Smaller rank means strictly preferred. Each opposite participant has exactly
one rank, and each rank names exactly one opposite participant. The
implementation proves constructive surjectivity from injectivity on the finite
rank set and obtains inverse maps by explicit finite search. No real-valued utility,
arbitrary comparison oracle, excluded-middle assumption, or pre-existing
matching is required.

The `Fin n` presentation represents every explicitly ranked strict complete
finite profile after a relabeling. A future API for abstract finite participant
types must take their enumerations as data or separately justify its
constructive transport; it is not supplied by the current theorem.

A perfect matching consists of maps

```text
partnerOfProposer : Fin n → Fin n
partnerOfReceiver : Fin n → Fin n
```

with both inverse laws. These laws establish exactly one partner for every
participant, rather than merely a list of apparently compatible pairs. Every
pair is acceptable in this selected complete-preference model; there is no
separate outside option.

For a proposer `p`, receiver `r`, preference profile `P`, and perfect matching
`M`, the intended blocking predicate is

```text
M.partnerOfProposer p ≠ r
∧ P.proposerRank p r < P.proposerRank p (M.partnerOfProposer p)
∧ P.receiverRank r p < P.receiverRank r (M.partnerOfReceiver r).
```

`Stable P M` means that this predicate is false for every `p` and `r`. The
explicit unmatched condition is redundant in a strict-rank presentation, but
retaining it makes the source comparison direct. It must not be replaced by a
one-sided preference condition or by testing only adjacent ranks.

The implemented construction has type

```text
stableMatch (P : Preferences n) :
  { M : PerfectMatching n // Stable P M }.
```

The public endpoint is `TNDLib.Matching.stableMatch` in
[`StableMatch.lean`](../pilot/TNDLib/Matching/StableMatch.lean). It supplies executable
matching data in `Type`, with
correctness in the accompanying property. Forgetting the data gives the
source-facing existence proposition. Conversely, merely proving an existential
in `Prop` does not by itself provide the desired executable API.

The source discussion treats an ordinary nonempty population. Including `n = 0`
is an explicit harmless boundary extension: the unique empty matching is
perfect and stable. Size one has a uniquely determined perfect matching. Both
cases should execute and check without assuming `0 < n` globally.

## Schedule and proof obligations

The implementation processes one unmatched proposer at a time. It does not
reproduce the source's simultaneous stages; it establishes the same existence
claim. Its proposal-count bound and transition trace must therefore be
documented as properties of this implementation; do not identify them with
the source's bound on simultaneous stages.

The proof architecture is as follows. Its sufficient invariants are established
from the empty initial state, rather than assumed in `Preferences` or the final
theorem. The endpoint table below identifies the exact formal statements.

1. **Consistent tentative matching.** Each held proposer is held by exactly
   one receiver. A single receiver-side map represents tentative assignments;
   there is no second partial map that could disagree with it. Reassignment
   releases the displaced proposer and leaves unrelated holdings unchanged.
2. **Proposal prefixes.** A proposer's next-rank cursor records exactly the
   already-proposed prefix of that proposer's ranking. Every transition
   advances one available cursor and no proposer/receiver pair is repeated.
3. **Receiver retention.** A receiver that has received a proposal always
   holds a proposer thereafter, and holds its most preferred proposer among
   those it has seen. A replacement strictly improves the held rank.
4. **Rejection persistence.** If a proposed pair is rejected immediately or
   displaced later, that receiver's current and subsequent held proposer is
   strictly preferred to the rejected proposer. This follows from strict
   rankings and monotone retention, but must be stated or derived in a form
   usable at termination.
5. **Termination.** At most `n * n` distinct proposals are available. A
   well-founded measure or fuel implementation must prove that every active
   transition consumes a new pair. Supplying finite fuel without proving
   non-exhaustion is insufficient for a total correct matching constructor.
6. **Progress and perfection.** If an unmatched proposer has exhausted all
   ranks, every receiver has received a proposal and therefore holds someone.
   Consistency would then account for `n` distinct held proposers while this
   proposer remains unmatched, a finite counting contradiction. Thus a
   terminal valid state is perfect.
7. **Stability.** If a proposer prefers another receiver to its final partner,
   proposal-prefix progress implies it proposed there earlier. Because the
   pair is not final, rejection persistence implies that receiver prefers its
   final partner. Hence the two strict inequalities of a blocking pair cannot
   both hold.

No-repetition alone would support a termination argument but would not establish
perfection or stability. A consistency-only invariant also does not establish
either result. The progress/counting lemma and the rejected-pair argument are
the substantive bridges from a finite proposal process to Theorem 1.

The implemented proof records `History`, a non-strict receiver-rank domination
bound for every tried rank, and `AssignedBelow`, a bound relating currently
held pairs to proposer cursors. Those bounds suffice for the final strict
blocking-pair contradiction. It does not expose a complete proposal trace or
a separate theorem asserting strict rejection persistence at every trace
position; the outline above explains the algorithmic meaning of the numerical
invariants rather than claiming such additional interfaces.

## Non-vacuity and coverage checks

- Do not assume `∃ M, Stable P M`, successful algorithm termination, a
  complete proposal trace, or final stability as an input to the theorem.
- Do not restrict input profiles to ones where a fixed participant labeling
  already produces a stable matching.
- Validate rankings independently of matching output. Duplicate ranks or
  missing preferences are malformed input, not counterexamples to this
  complete-preference theorem.
- Check rejected and reassigned proposals, not only profiles accepted on the
  first proposal. Include a deliberately unstable perfect matching to exercise
  the negative side of the blocking-pair checker.
- Small exhaustive profile tests are implementation evidence, not a proof
  over arbitrary `n`.
- A finite search that returns a stable matching whenever one exists proves
  conditional search completeness. It does not establish the selected
  universal existence claim unless existence is separately proved.

## Existing Lean work and provenance

The following AppliedModelingLib files were read at commit
`194edcc95df74806a39b961d10dedddc6e730cce`:

- [`LICENSE`](https://github.com/nikhgarg/AppliedModelingLib/blob/194edcc95df74806a39b961d10dedddc6e730cce/LICENSE), which identifies Apache License 2.0.
- [`SourceModel.lean`](https://github.com/nikhgarg/AppliedModelingLib/blob/194edcc95df74806a39b961d10dedddc6e730cce/papers/GS62CollegeAdmissions/SourceModel.lean).
- [`PaperInterface.lean`](https://github.com/nikhgarg/AppliedModelingLib/blob/194edcc95df74806a39b961d10dedddc6e730cce/papers/GS62CollegeAdmissions/PaperInterface.lean).

The source-facing existence specification uses abstract finite equal-sized
types and strict complete preferences represented by real-valued scores.
The repository's Lake configuration includes Mathlib. These observations do
not establish the axiom dependencies of its paper proofs. No proof or
implementation from those files was copied into this pilot. Further adaptation
requires inspection of the relevant source notices and preservation of
attribution. TND makes no first-formalization claim.

## Implemented endpoints and review status

The source comparison, model, completion argument, and public constructor were
reviewed by an agent separate from the constructor developer. The reviewer
also authored `Invariants.lean`, so this is not a claim that every proof module
received a wholly independent review. The
[`pilot/TNDLib/Matching/Basic.lean`](../pilot/TNDLib/Matching/Basic.lean) definitions match
the intended source-facing domain and blocking predicate:

| Specification element | Lean endpoint |
| --- | --- |
| Finite strict rankings | `TNDLib.Matching.Preferences` |
| Perfect matching with two inverse laws | `TNDLib.Matching.PerfectMatching` |
| Mutual strict improvement by an unmatched pair | `TNDLib.Matching.BlockingPair` |
| Absence of all blocking pairs | `TNDLib.Matching.Stable` |
| Executable finite checker | `TNDLib.Matching.checkStable` |
| Checker agrees with mathematical stability | `TNDLib.Matching.checkStable_eq_true_iff` |
| Finite rankings cover every rank | `TNDLib.Matching.surjectiveOfInjective` |
| Executable finite inverse | `TNDLib.Matching.inverseRank` |
| Single offer preserves held-rank bounds | `TNDLib.Matching.Proposal.offer_preserves_rank` |
| Offered receiver enters the tried prefix | `TNDLib.Matching.Algorithm.offeredReceiver_tried` |
| Next lookup excludes every previously tried receiver | `TNDLib.Matching.Algorithm.nextReceiver_not_tried` |
| Tried prefixes never shrink | `TNDLib.Matching.Algorithm.advance_nextRank_le` |
| Consistent assignments preserved | `TNDLib.Matching.Algorithm.consistent_advance` |
| Assigned partners lie below tried-rank cursors | `TNDLib.Matching.Algorithm.assignedBelow_advance` |
| Receiver domination for already-tried ranks | `TNDLib.Matching.Algorithm.history_advance` |
| No free proposer exhausts all ranks | `TNDLib.Matching.Algorithm.free_nextRank_lt` |
| Every valid transition preserves the full invariant bundle | `TNDLib.Matching.Algorithm.valid_advance` |
| Initial state satisfies the full bundle | `TNDLib.Matching.Algorithm.valid_initial` |
| The actual arbitrary-size run always finishes | `TNDLib.Matching.Algorithm.run_finishes` |
| Finished holdings decode to perfect matching data | `TNDLib.Matching.Algorithm.matchingOfFinished` |
| Decoded matching is stable from proved history | `TNDLib.Matching.Algorithm.matchingStableOfHistory` |
| Executable stable matching constructor | `TNDLib.Matching.stableMatch` |
| Stability of the computed matching | `TNDLib.Matching.stableMatch_stable` |
| Source-facing finite stable-existence result | `TNDLib.Matching.existsStableMatching` |

The matching maps are named `partner` and `inverse`, with both inverse laws
stored in the structure. The public constructor takes only `Preferences n`;
it has no stable-existence, successful-run, or algorithm-correctness premise.
`valid_initial` establishes bounded cursors, consistent holdings, proposal
history, and assigned-pair bounds. `runFuel_finishes` inducts over the actual
interpreter's finite fuel using its increasing bounded proposal count;
`run_finishes` instantiates the initial state and `n * n + 1` budget.

The no-repeat argument uses the three explicit prefix lemmas above: an offer
puts its receiver below the advanced cursor, all cursors are monotone, and a
later lookup cannot return any receiver below its current cursor. This is a
local transition argument; no separate trace-equivalence theorem is claimed.

The public constructor branches on the actual computed `Outcome`. Its finished
branch obtains data through executable searches in `chosenReceiver` and
`inverseRank`. Uses of the existential termination theorem only establish
properties in `Prop` or contradictions for unreachable error outcomes; no
existential proof is used to select matching data from `Prop`. This is an
executable construction, not merely a classical existence theorem.

An independent diagnostic run imported `TNDLib.Matching.Pilot` and checked the
types of `stableMatch` and `existsStableMatching`. Its `#print axioms` results
for `run_finishes`, `matchingStableOfHistory`, `stableMatch`, and
`existsStableMatching` were exactly `[propext, Quot.sound]`. Evaluating the
computed partner lists gave `[]` at size zero, `[0]` at size one, `[0, 1]` for
the size-two common-ranking profile, and `[1, 0]` for the size-two profile
requiring reassignment. These diagnostic evaluations supplement the generic
proof; they do not replace independent proof-object replay.

The full pilot uses structures, named decision evidence, inductive state/outcome types,
multiple imports, and other syntax outside the current source-admission
profile. The isolated seven-declaration `Proposal` module has been exercised
through a supplemental maintained parser specification and independent replay;
that restricted result does not admit or certify the entire pilot. Candidate
`286cdc677a418f994c4814d9492ebdd3726700e5` subsequently passed fresh-checkout
independent replay of all 223 exported matching declarations, with only the
allowed axioms; the exact evidence and its library-self-comparison scope are
recorded in the [review packet](MATCHING-REVIEW.md). Subsequently, the separate
restricted development source profile admitted all 14 actual sources and passed
13 positive and 91 hostile fixtures. Its exact-revision driver also completed
admission, same-byte compilation/export, and replay. These results satisfy the
local pilot source gate while leaving production adoption and native isolation
as separate decisions and validation work.

This establishes a Lean proof of the selected strict-complete finite
stable-existence result in an explicit indexed presentation. It does not
establish exact operational equivalence with the paper's simultaneous schedule,
the paper's optimality result, college quotas, general abstract finite-type
transport, full-paper coverage, public source-admission support, or production
certification.
