# Stable-matching pilot review packet

Status: mathematical development candidate and complete-source development
profile verified (`4eb427483923034000a9825cfd41f5d6a45c6861`, with CI follow-up
`3dbcf3013a8350e33c5e9950e0b01539cfc2915d` passing `Maintainer Regression` run
`41356432624`). Proof status is `proved-development` (verified by the isolated
source-admission parser and independent kernel proof-object checker while
`.choir/certification.json` remains fail-closed `false`/`false`/`null`, as
distinct from `source-published` unproved source and `production-certified`
native Linux quota-enforced release evidence).

## Mathematical result

The pilot implements the finite strict-complete stable-existence result from
Section 3, Theorem 1 of Gale and Shapley (1962). Inputs are explicit injective
rankings on each side of two `Fin n` populations. Every natural `n`, including
zero, is supported.

`TNDLib.Matching.stableMatch` returns actual perfect-matching data together with
its stability proof. `existsStableMatching` derives the corresponding
existential statement. The program executes serial deferred acceptance;
termination uses at most `n * n` individual proposals plus a final completion
check. This is a proposal-count bound, not a wall-clock complexity theorem or
the paper's simultaneous-stage bound.

The proof establishes the initial invariants, their preservation, bounded
proposal count, termination of the actual run, decoding of completed holdings
as a bijection, and the absence of blocking pairs. It assumes neither stable
existence nor correctness of the algorithm. Executable matching data comes
from the computed outcome; existential proof elimination supplies only proofs
and contradictions.

The independently reviewed [statement map](MATCHING-STATEMENT-MAP.md) lists
precise primary-paper locations, hypotheses, definition correspondence, and
proof endpoints. The selected theorem is a scoped formalization of an existing
result, with no first-formalization claim. Optimality, college quotas, ties,
incomplete preferences, and full-paper coverage remain outside this milestone.

## Local source identity

- Initial library snapshot: `a76c3fc5516e263229a41eb597e3a7ce9f870c8a`.
- Baseline/profile repair: `68f9090`.
- Mathematical implementation: `8403021115797242ddbf200a237fcefdbcf2d959`.
- Verified packaging/harness candidate:
  `286cdc677a418f994c4814d9492ebdd3726700e5`.
- Published development commit `4eb427483923034000a9825cfd41f5d6a45c6861` includes
  complete-source development admission, package-growth compatibility, two
  explicit no-repeat prefix lemmas, regression coverage, and the benchmark
  (followed by CI checkout-depth fix `3dbcf3013a8350e33c5e9950e0b01539cfc2915d`,
  verified in public run `41356432624`).

The implementation is an explicit `TNDMatchingPilot` Lake target under `pilot/`
configured via `LAKE_CONFIG_ENV=tnd-pilot` (see `lakefile.toml` and
`tests/check_downstream.py`); downstream users of the pilot target import
`TNDLib.Matching.Pilot`.
The original `TNDLib.lean` root and its approved production source/export
inventories are unchanged. Exact package policy permits only the reviewed
configuration, and the real canonical source-snapshot routine excludes pilot
files and stages a minimal original-library Lake project.

## Verified evidence at candidate `286cdc6`

- Fresh local checkout built the original library and all pilot modules.
- All nine matching Lean test files then present passed. The constructor was
  exercised on 234 profiles: exhaustive strict profiles for sizes 0–2 and
  216 deterministic size-three profiles. Cases include rejection,
  reassignment, negative unstable-match controls, and explicit fuel failures.
- The maintained independent checker replayed all **223** exported matching
  declarations, including generated declarations. The axiom closure is limited
  to `propext` and `Quot.sound`; no custom axiom, `sorryAx`, native-evaluation
  axiom, or `Classical.choice` was admitted.
- This library self-audit uses the same export as both comparator inputs.
  Kernel replay and dependency auditing are genuine; it does not establish
  comparison against a separately approved challenge. The paper-to-Lean
  semantic review is recorded independently.
