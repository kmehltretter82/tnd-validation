# Draft starter queue

**Proposed, not approved.** Nothing here is a published task or in
`audit/tasks.json`. Each statement needs maintainer review before it becomes a
Choir task. All were proved in term mode on Lean 4.35.0 with no Mathlib; `#print
axioms` is a diagnostic here, not the trusted checker's verdict. Reference proofs
are deliberately omitted so that the tasks stay open.

| Topic | Difficulty | Statement | Axioms seen |
| --- | --- | --- | --- |
| Propositional logic | Easy | `theorem notNotEm (p : Prop) : ¬¬(p ∨ ¬p)` | none |
| Predicate logic | Easy | `theorem notExistsIff {α : Type u} (p : α → Prop) : (¬∃ x, p x) ↔ ∀ x, ¬p x` | none |
| Decidability | Easy | `theorem emOfDecidable (p : Prop) [d : Decidable p] : p ∨ ¬p` | none |
| Natural numbers | Easy | `theorem twoMul (n : Nat) : 2 * n = n + n` | none |
| Lists | Easy | `theorem lengthReverse {α : Type u} (l : List α) : l.reverse.length = l.length` | `propext` |
| Witness extraction | Moderate | `def boundedWitness (p : Nat → Bool) (bound : Nat) (h : ∃ n, n < bound ∧ p n = true) : { n : Nat // n < bound ∧ p n = true }` | none |

`boundedWitness` is the one that shows the project's point: it computes a witness
from a bare existence proof, which the bound and decidable predicate make possible.
