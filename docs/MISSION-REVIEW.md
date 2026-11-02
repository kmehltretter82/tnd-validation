# Independent Mathematical, Provenance, and Security Review (`MISSION-REVIEW`)

Date: 2026-11-01
Reviewer Role: Independent Mathematical & Security Reviewer
Toolchain Pin: `leanprover/lean4:v4.35.0` (`Init` only; no Mathlib)

Repair verification: 2026-11-02, implementation follow-up. Both actionable
review defects are **resolved and locally verified**; see §5. This follow-up
checks the repaired source, statement maps, inventories, proof examples, and
axiom footprints. It does not attribute a second full provenance or security
review to the original independent reviewer. Sections 2–3 retain the original
pre-repair audit findings and back-translations as historical evidence; their
removed declarations and previous package models describe that earlier snapshot.
The current verdicts below and §5 take precedence.

---

## 1. Executive Summary & Review Scope

This document records the independent mathematical, source-provenance, constructivity, and security review of the TND German/DACH paper-mission expansion and Step 2 verification/merge-boundary updates:

1. **20-Paper German/DACH Backlog Catalogue** ([`audit/papers.json`](../audit/papers.json), [`docs/PAPER-BACKLOG.md`](PAPER-BACKLOG.md)):
   - 8 Historical Foundational papers (`H01`–`H08`), 6 Logic & Constructive Foundations papers (`L01`–`L06`), and 6 Modern Algorithm & Certificate papers (`M01`–`M06`).
2. **8 Source-Mapped Statement Packages** ([`audit/missions.json`](../audit/missions.json), [`docs/PACKAGES-STATEMENT-MAPS.md`](PACKAGES-STATEMENT-MAPS.md)):
   - 3 Active Mission modules in `TNDLib`:
     - **Mission `H01` (`mission-h01-cantor`)**: [`TNDLib/Cantor.lean`](../TNDLib/Cantor.lean) — Georg Cantor (1891 lecture / 1892 print), binary stream diagonalization.
     - **Mission `L06` (`mission-l06-lorenzen`)**: [`TNDLib/Lorenzen.lean`](../TNDLib/Lorenzen.lean) — Paul Lorenzen (1950 submitted / 1951 print), constructive lattice-ordered divisibility cone fragment.
     - **Mission `M01` (`mission-m01-certifying`)**: [`TNDLib/Certifying.lean`](../TNDLib/Certifying.lean) — Ross M. McConnell, Kurt Mehlhorn, Stefan Näher, and Pascal Schweitzer (2010 manuscript / 2011 print), executable length-2 pattern matching and mismatch certificates, plus cross-mission reuse of `TNDLib.Cantor`.
   - 5 Isolated Statement-Mapped Packages in `tests/packages/` (outside the proved `TNDLib` import closure):
     - [`tests/packages/M02_ShockHash.lean`](../tests/packages/M02_ShockHash.lean) (`M02`, Lehmann–Sanders–Walzer 2023/2025)
     - [`tests/packages/L01_Schoenfinkel.lean`](../tests/packages/L01_Schoenfinkel.lean) (`L01`, Schönfinkel 1920/1924)
     - [`tests/packages/L03_Ackermann.lean`](../tests/packages/L03_Ackermann.lean) (`L03`, Ackermann 1927/1928)
     - [`tests/packages/H08_PerronMoessner.lean`](../tests/packages/H08_PerronMoessner.lean) (`H08`, Perron 1951/1952)
     - [`tests/packages/H03_Sperner.lean`](../tests/packages/H03_Sperner.lean) (`H03`, Sperner 1927/1928)
3. **13 New Open Tasks & 2 Calibration Tasks** ([`audit/tasks.json`](../audit/tasks.json), `tasks/*.lean`, `tests/tasks/*`):
   - 2 solved calibration challenge/solution pairs (`cantor_diagonal_discrepancy` for `H01` and `lorenzen_order_cancel_left` for `L06`) promoted to `TNDLib.Cantor.diagonalDiscrepancy` and `TNDLib.Lorenzen.orderCancelLeft`.
   - 13 new open tasks across `H01` (4 tasks), `L06` (4 tasks), and `M01` (5 tasks), bringing `audit/tasks.json` to 20 total registered tasks (14 ready/open including `map_exists`, 6 previously solved).
4. **Admission, Import-DAG, and App Merge Preflight Security** ([`audit/admission/Main.lean`](../audit/admission/Main.lean), [`audit/admission/admit.py`](../audit/admission/admit.py), [`audit/admission/policy.json`](../audit/admission/policy.json), [`audit/production-manifest.json`](../audit/production-manifest.json), [`.choir/certification.json`](../.choir/certification.json), [`orchestrator/tnd_verification.py`](../orchestrator/tnd_verification.py), [`orchestrator/config_audit.py`](../orchestrator/config_audit.py)).

### Verification State & Public-Repository Hygiene
- **Verification State Separation**: All proved library theorems and calibration solutions carry status `proved-development` (verified by the isolated source-admission parser and independent kernel proof-object comparator). Open task files in `tasks/*.lean` carry status `source-published`. Production certification remains fail-closed (`source_binding_validated: false`, `resource_boundary_validated: false`, `resource_limits: null` in [`.choir/certification.json`](../.choir/certification.json)) pending native Linux XFS quota validation; no declaration is claimed as `production-certified`.
- **Public-Repository Hygiene**: Inspected `README.md`, `CONTRIBUTING.md`, `docs/*.md`, `audit/*.json`, `audit/README.md`, and `audit/matching/README.md`. Confirmed zero leaks of private workspace paths or internal planning artifacts.

### Summary of Audit Verdict & Actionable Defects

| Audit Area | Verdict | Summary of Findings |
| :--- | :---: | :--- |
| **Constructive Axiom Footprint** | **PASS** | The repaired snapshot compiles under Lean `4.35.0`: 10 active-core theorems, 11 isolated-package theorems, and 15 mission reference/calibration solutions. `#print axioms` reports no axioms for 34 of these 36 named theorems; only `orderCancelLeft` and its calibration solution use `[propext]`. No prohibited axiom occurs in those reports. |
| **Cross-Mission Reuse (`H01` → `M01`)** | **PASS** | `TNDLib/Certifying.lean` genuinely imports `TNDLib.Cantor`, defines `StreamDiscrepancyCert` via `TNDLib.Cantor.DiscrepancyWitness`, proves `diagonalStreamCert` via `TNDLib.Cantor.diagonal` and `TNDLib.Cantor.diagonalDiscrepancy`, and task `cert_cantor_falsifier` pairs `diagonalStreamCert` with `TNDLib.Cantor.diagonal_differ_at`. |
| **Non-Vacuity & Inhabitance** | **PASS** | Active-mission instances execute in `tests/corpus/Examples.lean`; the repair follow-up also checked temporary kernel examples for all five package models, including a nonempty orientation certificate and a singleton antichain (§5.1). |
| **Statement-Map vs. `tests/packages/*.lean` Sync** | **RESOLVED (2026-11-02)** | All five isolated packages now use the documented `TNDPackage.*` namespaces, declaration lists, and mathematical models. Ackermann uses the original three-variable recursion and corrected base values. The package maps include the typed dummy argument in the identity reduction and describe the actual middle-binomial implementation. All five packages compile; see §5. |
| **Open Tasks Already Solved in `TNDLib` Core** | **RESOLVED (2026-11-02)** | The five pre-solved duplicates have been removed from the core and approved inventories. Their reference solutions contain constructive proofs. All 13 mission task files remain open; the approved export inventory has 59 entries. Reference solutions remain isolated under `tests/tasks/`. See §5. |
| **Admission Test Harness (`test_admission.py`)** | **PASS** | `audit/admission/test_admission.py` passes all 69 fixtures (`{"passed": 69, "development_only": true}`), including `import_dag_and_unimported_module_policy` rejecting both unimported library modules and cyclic import graphs. |
| **Security & Merge Preflight Design** | **PASS** | `Main.lean` and `admit.py` enforce a closed, acyclic import DAG and full `TNDLib` aggregator reachability. `tnd_verification.py` and `config_audit.py` cleanly separate runtime `Administration: read` App self-bypass verification (`5555437`) from owner-side unredacted `bypass_actors` verification. |

---

## 2. Independent Back-Translation & Faithfulness Audit (Original Snapshot)

### 2.1 Catalogue-Wide Provenance & Scope Screening (20 Papers)

All 20 entries in [`audit/papers.json`](../audit/papers.json) and [`docs/PAPER-BACKLOG.md`](PAPER-BACKLOG.md) were checked for (i) explicit German/DACH institutional connection with dates and roles, (ii) reconciliation of lecture/submission/dissertation/preprint dates against print dates, (iii) primary source links, and (iv) honest scope classification (`main-theorem-constructive-core`, `supporting-lemma`, or `restricted-constructive-fragment`):

