# Paper pilot: constructive finite stable matching

Status: the selected arbitrary-size stable-existence theorem and executable
constructor are implemented and independently replayed (`proved-development` at
`4eb427483923034000a9825cfd41f5d6a45c6861`, CI verified at
`3dbcf3013a8350e33c5e9950e0b01539cfc2915d` in run `41356432624`). A separate
restricted development profile admits the complete source and has passed its
positive/hostile fixture matrix. This is a development-checked proof
(`proved-development`), not a `production-certified` claim. See the
[review packet](MATCHING-REVIEW.md) for exact candidate evidence and
[`docs/FOUNDATION.md`](FOUNDATION.md) for the library architecture.

## Why this pilot

The library needs a coherent example demonstrating that a constructive
formulation produces useful executable data. Another collection of elementary
logical lemmas would mainly exercise machinery already present. Finite stable
matching is a recognizable mathematical problem with a concrete algorithm and
an opportunity to reuse finite enumeration, decidability, lists, and explicit
witnesses.

It is substantially larger than the current corpus. Start with a feasibility
prototype and retain an honest smaller deliverable if the missing infrastructure
is disproportionate. The paper is the source of a mathematical specification;
it is not input to an unsupervised pipeline whose output is presumed faithful.

## Sources and existing work

- D. Gale and L. S. Shapley, *College Admissions and the Stability of Marriage*,
  The American Mathematical Monthly 69(1), 1962, pp. 9–15.
  [Publisher record](https://doi.org/10.1080/00029890.1962.11989827).
  [University-hosted primary-paper copy](https://iqua.ece.toronto.edu/baochun/ece1771f/papers/Gale-Shapley-1962.pdf).
- Selected source surface: Section 3's finite marriage model and Theorem 1,
  whose proof starts on printed page 12. Record precise source locations for
  each formal definition and theorem when writing the statement map.
- AppliedModelingLib already reports a Lean treatment of this paper's selected
  theoretical results. Read its
  [validation report](https://github.com/nikhgarg/AppliedModelingLib/blob/194edcc95df74806a39b961d10dedddc6e730cce/papers/GS62CollegeAdmissions/FINAL_VALIDATION_REPORT.md)
  before making any novelty claim. Its
  [Lake configuration](https://github.com/nikhgarg/AppliedModelingLib/blob/194edcc95df74806a39b961d10dedddc6e730cce/lakefile.toml)
  includes Mathlib; that is a dependency observation, not an audit of whether
  the paper-specific proofs depend on classical choice. These two files were
  checked at commit `194edcc95df74806a39b961d10dedddc6e730cce` on 2026-11-01.
  Inspect licenses before adapting
  any implementation, and retain attribution for any adapted material.

The intended TND contribution is an explicitly constructive, executable,
Mathlib-free treatment with audited dependencies and reusable finite APIs.
Existing formalization elsewhere does not establish that TND has achieved
these properties. A paper citation does not authorize redistributing its text;
store source references and our own statement map rather than copying the
paper into the repository.

## Initial mathematical scope

Use two participant sets represented by `Fin n`, for arbitrary natural `n`.
Each participant has an explicit strict complete preference ranking of the
opposite set. Ranking validity is part of the input representation, not a
classically supplied ordering or an assumed output property.

Define a perfect matching and a blocking pair, implement a finite checker, then
construct a matching and prove that it is perfect and stable for every valid
input. The returned matching must be data in `Type`; a bare existential
proposition is insufficient for the intended executable interface.

The intended interface has the conceptual shape:

```text
stableMatch (preferences : Preferences n) :
  { matching : PerfectMatching n // Stable preferences matching }
```

The implemented checked endpoint is `TNDLib.Matching.stableMatch` in
`pilot/TNDLib/Matching/StableMatch.lean`; the sketch above omits namespaces and
implicit parameters. Review the following independently:

- The input model includes all finite strict complete profiles on equal-sized
  sets; it does not hide an existence or correctness assumption.
- A perfect matching contains inverse maps or another representation strong
  enough to ensure every participant is paired exactly once.
- Stability excludes every unmatched pair whose members both prefer one
  another to their assigned partners.
- The construction is total at size zero as well as positive sizes.
- Preference assumptions, output validity, and stability are distinct; an
  invalid input or a vacuous output must not make correctness trivial.

Applicant/proposer optimality, ties, incomplete preferences, unequal population
sizes, college quotas, strategy-proofness, and all-paper coverage are future
work. A serial proposal schedule may be used if its relationship to the source
result is documented; do not claim that its operational trace reproduces the
paper's simultaneous stages.

## Feasibility gate

Before committing to the full correctness proof:

1. Write the source-to-statement map and inspect the needed core declarations
   for dependency and computational issues.
2. Define valid preferences, matching data, and a decidable blocking-pair
   predicate. Make small positive and negative examples execute.
3. Prototype one proposal transition with explicit state, and prove one central
   invariant, such as consistency of tentative assignments or no repeated
   proposal. This must be a real reusable lemma, not the statement that an
   already-correct algorithm is correct.
4. Check that the new source, generated declarations, statement, and proof can
   traverse the current admission/export/checker route. Record any term-only
   or hidden-helper limitation at its actual stage of failure.
5. Estimate the remaining finite infrastructure from that prototype. Prefer
   small purpose-built definitions over building a general order/graph library.

The gate succeeds when there is an executable transition, a checked invariant,
and an explicit path through the verification boundary. If two consecutive
prototype checkpoints make no progress on these, document the concrete blocker
and reduce scope. Do not repeatedly expand the platform to avoid the theorem.

## Dependency-ordered proof work

1. Preference lookup, finite search, and the validity of the ranking
   representation.
2. Partial/tentative matching state and consistency of its two sides.
3. Proposal transition and preservation of consistency, monotone receiver
   preference, and the no-repeated-proposal invariant.
4. Termination using a decreasing finite measure or bounded fuel with a proof
   that valid executions cannot exhaust it prematurely. A bound on individual
   proposals, naturally at most `n * n`, belongs here; a polished runtime
   complexity theorem can wait. Do not confuse proposal count with wall-clock
   complexity or with the paper's simultaneous-round bound.
5. Perfection at termination and the absence of blocking pairs.
6. A total executable constructor, the arbitrary-size correctness theorem, and
   a clean downstream example using both.

Use independent agent review for the statement map, invariant sufficiency, and
final assumptions/dependency report. Passing Lean's checker establishes the
formal statement under its recorded assumptions; the paper-to-Lean semantic
comparison remains a separately reviewable argument.

## Smaller fallback

A decidable stability checker plus exhaustive finite matching search is a useful
independent artifact. Prove checker soundness and completeness, and search
soundness/completeness relative to whether a stable matching exists. Exercise
it on finite examples. Clearly mark the universal stable-existence theorem as
open: assuming that a stable matching exists and then finding one does not
prove the selected source theorem. Do not promote this fallback as a completed
formalization of Theorem 1.

## Acceptance and downstream demonstration

- Build from a clean exact local snapshot without Mathlib or platform imports.
- Audit transitive dependencies of statements, definitions, and proofs against
  the existing allowed-axiom policy; no `sorry`, native-evaluation axiom,
  custom axiom, or `Classical.choice` is permitted in the completed result.
- Run the independent checker on the exact selected declaration inventory.
  An ordinary Lean build or `#print axioms` diagnostic alone does not meet
  this requirement.
- Verify the generic correctness result for arbitrary `n`; test empty and
  singleton instances, profiles requiring rejection/reassignment, multiple
  stable outcomes, and deliberately unstable candidate matchings.
- Exhaust small profile spaces where practical, then use deterministic larger
  samples. Compare executable results with an independent finite checker;
  these checks help find implementation/specification errors but do not replace
  the proof.
- Have a separate Lake project import the exact full-SHA snapshot, compute a
  nontrivial matching, and use the generic correctness theorem. Report the
  actual remaining dependencies and clean-build/audit cost.
- Produce one review packet with the source map, interfaces, theorem scope,
  exact code/diffs, computed example, audit evidence, provenance, and open
  limitations. Publication and production certification remain separate
  explicit decisions.
