# Starter queue

**Approved by the maintainer on 2026-10-31, not yet published.** Each statement is
committed under `tasks/` and registered in `audit/tasks.json`, and becomes a Choir task
only when the maintainer publishes it. All were proved in term mode on Lean 4.35.0 with no Mathlib; `#print
axioms` is a diagnostic here, not the trusted checker's verdict. Reference proofs
are deliberately omitted so that the tasks stay open.

| Topic | Difficulty | Statement | Axioms seen |
| --- | --- | --- | --- |
| Propositional logic | Easy | `theorem notNotEm (p : Prop) : ¬¬(p ∨ ¬p)` | none |
| Predicate logic | Easy | `theorem notExistsIff {α : Type u} (p : α → Prop) : (¬∃ x, p x) ↔ ∀ x, ¬p x` | none |
| Decidability | Easy | `theorem emOfDecidable (p : Prop) [d : Decidable p] : p ∨ ¬p` | none |
| Natural numbers | Easy | `theorem twoMul (n : Nat) : 2 * n = n + n` | none |
| Lists | Easy | `theorem lengthReverse {α : Type u} (l : List α) : l.reverse.length = l.length` | `propext` |
| Witness extraction | Moderate | `theorem selectHeadWitness {n : Nat} (p : Fin n → Prop) [DecidablePred p] (h : ∃ i, p i) : ∃ i, (TNDLib.Finite.select n p).head? = some i ∧ p i` | `propext` |

`selectHeadWitness` is the one that shows the project's point: the library's bounded search
computes a list, and its first entry is a real witness whenever a bare proof says one exists.
A task must be a theorem. The comparator checks a theorem's statement, while a definition's
body is its meaning, so a placeholder definition cannot be compared with its solution.