- **Historical Foundational (`H01`–`H08`)**:
  - `H01` (Cantor 1891 Halle DMV lecture / 1892 print, Halle): `main-theorem-constructive-core` — binary sequence diagonalization on pp. 75–76; excludes arbitrary cardinal exponentiation on pp. 77–78.
  - `H02` (Schur 1916 dated / 1917 print, Berlin): `supporting-lemma` — finite-coloring *Hilfssatz* (pp. 114–115) only; excludes the modular Fermat congruence theorem.
  - `H03` (Sperner 1927 submitted / 1928 print, Hamburg): `main-theorem-constructive-core` in catalogue metadata — see §2.9 below regarding the actual `tests/packages/H03_Sperner.lean` file, which only models infinite predicate containment/incomparability on `Nat → Prop` rather than the finite middle-binomial antichain bound.
  - `H04` (Sperner 1928 dissertation/print, Hamburg): `supporting-lemma` — finite 2D simplicial labeling lemma; excludes topological invariance of dimension/domain.
  - `H05` (van der Waerden 1927 issue / 1927–28 volume, Göttingen/Hamburg/Leipzig/Zürich): `main-theorem-constructive-core` — explicit primitive-recursive bound $W(k, r)$ for monochromatic arithmetic progressions.
  - `H06` (Rado 1931 Berlin dissertation / 1933 print): `restricted-constructive-fragment` — single-equation partition regularity with positive integer unknowns; requires constructive replacement of compactness.
  - `H07` (Menger 1926 submitted / 1927 print, Vienna): `restricted-constructive-fragment` — finite graph vertex-separator/disjoint-paths reformulation of Menger's topological curve theorem.
  - `H08` (Perron 1951 Munich Academy session / 1952 print, LMU & BAdW Munich): `main-theorem-constructive-core` in catalogue metadata — see §2.8 below regarding the actual `tests/packages/H08_PerronMoessner.lean` file, which only formalizes the rank-2 triangular sum identity $2 \sum_{k=1}^n k = n(n+1)$, a `restricted-constructive-fragment` rather than the full arbitrary-rank Moessner sieve theorem.
- **Logic & Constructive Foundations (`L01`–`L06`)**:
  - `L01` (Schönfinkel 1920 Göttingen lecture / 1924 print): `restricted-constructive-fragment` — typed combinators and §4 reductions to $C$ ($K$) and $S$; excludes untyped bound-variable elimination metatheory.
  - `L02` (Curry 1929 Göttingen dissertation / 1930 print): `restricted-constructive-fragment` — held in screened backlog to avoid duplicating `L01` pointwise combinators.
  - `L03` (Ackermann 1927 submitted / 1928 print, Göttingen): `restricted-constructive-fragment` — arithmetic hierarchy slices excluding the metamathematical non-primitive-recursiveness proof; see §2.7 below for the discrepancy between the 3-variable specification in `audit/missions.json` and the unary functions in `tests/packages/L03_Ackermann.lean`.
  - `L04` (Gentzen 1933 Göttingen dissertation / 1934–35 print): `restricted-constructive-fragment` — propositional intuitionistic sequent calculus $\mathbf{LJ}$ structural rules and cut elimination.
  - `L05` (Gödel 1930 announced & submitted / 1931 print, Vienna): `restricted-constructive-fragment` — syntactic diagonalization and Satz VI retaining Gödel's explicit $\omega$-consistency hypothesis.
  - `L06` (Lorenzen 1950 submitted / 1951 print, Bonn): `restricted-constructive-fragment` — constructive cone order laws from §1; excludes §2 infinitary systems and full group embedding.
- **Modern Algorithms & Certificates (`M01`–`M06`)**:
  - `M01` (McConnell, Mehlhorn, Näher, Schweitzer 2010 manuscript / 2011 print, MPI-INF Saarbrücken / Saarland / Trier): `restricted-constructive-fragment` — executable witness checking (§2) and length-2 pattern/mismatch certificates (§9.5) plus Cantor stream discrepancy certificates.
  - `M02` (Lehmann, Sanders, Walzer 2023 arXiv / 2025 Algorithmica, KIT Karlsruhe): `restricted-constructive-fragment` — deterministic two-choice bucket selection and pairwise collision-freedom certificates; excludes probabilistic cuckoo thresholds and asymptotic space bounds.
  - `M03` (Meyer, Tran, Tsakalidis 2023 WALCOM / 2024 journal, Frankfurt): `restricted-constructive-fragment` — §3.2 threshold-graph construction/elimination certificate checker; excludes external-memory I/O bounds.
  - `M04` (Geisberger, Sanders, Schultes, Delling 2008 WEA, Karlsruhe/KIT): `restricted-constructive-fragment` — shortcut unpacking and single-vertex contraction witness paths over `Nat` weights.
  - `M05` (Mehlhorn, Neumann, Schmidt 2013 arXiv / 2017 Algorithmica, MPI-INF / TU Ilmenau / Rostock): `restricted-constructive-fragment` — finite construction-trace checker from $K_2^3$ over multigraphs.
  - `M06` (Henzinger, Rao, Wang 2017 SODA / 2019 arXiv v2 / 2020 SICOMP, Vienna / ISTA): `supporting-lemma` — local Unit-Flow push/relabel mass-conservation invariant (§3 of `arXiv:1704.01254v2`).

---

### 2.2 Active Mission `H01` — Cantor's Diagonal Construction (`TNDLib/Cantor.lean`)

- **Primary Source**: Georg Cantor, *Ueber eine elementare Frage der Mannigfaltigkeitslehre*, Jahresbericht der Deutschen Mathematiker-Vereinigung **1** (presented 24 September 1891 in Halle; printed 1892), pp. 75–78.
- **Target Scope**: `main-theorem-constructive-core` (honestly labeled: covers the pp. 75–76 binary-sequence diagonal construction and non-enumerability; excludes pp. 77–78 cardinal exponentiation).

#### Independent AST Back-Translation (`TNDLib/Cantor.lean` & `tasks/cantor_*.lean`)

| Declaration | Lean AST Type / Body | Independent Natural-Language Back-Translation | Source Faithfulness Check |
| :--- | :--- | :--- | :--- |
| `TNDLib.Cantor.flip` | `def flip (b : Bool) : Bool := Bool.casesOn b true false` | Given a boolean $b \in \{\mathsf{false}, \mathsf{true}\}$, returns $\mathsf{true}$ if $b = \mathsf{false}$ and $\mathsf{false}$ if $b = \mathsf{true}$. | Matches p. 75–76: two mutually exclusive characters $\{m, w\}$ with explicit opposite selection $b_\nu \ne a_{\nu,\nu}$. |
| `TNDLib.Cantor.diagonal` | `def diagonal (enum : Nat → Nat → Bool) (n : Nat) : Bool := flip (enum n n)` | Given an indexed family of binary sequences $E : \mathbb{N} \to (\mathbb{N} \to \mathsf{Bool})$, constructs the diagonal sequence $E_0(n) = \mathsf{flip}(E_n(n))$. | Matches p. 76: definition of $E_0 = (b_1, b_2, \dots, b_\nu, \dots)$ where $b_\nu$ is the opposite of $a_{\nu,\nu}$. |
| `TNDLib.Cantor.DiscrepancyAt` | `def DiscrepancyAt (f g : Nat → Bool) (n : Nat) : Prop := f n = flip (g n)` | Binary sequences $f$ and $g$ have a constructive flip-discrepancy at index $n$ iff $f(n) = \mathsf{flip}(g(n))$. | Matches p. 76: explicit coordinate opposition at index $\nu$. |
| `TNDLib.Cantor.DiscrepancyWitness` | `def DiscrepancyWitness (enum : Nat → Nat → Bool) (candidate : Nat → Bool) (n : Nat) : Prop := DiscrepancyAt candidate (enum n) n` | Sequence $\mathit{candidate}$ has a diagonal discrepancy against row $n$ of $\mathit{enum}$ iff $\mathit{candidate}(n) = \mathsf{flip}(\mathit{enum}(n, n))$. | Matches p. 76: comparison of $E_0$ against $E_\nu$ at coordinate $\nu$. |
| `TNDLib.Cantor.flip_ne_self` | `theorem flip_ne_self (b : Bool) : (flip b = b) → False` | For every boolean $b$, $\mathsf{flip}(b) = b$ implies $\bot$. | Faithful constructive negation of self-equality for $\{m, w\}$. |
| `TNDLib.Cantor.flip_involutive` | `theorem flip_involutive (b : Bool) : flip (flip b) = b` | Flipping any boolean twice yields the original boolean. | Faithful involution law on $\{m, w\}$ (note: see §2.10 regarding duplicate open task `cantor_flip_involution`). |
| `TNDLib.Cantor.diagonalDiscrepancy` (Calibration `cantor_diagonal_discrepancy`) | `theorem diagonalDiscrepancy (enum : Nat → Nat → Bool) (n : Nat) : DiscrepancyWitness enum (diagonal enum) n := rfl` | For every enumeration $\mathit{enum}$ and row index $n$, the diagonal sequence $\mathsf{diagonal}(\mathit{enum})$ satisfies the discrepancy witness against row $n$ at index $n$. | Faithful constructive core of Cantor's diagonal witness (p. 76). |
| `TNDLib.Cantor.diagonal_differ_at` | `theorem diagonal_differ_at (enum : Nat → Nat → Bool) (n : Nat) : (diagonal enum n = enum n n) → False` | For every enumeration $\mathit{enum}$ and index $n$, $\mathsf{diagonal}(\mathit{enum})(n) \ne \mathit{enum}(n, n)$. | Matches p. 76: $E_0$ differs from $E_\nu$ in the $\nu$-th coordinate. |
| `TNDTask.cantorFlipInvolution` (`tasks/cantor_flip_involution.lean`) | `theorem cantorFlipInvolution (b : Bool) : flip (flip b) = b` | For all $b : \mathsf{Bool}$, $\mathsf{flip}(\mathsf{flip}(b)) = b$. | Faithful, but duplicates `TNDLib.Cantor.flip_involutive` already in `TNDLib/Cantor.lean` (see §2.10). |
| `TNDTask.cantorDiagonalSpec` (`tasks/cantor_diagonal_spec.lean`) | `theorem cantorDiagonalSpec (enum : Nat → Nat → Bool) (n : Nat) : diagonal enum n = flip (enum n n)` | Unfolds the pointwise equation $\mathsf{diagonal}(\mathit{enum})(n) = \mathsf{flip}(\mathit{enum}(n, n))$. | Faithful definitional specification of $b_\nu$ (p. 76). |
| `TNDTask.cantorDiscrepancyNe` (`tasks/cantor_discrepancy_ne.lean`) | `theorem cantorDiscrepancyNe (f g : Nat → Bool) (n : Nat) : DiscrepancyAt f g n → (f n = g n) → False` | If $f(n) = \mathsf{flip}(g(n))$, then $f(n) = g(n)$ implies $\bot$. | Faithful bridge from flip-discrepancy to coordinate inequality. |
| `TNDTask.cantorNoSurjection` (`tasks/cantor_no_surjection.lean`) | `theorem cantorNoSurjection (enum : Nat → Nat → Bool) (n : Nat) : (enum n = diagonal enum) → False` | For every enumeration $\mathit{enum}$ and index $n$, the $n$-th enumerated stream $\mathit{enum}(n)$ cannot equal $\mathsf{diagonal}(\mathit{enum})$. | Matches Cantor's main non-enumerability conclusion on p. 76 ($E_0$ is not among $E_1, E_2, \dots$). Conclusion is neither weakened nor vacuous. |

