# tndlib

`tndlib` is a standalone Lean 4 library for constructive mathematics. Its definitions and proofs are designed to avoid assuming excluded middle for arbitrary propositions. The library has no direct or transitive Mathlib dependency.

**Status:** early development. The initial corpus builds, but the independent verifier and end-to-end contribution workflow are still being validated. Do not treat an unverified build or a GitHub label as proof of certification.

The [2026-11-01 baseline report](docs/BASELINE.md) records exact local snapshots,
fresh-checkout results, and the separation between production's disabled
certification profile and deliberately activated test-repository flags.

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
The separate [stable-matching pilot](audit/matching/README.md) adds an executable
constructor and an arbitrary-size stability proof. Build it explicitly with
`lake build TNDMatchingPilot` and import `TNDLib.Matching.Pilot`. Its sources
remain outside the approved production inventory while full source admission
is reviewed; it is development mathematics, not a certified release.
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

## Contributing and Agent Missions

TND provides a [Choir](https://github.com/Weber-GeoML/Choir)-based contributor loop (`discover → claim → prove → submit → verify → merge`) for reviewed German/DACH mathematical and computer-science paper missions:
- **[Agent Entry Guide (`docs/AGENT-GUIDE.md`)](docs/AGENT-GUIDE.md)** — Exact setup, discovery, lease claiming/renewal/release, local admission & kernel verification, PR submission, and failure recovery.
- **[Contributor Guide (`CONTRIBUTING.md`)](CONTRIBUTING.md)** — Full Choir worker CLI instructions and submission rules.
- **[Starter & Mission Task Queue (`docs/STARTER-QUEUE.md`)](docs/STARTER-QUEUE.md)** — Ready proof tasks across the active missions (`H01` Cantor 1891/92, `L06` Lorenzen 1951, `M01` McConnell–Mehlhorn–Näher–Schweitzer 2011 §9.5) and foundation starter task (`map_exists`).
- **[Screened Paper Backlog (`docs/PAPER-BACKLOG.md`)](docs/PAPER-BACKLOG.md)** and **[Statement Maps (`docs/PACKAGES-STATEMENT-MAPS.md`)](docs/PACKAGES-STATEMENT-MAPS.md)** — 20 screened German/DACH paper records (`audit/papers.json`) and 8 source-mapped statement packages (`audit/missions.json`).

TND distinguishes three verification states: `source-published` (reviewed definitions and open `sorry` task challenges in git), `proved-development` (verified by the isolated source-admission parser and independent kernel proof-object checker while `.choir/certification.json` remains fail-closed), and `production-certified` (native Linux quota-enforced release evidence).

## License

Apache License 2.0; see [LICENSE](LICENSE). TND changes and the pinned Choir
integration are attributed separately; the complete preserved Choir license is
in [`.choir/CHOIR-LICENSE`](.choir/CHOIR-LICENSE).
