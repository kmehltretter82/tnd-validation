# Corpus regression examples

From the repository root, with the pinned Lean toolchain installed, run:

```sh
lake build TNDLib
lake env lean tests/corpus/Examples.lean
lake env lean tests/corpus/Axioms.lean
lake env lean tests/corpus/Automation.lean
```

The example check exits with status zero and no diagnostic output. The axiom
inspection prints diagnostic results; it does not enforce the policy. These
fixtures are outside `TNDLib.lean` and the certified library imports.

`Automation.lean` separately compares `omega`, `simp`, and `decide` with an
explicitly classical control. The control intentionally depends on
`Classical.choice` and must never be imported into the library. Its diagnostic
output is exploratory; the source admission prototype currently rejects tactic
proofs, and the trusted verifier remains necessary for acceptance.

`Examples.lean` contains 11 kernel-checked examples: zero and positive triangular
sums, list splits at zero/inside/beyond the input length, empty and nonempty finite
enumerations, a decidable finite filter, a list product, application of the generic
product/append theorem, and explicit witness-function assembly. Four runtime
assertions additionally execute the sum, split, filter, and product. A wrong
runtime result raises an IO error, causing the command to fail.

The sample equalities exercise concrete inputs. General guarantees come from the
theorems in `TNDLib/`: explicit decidability for the two classical-looking logic
rules, pointwise witness data for function assembly, a lower bound for the
triangular sum, ordered recombination and a prefix-length bound for splitting,
enumeration membership/length and filter membership, and algebraic product laws
under their stated associativity and identity hypotheses. The corpus does not
claim a complete arithmetic, finite-set, or algebra library.

These regression checks do not replace the trusted proof/statement verifier or
the transitive axiom audit. In particular, `#eval` is used here only to exercise
programs; no library theorem relies on native evaluation.

## Recorded development checks

The six corpus modules, root import, all 11 examples, and four runtime assertions
passed on Lean 4.33.1 and Lean 4.35.0. The local macOS 4.35.0 run used a temporary
development assembly. A clean build with the checksum-verified official Linux ARM64
archive has also passed. A clean checkout on the target x86-64 runner has not.

Diagnostic `#print axioms` inspection of all 28 explicitly named exports produced
the same result on both versions: 20 have no axiom dependencies and eight depend
only on `propext`. The eight are the three finite-enumeration/filter theorems and
the five list-splitting exports. This count covers the explicitly named source
declarations; the release audit must also cover generated declarations and their
dependencies.
