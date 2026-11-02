# Matching pilot: development verification

The pilot is an explicit `TNDMatchingPilot` Lake library target whose sources
live under `pilot/`. Its logical modules are `TNDLib.Matching.*`; it imports
only the existing finite-enumeration module and the bundled Lean core.
It is not imported by the approved `TNDLib.lean` root and is not part of the
existing production admission/export inventory. This separation keeps the
existing source guard effective while the new source grammar is reviewed.

The pilot target is declared after the original library: pinned Lake 4.35
resolves overlapping buildable modules from the last matching library. The
original library keeps its normal root behavior so future approved task
promotions can add modules; it is not frozen to a hard-coded list of six files.

The mathematical endpoint is:

```text
TNDLib.Matching.stableMatch (preferences : Preferences n) :
  { matching : PerfectMatching n // Stable preferences matching }
```

The actual program executes serial deferred acceptance. A generic proof shows
that `n * n + 1` units of interpreter fuel suffice, including the final
completion check. The resulting matching and its correctness proof cover
arbitrary valid input sizes, including zero. This is the selected finite
strict-complete stable-existence result; optimality, college quotas, ties,
incomplete preferences, and the whole paper are outside its scope.

## Reproduce

From the library root:

```sh
lake build TNDLib TNDMatchingPilot
lake env lean tests/matching/StableMatch.lean
python3 tests/matching/check_proposal.py
python3 audit/matching/test_admission.py
python3 tests/matching/check_source.py --revision FULL_40_CHARACTER_COMMIT_SHA
python3 tests/matching/check_pilot.py --revision FULL_40_CHARACTER_COMMIT_SHA
python3 tests/matching/check_downstream.py --revision FULL_40_CHARACTER_COMMIT_SHA
```

The maintainer regression workflow contains these pilot build, fixture, source,
and downstream checks. It retains its original same-repository/main guards and
read-only permissions, and passed public GitHub Actions run `41356432624` on
commit `3dbcf3013a8350e33c5e9950e0b01539cfc2915d` (following initial publication
commit `4eb427483923034000a9825cfd41f5d6a45c6861`).

The exact-revision scripts require a committed candidate. They inspect its
production policy and reject validation-only activated flags. The downstream
script consumes that full Git SHA and its toolchain pin in a separate clean
Lake project, checks the resolved dependency graph, computes a size-three
matching, invokes the generic theorem, and checks the output with a separately
written finite blocking-pair predicate.

`check_pilot.py` clones the exact candidate locally without build products,
builds the original library and the pilot, runs all matching Lean test files,
exports the complete matching namespace, and replays it with the maintained
independent checker against `pilot-exports.json`. The manifest contains the
complete public generated and authored declaration inventory, not just the
displayed theorem names. Dependency auditing includes proof and statement
dependencies and rejects axioms outside `propext` and `Quot.sound`.

The same candidate export is supplied as both comparator inputs. This is a
library self-audit: kernel replay and dependency auditing are genuine, while
comparison to itself does not independently establish agreement with a separate
approved challenge statement. The separately reviewed
[statement map](../../docs/MATCHING-STATEMENT-MAP.md) explains the source-to-Lean
correspondence. A proof-task comparison against an independently approved
challenge is a different operation.

## Development source admission and production boundary

The unchanged production parser admits the seven-declaration plain-term
`Proposal` module in a supplemental fixed-inventory snapshot. The full pilot
uses a richer, still pure mathematical syntax, including explicit data
structures and inductive result types. Its direct admission probe is rejected
at `Lean.Parser.Command.structure`.

The separate development profile in `Main.lean` now admits all 14 actual source
files, including the finite-enumeration dependency. It fixes the exact data
declarations, namespace sequences, headers, and declaration inventory. Its
fixture harness passed 13 positive and 91 hostile cases, including an
unknown-import initializer that must remain inert.

`check_source.py` reads ordinary bounded Git blobs from an exact commit using
maintained policy, validates an acyclic import closure with `Init` as the only
external module, and stages a fresh project. Exact copies of the maintained
parser/policy/manifest are used, the admitted source is compiled and exported,
and the independent checker replays all matching declarations. Source hashes
are checked again afterward. Unsafe modes, unlisted files, and invalid sizes
are rejected before compilation. This is host-local development evidence,
not an immutable mount or filesystem/network isolation claim.

The original production parser still rejects the richer source. The proof-only
replay script records that as `production_source_admission`; the separate
development source report records its own accepted profile. Both keep
`development_only: true` and `production_certification: false`. The full pilot's
development acceptance is not inferred from the seven-declaration subset.
No production flag, parser allowlist, or approved production source inventory
has been expanded by these scripts.

[ADMISSION-REVIEW.md](ADMISSION-REVIEW.md) documents the implemented restricted
development profile, observed syntax, negative controls, and remaining limits.
Production integration and native-runner certification remain separate gates.

## Evidence files

Generated reports and large exports can be written to any caller-selected
temporary directory (defaulting to an ignored local output path during manual
runs). Their source/manifest/binary hashes and candidate SHA bind each report to
its actual inputs. These development runs establish `proved-development` status;
they do not establish `production-certified` native-Linux quota isolation or
immutable release evidence.
