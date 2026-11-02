# Source-to-Lean Statement Maps for Initial Missions and Statement Packages

Reviewed on 2026-11-01. This document provides the formal source-to-Lean statement maps, natural-language back-translations, non-vacuity checks, and explicit scope disclosures for the eight initial German/DACH source packages catalogued in [`docs/PAPER-BACKLOG.md`](PAPER-BACKLOG.md) and [`audit/missions.json`](../audit/missions.json):

- **Three Active Missions (`TNDLib` reviewed cores + open task frontier):**
  1. **Package `H01` (`mission-h01-cantor`):** Georg Cantor (1891 lecture / 1892 print), *Ueber eine elementare Frage der Mannigfaltigkeitslehre*.
  2. **Package `L06` (`mission-l06-lorenzen`):** Paul Lorenzen (1950 submitted / 1951 published), *Algebraische und logistische Untersuchungen über freie Verbände*.
  3. **Package `M01` (`mission-m01-certifying`):** Ross M. McConnell, Kurt Mehlhorn, Stefan Näher, and Pascal Schweitzer (2010 manuscript / 2011 published), *Certifying Algorithms* (with cross-mission import from `mission-h01-cantor`).
- **Five Additional Statement-Mapped Packages (`tests/packages/`):**
  4. **Package `M02`:** Hans-Peter Lehmann, Peter Sanders, and Stefan Walzer (2023 preprint / 2025 published), *ShockHash: Near Optimal-Space Minimal Perfect Hashing Beyond Brute-Force*.
  5. **Package `L01`:** Moses Schönfinkel (1920 lecture / 1924 published), *Über die Bausteine der mathematischen Logik*.
  6. **Package `L03`:** Wilhelm Ackermann (1927 submitted / 1928 published), *Zum Hilbertschen Aufbau der reellen Zahlen*.
  7. **Package `H08`:** Oskar Perron (1951 lecture / 1952 print), *Beweis des Moessnerschen Satzes*.
  8. **Package `H03`:** Emanuel Sperner (1927 submitted / 1928 published), *Ein Satz über Untermengen einer endlichen Menge*.

All eight packages compile against Lean 4 `Init` without Mathlib and adhere to the TND constructive contract (`propext` and `Quot.sound` only; no `Classical.choice`, `sorryAx`, or native-evaluation axioms in accepted theorems). Unproved open tasks live in `tasks/` outside the proved `TNDLib` import closure.

---

## 1. Package `H01` — Cantor's Diagonal Construction (`mission-h01-cantor`)