---

### 2.3 Active Mission `L06` — Lorenzen's Constructive Cone Order Fragment (`TNDLib/Lorenzen.lean`)

- **Primary Source**: Paul Lorenzen, *Algebraische und logistische Untersuchungen über freie Verbände*, The Journal of Symbolic Logic **16**(2) (submitted 3 August 1950; published June 1951), pp. 81–106 (§1, pp. 81–86).
- **Target Scope**: `restricted-constructive-fragment`.
- **Scope Honesty & Representation Audit**:
  - In §1 (pp. 81–86), Lorenzen studies a commutative cancellative semigroup/group $G$ equipped with a translation-invariant lattice preorder $a \le b$ (modeling divisibility in the positive cone, where $a \wedge b$ is greatest common divisor, $a \vee b$ is least common multiple, and $a \wedge b = 0$ is relative primality), before introducing finite-context deductive entailment relations in §2 (Theorems 2 and 6) to eliminate Zorn's Lemma from the embedding into linearly ordered groups.
  - `TNDLib/Lorenzen.lean` instantiates this cone structure on the single-prime-exponent valuation cone $(\mathbb{N}, \le, +, \min, \max)$ where `LOrder a b` is `a ≤ b`, `meet a b` is `if a ≤ b then a else b` ($\min(a,b)$), `join a b` is `if a ≤ b then b else a` ($\max(a,b)$), and `RelPrime a b` is `∀ x, LOrder x a → LOrder x b → LOrder x 0` ($\min(a,b) \le 0$).
  - Because `TNDLib/Lorenzen.lean` fixes the carrier to `Nat` with its standard linear order `a ≤ b` rather than an abstract lattice-ordered cone or the §2 finite-context entailment calculus over an arbitrary preorder, labeling `L06` as `restricted-constructive-fragment` is **mandatory** and correctly applied in `audit/papers.json` and `audit/missions.json`. However, `audit/missions.json` (lines 209–223) should avoid implying that `meet`/`join` in `TNDLib/Lorenzen.lean` compute number-theoretic $\gcd/\mathrm{lcm}$ on $\mathbb{N}^+$ directly; in `TNDLib/Lorenzen.lean` they compute the additive valuation cone $\min/\max$ on exponent naturals.

#### Independent AST Back-Translation (`TNDLib/Lorenzen.lean` & `tasks/lorenzen_*.lean`)

| Declaration | Lean AST Type / Body | Independent Natural-Language Back-Translation | Source Faithfulness Check |
| :--- | :--- | :--- | :--- |
| `TNDLib.Lorenzen.LOrder` | `def LOrder (a b : Nat) : Prop := a ≤ b` | Natural number $a$ precedes $b$ in the cone order iff $a \le b$. | Models a single linear component of Lorenzen's §1 cone preorder. |
| `TNDLib.Lorenzen.meet` | `def meet (a b : Nat) : Nat := if a ≤ b then a else b` | Returns the minimum of $a$ and $b$ via decidable comparison on $\mathbb{N}$. | Constructive infimum on $(\mathbb{N}, \le)$ (§1, p. 82). |
| `TNDLib.Lorenzen.join` | `def join (a b : Nat) : Nat := if a ≤ b then b else a` | Returns the maximum of $a$ and $b$ via decidable comparison on $\mathbb{N}$. | Constructive supremum on $(\mathbb{N}, \le)$ (§1, p. 82). |
| `TNDLib.Lorenzen.RelPrime` | `def RelPrime (a b : Nat) : Prop := ∀ x : Nat, LOrder x a → LOrder x b → LOrder x 0` | $a$ and $b$ are disjoint (relatively prime in the cone order) iff every common lower bound $x \le a, b$ satisfies $x \le 0$. | Matches Lorenzen's order-theoretic definition of *Teilerfremdheit* $a \wedge b \le e$ (§1, p. 83). |
| `TNDLib.Lorenzen.orderCancelLeft` (Calibration `lorenzen_order_cancel_left`) | `theorem orderCancelLeft (c a b : Nat) : LOrder (c + a) (c + b) → LOrder a b` | Left additive cancellation: if $c + a \le c + b$, then $a \le b$. | Matches §1, p. 81 translation invariance of the semigroup preorder. |
| `TNDLib.Lorenzen.meet_le_left` / `meet_le_right` | `LOrder (meet a b) a` / `LOrder (meet a b) b` | $\mathsf{meet}(a, b) \le a$ and $\mathsf{meet}(a, b) \le b$. | Standard infimum projections (§1, p. 82). |
| `TNDLib.Lorenzen.le_meet` | `LOrder x a → LOrder x b → LOrder x (meet a b)` | Greatest-lower-bound universal property: if $x \le a$ and $x \le b$, then $x \le \mathsf{meet}(a, b)$. | Matches §1, p. 82 infimum universal law. |
| `TNDLib.Lorenzen.meet_idem` / `TNDTask.lorenzenMeetIdem` | `meet a a = a` | Idempotence of meet: $\mathsf{meet}(a, a) = a$. | Faithful lattice law, but duplicated between `TNDLib/Lorenzen.lean` and `tasks/lorenzen_meet_idem.lean` (see §2.10). |
| `TNDLib.Lorenzen.meet_comm` / `TNDTask.lorenzenMeetComm` | `meet a b = meet b a` | Commutativity of meet: $\mathsf{meet}(a, b) = \mathsf{meet}(b, a)$. | Faithful lattice law, duplicated between `TNDLib/Lorenzen.lean` and `tasks/lorenzen_meet_comm.lean` (see §2.10). |
| `TNDLib.Lorenzen.le_join_left` / `TNDTask.lorenzenLeJoinLeft` | `LOrder a (join a b)` | Left upper-bound law for join: $a \le \mathsf{join}(a, b)$. | Faithful lattice law, duplicated between `TNDLib/Lorenzen.lean` and `tasks/lorenzen_le_join_left.lean` (see §2.10). |
| `TNDLib.Lorenzen.le_join_right` | `LOrder b (join a b)` | Right upper-bound law for join: $b \le \mathsf{join}(a, b)$. | Faithful lattice law (§1, p. 82). |
| `TNDTask.lorenzenRelPrimeSymm` (`tasks/lorenzen_relprime_symm.lean`) | `RelPrime a b → RelPrime b a` | Symmetry of relative primality: if every common lower bound of $a, b$ is $\le 0$, then every common lower bound of $b, a$ is $\le 0$. | Genuinely open task in `TNDLib`; proof swaps hypotheses `hxa` and `hxb`. |

---

### 2.4 Active Mission `M01` — Certifying Algorithms (`TNDLib/Certifying.lean`)

