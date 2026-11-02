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

---

## Active German/DACH Paper Missions (`audit/missions.json` & `audit/tasks.json`)

In addition to the foundation starter task (`tasks/map_exists.lean`), three German/DACH paper missions supply 13 open, dependency-ready proof tasks in `tasks/*.lean` (plus 2 solved calibration tasks promoted into `TNDLib/Cantor.lean` and `TNDLib/Lorenzen.lean`):

| Mission | Paper Source | Promoted Calibration Result | Open Ready Tasks (`tasks/*.lean`) |
| --- | --- | --- | --- |
| `mission-h01-cantor` (`H01`) | Cantor (1891/1892, Univ. Halle / DMV) | `TNDLib.Cantor.diagonalDiscrepancy` (`proved-development`) | `cantor_flip_involution`, `cantor_diagonal_spec`, `cantor_discrepancy_ne`, `cantor_no_surjection` |
| `mission-l06-lorenzen` (`L06`) | Lorenzen (1950/1951, Univ. Bonn) | `TNDLib.Lorenzen.orderCancelLeft` (`proved-development`) | `lorenzen_meet_idem`, `lorenzen_meet_comm`, `lorenzen_le_join_left`, `lorenzen_relprime_symm` |
| `mission-m01-certifying` (`M01`) | McConnell–Mehlhorn–Näher–Schweitzer (2011 §9.5, MPI Saarbrücken & Univ. Trier) | Reuses `TNDLib.Cantor.diagonalDiscrepancy` from `H01` (`TNDLib.Certifying.diagonalStreamCert`) | `cert_match_at_pos0`, `cert_match_at_pos1`, `cert_check_match_sound`, `cert_mismatch_offset0_sound`, `cert_cantor_falsifier` |

See [`docs/AGENT-GUIDE.md`](AGENT-GUIDE.md) and [`docs/PACKAGES-STATEMENT-MAPS.md`](PACKAGES-STATEMENT-MAPS.md) for exact task declarations and local verification commands.