### Primary Source and Provenance
- **Citation:** Georg Cantor, *Ueber eine elementare Frage der Mannigfaltigkeitslehre*, Jahresbericht der Deutschen Mathematiker-Vereinigung **1** (for 1890/91, printed 1892), pp. 75–78.
- **Date Reconciliation:** Lecture delivered on 24 September 1891 at the Halle DMV meeting; volume printed in 1892.
- **Primary Source Link:** [GDZ Göttingen scan (`PPN37721857X_0001`)](https://gdz.sub.uni-goettingen.de/id/PPN37721857X_0001).
- **German/DACH Connection:** Martin-Luther-Universität Halle-Wittenberg and Deutsche Mathematiker-Vereinigung (DMV), Halle (Saale), Germany.
- **Scope Classification:** `main-theorem-constructive-core`. Formalizes the binary-sequence diagonalization on pp. 75–76; excludes the cardinal-exponentiation generalizations for arbitrary uncountable sets on pp. 77–78.

### Source-to-Lean Statement Map (`TNDLib/Cantor.lean` & `tasks/cantor_*.lean`)

| Source Location | Mathematical Content in Source | Lean Declaration | Kind / Status | Natural-Language Back-Translation |
| :--- | :--- | :--- | :--- | :--- |
| p. 75 | Two mutually exclusive characters $m$ and $w$; choosing the opposite character | `TNDLib.Cantor.flip` | `def` (Reviewed Core) | Maps `Bool` to its opposite (`true ↦ false`, `false ↦ true`) via `Bool.rec`. |
| p. 76 | Diagonal sequence $E_0 = (b_1, b_2, \dots)$ with $b_\nu \ne a_{\nu,\nu}$ | `TNDLib.Cantor.diagonal` | `def` (Reviewed Core) | Given an enumeration `enum : Nat → Nat → Bool`, defines the binary stream `fun n => flip (enum n n)`. |
| p. 76 | Coordinate-level discrepancy between two sequences at index $\nu$ | `TNDLib.Cantor.DiscrepancyAt` | `def` (Reviewed Core) | `DiscrepancyAt f g n` holds iff `f n = flip (g n)`. |
| p. 76 | Row discrepancy between candidate stream and $\nu$-th enumerated row $E_\nu$ at coordinate $\nu$ | `TNDLib.Cantor.DiscrepancyWitness` | `def` (Reviewed Core) | `DiscrepancyWitness enum candidate n` holds iff `DiscrepancyAt candidate (enum n) n`. |
| p. 75–76 | Mutual exclusivity of $m$ and $w$ ($b_\nu \ne a_{\nu,\nu}$) | `TNDLib.Cantor.flip_ne_self` | `theorem` (Reviewed Core) | For every `b : Bool`, `flip b = b → False`. |
| p. 76 | Constructive witness that $E_0$ satisfies the diagonal discrepancy against every row $E_\nu$ | `TNDLib.Cantor.diagonalDiscrepancy` | `theorem` (Promoted Calibration `cantor_diagonal_discrepancy`) | For every `enum : Nat → Nat → Bool` and `n : Nat`, `DiscrepancyWitness enum (diagonal enum) n`. |
| p. 76 | Pointwise inequality $E_0(\nu) \ne E_\nu(\nu)$ | `TNDLib.Cantor.diagonal_differ_at` | `theorem` (Reviewed Core) | For every `enum` and `n`, `diagonal enum n = enum n n → False`. |
| p. 75 | Double-negation/involution of character flip | `TNDTask.cantorFlipInvolution` (`tasks/cantor_flip_involution.lean`) | Open Task (`cantor_flip_involution`) | For every `b : Bool`, `flip (flip b) = b`. |
| p. 76 | Explicit coordinate equation for $E_0(\nu)$ | `TNDTask.cantorDiagonalSpec` (`tasks/cantor_diagonal_spec.lean`) | Open Task (`cantor_diagonal_spec`) | For every `enum` and `n`, `diagonal enum n = flip (enum n n)`. |
| p. 76 | Discrepancy witness at $\nu$ refutes coordinate agreement at $\nu$ | `TNDTask.cantorDiscrepancyNe` (`tasks/cantor_discrepancy_ne.lean`) | Open Task (`cantor_discrepancy_ne`) | If `DiscrepancyAt f g n` holds, then `f n = g n → False`. |
| p. 76 | Non-enumerability: $E_0 \ne E_\nu$ for every index $\nu$ | `TNDTask.cantorNoSurjection` (`tasks/cantor_no_surjection.lean`) | Open Task (`cantor_no_surjection`) | For every `enum : Nat → Nat → Bool` and `n : Nat`, `(enum n = diagonal enum) → False`. |

---

## 2. Package `L06` — Lorenzen's Constructive Lattice-Ordered Divisibility Fragment (`mission-l06-lorenzen`)

### Primary Source and Provenance
- **Citation:** Paul Lorenzen, *Algebraische und logistische Untersuchungen über freie Verbände*, The Journal of Symbolic Logic **16**(2) (June 1951), pp. 81–106.
- **Date Reconciliation:** Submitted 3 August 1950 from the University of Bonn; published June 1951. Numbered English translation at [arXiv:1710.08138](https://arxiv.org/pdf/1710.08138).
- **Primary Source Link:** [JSTOR (`2266681`)](https://www.jstor.org/stable/2266681) / [arXiv:1710.08138](https://arxiv.org/pdf/1710.08138).
- **German/DACH Connection:** Rheinische Friedrich-Wilhelms-Universität Bonn, Germany.
- **Scope Classification:** `restricted-constructive-fragment`. Formalizes the §1 (pp. 81–86) constructive additive and lattice-order laws on the natural-number divisibility cone (`LOrder`, `meet`, `join`, `RelPrime`, and additive cancellation); excludes the infinitary inductive entailment systems and embedding theorems of §2–§3.

### Source-to-Lean Statement Map (`TNDLib/Lorenzen.lean` & `tasks/lorenzen_*.lean`)

| Source Location | Mathematical Content in Source | Lean Declaration | Kind / Status | Natural-Language Back-Translation |
| :--- | :--- | :--- | :--- | :--- |
| §1, p. 81 | Preorder relation $a \le b$ on the positive divisibility cone | `TNDLib.Lorenzen.LOrder` | `def` (Reviewed Core) | `LOrder a b` is the constructive order $a \le b$ on `Nat`. |
| §1, p. 82 | Infimum (greatest common divisor) $a \wedge b$ | `TNDLib.Lorenzen.meet` | `def` (Reviewed Core) | Constructive lattice meet `if a ≤ b then a else b`. |
| §1, p. 82 | Supremum (least common multiple) $a \vee b$ | `TNDLib.Lorenzen.join` | `def` (Reviewed Core) | Constructive lattice join `if a ≤ b then b else a`. |
| §1, p. 83 | Relative primality (*Teilerfremdheit*) $a \wedge b \le 0$ | `TNDLib.Lorenzen.RelPrime` | `def` (Reviewed Core) | `RelPrime a b` holds iff for every `x : Nat`, `LOrder x a → LOrder x b → LOrder x 0`. |
| §1, p. 81 | Left equality transport for cone order ($x = y \land y \le z \implies x \le z$) | `TNDLib.Lorenzen.lorder_of_eq_left` | `theorem` (Reviewed Core) | For all `x y z : Nat`, `x = y → LOrder y z → LOrder x z`. |
| §1, p. 81 | Right equality transport for cone order ($x \le y \land z = y \implies x \le z$) | `TNDLib.Lorenzen.lorder_of_eq_right` | `theorem` (Reviewed Core) | For all `x y z : Nat`, `LOrder x y → z = y → LOrder x z`. |
| §1, p. 81 | Left cancellation of addition in the cone order ($c + a \le c + b \implies a \le b$) | `TNDLib.Lorenzen.orderCancelLeft` | `theorem` (Promoted Calibration `lorenzen_order_cancel_left`) | For all `c a b : Nat`, `LOrder (c + a) (c + b) → LOrder a b`. |
| §1, p. 82 | Meet left projection $a \wedge b \le a$ | `TNDLib.Lorenzen.meet_le_left` | `theorem` (Reviewed Core) | For all `a b : Nat`, `LOrder (meet a b) a`. |
| §1, p. 82 | Meet right projection $a \wedge b \le b$ | `TNDLib.Lorenzen.meet_le_right` | `theorem` (Reviewed Core) | For all `a b : Nat`, `LOrder (meet a b) b`. |
| §1, p. 82 | Universal greatest-lower-bound law ($x \le a \land x \le b \implies x \le a \wedge b$) | `TNDLib.Lorenzen.le_meet` | `theorem` (Reviewed Core) | For all `x a b : Nat`, `LOrder x a → LOrder x b → LOrder x (meet a b)`. |
| §1, p. 82 | Idempotence of meet ($a \wedge a = a$) | `TNDTask.lorenzenMeetIdem` (`tasks/lorenzen_meet_idem.lean`) | Open Task (`lorenzen_meet_idem`) | For all `a : Nat`, `meet a a = a`. |
| §1, p. 82 | Commutativity of meet ($a \wedge b = b \wedge a$) | `TNDTask.lorenzenMeetComm` (`tasks/lorenzen_meet_comm.lean`) | Open Task (`lorenzen_meet_comm`) | For all `a b : Nat`, `meet a b = meet b a`. |
| §1, p. 82 | Join left embedding $a \le a \vee b$ | `TNDTask.lorenzenLeJoinLeft` (`tasks/lorenzen_le_join_left.lean`) | Open Task (`lorenzen_le_join_left`) | For all `a b : Nat`, `LOrder a (join a b)`. |
| §1, p. 83 | Symmetry of relative primality | `TNDTask.lorenzenRelPrimeSymm` (`tasks/lorenzen_relprime_symm.lean`) | Open Task (`lorenzen_relprime_symm`) | For all `a b : Nat`, `RelPrime a b → RelPrime b a`. |

---

## 3. Package `M01` — Certifying Algorithms: String Matching & Discrepancy Certificates (`mission-m01-certifying`)

### Primary Source and Provenance
- **Citation:** Ross M. McConnell, Kurt Mehlhorn, Stefan Näher, and Pascal Schweitzer, *Certifying Algorithms*, Computer Science Review **5**(2) (May 2011), pp. 119–161.
- **Date Reconciliation:** 2010 MPI-INF manuscript; published May 2011 in *Computer Science Review*.
- **Primary Source Link:** [MPI-INF author manuscript (`CertifyingAlgorithms.pdf`)](https://people.mpi-inf.mpg.de/~mehlhorn/ftp/CertifyingAlgorithms.pdf).
- **German/DACH Connection:** Max-Planck-Institut für Informatik (MPI-INF), Universität des Saarlandes (Saarbrücken), and Universität Trier, Germany.
- **Scope Classification:** `restricted-constructive-fragment`. Formalizes executable witness checking (§2, pp. 121–125) and 2-character pattern occurrence / mismatch certificates (§9.5, pp. 142–143), and demonstrates cross-mission theorem reuse by importing `TNDLib.Cantor` (`mission-h01-cantor`) to certify universal pattern-table falsifiers.

### Source-to-Lean Statement Map (`TNDLib/Certifying.lean` & `tasks/cert_*.lean`)

| Source Location | Mathematical Content in Source | Lean Declaration | Kind / Status | Natural-Language Back-Translation |
| :--- | :--- | :--- | :--- | :--- |
| §9.5, p. 142 | Exact 2-symbol pattern occurrence at text position `pos` | `TNDLib.Certifying.MatchAt2` | `def` (Reviewed Core) | `MatchAt2 text p0 p1 pos` holds iff `text pos = p0 ∧ text (pos + 1) = p1`. |
| §2.1, p. 122 & §9.5, p. 142 | Executable boolean witness checker for pattern occurrence | `TNDLib.Certifying.checkMatchAt2` | `def` (Reviewed Core) | Tests `text pos = p0` and `text (pos + 1) = p1`, returning `true` iff both match. |
| §9.5, pp. 142–143 | Explicit mismatch-offset certificate refuting a match at `pos` | `TNDLib.Certifying.MismatchWitness2` | `def` (Reviewed Core) | Witness that either `offset = 0 ∧ (text pos = p0 → False)` or `offset = 1 ∧ (text (pos + 1) = p1 → False)`. |
| §2.1, p. 122 + Cantor p. 76 | Cross-mission certificate that a stream falsifies row `n` of a pattern table at position `n` | `TNDLib.Certifying.StreamDiscrepancyCert` | `def` (Reviewed Core, imports `TNDLib.Cantor`) | Defined as `TNDLib.Cantor.DiscrepancyWitness table candidate n`. |
| §2.1, p. 122 + Cantor p. 76 | Universal falsifier certificate via Cantor's diagonal stream | `TNDLib.Certifying.diagonalStreamCert` | `theorem` (Reviewed Core, reuses `TNDLib.Cantor.diagonalDiscrepancy`) | For every `table : Nat → Nat → Bool` and `n : Nat`, `StreamDiscrepancyCert table (TNDLib.Cantor.diagonal table) n`. |
| §9.5, p. 142 | First-character projection of a verified occurrence | `TNDTask.certMatchAtPos0` (`tasks/cert_match_at_pos0.lean`) | Open Task (`cert_match_at_pos0`) | `MatchAt2 text p0 p1 pos → text pos = p0`. |
| §9.5, p. 142 | Second-character projection of a verified occurrence | `TNDTask.certMatchAtPos1` (`tasks/cert_match_at_pos1.lean`) | Open Task (`cert_match_at_pos1`) | `MatchAt2 text p0 p1 pos → text (pos + 1) = p1`. |
| §2.1, p. 122 & §9.5, p. 142 | Soundness of executable match checker | `TNDTask.certCheckMatchSound` (`tasks/cert_check_match_sound.lean`) | Open Task (`cert_check_match_sound`) | `checkMatchAt2 text p0 p1 pos = true → MatchAt2 text p0 p1 pos`. |
| §9.5, pp. 142–143 | Soundness of offset-0 mismatch refutation | `TNDTask.certMismatchOffset0Sound` (`tasks/cert_mismatch_offset0_sound.lean`) | Open Task (`cert_mismatch_offset0_sound`) | `(text pos = p0 → False) → MatchAt2 text p0 p1 pos → False`. |
| §2.1, p. 122 + Cantor p. 76 | Paired discrepancy certificate and pointwise falsification witness | `TNDTask.certCantorFalsifier` (`tasks/cert_cantor_falsifier.lean`) | Open Task (`cert_cantor_falsifier`, cross-mission consumer) | `StreamDiscrepancyCert table (diagonal table) n ∧ ((diagonal table n = table n n) → False)`. |

---

## 4. Package `M02` — ShockHash Two-Choice & Pseudoforest Orientation Certificates

### Primary Source and Provenance
- **Citation:** Hans-Peter Lehmann, Peter Sanders, and Stefan Walzer, *ShockHash: Near Optimal-Space Minimal Perfect Hashing Beyond Brute-Force*, Algorithmica **87** (2025), pp. 427–461.
- **Date Reconciliation:** Posted as arXiv preprint `2308.09561` in August 2023 and presented at ALENEX 2024; journal version published in *Algorithmica* 87 in 2025.
- **Primary Source Link:** [Springer Open Access (`10.1007/s00453-025-01321-z`)](https://link.springer.com/article/10.1007/s00453-025-01321-z) / [KIT repository (`1000187076`)](https://publikationen.bibliothek.kit.edu/1000187076).
- **German/DACH Connection:** Karlsruher Institut für Technologie (KIT), Karlsruhe, Germany.
- **Scope Classification:** `restricted-constructive-fragment`. Formalizes the deterministic 1-bit two-choice hash selector model, collision-free slot assignment, and pseudoforest orientation certificates (§2–§3, pp. 430–436). Probabilistic cuckoo-graph threshold bounds and expected running-time asymptotics are excluded.

### Source-to-Lean Statement Map (`tests/packages/M02_ShockHash.lean`)

| Source Location | Mathematical Content in Source | Lean Declaration | Kind / Status | Natural-Language Back-Translation |
| :--- | :--- | :--- | :--- | :--- |
| §2, p. 430 | Pair of candidate hash functions $h_0, h_1 : [n] \to [m]$ | `TNDPackage.M02ShockHash.TwoChoiceHash` | `structure` | Stores two candidate slot maps `h0 h1 : Fin n → Fin m` for `n` keys and `m` slots. |
| §3, p. 432 | 1-bit choice vector $s \in \{0, 1\}^n$ selecting between $h_0$ and $h_1$ | `TNDPackage.M02ShockHash.SelectorBits` | `def` | Function `Fin n → Bool` assigning one selector bit to each key. |
| §3, p. 432 | Evaluated slot $h_{s(i)}(i)$ for key $i$ | `TNDPackage.M02ShockHash.selectedSlot` | `def` | Returns `H.h1 i` if `s i = true`, and `H.h0 i` if `s i = false`. |
| §2, p. 430 | Collision-free (injective) placement of keys into slots | `TNDPackage.M02ShockHash.CollisionFree` | `def` | For all `i j : Fin n`, `selectedSlot H s i = selectedSlot H s j → i = j`. |
| §3.1, p. 433 | Pseudoforest 1-orientation certificate (each slot has at most one incoming oriented edge) | `TNDPackage.M02ShockHash.PseudoforestOrientationCert` | `structure` | Bundles selector bits `s`, inverse slot owner table `slotOwner : Fin m → Option (Fin n)`, and proof `owner_correct : ∀ i, slotOwner (selectedSlot H s i) = some i`. |
| §3.1, p. 433 | Soundness of pseudoforest orientation certificate | `TNDPackage.M02ShockHash.orientation_cert_implies_collision_free` | `theorem` (Proved in package) | Any `TwoChoiceHash` equipped with a `PseudoforestOrientationCert` satisfies `CollisionFree H cert.s`. |
| §3, p. 432 | Two-key non-collision specialization | `TNDPackage.M02ShockHash.CollisionFreePair2` | `def` | Two selected slots `slot0` and `slot1` are collision-free when `slot0 = slot1 → False`. |

---

## 5. Package `L01` — Schönfinkel's Typed Combinators $I, C, T, Z, S$

### Primary Source and Provenance
- **Citation:** Moses Schönfinkel, *Über die Bausteine der mathematischen Logik*, Mathematische Annalen **92** (1924), pp. 305–316.
- **Date Reconciliation:** Lecture presented to the Göttingen Mathematical Society on 7 December 1920; prepared with Heinrich Behmann in March 1924 and published in *Mathematische Annalen* 92 in 1924.
- **Primary Source Link:** [LMU Munich scan (`1924 - Schoenfinkel - Ueber die Bausteine der mathematischen Logik.pdf`)](https://www.cip.ifi.lmu.de/~langeh/test/1924%20-%20Schoenfinkel%20-%20Ueber%20die%20Bausteine%20der%20mathematischen%20Logik.pdf).
- **German/DACH Connection:** Georg-August-Universität Göttingen and Mathematische Gesellschaft in Göttingen, Germany.
- **Scope Classification:** `restricted-constructive-fragment`. Formalizes typed currying/uncurrying (§2, p. 306), the five fundamental combinators $I, C, T, Z, S$ (§3, pp. 308–310), and Schönfinkel's §4 reductions of $I$, $Z$, and $T$ to $C$ and $S$ alone (pp. 311–312). Notation translation is documented explicitly: Schönfinkel's constancy combinator $C$ is modern $K$, swap $T$ (*Vertauschungsfunktion*) is modern $C$, and composition $Z$ (*Zusammensetzungsfunktion*) is modern $B$.

### Source-to-Lean Statement Map (`tests/packages/L01_Schoenfinkel.lean`)

| Source Location | Mathematical Content in Source | Lean Declaration | Kind / Status | Natural-Language Back-Translation |
| :--- | :--- | :--- | :--- | :--- |
| §2, p. 306 | Currying $f(x, y) \mapsto (x \mapsto (y \mapsto f(x, y)))$ | `TNDPackage.L01Schoenfinkel.curry` | `def` | Converts `f : α × β → γ` into `fun a b => f (a, b)`. |
| §2, p. 306 | Uncurrying $(x \mapsto (y \mapsto g x y)) \mapsto ((x, y) \mapsto g x y)$ | `TNDPackage.L01Schoenfinkel.uncurry` | `def` | Converts `g : α → β → γ` into `fun p => g p.1 p.2`. |
| §3, p. 308, eq. (1) | *Identitätsfunktion* $I x = x$ | `TNDPackage.L01Schoenfinkel.combI` | `def` | Identity combinator `fun x => x`. |
| §3, p. 309, eq. (2) | *Konstanzfunktion* $(C x) y = x$ (modern $K$) | `TNDPackage.L01Schoenfinkel.combC` | `def` | Constancy combinator `fun x _ => x`. |
| §3, p. 309, eq. (3) | *Vertauschungsfunktion* $(T f) x y = f y x$ (modern $C$) | `TNDPackage.L01Schoenfinkel.combT` | `def` | Argument-swapping combinator `fun f x y => f y x`. |
| §3, p. 310, eq. (4) | *Zusammensetzungsfunktion* $Z f g x = f(g x)$ (modern $B$) | `TNDPackage.L01Schoenfinkel.combZ` | `def` | Function-composition combinator `fun f g x => f (g x)`. |
| §3, p. 310, eq. (5) | *Verschmelzungsfunktion* $S f g x = (f x)(g x)$ | `TNDPackage.L01Schoenfinkel.combS` | `def` | Fusion/application combinator `fun f g x => (f x) (g x)`. |
| §4, p. 311 | Reduction of $I$ to $C$ and $S$: $I x = (S C C) x$ | `TNDPackage.L01Schoenfinkel.schoenfinkel_I_from_CS` | `theorem` (Proved in package) | For arbitrary dummy `w : β`, the typed pointwise identity `combS combC (combC (α := β) (β := α) w) x = combI x`. |
| §4, p. 311 | Reduction of $Z$ to $C$ and $S$: $Z = S (C S) C$ | `TNDPackage.L01Schoenfinkel.schoenfinkel_Z_from_CS` | `theorem` (Proved in package) | Pointwise identity `combS (combC combS) combC f g x = combZ f g x`. |
| §4, p. 312 | Reduction of $T$ to $C, S, Z$: $T = S (Z Z S) (C C)$ | `TNDPackage.L01Schoenfinkel.schoenfinkel_T_from_CSZ` | `theorem` (Proved in package) | Pointwise identity `combS (combZ combZ combS) (combC combC) f x y = combT f x y`. |

---

## 6. Package `L03` — Ackermann's Original 3-Variable Hierarchy $\varphi(a, b, n)$

### Primary Source and Provenance
- **Citation:** Wilhelm Ackermann, *Zum Hilbertschen Aufbau der reellen Zahlen*, Mathematische Annalen **99** (1928), pp. 118–133.
- **Date Reconciliation:** Received 25 March 1927 (Göttingen byline); published in *Mathematische Annalen* 99 in 1928.
- **Primary Source Link:** [Primary scan (`Ackermann1928_126.pdf`)](https://eretrandre.org/rb/files/Ackermann1928_126.pdf).
- **German/DACH Connection:** Georg-August-Universität Göttingen, Germany.
- **Scope Classification:** `restricted-constructive-fragment`. Formalizes Ackermann's original 3-variable function $\varphi(a, b, n)$ and its initial-value helper $\alpha(a, n)$ on pp. 119–120, preserving the historical base values ($\varphi(a, 0, 1) = 0$, $\varphi(a, 0, 2) = 1$, $\varphi(a, 0, n+1) = a$ for $n \ge 2$). Excludes the metamathematical proof (pp. 121–133) that $\varphi$ majorizes every primitive recursive function.

### Source-to-Lean Statement Map (`tests/packages/L03_Ackermann.lean`)

| Source Location | Mathematical Content in Source | Lean Declaration | Kind / Status | Natural-Language Back-Translation |
| :--- | :--- | :--- | :--- | :--- |
| p. 120 | Base-value helper $\alpha(a, n) = 0$ ($n=0$), $1$ ($n=1$), $a$ ($n \ge 2$) | `TNDPackage.L03Ackermann.ackAlpha` | `def` | Returns `0` for `n = 0`, `1` for `n = 1`, and `a` for `n + 2`. |
| p. 120 | Simultaneous recursion for $\varphi(a, b, n)$ | `TNDPackage.L03Ackermann.ackPhi` | `def` | Defines $\varphi(a, b, 0) = a + b$, $\varphi(a, 0, n+1) = \alpha(a, n)$, and $\varphi(a, b+1, n+1) = \varphi(a, \varphi(a, b, n+1), n)$. |
| p. 119, eq. (1) | Level-0 identity $\varphi(a, b, 0) = a + b$ | `TNDPackage.L03Ackermann.ackPhi_level0` | `theorem` (Proved in package) | For all `a b : Nat`, `ackPhi a b 0 = a + b`. |
| p. 119 | Level-1 base value $\varphi(a, 0, 1) = 0$ | `TNDPackage.L03Ackermann.ackPhi_level1_zero` | `theorem` (Proved in package) | For all `a : Nat`, `ackPhi a 0 1 = 0`. |
| p. 120 | Level-2 base value $\varphi(a, 0, 2) = 1$ | `TNDPackage.L03Ackermann.ackPhi_level2_zero` | `theorem` (Proved in package) | For all `a : Nat`, `ackPhi a 0 2 = 1`. |
| p. 120 | Level-3 base value $\varphi(a, 0, 3) = a$ | `TNDPackage.L03Ackermann.ackPhi_level3_zero` | `theorem` (Proved in package) | For all `a : Nat`, `ackPhi a 0 3 = a`. |
| p. 119 | Level-1 multiplication characterization $\varphi(a, b, 1) = a \cdot b$ | `TNDPackage.L03Ackermann.AckLevel1Spec` | `def` (Target proposition) | `∀ a b : Nat, ackPhi a b 1 = a * b`. |

---

## 7. Package `H08` — Perron's Proof of Moessner's Theorem

### Primary Source and Provenance
- **Citation:** Oskar Perron, *Beweis des Moessnerschen Satzes*, Sitzungsberichte der Mathematisch-Naturwissenschaftlichen Klasse der Bayerischen Akademie der Wissenschaften zu München **1951** (printed 1952), pp. 31–34.
- **Date Reconciliation:** Presented at the Munich Academy session on 5 October 1951; published in the 1951 *Sitzungsberichte* volume printed in 1952.
- **Primary Source Link:** [BAdW Munich archive (`043542577.pdf`)](https://archiv.badw.de/de/043542577/043542577.pdf).
- **German/DACH Connection:** Ludwig-Maximilians-Universität München and Bayerische Akademie der Wissenschaften, Munich, Germany.
- **Scope Classification:** `main-theorem-constructive-core`. Formalizes the partial-sum sieve operator, Pascal binomial coefficients used in Perron's triangular recurrence (p. 32), and the rank-2 Moessner identity equating partial sums of odd numbers to squares $n^2$.

### Source-to-Lean Statement Map (`tests/packages/H08_PerronMoessner.lean`)

| Source Location | Mathematical Content in Source | Lean Declaration | Kind / Status | Natural-Language Back-Translation |
| :--- | :--- | :--- | :--- | :--- |
| p. 31 | Partial-sum accumulation of a sequence | `TNDPackage.H08PerronMoessner.prefixSum` | `def` | Recursively sums `f 0 + f 1 + ... + f (n - 1)`. |
| p. 31 | Sequence of odd integers $1, 3, 5, \dots$ remaining after dropping every second integer | `TNDPackage.H08PerronMoessner.oddTerm` | `def` | Defines `oddTerm k = 2 * k + 1`. |
| p. 32 | Binomial coefficients $\binom{n}{k}$ governing Perron's sieve recurrence | `TNDPackage.H08PerronMoessner.binom` | `def` | Standard recursive Pascal triangle definition on `Nat`. |
| p. 32 | Pascal recurrence $\binom{n+1}{k+1} = \binom{n}{k} + \binom{n}{k+1}$ | `TNDPackage.H08PerronMoessner.pascal_step` | `theorem` (Proved in package) | `binom (n + 1) (k + 1) = binom n k + binom n (k + 1)`. |
| p. 31 | Rank-2 Moessner step recurrence | `TNDPackage.H08PerronMoessner.moessner_rank2_step` | `theorem` (Proved in package) | `prefixSum oddTerm (n + 1) = prefixSum oddTerm n + (2 * n + 1)`. |
| p. 31 | Rank-2 Moessner power theorem ($\sum_{k=0}^{n-1} (2k+1) = n^2$) | `TNDPackage.H08PerronMoessner.MoessnerRank2Squares` | `def` (Target proposition) | `∀ n : Nat, prefixSum oddTerm n = n * n`. |

---

## 8. Package `H03` — Sperner's Antichain Bound

### Primary Source and Provenance
- **Citation:** Emanuel Sperner, *Ein Satz über Untermengen einer endlichen Menge*, Mathematische Zeitschrift **27** (1928), pp. 544–548.
- **Date Reconciliation:** Received 17 November 1927; published in *Mathematische Zeitschrift* 27 in 1928.
- **Primary Source Link:** [GDZ Göttingen scan (`PPN266833020_0027`)](https://gdz.sub.uni-goettingen.de/download/pdf/PPN266833020_0027/LOG_0034.pdf).
- **German/DACH Connection:** Universität Hamburg, Germany.
- **Scope Classification:** `main-theorem-constructive-core`. Formalizes subset inclusion on bitvectors `Fin n → Bool`, incomparability, duplicate-free pairwise antichains, the middle binomial coefficient $\binom{n}{\lfloor n/2 \rfloor}$, and the main upper-bound specification (p. 544). Full characterization of extremal equality cases (pp. 546–548) is separated from the upper-bound specification.

### Source-to-Lean Statement Map (`tests/packages/H03_Sperner.lean`)

| Source Location | Mathematical Content in Source | Lean Declaration | Kind / Status | Natural-Language Back-Translation |
| :--- | :--- | :--- | :--- | :--- |
| p. 544 | Subset of an $n$-element ground set | `TNDPackage.H03Sperner.BitSubset` | `def` | Characteristic vector `Fin n → Bool`. |
| p. 544 | Subset containment $A \subseteq B$ | `TNDPackage.H03Sperner.SubsetLe` | `def` | `∀ i : Fin n, A i = true → B i = true`. |
| p. 544 | Mutual non-containment (incomparability) of subsets $A$ and $B$ | `TNDPackage.H03Sperner.Incomparable` | `def` | `(SubsetLe A B → False) ∧ (SubsetLe B A → False)`. |
| p. 544 | Antichain family (no member contains another; forces duplicate-freedom) | `TNDPackage.H03Sperner.PairwiseAntichain` | `def` | Inductive pairwise predicate requiring `Incomparable A B` for all ordered pairs in `F : List (BitSubset n)`. |
| p. 544 | Middle binomial coefficient $\binom{n}{\lfloor n/2 \rfloor}$ | `TNDPackage.H03Sperner.middleBinom` | `def` | Evaluates the explicit Pascal recurrence at `(n, n / 2)` and returns `(coefficient - 1) + 1`; the middle coefficient is positive, so this is the middle binomial coefficient. |
| p. 544, *Satz* | Main antichain upper bound $|F| \le \binom{n}{\lfloor n/2 \rfloor}$ | `TNDPackage.H03Sperner.SpernerBoundSpec` | `def` (Target proposition) | `∀ F : List (BitSubset n), PairwiseAntichain F → F.length ≤ middleBinom n`. |
| p. 544 | Non-vacuity and singleton antichain bound verification | `TNDPackage.H03Sperner.singleton_antichain_bound` | `theorem` (Proved in package) | Every singleton family `[A]` satisfies `PairwiseAntichain [A]` and `[A].length ≤ middleBinom n`. |