- **Primary Source**: Ross M. McConnell, Kurt Mehlhorn, Stefan Näher, and Pascal Schweitzer, *Certifying Algorithms*, Computer Science Review **5**(2) (2010 MPI-INF manuscript; published May 2011), pp. 119–161 (§2, pp. 121–125 & §9.5, pp. 142–143).
- **Target Scope**: `restricted-constructive-fragment`.
- **Scope Honesty Audit**:
  - Correctly labeled `restricted-constructive-fragment`. The paper surveys certifying algorithms across LEDA graph algorithms, planarity, shortest paths, and string matching (§9.5). `TNDLib/Certifying.lean` extracts a minimal, dependency-free constructive slice: fixed length-2 binary pattern matching (`MatchAt2`, `checkMatchAt2`), explicit offset-0/1 mismatch certificates (`MismatchWitness2`), and cross-mission universal stream-table discrepancy certificates (`StreamDiscrepancyCert`, `diagonalStreamCert`) importing `TNDLib.Cantor`. It does not claim coverage of arbitrary-length KMP/BM string matchers or LEDA graph certifiers.

#### Independent AST Back-Translation (`TNDLib/Certifying.lean` & `tasks/cert_*.lean`)

| Declaration | Lean AST Type / Body | Independent Natural-Language Back-Translation | Source Faithfulness Check |
| :--- | :--- | :--- | :--- |
| `TNDLib.Certifying.MatchAt2` | `def MatchAt2 (text : Nat → Bool) (p0 p1 : Bool) (pos : Nat) : Prop := text pos = p0 ∧ text (pos + 1) = p1` | Binary stream $\mathit{text}$ matches the 2-bit pattern $(p_0, p_1)$ at index $\mathit{pos}$ iff $\mathit{text}(\mathit{pos}) = p_0$ and $\mathit{text}(\mathit{pos}+1) = p_1$. | Faithful length-2 specialization of §9.5 (p. 142) exact pattern occurrence at position $\mathit{pos}$. |
| `TNDLib.Certifying.checkMatchAt2` | `def checkMatchAt2 (text : Nat → Bool) (p0 p1 : Bool) (pos : Nat) : Bool := if text pos = p0 then if text (pos + 1) = p1 then true else false else false` | Executable boolean checker returning $\mathsf{true}$ iff both $\mathit{text}(\mathit{pos}) = p_0$ and $\mathit{text}(\mathit{pos}+1) = p_1$ hold. | Faithful executable witness checker (§2.1, p. 122 & §9.5, p. 142). |
| `TNDLib.Certifying.MismatchWitness2` | `def MismatchWitness2 (text : Nat → Bool) (p0 p1 : Bool) (pos : Nat) (offset : Nat) : Prop := (offset = 0 ∧ (text pos = p0 → False)) ∨ (offset = 1 ∧ (text (pos + 1) = p1 → False))` | Explicit non-occurrence witness at position $\mathit{pos}$ specifying either offset $0$ with $\mathit{text}(\mathit{pos}) \ne p_0$ or offset $1$ with $\mathit{text}(\mathit{pos}+1) \ne p_1$. | Matches §9.5 (pp. 142–143): certifying non-occurrence at position $i$ by exhibiting a specific mismatch offset $j$ where $T[i+j] \ne P[j]$. |
| `TNDLib.Certifying.StreamDiscrepancyCert` | `def StreamDiscrepancyCert (table : Nat → Nat → Bool) (candidate : Nat → Bool) (n : Nat) : Prop := TNDLib.Cantor.DiscrepancyWitness table candidate n` | Certificate that binary stream $\mathit{candidate}$ differs from row $n$ of $\mathit{table}$ at position $n$ by taking the flipped bit. | Faithful cross-mission witness predicate combining §2.1 witness checking with Mission `H01`. |
| `TNDLib.Certifying.checkMatchAt2_true` / `TNDTask.certCheckMatchSound` | `checkMatchAt2 text p0 p1 pos = true → MatchAt2 text p0 p1 pos` | If the executable checker returns $\mathsf{true}$, then the propositional specification `MatchAt2` holds. | Faithful checker soundness theorem (§2.1, p. 122), but duplicated between `TNDLib/Certifying.lean` and `tasks/cert_check_match_sound.lean` (see §2.10). |
| `TNDLib.Certifying.diagonalStreamCert` | `theorem diagonalStreamCert (table : Nat → Nat → Bool) (n : Nat) : StreamDiscrepancyCert table (TNDLib.Cantor.diagonal table) n := TNDLib.Cantor.diagonalDiscrepancy table n` | For every pattern table and row $n$, Cantor's diagonal stream produces a valid `StreamDiscrepancyCert` at row $n$. | Genuine cross-mission theorem reuse importing `TNDLib.Cantor.diagonal` and `TNDLib.Cantor.diagonalDiscrepancy`. |
| `TNDTask.certMatchAtPos0` / `certMatchAtPos1` | `MatchAt2 text p0 p1 pos → text pos = p0` / `... → text (pos + 1) = p1` | Projects the first-bit and second-bit equalities from a verified match `MatchAt2`. | Genuinely open projection lemmas. |
| `TNDTask.certMismatchOffset0Sound` | `(text pos = p0 → False) → MatchAt2 text p0 p1 pos → False` | An offset-0 character mismatch refutes `MatchAt2` at `pos`. | Genuinely open negative-certificate soundness lemma (§9.5, p. 142). |
| `TNDTask.certCantorFalsifier` | `StreamDiscrepancyCert table (diagonal table) n ∧ ((diagonal table n = table n n) → False)` | Pairs the cross-mission `StreamDiscrepancyCert` witness with the pointwise inequality $\mathsf{diagonal}(\mathit{table})(n) \ne \mathit{table}(n, n)$. | Genuinely open cross-mission synthesis task combining `TNDLib.Certifying.diagonalStreamCert` and `TNDLib.Cantor.diagonal_differ_at`. |

---

### 2.5 Statement-Mapped Package `M02` — ShockHash (`tests/packages/M02_ShockHash.lean`)

- **Primary Source**: Hans-Peter Lehmann, Peter Sanders, and Stefan Walzer, *ShockHash: Near Optimal-Space Minimal Perfect Hashing Beyond Brute-Force*, Algorithmica **87** (2023 arXiv `2308.09561` / 2024 ALENEX / 2025 Algorithmica), pp. 427–461 (§2–§3, pp. 430–436).
- **Target Scope**: `restricted-constructive-fragment` (correctly excludes probabilistic cuckoo thresholds and asymptotic space analysis).
- **Independent AST Back-Translation of `tests/packages/M02_ShockHash.lean` (`namespace TNDPackages.M02`)**:
  - `selectBucket (h0 h1 : Nat → Nat) (orient : Nat → Bool) (key : Nat) : Nat := Bool.casesOn (orient key) (h0 key) (h1 key)`: evaluates candidate hash function $h_0(\mathit{key})$ when $\mathit{orient}(\mathit{key}) = \mathsf{false}$ and $h_1(\mathit{key})$ when $\mathit{orient}(\mathit{key}) = \mathsf{true}$.
  - `PairCollisionFree (h0 h1 : Nat → Nat) (orient : Nat → Bool) (k1 k2 : Nat) : Prop := (selectBucket h0 h1 orient k1 = selectBucket h0 h1 orient k2) → False`: asserts that keys $k_1, k_2$ map to distinct buckets under orientation bit vector $\mathit{orient}$.
  - `checkPairCollisionFree (h0 h1 : Nat → Nat) (orient : Nat → Bool) (k1 k2 : Nat) : Bool`: executable boolean checker returning $\mathsf{true}$ iff $\mathsf{selectBucket}(h_0, h_1, \mathit{orient}, k_1) \ne \mathsf{selectBucket}(h_0, h_1, \mathit{orient}, k_2)$.
  - `ValidOrientationOn (h0 h1 : Nat → Nat) (orient : Nat → Bool) (k1 k2 : Nat) : Prop := (k1 = k2 → False) → PairCollisionFree h0 h1 orient k1 k2`: if $k_1 \ne k_2$, their selected buckets do not collide.
  - Proved theorems: `selectBucket_false`, `selectBucket_true`, `checkPairCollisionFree_sound`, `validOrientation_no_collision`, plus a concrete kernel-checked `example` on keys `0` and `2` with $h_0(k) = k \bmod 2$, $h_1(k) = (k+1) \bmod 2$.
- **Defect Identified (Statement-Map Desynchronization)**:
  - [`audit/missions.json`](../audit/missions.json) (lines 337–380) and [`docs/PACKAGES-STATEMENT-MAPS.md`](PACKAGES-STATEMENT-MAPS.md) (lines 115–123) document a completely different namespace and declaration list (`TNDPackage.M02ShockHash.TwoChoiceHash`, `SelectorBits`, `selectedSlot`, `CollisionFree`, `PseudoforestOrientationCert`, `orientation_cert_implies_collision_free`, `CollisionFreePair2` over `Fin n → Fin m`) that do not exist in [`tests/packages/M02_ShockHash.lean`](../tests/packages/M02_ShockHash.lean). Moreover, `tests/packages/M02_ShockHash.lean` models pairwise two-choice bucket selection on `Nat → Nat` rather than pseudoforest in-degree $\le 1$ orientation certificates on `Fin n → Fin m`.

---

### 2.6 Statement-Mapped Package `L01` — Schönfinkel's Combinators (`tests/packages/L01_Schoenfinkel.lean`)

