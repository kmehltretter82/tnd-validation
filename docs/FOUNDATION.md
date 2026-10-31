# Foundation: initial development evaluation

This document records local evidence and remaining work. It does not constitute a release or certification.

## Chosen starting point

The library uses upstream Lean `leanprover/lean4:v4.35.0` and imports only Lean's bundled `Init` modules. The generated Lake manifest contains no external packages; Mathlib is neither a direct nor a transitive dependency. The platform and Choir tooling are not mathematical imports required by downstream users.

The corpus contains 28 explicitly named declarations across propositional logic, predicate logic, natural-number sums and witnesses, list splitting, bounded enumeration and filtering, and a small algebraic product. These are examples of the first release's intended scope, not a claim of broad mathematical coverage. For finite selection and constructive excluded middle, the decision procedure is an explicit input. Witness-producing definitions return data in `Type`.

## Observations

- The initial corpus, its root module, and the [regression examples](../tests/corpus/README.md) compile on Lean 4.33.1 and 4.35.0. The local macOS 4.35.0 run uses a temporary development assembly. Separately, a clean Linux ARM64 environment using the official Lean 4.35.0 release archive (SHA-256 `c8f0f8a3920e839718b1343e6781fd80a3e9b1024fbcd7078eb30f54e806b028`) built the library and examples. This validates the release archive, not the guarded production runner.
- A minimal downstream Lake project now consumes a temporary source snapshot as
  a real Git dependency pinned to its full commit SHA, builds it, verifies the
  resolved package revision, and rejects any transitive package. Reproduce it
  with `python3 tests/check_downstream.py`. This exercises immutable Git-pin
  consumption without relying on a path dependency; the temporary repository
  is still local, so it does not validate a public tag/release, network fetch,
  or the production source-admission boundary.
- Diagnostic `#print axioms` inspection of the 28 authored declarations reported 20 with no axiom dependencies and eight using only `propext`. The inspection command is `lake env lean tests/corpus/Axioms.lean` after `lake build`. This diagnostic is not the acceptance gate.
- A development run of the independent checker replayed an export containing 37 public declarations, including generated helpers, and reported 29 with no axioms and eight using only `propext`. All 21 maintained proof-object acceptance and rejection fixtures also passed in a network-disabled Linux container. These tests did not exercise the guarded production runner or complete pull-request workflow.
- Lean core includes classical choice, and `propext` remains an allowed axiom under the proposed policy. A no-Mathlib build by itself does not establish constructivity. Statement assumptions and dependencies, definitions, generated declarations, and proof bodies all require checking.
- Useful basic constructions can be defined with Lean core, but there is not yet enough data to estimate how much arithmetic, algebra, automation, or proof-search infrastructure will need to be developed. The first release is deliberately small.

## Automation probe

The [automation fixture](../tests/corpus/Automation.lean) imports only Lean's
bundled `Init` and is **not** imported by the library. On the local Lean 4.35.0
development assembly, `omega` proved a natural-number additive bound with
`propext` and `Quot.sound`; `simp` proved a singleton-list reversal with
`propext`; and `decide` proved a closed arithmetic equality with no axioms.
A deliberate `Classical.em` control reported `Classical.choice` in addition to
`propext` and `Quot.sound`. All four observations come from diagnostic `#print
axioms`, not an acceptance decision. They illustrate that the resulting proof
must be checked for each use; a tactic's name alone does not establish its
dependencies. This control is intentionally nonconstructive and remains
outside the published corpus.

Reproduce with `lake env lean tests/corpus/Automation.lean`. One run using the
temporary development assembly and a warm local cache took 0.22 seconds elapsed
on this host; this is a small diagnostic, not a clean-build or audit benchmark.
The current experimental admission policy accepts plain terms but rejects `by`
tactics, including the tactic examples above. They measure what upstream Lean
can do without Mathlib, not what a contributor submission can currently pass.
Safely broadening admission and measuring the resulting workflow is separate
work; the examples do not establish that arbitrary automation is safe.

For the initial release, keep the current 28 declarations and one example
task as a bounded starting corpus rather than promise broad coverage. Existing
definitions use core list, natural-number, finite-index and logical lemmas;
future work will need wider APIs and tested constructive replacements where a
needed dependency uses choice. There is not enough measured work to give a
credible effort estimate for a Mathlib-scale library or its automation.

## Measured build cost

A clean library build took 2.5 s and 0.48 GiB, and the checker and exporter took 22 s
and 1.6 GiB, on a 3-vCPU Linux ARM64 VM. These are single development measurements;
see [the local Linux evidence](../audit/LOCAL-LINUX-EVIDENCE.md). They are not
measurements of the hosted runner or a selected resource budget.

## Research references and provenance

Riccardo Brasca's [`less_choice` work](https://leanprover-community.github.io/archive/stream/113488-general/topic/Make.20mathlib.20less.20dependent.20on.20choice.html) demonstrates how a classical dependency in a basic proof can propagate widely. SDG's [linter and dependency setup](https://github.com/riccardobrasca/SDG) were studied as design references. Revisions read on 2026-10-30, after the corpus was written, for this record: the
`less_choice` branch and open Mathlib PR #35685 at `c2934be473385c5b1e3a639cad5c00547d65e354`,
and SDG at `e4cd622492aba9be421ec0abcf152f58a0ee98df` (Apache-2.0; toolchain
`riccardobrasca/lean4:v4.35.0-less-choice`; linter `SDG/Linters/choice.lean`; unique-choice
axiom `SDG/Axiom/UniqueChoice.lean`). The revisions used for the original study were not
recorded. No Mathlib or SDG source has been imported into the corpus. The audit tool's comparator adaptation retains its attribution in its source header.

## Open release gates

Before claiming a certified release, run the complete guarded audit from an exact tracked commit with a host-visible installation of the unmodified pinned Lean release on supported native Linux. Validate the parser, byte-and-inode quotas, build/export separation, independent checker, cleanup, and hostile fixtures on that host, then exercise the required acceptance and rejection cases against the actual merge path. Verify a task proof against its approved statement, separately promote it, and re-audit the exact library commit. Do not publish an open task's `sorry` as a library result.

The exact manual freeze, evidence, tag, downstream, and withdrawal sequence is
recorded in [the release procedure](RELEASING.md). It expressly forbids a
release while either certification flag or either development-only marker
remains in place.