- A clean downstream Lake project consumed the exact full SHA and that
  revision's toolchain pin. Its only package dependency was `tndlib`, with no
  transitive packages. It computed `[0, 1, 2]`, invoked the generic correctness
  theorem, and checked its output with a separately written finite predicate.
- The real canonical snapshot contained exactly the original seven source
  files, excluding all pilot source. Five real-Git isolation tests also check
  exclusion of an unreviewed pilot module and rejection of unrelated roots,
  extra canonical modules, and altered package configuration.
- The current full Python regression run passed **470 tests**, with three
  Linux-only skips and 81 passing subtests. Ruff and the frozen offline lock
  check passed. The original task-to-promotion rehearsal still passed after
  the package changes and replayed the resulting 38-declaration inventory.
- The existing 21 proof-object fixture expectations passed, including choice,
  unfinished proofs, extra axioms, statement changes, and forged-object
  rejection. One fixture explicitly records a known unimported-module gap
  with production disabled; these results do not resolve that gap.

Reproduce exact-candidate evidence with the commands in the
[verification guide](../audit/matching/README.md), writing output to a caller-chosen
temporary directory (for example `/tmp/tnd-matching-report.json`). The full
replay report for `286cdc6` has SHA-256
`e3ff0c0526bd90b3d13afd733b0c69b65a32b86f9e77837c738d78c65a5263a4`.
Regenerated reports or new candidates need their own recorded hashes.

## Informal computation measurements

The later development benchmark `tests/matching/Benchmark.lean` computes the
constructor, runs finite stability/inverse checks, and prints the actual data
before stopping its timer. On the installed macOS Lean 4.35.0 interpreter,
single samples for identical index-ranked preference rows took 11 ms at size
8 and 366 ms at size 16. Sizes 0–3 took 0–1 ms at timer resolution.

These are worktree measurements using the unchanged candidate mathematics,
not measurements bound to a final benchmark commit. They include checks and
output, exclude process startup, use one preference family, and establish no
large-input performance or resource-boundary claim. The implementation uses
simple finite scans and functional state updates; efficient data structures
are future work justified by measured need.

## Complete-source development gate

The unchanged production parser admits the isolated seven-declaration
plain-term receiver transition and its meaningful rank-preservation invariant.
The richer pilot remains outside that production dialect.

The implemented [development profile](../audit/matching/ADMISSION-REVIEW.md)
accepted all 14 actual source files, 13 positive fixtures, and 91 hostile
fixtures with the expected outcomes. An unknown imported initializer remained
inert. Receipt hashes identify the exact parser, maintained policy, and harness.
The corresponding exact-revision driver reads bounded ordinary Git blobs,
validates their closed acyclic imports, parses the entire staged source,
compiles those same bytes, and independently replays all 223 declarations.
The full path passed for mathematical candidate `286cdc6` with maintained
development tooling; final frozen-candidate evidence is recorded separately.
The final export inventory contains 225 declarations after adding the two
prefix lemmas; the historical 223-declaration report above retains its original
scope. The workspace manifest records the final inventory's replay outcome.

This satisfies the pilot's local full-source development gate. It establishes
neither formal completeness of the admitted language semantics nor native-host
filesystem/network isolation. Production parser, source inventories, resource
settings, and certification flags remain under their existing policy.

## Provenance and publication decisions

The mathematical proof implementation was developed locally for TND. Prior
AppliedModelingLib work was inspected at its recorded fixed revision as a
specification/reference source; its proof implementation was not copied.
Retain the existing Apache-2.0 licensing and Lean/Choir/comparator attribution.
The primary paper is linked and cited rather than redistributed.

The workspace review manifest identifies the exact final candidate and evidence
receipts. Any public push, production integration, certification change,
release, deployment, or announcement requires its own concrete user review
under the workspace rules. The app-only GitHub merge lane remains a separate
operational issue and does not authorize bypassing those rules.

The proposed next external action, subject to exact-content review, is a
development source publication of the frozen candidate with the status above.
It would carry no certified tag or badge. Production activation, site evidence,
community invitations, and announcements require later reviewed decisions.