- **Primary Source**: Moses Schönfinkel, *Über die Bausteine der mathematischen Logik*, Mathematische Annalen **92** (presented 7 December 1920 in Göttingen; published 1924), pp. 305–316 (§2–§4, pp. 306–312).
- **Target Scope**: `restricted-constructive-fragment` (typed pointwise combinators; excludes untyped syntactic bound-variable elimination).
- **Independent AST Back-Translation of `tests/packages/L01_Schoenfinkel.lean` (`namespace TNDPackages.L01`)**:
  - `K {α β} (x : α) (_ : β) : α := x` (Schönfinkel's *Konstanzfunktion* $C$, §3 p. 309 eq. 2).
  - `S {α β γ} (f : α → β → γ) (g : α → β) (x : α) : γ := f x (g x)` (Schönfinkel's *Verschmelzungsfunktion* $S$, §3 p. 310 eq. 5).
  - `I {α} (x : α) : α := S K (K (β := α) x) x` (Identity combinator reduced to $S$ and $K$, §4 p. 311).
  - `B {α β γ} (f : β → γ) (g : α → β) (x : α) : γ := S (K f) g x` (Schönfinkel's *Zusammensetzungsfunktion* $Z = S (C S) C$ applied pointwise as $S (K f) g x$, §3 p. 310 eq. 4 & §4 p. 311).
  - `C {α β γ} (f : α → β → γ) (y : β) (x : α) : γ := B (S f) K y x` (Schönfinkel's *Vertauschungsfunktion* $T$, §3 p. 309 eq. 3, reduced pointwise via $B (S f) K y x = f x y$).
  - Proved theorems: `k_spec`, `s_spec`, `skk_eq_id` (`S K (K w) x = x`), `i_eq_id`, `b_comp_spec`, `c_swap_spec`, plus 3 concrete `example` declarations.
- **Defects Identified**:
  1. **Statement-Map Desynchronization**: [`audit/missions.json`](../audit/missions.json) (lines 395–455) and [`docs/PACKAGES-STATEMENT-MAPS.md`](PACKAGES-STATEMENT-MAPS.md) (lines 138–150) list `TNDPackage.L01Schoenfinkel.curry`, `uncurry`, `combI`, `combC`, `combT`, `combZ`, `combS`, `schoenfinkel_I_from_CS`, `schoenfinkel_Z_from_CS`, and `schoenfinkel_T_from_CSZ`, none of which match the actual identifiers in `tests/packages/L01_Schoenfinkel.lean`.
  2. **Combinator Reduction Detail**: In `tests/packages/L01_Schoenfinkel.lean`, `def I (x : α) := S K (K x) x` mentions `x` inside the second `K` argument (though `skk_eq_id` on line 42 properly proves `S K (K w) x = x` for an arbitrary dummy constant `w`), and `C` is defined as `B (S f) K y x` (which applies `S` to `f` before `B`) rather than Schönfinkel's closed combinator equation $T = S (Z Z S) (C C)$ on p. 312.

---

### 2.7 Statement-Mapped Package `L03` — Ackermann's Growth Hierarchy (`tests/packages/L03_Ackermann.lean`)

- **Primary Source**: Wilhelm Ackermann, *Zum Hilbertschen Aufbau der reellen Zahlen*, Mathematische Annalen **99** (received 25 March 1927, Göttingen; published 1928), pp. 118–133 (pp. 119–120).
- **Target Scope**: `restricted-constructive-fragment`.
- **Independent AST Back-Translation of `tests/packages/L03_Ackermann.lean` (`namespace TNDPackages.L03`)**:
  - `ack0 (n : Nat) : Nat := n + 1`
  - `ack1 (n : Nat) : Nat := n + 2`
  - `ack2 (n : Nat) : Nat := 2 * n + 3`
  - `iter2 (f : Nat → Nat) (n : Nat) : Nat := f (f n)`
  - Proved theorems: `ack0_gt_self` ($n < \mathsf{ack}_0(n)$), `ack1_eq_iter2_ack0` ($\mathsf{ack}_1(n) = \mathsf{ack}_0(\mathsf{ack}_0(n))$), `ack1_gt_ack0` ($\mathsf{ack}_0(n) < \mathsf{ack}_1(n)$), `ack1_step` ($\mathsf{ack}_1(n+1) = \mathsf{ack}_0(\mathsf{ack}_1(n))$), `ack0_strict_mono`, `ack1_strict_mono`, `ack2_pos` ($0 < 2n+3$), plus 3 concrete `example` checks.
- **Defects Identified (Mathematical Faithfulness & Statement-Map Desynchronization)**:
  1. **Unary Péter–Robinson Slices vs. Ackermann's 1928 3-Variable Hierarchy $\varphi(a, b, n)$**: The actual file [`tests/packages/L03_Ackermann.lean`](../tests/packages/L03_Ackermann.lean) defines unary functions $n + 1$, $n + 2$, and $2n + 3$ (which are the $m = 0, 1, 2$ slices of the later 1935 Péter–Robinson 2-argument function $A(m, n)$), **not** Ackermann's 1928 three-variable function $\varphi(a, b, n)$ on pp. 119–120.
  2. **Desynchronization with `audit/missions.json` and `docs/PACKAGES-STATEMENT-MAPS.md`**: [`audit/missions.json`](../audit/missions.json) (lines 470–513) and [`docs/PACKAGES-STATEMENT-MAPS.md`](PACKAGES-STATEMENT-MAPS.md) (lines 164–173) describe `TNDPackage.L03Ackermann.ackAlpha`, `ackPhi`, `ackPhi_level0`, `ackPhi_level1_zero`, `ackPhi_level2_zero`, `ackPhi_level3_zero` ($\varphi(a, 0, 3) = \alpha(a, 2) = a$), and `AckLevel1Spec` — none of which exist in `tests/packages/L03_Ackermann.lean`.
  3. **Base-Value Note in `audit/papers.json` & `docs/PAPER-BACKLOG.md`**: On p. 120 of Ackermann (1928), $\alpha(a, 0) = 0$, $\alpha(a, 1) = 1$, and $\alpha(a, n) = a$ for $n \ge 2$, so $\varphi(a, 0, n+1) = \alpha(a, n)$ gives $\varphi(a, 0, 1) = 0$, $\varphi(a, 0, 2) = 1$ (so $\varphi(a, b, 2) = a^b$), and $\varphi(a, 0, 3) = a$ (so $\varphi(a, b, 3)$ is $b$-fold iterated exponentiation with base $a$, i.e. $a \uparrow\uparrow (b+1)$). While `audit/missions.json` (lines 498–506) and `docs/PACKAGES-STATEMENT-MAPS.md` (lines 170–171) state $\varphi(a, 0, 2) = 1$ and $\varphi(a, 0, 3) = a$ accurately, `audit/papers.json` (line 344) and `docs/PAPER-BACKLOG.md` (line 136) mistakenly attribute the base value $a$ to $\varphi(a, 0, 2)$ instead of $\varphi(a, 0, 3)$.

---

### 2.8 Statement-Mapped Package `H08` — Perron's Proof of Moessner's Theorem (`tests/packages/H08_PerronMoessner.lean`)

- **Primary Source**: Oskar Perron, *Beweis des Moessnerschen Satzes*, Sitzungsberichte der Mathematisch-Naturwissenschaftlichen Klasse der Bayerischen Akademie der Wissenschaften zu München **1951** (presented 5 October 1951; printed 1952), pp. 31–34.
- **Independent AST Back-Translation of `tests/packages/H08_PerronMoessner.lean` (`namespace TNDPackages.H08`)**:
  - Imports `TNDLib`.
  - `triSum (n : Nat) : Nat := TNDLib.Nat.sumTo n`: computes the triangular partial sum $1 + 2 + \dots + n$.
  - `triSum_zero : triSum 0 = 0 := rfl`.
  - `triSum_succ (n : Nat) : triSum (n + 1) = triSum n + (n + 1) := rfl`.
  - `two_mul_triSum (n : Nat) : 2 * triSum n = n * (n + 1)`: proves by induction on $n$ (`Nat.rec` + `calc`) that twice the $n$-th triangular partial sum equals $n(n+1)$.
- **Defects Identified**:
  1. **Statement-Map Desynchronization**: [`audit/missions.json`](../audit/missions.json) (lines 527–563) and [`docs/PACKAGES-STATEMENT-MAPS.md`](PACKAGES-STATEMENT-MAPS.md) (lines 187–195) document `TNDPackage.H08PerronMoessner.prefixSum`, `oddTerm`, `binom`, `pascal_step`, `moessner_rank2_step`, and `MoessnerRank2Squares` ($\sum_{k=0}^{n-1} (2k+1) = n^2$), none of which appear in `tests/packages/H08_PerronMoessner.lean`.
  2. **Scope Classification**: `tests/packages/H08_PerronMoessner.lean` formalizes only the triangular-number identity $2 \sum_{k=1}^n k = n(n+1)$ (which is the first partial-sum row before dropping every second term to obtain squares $n^2$), so its scope is a `restricted-constructive-fragment` rather than `main-theorem-constructive-core` unless the Moessner sieve / odd-prefix-sum square identity and Pascal recurrence from the statement map are actually placed into `tests/packages/H08_PerronMoessner.lean`.

---

### 2.9 Statement-Mapped Package `H03` — Sperner's Antichain Foundation (`tests/packages/H03_Sperner.lean`)

- **Primary Source**: Emanuel Sperner, *Ein Satz über Untermengen einer endlichen Menge*, Mathematische Zeitschrift **27** (received 17 November 1927; published 1928), pp. 544–548.
- **Independent AST Back-Translation of `tests/packages/H03_Sperner.lean` (`namespace TNDPackages.H03`)**:
  - `Subpred (P Q : Nat → Prop) : Prop := ∀ x : Nat, P x → Q x`: pointwise containment $P \subseteq Q$ of predicates on $\mathbb{N}$.
  - `StrictSubpred (P Q : Nat → Prop) : Prop := Subpred P Q ∧ ∃ x : Nat, Q x ∧ (P x → False)`: strict containment $P \subset Q$ witnessed constructively by $x \in Q \setminus P$.
  - `Incomparable (P Q : Nat → Prop) : Prop := (Subpred P Q → False) ∧ (Subpred Q P → False)`: mutual non-containment of predicates $P$ and $Q$.
  - `AntichainPair (P Q : Nat → Prop) (wPQ wQP : Nat) : Prop := (P wPQ ∧ (Q wPQ → False)) ∧ (Q wQP ∧ (P wQP → False))`: explicit witness pair $(w_{PQ}, w_{QP})$ certifying $w_{PQ} \in P \setminus Q$ and $w_{QP} \in Q \setminus P$.
  - Proved theorems: `subpred_refl`, `subpred_trans`, `strictSubpred_not_subpred`, `antichainPair_symm`, `antichainPair_incomparable`, `incomparable_symm`, plus a concrete `example` proving `Incomparable (fun x => x = 0) (fun x => x = 1)`.
- **Defects Identified**:
  1. **Statement-Map Desynchronization**: [`audit/missions.json`](../audit/missions.json) (lines 578–621) and [`docs/PACKAGES-STATEMENT-MAPS.md`](PACKAGES-STATEMENT-MAPS.md) (lines 209–218) document `TNDPackage.H03Sperner.BitSubset`, `SubsetLe`, `Incomparable`, `PairwiseAntichain`, `middleBinom`, `SpernerBoundSpec` ($|F| \le \binom{n}{\lfloor n/2 \rfloor}$), and `singleton_antichain_bound`, which are absent from `tests/packages/H03_Sperner.lean`.
  2. **Scope Classification**: Because `tests/packages/H03_Sperner.lean` only formalizes general predicate containment and 2-set incomparability witnesses over `Nat → Prop` without a finite ground set `Fin n` or the middle binomial coefficient upper bound $\binom{n}{\lfloor n/2 \rfloor}$, labeling `tests/packages/H03_Sperner.lean` as `main-theorem-constructive-core` overstates its scope unless the finite bitvector antichain bound from `docs/PACKAGES-STATEMENT-MAPS.md` is actually included in `tests/packages/H03_Sperner.lean`.

---

### 2.10 Audit of Open Task Readiness & Core Duplication (13 Open Tasks)

A critical pilot-readiness requirement is that the 3 active missions provide at least 12 genuinely open, non-duplicate, dependency-ready proof tasks. Solved examples do not count as open.

Inspection of `TNDLib/*.lean`, `tasks/*.lean`, and `tests/tasks/*_solution.lean` shows that **5 of the 13 new open tasks already have their exact theorem proved inside `TNDLib`**:

| Open Task ID | Task Declaration (`tasks/*.lean`) | Pre-Existing Proved Theorem in `TNDLib` | Reference Solution Body (`tests/tasks/*_solution.lean`) | Genuinely Unproved in `TNDLib`? |
| :--- | :--- | :--- | :--- | :---: |
| `cantor_flip_involution` | `TNDTask.cantorFlipInvolution` | `TNDLib.Cantor.flip_involutive` (`TNDLib/Cantor.lean:31`) | `TNDLib.Cantor.flip_involutive b` | **NO** (Already proved in `TNDLib.Cantor`) |
| `cantor_diagonal_spec` | `TNDTask.cantorDiagonalSpec` | *(none)* | `rfl` | **YES** |
| `cantor_discrepancy_ne` | `TNDTask.cantorDiscrepancyNe` | *(none)* | `fun h1 h2 => TNDLib.Cantor.flip_ne_self (g n) (Eq.trans (Eq.symm h1) h2)` | **YES** |
| `cantor_no_surjection` | `TNDTask.cantorNoSurjection` | *(none)* | `fun h => TNDLib.Cantor.diagonal_differ_at enum n (Eq.symm (congrFun h n))` | **YES** |
| `lorenzen_meet_idem` | `TNDTask.lorenzenMeetIdem` | `TNDLib.Lorenzen.meet_idem` (`TNDLib/Lorenzen.lean:58`) | `TNDLib.Lorenzen.meet_idem a` | **NO** (Already proved in `TNDLib.Lorenzen`) |
| `lorenzen_meet_comm` | `TNDTask.lorenzenMeetComm` | `TNDLib.Lorenzen.meet_comm` (`TNDLib/Lorenzen.lean:62`) | `TNDLib.Lorenzen.meet_comm a b` | **NO** (Already proved in `TNDLib.Lorenzen`) |
| `lorenzen_le_join_left` | `TNDTask.lorenzenLeJoinLeft` | `TNDLib.Lorenzen.le_join_left` (`TNDLib/Lorenzen.lean:72`) | `TNDLib.Lorenzen.le_join_left a b` | **NO** (Already proved in `TNDLib.Lorenzen`) |
| `lorenzen_relprime_symm` | `TNDTask.lorenzenRelPrimeSymm` | *(none)* | `fun h x hxb hxa => h x hxa hxb` | **YES** |
| `cert_match_at_pos0` | `TNDTask.certMatchAtPos0` | *(none)* | `fun h => h.1` | **YES** |
| `cert_match_at_pos1` | `TNDTask.certMatchAtPos1` | *(none)* | `fun h => h.2` | **YES** |
| `cert_check_match_sound` | `TNDTask.certCheckMatchSound` | `TNDLib.Certifying.checkMatchAt2_true` (`TNDLib/Certifying.lean:27`) | `TNDLib.Certifying.checkMatchAt2_true text p0 p1 pos` | **NO** (Already proved in `TNDLib.Certifying`) |
| `cert_mismatch_offset0_sound` | `TNDTask.certMismatchOffset0Sound` | *(none)* | `fun hne hm => hne hm.1` | **YES** |
| `cert_cantor_falsifier` | `TNDTask.certCantorFalsifier` | *(none)* | `⟨TNDLib.Certifying.diagonalStreamCert table n, TNDLib.Cantor.diagonal_differ_at table n⟩` | **YES** |

**Original Remediation Request (completed; see §5)**: Remove the 5 pre-solved duplicate theorems (`flip_involutive`, `meet_idem`, `meet_comm`, `le_join_left`, `checkMatchAt2_true`) from `TNDLib/Cantor.lean`, `TNDLib/Lorenzen.lean`, and `TNDLib/Certifying.lean` (and update `audit/exports.json`, `audit/admission/policy.json`, `audit/tasks.json`, and `tests/tasks/*_solution.lean` so those 5 reference solutions contain the actual constructive proof terms rather than 1-line delegations to `TNDLib`). Nothing in `TNDLib` or `tests/corpus/Examples.lean` depends on those 5 theorems, so removing them from `TNDLib` makes all 13 mission tasks genuinely open, non-trivial proof obligations.

---

## 3. Non-Vacuity, Constructivity & Cross-Mission Reuse Audit (Original Snapshot)

### 3.1 Non-Vacuity and Domain Inhabitance

Every definition, structure, and theorem premise across the 3 active missions and 5 statement-mapped packages was checked for non-vacuity and concrete inhabitance:

1. **Mission `H01` (`TNDLib/Cantor.lean`)**:
   - [`tests/corpus/Examples.lean`](../tests/corpus/Examples.lean) (lines 36–46, 85–86) instantiates `flip true = false`, `flip false = true`, `diagonal (fun _ _ => false) 3 = true`, `DiscrepancyWitness (fun _ _ => false) (diagonal (fun _ _ => false)) 3`, and `diagonal_differ_at (fun i j => decide (i = j)) 4` by kernel reduction (`rfl`) and compiled `#eval` execution.
2. **Mission `L06` (`TNDLib/Lorenzen.lean`)**:
   - [`tests/corpus/Examples.lean`](../tests/corpus/Examples.lean) (lines 48–62, 87–88) instantiates `meet 4 9 = 4`, `join 4 9 = 9`, `orderCancelLeft 5 3 7` (with an explicit proof of `5 + 3 ≤ 5 + 7`), `meet_le_left 6 2`, and `le_meet 2 6 2` (with explicit proofs of `2 ≤ 6` and `2 ≤ 2`).
   - `RelPrime a b` is non-vacuous and inhabited for any pair with $\min(a, b) = 0$, e.g. `RelPrime 0 b` (`fun x hx0 _ => hx0`).
3. **Mission `M01` (`TNDLib/Certifying.lean`)**:
   - [`tests/corpus/Examples.lean`](../tests/corpus/Examples.lean) (lines 64–74, 89–90) instantiates `checkMatchAt2 (fun i => decide (i % 2 = 0)) true false 4 = true`, derives `MatchAt2 (fun i => decide (i % 2 = 0)) true false 4` via `checkMatchAt2_true`, and instantiates `StreamDiscrepancyCert (fun i j => decide (i = j)) (diagonal (fun i j => decide (i = j))) 2` via `diagonalStreamCert`.
4. **Isolated Statement Packages (`tests/packages/*.lean`)**:
   - `M02_ShockHash.lean` (lines 50–61): Concrete `example` proves `ValidOrientationOn (fun k => k % 2) (fun k => (k + 1) % 2) (fun k => decide (k = 2)) 0 2` via `validOrientation_no_collision ... rfl`.
   - `L01_Schoenfinkel.lean` (lines 60–67): Concrete `example` declarations verify `S K (K true) 7 = 7`, `B (· * 2) (· + 3) 4 = 14`, and `C Nat.sub 3 10 = 7`.
   - `L03_Ackermann.lean` (lines 55–59): Concrete `example` declarations verify `5 < ack0 5`, `ack0 5 < ack1 5`, and `ack2 4 = 11`.
   - `H08_PerronMoessner.lean` (lines 36–37): Concrete `example` verifies `2 * triSum 6 = 6 * 7`.
   - `H03_Sperner.lean` (lines 59–62): Concrete `example` constructs an inhabited `AntichainPair (fun x => x = 0) (fun x => x = 1) 0 1` and derives `Incomparable (fun x => x = 0) (fun x => x = 1)`.

### 3.2 Constructive Axiom Footprint Audit (`leanprover/lean4:v4.35.0`)

All 14 theorems in `TNDLib/Cantor.lean`, `TNDLib/Lorenzen.lean`, and `TNDLib/Certifying.lean`, all 15 task solutions in `tests/tasks/*_solution.lean` (13 open task reference solutions + 2 calibration task solutions), and all 12 theorems in `tests/packages/*.lean` were audited directly with `#print axioms` under `leanprover/lean4:v4.35.0`:

| Module / File | Checked Theorems | Axiom Footprint (`#print axioms`) | Classical / Prohibited Axioms |
| :--- | :--- | :---: | :---: |
| `TNDLib/Cantor.lean` | `flip_ne_self`, `flip_involutive`, `diagonalDiscrepancy`, `diagonal_differ_at` | `[]` (no axioms) | None |
| `TNDLib/Lorenzen.lean` | `orderCancelLeft` | `[propext]` | None |
| `TNDLib/Lorenzen.lean` | `lorder_of_eq_left`, `lorder_of_eq_right`, `meet_le_left`, `meet_le_right`, `le_meet`, `meet_idem`, `meet_comm`, `le_join_left`, `le_join_right` | `[]` (no axioms) | None |
| `TNDLib/Certifying.lean` | `checkMatchAt2_true`, `diagonalStreamCert` | `[]` (no axioms) | None |
| `tests/tasks/cantor_*_solution.lean` (5 files) | `cantorDiagonalDiscrepancy`, `cantorFlipInvolution`, `cantorDiagonalSpec`, `cantorDiscrepancyNe`, `cantorNoSurjection` | `[]` (no axioms) | None |
| `tests/tasks/lorenzen_*_solution.lean` (5 files) | `lorenzenOrderCancelLeft` (`[propext]`); `lorenzenMeetIdem`, `lorenzenMeetComm`, `lorenzenLeJoinLeft`, `lorenzenRelPrimeSymm` (`[]`) | `[]` / `[propext]` | None |
| `tests/tasks/cert_*_solution.lean` (5 files) | `certMatchAtPos0`, `certMatchAtPos1`, `certCheckMatchSound`, `certMismatchOffset0Sound`, `certCantorFalsifier` | `[]` (no axioms) | None |
| `tests/packages/M02_ShockHash.lean` | `selectBucket_false`, `selectBucket_true`, `checkPairCollisionFree_sound`, `validOrientation_no_collision` | `[]` (no axioms) | None |
| `tests/packages/L01_Schoenfinkel.lean` | `k_spec`, `s_spec`, `skk_eq_id`, `i_eq_id`, `b_comp_spec`, `c_swap_spec` | `[]` (no axioms) | None |
| `tests/packages/L03_Ackermann.lean` | `ack0_gt_self`, `ack1_eq_iter2_ack0`, `ack1_gt_ack0`, `ack1_step`, `ack0_strict_mono`, `ack1_strict_mono`, `ack2_pos` | `[]` (no axioms) | None |
| `tests/packages/H08_PerronMoessner.lean` | `triSum_zero`, `triSum_succ` (`[]`); `two_mul_triSum` (`[propext]`) | `[]` / `[propext]` | None |
| `tests/packages/H03_Sperner.lean` | `subpred_refl`, `subpred_trans`, `strictSubpred_not_subpred`, `antichainPair_symm`, `antichainPair_incomparable`, `incomparable_symm` | `[]` (no axioms) | None |

No proof or statement uses `Classical.choice`, `sorryAx`, `Lean.ofReduceBool`, `Lean.trustCompiler`, or any custom `axiom`/`opaque`.

### 3.3 Cross-Mission Reuse Verification (`mission-h01-cantor` → `mission-m01-certifying`)

The cross-mission dependency chain from Mission `H01` (`TNDLib/Cantor.lean`) to Mission `M01` (`TNDLib/Certifying.lean` and `tasks/cert_cantor_falsifier.lean`) is genuine and non-trivial:
1. **Module-Level Import**: [`TNDLib/Certifying.lean`](../TNDLib/Certifying.lean) line 1 declares `import TNDLib.Cantor`, and [`audit/admission/policy.json`](../audit/admission/policy.json) line 164 pins `"imports": ["TNDLib.Cantor"]` for `TNDLib.Certifying`.
2. **Definition-Level Reuse**: `TNDLib.Certifying.StreamDiscrepancyCert` (`TNDLib/Certifying.lean:23–24`) is defined directly as `TNDLib.Cantor.DiscrepancyWitness table candidate n`.
3. **Theorem-Level Reuse**: `TNDLib.Certifying.diagonalStreamCert` (`TNDLib/Certifying.lean:39–41`) has type `StreamDiscrepancyCert table (TNDLib.Cantor.diagonal table) n` and is proved by applying Mission `H01`'s promoted calibration theorem `TNDLib.Cantor.diagonalDiscrepancy table n`.
4. **Task-Level Reuse**: Open task `cert_cantor_falsifier` ([`tasks/cert_cantor_falsifier.lean`](../tasks/cert_cantor_falsifier.lean)) requires proving the conjunction `StreamDiscrepancyCert table (TNDLib.Cantor.diagonal table) n ∧ ((TNDLib.Cantor.diagonal table n = table n n) → False)`, whose reference solution ([`tests/tasks/cert_cantor_falsifier_solution.lean`](../tests/tasks/cert_cantor_falsifier_solution.lean)) pairs `TNDLib.Certifying.diagonalStreamCert table n` with `TNDLib.Cantor.diagonal_differ_at table n` and is replayed end-to-end by the independent kernel comparator in [`tests/audit/check_fixtures.py`](../tests/audit/check_fixtures.py) (`mission_m01_cross_mission_solution`).

---

## 4. Security & Admission Boundary Audit

### 4.1 Source-Admission Parser, Import-DAG Closure, and Unimported-Module Gap (`audit/admission/`)

1. **Closed Acyclic Import-DAG & Root Reachability in `Main.lean` (`lines 321–349`)**:
   - `TNDAdmission.checkImportGraph` verifies that:
     - No duplicate `module_name` entries exist in `specs`.
     - Every module import is either `"Init"` or another approved `module_name` in `specs` (`import outside approved module DAG` otherwise).
     - The import relation among approved modules is strictly acyclic: for every module `m`, `reachableFrom m` (computed by `specs.size`-step transitive closure of non-`Init` imports) does not contain `m` (`import graph contains a cycle involving ...` otherwise).
     - When `"TNDLib"` is present, every module whose name begins with `"TNDLib."` belongs to `reachableFrom "TNDLib"` (`unimported library module: ...` otherwise).
   - This enables inter-module library imports (specifically `TNDLib.Certifying` importing `TNDLib.Cantor`) while guaranteeing that no `TNDLib.*` module can sit unimported outside the `TNDLib` root export closure.
2. **Python Admission Enforcement in `admit.py` (`lines 88–184`)**:
   - `policy_for` checks that `TNDLib.lean` is present and its `imports` set equals the exact set of all non-root library modules (`trusted aggregator does not cover every source module` otherwise), checks that every library module imports only `"Init"` or approved library modules, and verifies acyclicity of `import_map`.
   - `source_bytes` walks `source` and `source / "TNDLib"` without following symlinks (`O_NOFOLLOW`), rejects any symlink, non-regular file, empty/oversized file, or NUL byte, and requires the discovered `.lean` file set `actual` to equal `expected` (`source module inventory mismatch` otherwise). Thus an unlisted file such as `TNDLib/Evil.lean` is rejected before Lean is invoked.
3. **Fail-Closed Certification & Trusted Input Digests**:
   - [`.choir/certification.json`](../.choir/certification.json) remains fail-closed (`"source_binding_validated": false`, `"resource_boundary_validated": false`, `"resource_limits": null`).
   - All 16 SHA-256 digests recorded in [`audit/production-manifest.json`](../audit/production-manifest.json) (`trusted_input_digests`) were independently recomputed and match the exact file bytes on disk.
4. **Adversarial & Import-DAG Regression Suite (`audit/admission/test_admission.py`)**:
   - Executing `python3 audit/admission/test_admission.py --lean ~/.elan/toolchains/leanprover--lean4---v4.35.0/bin/lean` passes all **69** fixtures (`{"passed": 69, "development_only": true}`), including `unimported_module`, `missing_root_import`, `task_exact_bytes`, `task_admit_into`, and `import_dag_and_unimported_module_policy` (verifying rejection of both unimported library modules and cyclic import graphs in `admit.policy_for`).

### 4.2 Merge Preflight & Owner Configuration Audit (`orchestrator/tnd_verification.py`, `orchestrator/config_audit.py`)

1. **Runtime Merge Preflight (`require_app_only_merge_ruleset` in `orchestrator/tnd_verification.py:116–195`)**:
   - Validates that `app_id` (and optional `expected_ruleset_id`) is a positive integer (rejecting `bool`).
   - Requires at least one active (`enforcement == "active"`), branch-targeting (`target == "branch"`) ruleset covering `"~DEFAULT_BRANCH"` or `"refs/heads/main"` with an empty `exclude` list (`_targets_main_branch`) and containing an `"update"` rule.
   - **Two-Mode Bypass Verification**:
     - When `bypass_actors` is present and non-empty (e.g., under admin/owner credentials), it requires `len(bypass) == 1` with `actor_type == "Integration"`, `actor_id == app_id` (`5555437`), and `bypass_mode == "always"` (`verification_mode: "unredacted_bypass_actors"`).
     - When `require_unredacted_actors=False` (runtime merge lane using the short-lived GitHub App installation token with `Administration: read`, where GitHub redacts `bypass_actors` to `None` or `[]`), it accepts the ruleset iff `current_user_can_bypass == "always"` for the authenticated Merge App token (`verification_mode: "app_token_self_bypass"`).
2. **Owner-Side Configuration Audit (`audit_merge_config` in `orchestrator/config_audit.py:34–92`)**:
   - Queries `/branches/main/protection`, `/rulesets`, and `/rulesets/{ruleset_id}` with owner credentials.
   - Calls `require_merge_protection(protection)` to verify strict required status checks (`strict: True`), `enforce_admins.enabled: True`, and all required `BRANCH_PROTECTION_CONTEXTS`.
   - Calls `require_app_only_merge_ruleset(..., app_id=5555437, require_unredacted_actors=True, expected_ruleset_id=expected_ruleset_id)`, which refuses redacted `bypass_actors` lists and verifies that GitHub App `5555437` is the sole bypass actor.
   - Explicitly checks `matched_detail.get("current_user_can_bypass") == "never"`, ensuring the repository owner cannot bypass the ruleset directly.
   - Keeps runtime `Administration: read` on the Merge App installation while providing complete owner-verifiable governance auditability.


---

## 5. Repair Verification and Current Disposition (2026-11-02)

### 5.1 Defect 1 — Package and Statement-Map Synchronization: Resolved

The repaired package sources were read against `audit/missions.json` and
`docs/PACKAGES-STATEMENT-MAPS.md`. A source-declaration inventory comparison
confirmed exact agreement for all advertised named declarations:

| Package | Current namespace | Named declarations | Verified repair |
| :--- | :--- | :---: | :--- |
| `M02` | `TNDPackage.M02ShockHash` | 7 | Finite two-choice maps and selector bits; inverse slot-owner witness certificate; collision-freedom soundness theorem. |
| `L01` | `TNDPackage.L01Schoenfinkel` | 10 | Typed currying/uncurrying and `I`, `C`, `T`, `Z`, `S`; three pointwise reductions. The identity reduction explicitly quantifies the arbitrary dummy `w`. |
| `L03` | `TNDPackage.L03Ackermann` | 7 | Original three-variable `ackPhi` recursion and `ackAlpha`; base values at levels 1, 2, 3 are respectively `0`, `1`, `a`. Both backlog records agree. |
| `H08` | `TNDPackage.H08PerronMoessner` | 6 | Prefix sums of odd integers, Pascal recurrence, and rank-2 step; `MoessnerRank2Squares` is an unproved target proposition. |
| `H03` | `TNDPackage.H03Sperner` | 7 | Finite characteristic vectors, pairwise incomparability, middle coefficient, and singleton bound; `SpernerBoundSpec` is an unproved target proposition. |

The `L01` identity and `H03` middle-coefficient prose were corrected during
this follow-up so their back-translations describe the exact checked code.
The original unary Ackermann slices, triangular-number-only Perron package,
and infinite-predicate Sperner package in §§2.7–2.9 have been replaced.
`H03` and `H08` now state the advertised finite/rank-2 targets; neither target
specification has thereby become a proved theorem. All five packages remain
outside the `TNDLib` import closure and approved production export inventory.

All five package files compile with `lake env lean`. Additional temporary
kernel examples checked nonempty one-key ShockHash certificate soundness,
Schönfinkel composition and argument swapping, Ackermann addition,
multiplication, exponentiation and level-3 computation, an odd prefix sum
`1 + 3 + 5 + 7 + 9 = 25`, Pascal `C(6, 3) = 20`, middle coefficients for
`n = 0, 1, 2, 4, 8`, and an inhabited singleton antichain.
These are finite sanity checks, not proofs of the open specifications.

### 5.2 Defect 2 — Pre-Solved Open-Task Duplicates: Resolved

The following named theorems are absent from `TNDLib/*.lean`,
`audit/exports.json`, `audit/admission/policy.json`, and `audit/tasks.json`;
none of the reference solutions delegates to them:

| Removed core theorem | Open task | Current isolated reference proof |
| :--- | :--- | :--- |
| `TNDLib.Cantor.flip_involutive` | `cantor_flip_involution` | Boolean elimination, with both cases proved by `rfl`. |
| `TNDLib.Lorenzen.meet_idem` | `lorenzen_meet_idem` | Conditional reduction using `Nat.le_refl`. |
| `TNDLib.Lorenzen.meet_comm` | `lorenzen_meet_comm` | Explicit order cases, antisymmetry, and conditional reduction. |
| `TNDLib.Lorenzen.le_join_left` | `lorenzen_le_join_left` | Explicit order cases and equality transport. |
| `TNDLib.Certifying.checkMatchAt2_true` | `cert_check_match_sound` | Explicit symbol-equality cases; impossible checker outcomes eliminated by `Bool.noConfusion`. |

The approved export inventory contains **59 entries**. The task registry has
**20 entries**: 6 previously solved starter tasks, `map_exists`, and **13 open
mission tasks** across `H01` (4), `L06` (4), and `M01` (5). The 13 mission task
files retain their unproved placeholders; constructive reference solutions
are confined to `tests/tasks/*_solution.lean`. All 15 mission reference and
calibration solutions compile independently. These are locally ready proof
obligations; publication and a live contributor claim are separate steps.

### 5.3 Current Axiom and Policy Checks

`#print axioms` was appended to temporary copies of each checked source,
then checked with the pinned `lake env lean` toolchain. The current results
supersede the original snapshot counts and declaration lists in §3.2:

| Scope | Named theorems checked | Axiom footprint |
| :--- | :---: | :--- |
| Three active mission cores | 10 | Nine use no axioms; `TNDLib.Lorenzen.orderCancelLeft` uses `[propext]`. |
| Five isolated packages | 11 | All use no axioms. |
| Thirteen mission reference solutions plus two calibration solutions | 15 | Fourteen use no axioms; `TNDTask.lorenzenOrderCancelLeft` uses `[propext]`. |

All **16** trusted-input SHA-256 digests in `audit/production-manifest.json`
were recomputed and match the current file bytes. Certification remains
**false / false / null**: `source_binding_validated: false`,
`resource_boundary_validated: false`, `resource_limits: null`. The selected
production limits recorded in the manifest are the previously accepted proposal
values (1 GiB / 100,000 inodes for build; 256 MiB / 4,096 inodes for export),
subject to the outstanding native-Linux measurements. Recording that selection
does not activate production resource limits or validate the boundary.

To repeat the direct source-compilation portion from the repository root:

```bash
export PATH="$HOME/.elan/bin:$PATH"
for file in tests/packages/*.lean tests/tasks/cantor*_solution.lean tests/tasks/lorenzen*_solution.lean tests/tasks/cert*_solution.lean; do
  lake env lean "$file" || exit 1
done
```

The full admission, independent replay, promotion, downstream, and regression
suites are recorded separately in the review packet for the exact local
candidate commit. This focused repair verification does not establish a
production source/resource boundary, a successful protected App merge, public
publication of the new tasks, or an outside contributor completing the loop.
