# tndlib

`tndlib` is a standalone Lean 4 library for constructive mathematics. Its definitions and proofs are designed to avoid assuming excluded middle for arbitrary propositions. The library has no direct or transitive Mathlib dependency.

**Status:** early development. The initial corpus builds, but the independent verifier and end-to-end contribution workflow are still being validated. Do not treat an unverified build or a GitHub label as proof of certification.

## Get started

Install [Lean with elan](https://lean-lang.org/install/), then from this repository run:

```sh
lake build
lake env lean tests/corpus/Examples.lean
python3 tests/check_downstream.py
```

`lean-toolchain` pins Lean `v4.35.0`. The library currently uses Lean's bundled `Init` modules and has no external Lean package dependencies. Import `TNDLib` to use the initial library. Its modules cover basic logic, witnesses, natural numbers, lists, finite enumeration, and elementary algebra.

## Constructive policy

For the proposed default policy, audited declarations may depend on `propext` and `Quot.sound`; they may not depend on `Classical.choice`, `sorryAx`, custom axioms, or native-evaluation axioms. The check must include transitive dependencies of both proofs and statements. Explicit hypotheses matter too: assuming excluded middle is not detected as an axiom dependency, so theorem statements must be reviewed.

Lean's bundled core contains classical facilities. A successful build alone therefore does not establish this policy. See [Lean's account of axioms and computation](https://lean-lang.org/theorem_proving_in_lean4/Axioms-and-Computation/) and the verifier documentation as it becomes available.

The [foundation evaluation](docs/FOUNDATION.md) records the initial corpus, local checks, and outstanding release gates.
The [release procedure](docs/RELEASING.md) records the future freeze, evidence,
immutable-pin, publication, and withdrawal steps; current policy explicitly
forbids carrying them out as a certified release.

`TNDLib.Finite.select`, for example, takes a decision procedure for its predicate explicitly. Decidable propositions may have constructive proofs of excluded middle; the policy does not assert its negation.

## Maintainer regression checks

`maintainer-regression` rebuilds the library, examples, downstream consumer,
checker/exporter, admission and proof-object fixtures, promotion rehearsal, and
Python test/style suite. It runs on `main` and on same-repository pull-request
branches only; fork heads are never checked out or executed by this workflow.
Manual dispatch is restricted to `refs/heads/main`.

This matrix is ordinary development CI. It does not run the validated native-
Linux quota boundary, issue proof evidence, enable the certification flags, or
replace the guarded proof-submission workflows.

The workflow installs Lean with `audit/install_lean.py`, which refuses any
archive whose size or SHA-256 differs from the reviewed official release pin for
the runner's architecture. That fixes the installed bytes; it is a supply-chain
control, not certification. The production release gate separately requires the
native-Linux boundary evidence described in the foundation report.

## Contributing

The project is preparing a [Choir](https://github.com/Weber-GeoML/Choir) workflow for approved tasks and independently checked proof submissions. Humans and contributors using their own agents are welcome. The [draft contributor guide](CONTRIBUTING.md) describes the intended workflow; task publication, claiming, and merge checks are not yet ready for a public pilot.

## License

Apache License 2.0; see [LICENSE](LICENSE). TND changes and the pinned Choir
integration are attributed separately; the complete preserved Choir license is
in [`.choir/CHOIR-LICENSE`](.choir/CHOIR-LICENSE).
