# German/DACH Constructive Mathematics Paper Backlog & Provenance Screening

Reviewed on 2026-11-01. This document is the human-readable companion to [`audit/papers.json`](../audit/papers.json) and [`docs/PACKAGES-STATEMENT-MAPS.md`](PACKAGES-STATEMENT-MAPS.md). It records source-provenance verification, lecture/submission versus publication date reconciliation, documented German/DACH academic connections, constructive and axiom-risk screening, existing Lean formalization checks, and exact target-scope boundaries for all 20 catalogue papers (`H01`–`H08`, `L01`–`L06`, `M01`–`M06`).

## Scope and Intake Discipline

1. **Explicit German/DACH Academic Connection:** Every entry documents a concrete German, Austrian, or German-speaking Swiss university or research-institute affiliation with explicit dates and roles. Academic connection is never inferred from surname or publication language alone.
2. **Date Reconciliation:** Historical and modern papers frequently have divergent lecture, dissertation, submission, preprint, or volume-label dates versus print or journal-publication dates (for example, Cantor's 1891 Halle DMV lecture printed in the 1892 volume; Schönfinkel's 1920 Göttingen lecture published in 1924; Lorenzen's 1950 submission published in 1951; ShockHash's 2023 preprint and 2025 journal publication). Both dates and their reconciliation are recorded explicitly.
3. **Honest Scope Classification:** Every target is classified as one of:
   - `main-theorem-constructive-core`: The primary theorem of the paper (or its constructive discrete core), formulated without classical axioms.
   - `supporting-lemma`: A specific auxiliary lemma (`Hilfssatz`) or invariant used within a larger paper whose full theorem remains outside current scope.
   - `restricted-constructive-fragment`: A self-contained, finite, typed, or quantifier-free constructive fragment extracted from a broader paper. Small fragments are never overstated as full-paper formalizations.
4. **Constructive Contract (`propext` / `Quot.sound` only):** All active missions and statement packages target Lean 4 `Init` without Mathlib, rejecting `Classical.choice`, `sorryAx`, custom axioms, and native-evaluation axioms.

---

## Summary Table of 20 Screened Papers

| ID | Authors | Lecture / Subm. | Publ. | Title | DACH Institution(s) | Target Scope | Readiness State | Mission / Package Path |
| :--- | :--- | :---: | :---: | :--- | :--- | :--- | :--- | :--- |
| **H01** | G. Cantor | 1891 | 1892 | *Ueber eine elementare Frage der Mannigfaltigkeitslehre* | Univ. Halle-Wittenberg; DMV (Halle) | `main-theorem-constructive-core` | `active-mission` | `mission-h01-cantor` (`TNDLib/Cantor.lean`) |
| **H02** | I. Schur | 1916 | 1917 | *Über die Kongruenz $x^m + y^m \equiv z^m \pmod{p}$* | Univ. Berlin | `supporting-lemma` | `screened-backlog` | — |
| **H03** | E. Sperner | 1927 | 1928 | *Ein Satz über Untermengen einer endlichen Menge* | Univ. Hamburg | `main-theorem-constructive-core` | `statement-mapped-package` | `tests/packages/H03_Sperner.lean` |
| **H04** | E. Sperner | 1928 | 1928 | *Neuer Beweis für die Invarianz der Dimensionszahl und des Gebietes* | Univ. Hamburg | `supporting-lemma` | `screened-backlog` | — |
| **H05** | B. L. van der Waerden | 1927 | 1927 | *Beweis einer Baudetschen Vermutung* | Univ. Göttingen; Univ. Hamburg; Univ. Leipzig; Univ. Zürich | `main-theorem-constructive-core` | `screened-backlog` | — |
| **H06** | R. Rado | 1931 | 1933 | *Studien zur Kombinatorik* | Univ. Berlin | `restricted-constructive-fragment` | `screened-backlog` | — |
| **H07** | K. Menger | 1926 | 1927 | *Zur allgemeinen Kurventheorie* | Univ. Wien | `restricted-constructive-fragment` | `screened-backlog` | — |
| **H08** | O. Perron | 1951 | 1952 | *Beweis des Moessnerschen Satzes* | LMU München; BAdW München | `main-theorem-constructive-core` | `statement-mapped-package` | `tests/packages/H08_PerronMoessner.lean` |
| **L01** | M. Schönfinkel | 1920 | 1924 | *Über die Bausteine der mathematischen Logik* | Univ. Göttingen | `restricted-constructive-fragment` | `statement-mapped-package` | `tests/packages/L01_Schoenfinkel.lean` |
| **L02** | H. B. Curry | 1929 | 1930 | *Grundlagen der Kombinatorischen Logik (Teile I & II)* | Univ. Göttingen | `restricted-constructive-fragment` | `screened-backlog` | — |
| **L03** | W. Ackermann | 1927 | 1928 | *Zum Hilbertschen Aufbau der reellen Zahlen* | Univ. Göttingen | `restricted-constructive-fragment` | `statement-mapped-package` | `tests/packages/L03_Ackermann.lean` |
| **L04** | G. Gentzen | 1933 | 1935 | *Untersuchungen über das logische Schließen I & II* | Univ. Göttingen | `restricted-constructive-fragment` | `screened-backlog` | — |
| **L05** | K. Gödel | 1930 | 1931 | *Über formal unentscheidbare Sätze der Principia Mathematica und verwandter Systeme I* | Univ. Wien; ÖAW Wien | `restricted-constructive-fragment` | `screened-backlog` | — |
| **L06** | P. Lorenzen | 1950 | 1951 | *Algebraische und logistische Untersuchungen über freie Verbände* | Univ. Bonn | `restricted-constructive-fragment` | `active-mission` | `mission-l06-lorenzen` (`TNDLib/Lorenzen.lean`) |
| **M01** | R. M. McConnell, K. Mehlhorn, S. Näher, P. Schweitzer | 2010 | 2011 | *Certifying Algorithms* | MPI-INF Saarbrücken; Univ. des Saarlandes; Univ. Trier | `restricted-constructive-fragment` | `active-mission` | `mission-m01-certifying` (`TNDLib/Certifying.lean`) |
| **M02** | H.-P. Lehmann, P. Sanders, S. Walzer | 2023 | 2025 | *ShockHash: Near Optimal-Space Minimal Perfect Hashing Beyond Brute-Force* | KIT Karlsruhe | `restricted-constructive-fragment` | `statement-mapped-package` | `tests/packages/M02_ShockHash.lean` |
| **M03** | U. Meyer, H. Tran, K. Tsakalidis | 2023 | 2024 | *Certifying Induced Subgraphs in Large Graphs* | Goethe-Univ. Frankfurt | `restricted-constructive-fragment` | `screened-backlog` | — |
| **M04** | R. Geisberger, P. Sanders, D. Schultes, D. Delling | 2008 | 2008 | *Contraction Hierarchies: Faster and Simpler Hierarchical Routing in Road Networks* | Univ. Karlsruhe (KIT) | `restricted-constructive-fragment` | `screened-backlog` | — |
| **M05** | K. Mehlhorn, A. Neumann, J. M. Schmidt | 2013 | 2017 | *Certifying 3-Edge-Connectivity* | MPI-INF Saarbrücken; TU Ilmenau; Univ. Rostock | `restricted-constructive-fragment` | `screened-backlog` | — |
| **M06** | M. Henzinger, S. Rao, D. Wang | 2017 | 2020 | *Local Flow Partitioning for Faster Edge Connectivity* | Univ. Wien; ISTA Klosterneuburg | `supporting-lemma` | `screened-backlog` | — |

---

## Detailed Provenance and Constructivity Screening Notes

### Part I: Historical Finite and Foundational Mathematics (`H01`–`H08`)

#### H01 — Georg Cantor (1891 lecture / 1892 print)
- **Citation:** Georg Cantor, *Ueber eine elementare Frage der Mannigfaltigkeitslehre*, Jahresbericht der Deutschen Mathematiker-Vereinigung **1**, pp. 75–78.
- **Date Reconciliation:** Presented on 24 September 1891 at the Halle meeting of the Gesellschaft Deutscher Naturforscher und Ärzte (establishing the DMV). Appears in DMV *Jahresbericht* Volume 1 covering 1890/91, printed and issued by Georg Reimer (Berlin) in 1892.
- **Primary Source:** [GDZ Göttingen scan (`PPN37721857X_0001`)](https://gdz.sub.uni-goettingen.de/id/PPN37721857X_0001).
- **German/DACH Connection:** Cantor spent his entire academic career at Martin-Luther-Universität Halle-Wittenberg (Privatdozent 1869, Extraordinary Professor 1872, Ordinary Professor 1879–1913) and was the founding president of the Deutsche Mathematiker-Vereinigung (DMV) in Halle (Saale).
- **Target Scope (`main-theorem-constructive-core`):** On p. 75–76, Cantor replaces real-number decimal expansions with infinite sequences over a two-element alphabet $(m, w)$ and constructs the diagonal sequence $E_0 = (b_1, b_2, \dots, b_\nu, \dots)$ where each $b_\nu$ is explicitly chosen distinct from the $\nu$-th coordinate $a_{\nu,\nu}$ of the $\nu$-th enumerated sequence $E_\nu$. TNDLib formalizes this constructive core on `Nat → Bool` via `TNDLib.Cantor.flip` and `TNDLib.Cantor.diagonal`, producing an explicit discrepancy index (`TNDLib.Cantor.diagonalDiscrepancy`) and refuting surjectivity without classical choice or excluded middle on function equality. Cardinal exponentiation claims on p. 77–78 for arbitrary uncountable powers are outside scope.
- **Existing Lean Check & Readiness:** Mathlib provides `Function.cantor_surjective` over `Set α` using classical logic; `TNDLib/Cantor.lean` provides a zero-dependency constructive stream formulation. **Readiness:** `active-mission` (`mission-h01-cantor`).

#### H02 — Issai Schur (1916 dated / 1917 published)
- **Citation:** Issai Schur, *Über die Kongruenz $x^m + y^m \equiv z^m \pmod{p}$*, Jahresbericht der Deutschen Mathematiker-Vereinigung **25**, pp. 114–117.
- **Date Reconciliation:** Conventionally cited as 1916 (dated Berlin 1916); published in DMV *Jahresbericht* Volume 25, whose title page carries the imprint year 1917.
- **Primary Source:** [GDZ Göttingen scan (`PPN37721857X_0025`)](https://gdz.sub.uni-goettingen.de/download/pdf/PPN37721857X_0025/LOG_0014.pdf).
- **German/DACH Connection:** Friedrich-Wilhelms-Universität Berlin (now Humboldt-Universität zu Berlin), where Schur earned his doctorate (1901) and habilitation (1903), and served as professor until 1935 (with an intermediate professorship at Bonn 1913–1916).
- **Target Scope (`supporting-lemma`):** Targets only the combinatorial *Hilfssatz* (pp. 114–115): for every finite number of classes (colors) $r$, any partitioning of $\{1, \dots, N\}$ with $N \ge \lfloor r! e \rfloor$ contains monochromatic positive integers $x, y, z$ satisfying $x + y = z$. Excludes the modular Fermat-congruence deduction using cyclotomic cosets.
- **Constructivity & Readiness:** The inductive difference-coloring proof is finite and constructive once finite-set pigeonhole/counting over `Fin` or `List` is established. **Readiness:** `screened-backlog` (awaiting finite coloring/pigeonhole prerequisites).

#### H03 — Emanuel Sperner (1927 submitted / 1928 published)
- **Citation:** Emanuel Sperner, *Ein Satz über Untermengen einer endlichen Menge*, Mathematische Zeitschrift **27** (1928), pp. 544–548.
- **Date Reconciliation:** Received (*Eingegangen*) on 17 November 1927; published in *Mathematische Zeitschrift* Volume 27 in 1928.
- **Primary Source:** [GDZ Göttingen scan (`PPN266833020_0027`)](https://gdz.sub.uni-goettingen.de/download/pdf/PPN266833020_0027/LOG_0034.pdf).
- **German/DACH Connection:** Written at Universität Hamburg while Sperner was a doctoral student under Wilhelm Blaschke and Otto Schreier (subsequently professor at Königsberg, Bonn, and Hamburg).
- **Target Scope (`main-theorem-constructive-core`):** Bounds the size of a duplicate-free antichain of subsets of an $n$-element set by the middle binomial coefficient $\binom{n}{\lfloor n/2 \rfloor}$ (p. 544). The statement package separates (1) the subset/incomparability/antichain definitions on bitvectors `Fin n → Bool`, (2) the upper bound `sperner_antichain_bound`, and (3) concrete low-dimension verifications (`n = 1, 2`); full characterization of equality cases (pp. 546–548) is excluded from the initial package.
- **Existing Lean Check & Readiness:** Mathlib proves Sperner's theorem via `Finset` and the LYM inequality. TNDLib maps the self-contained statement package in [`tests/packages/H03_Sperner.lean`](../tests/packages/H03_Sperner.lean). **Readiness:** `statement-mapped-package`.

#### H04 — Emanuel Sperner (1928 dissertation / 1928 published)
- **Citation:** Emanuel Sperner, *Neuer Beweis für die Invarianz der Dimensionszahl und des Gebietes*, Abhandlungen aus dem Mathematischen Seminar der Universität Hamburg **6** (1928), pp. 265–272.
- **Date Reconciliation:** Submitted as Sperner's Hamburg doctoral dissertation in 1928 and published in the same year in *Abh. Math. Sem. Univ. Hamburg* 6.
- **Primary Source:** [Springer archive record (`10.1007/BF02940617`)](https://link.springer.com/article/10.1007/BF02940617).
- **German/DACH Connection:** Mathematisches Seminar der Universität Hamburg (1928 dissertation).
- **Target Scope (`supporting-lemma`):** Restricted strictly to the combinatorial simplicial labeling parity lemma (Sperner's Lemma in dimension 1 and 2); excludes the topological deduction of invariance of dimension and domain via closed covers and limit compactness.
- **Constructivity & Readiness:** Constructive double-counting of doors/simplices on a finite grid triangulation, but blocked in `screened-backlog` until verbatim primary-scan page verification and an explicit 2D triangulation representation are completed.

#### H05 — Bartel Leendert van der Waerden (1927 issue / 1927–28 volume)
- **Citation:** B. L. van der Waerden, *Beweis einer Baudetschen Vermutung*, Nieuw Archief voor Wiskunde (2) **15** (1927), pp. 212–216.
- **Date Reconciliation:** Developed during discussions with Emil Artin and Otto Schreier at Universität Hamburg (1926/27); published in *Nieuw Archief voor Wiskunde* Series 2, Volume 15 (issue printed 1927; full volume bound 1927/28).
- **Primary Source:** [Koninklijke Bibliotheek resolver (`MMKWG01:022157001:00228`)](https://resolver.kb.nl/resolve?urn=MMKWG01:022157001:00228).
- **German/DACH Connection:** Van der Waerden trained and worked at Georg-August-Universität Göttingen and Universität Hamburg (1924–1928, Rockefeller fellow and assistant), served as professor at Universität Leipzig (1931–1945), and was professor at Universität Zürich (1951–1972).
- **Target Scope (`main-theorem-constructive-core`):** Explicit primitive-recursive finite bound $W(k, r)$ such that every $r$-coloring of $\{1, \dots, W(k, r)\}$ contains a monochromatic $k$-term arithmetic progression with positive common difference $d > 0$.
- **Constructivity & Readiness:** Van der Waerden's double induction over $(k, r)$ is fully constructive and provides explicit bounds, avoiding topological/ultrafilter compactness. Held in `screened-backlog` pending finite block-fan infrastructure.

#### H06 — Richard Rado (1931 dissertation / 1932 submitted / 1933 published)
- **Citation:** Richard Rado, *Studien zur Kombinatorik*, Mathematische Zeitschrift **36** (1933), pp. 424–470.
- **Date Reconciliation:** Approved as a doctoral dissertation under Issai Schur at Berlin in 1931 (degree formally conferred 1933); journal manuscript received 13 May 1932 and published in *Mathematische Zeitschrift* 36 in 1933.
- **Primary Source:** [HU Berlin edoc repository (`56771e92-8c93-4f3d-8d8e-06c0533466fa`)](https://edoc.hu-berlin.de/items/56771e92-8c93-4f3d-8d8e-06c0533466fa).
- **German/DACH Connection:** Friedrich-Wilhelms-Universität Berlin (now Humboldt-Universität zu Berlin), doctoral student and research assistant (1927–1933).
- **Target Scope (`restricted-constructive-fragment`):** Restricted to the single-equation partition-regularity specialization (Satz IV for a single linear equation $\sum c_i x_i = 0$ with nonzero integer coefficients and a non-empty subset of coefficients summing to zero, requiring positive solutions $x_i > 0$).
- **Constructivity & Readiness:** Rado's transition from unbounded colorings to a finite threshold $N(r)$ uses a compactness argument that must be replaced by an explicit constructively bounded color-focusing bound. **Readiness:** `screened-backlog`.

#### H07 — Karl Menger (1926 submitted / 1927 published)
- **Citation:** Karl Menger, *Zur allgemeinen Kurventheorie*, Fundamenta Mathematicae **10** (1927), pp. 96–115.
- **Date Reconciliation:** Submitted from Vienna in 1926; published in *Fundamenta Mathematicae* Volume 10 in 1927.
- **Primary Source:** [ICM Polish Virtual Library of Science (`fm1012.pdf`)](https://matwbn.icm.edu.pl/ksiazki/fm/fm10/fm1012.pdf).
- **German/DACH Connection:** Universität Wien (doctorate 1924 under Hans Hahn; professor of geometry at Vienna 1927–1936 and member of the Vienna Circle).
- **Target Scope (`restricted-constructive-fragment`):** Finite-graph reformulation of Menger's $n$-bogenverknüpft theorem (pp. 96–103): for non-adjacent terminals $s, t$ in a finite graph, the minimum size of an $s$-$t$ vertex separator equals the maximum number of internally vertex-disjoint $s$-$t$ paths.
- **Constructivity & Readiness:** Original paper is phrased in point-set topology (regular curves in compact metric spaces); the finite graph theorem is constructively valid but requires explicit finite graph and path-packing definitions. **Readiness:** `screened-backlog`.

#### H08 — Oskar Perron (1951 lecture / 1952 volume print)
- **Citation:** Oskar Perron, *Beweis des Moessnerschen Satzes*, Sitzungsberichte der Mathematisch-Naturwissenschaftlichen Klasse der Bayerischen Akademie der Wissenschaften zu München **1951**, pp. 31–34.
- **Date Reconciliation:** Presented at the Academy session (*Sitzung*) of 5 October 1951; published in the *Jahrgang 1951* proceedings volume, printed by Verlag der Bayerischen Akademie der Wissenschaften in 1952.
- **Primary Source:** [Bayerische Akademie der Wissenschaften archive (`043542577.pdf`)](https://archiv.badw.de/de/043542577/043542577.pdf).
- **German/DACH Connection:** Ludwig-Maximilians-Universität München (Professor of Mathematics 1922–1951) and Ordinary Member of the Bayerische Akademie der Wissenschaften in Munich.
- **Target Scope (`main-theorem-constructive-core`):** Formalizes the Moessner delete-and-partial-sum sieve, Pascal binomial coefficients (`binom`), Perron's explicit polynomial/binomial coefficient matrix transition step, and the concrete rank-1 ($n^1$) and rank-2 ($n^2$ as sum of first $n$ odd numbers) power theorems.
- **Existing Lean Check & Readiness:** Statement-mapped in [`tests/packages/H08_PerronMoessner.lean`](../tests/packages/H08_PerronMoessner.lean). **Readiness:** `statement-mapped-package`.

---

### Part II: Logic and Constructive Foundations (`L01`–`L06`)

#### L01 — Moses Schönfinkel (1920 lecture / 1924 published)
- **Citation:** Moses Schönfinkel, *Über die Bausteine der mathematischen Logik*, Mathematische Annalen **92** (1924), pp. 305–316.
- **Date Reconciliation:** Presented to the Mathematische Gesellschaft in Göttingen on 7 December 1920 (as recorded in the first-page footnote); prepared for print with stylistic additions by Heinrich Behmann in March 1924 and published in *Mathematische Annalen* Volume 92 (1924).
- **Primary Source:** [LMU Munich scan (`1924 - Schoenfinkel - Ueber die Bausteine der mathematischen Logik.pdf`)](https://www.cip.ifi.lmu.de/~langeh/test/1924%20-%20Schoenfinkel%20-%20Ueber%20die%20Bausteine%20der%20mathematischen%20Logik.pdf).
- **German/DACH Connection:** Georg-August-Universität Göttingen (1914–1924, member of David Hilbert's foundational research group; lecture delivered to the Göttingen Mathematical Society and prepared for publication by Göttingen logician Heinrich Behmann, with Moscow printed as Schönfinkel's 1924 residence).
- **Target Scope (`restricted-constructive-fragment`):** Formalizes the typed, pointwise versions of Schönfinkel's §2 currying/uncurrying isomorphism (p. 306), §3 fundamental combinators $I, C, T, Z, S$ (pp. 308–310, preserving Schönfinkel's original $C$ for constancy = modern $K$, $T$ for *Vertauschungsfunktion* = modern $C$, $Z$ for *Zusammensetzungsfunktion* = modern $B$, and $S$ for *Verschmelzungsfunktion*), and §4 reductions of $I$, $T$, and $Z$ in terms of $C$ and $S$ alone (pp. 311–312). Excludes untyped syntactic bound-variable elimination over first-order formulas (§5–§6).
- **Existing Lean Check & Readiness:** Statement-mapped in [`tests/packages/L01_Schoenfinkel.lean`](../tests/packages/L01_Schoenfinkel.lean). **Readiness:** `statement-mapped-package`.

#### L02 — Haskell Brooks Curry (1929 dissertation / 1930 published)
- **Citation:** H. B. Curry, *Grundlagen der Kombinatorischen Logik*, American Journal of Mathematics **52**(3) (1930), pp. 509–536 (Part I) and **52**(4) (1930), pp. 789–834 (Part II).
- **Date Reconciliation:** Completed as Curry's *Inaugural-Dissertation* at Georg-August-Universität Göttingen in 1929 under David Hilbert and Paul Bernays (oral examination July 1929, degree conferred 1930); published in two parts in *Amer. J. Math.* in July and October 1930.
- **Primary Source:** [JSTOR Part I (`2370619`)](https://www.jstor.org/stable/2370619) and [JSTOR Part II (`2370716`)](https://www.jstor.org/stable/2370716).
- **German/DACH Connection:** Georg-August-Universität Göttingen (doctoral studies and dissertation 1928–1930 under Hilbert and Bernays).
- **Target Scope (`restricted-constructive-fragment`):** Part I combinatory product/composition ($B$), permutation ($C$), and duplication ($W$) laws and finite combinatory equality axioms. Held in `screened-backlog` so that syntactic combinatory equality rules are modeled distinctly rather than duplicating `L01`'s pointwise typed combinator identities.

#### L03 — Wilhelm Ackermann (1927 submitted / 1928 published)
- **Citation:** Wilhelm Ackermann, *Zum Hilbertschen Aufbau der reellen Zahlen*, Mathematische Annalen **99** (1928), pp. 118–133.
- **Date Reconciliation:** Received (*Eingegangen*) on 25 March 1927 with a Göttingen byline; published in *Mathematische Annalen* Volume 99 in 1928.
- **Primary Source:** [Primary scan (`Ackermann1928_126.pdf`)](https://eretrandre.org/rb/files/Ackermann1928_126.pdf) and [Springer record (`10.1007/BF01459088`)](https://link.springer.com/article/10.1007/BF01459088).
- **German/DACH Connection:** Georg-August-Universität Göttingen (doctoral dissertation under David Hilbert 1925; collaborator on Hilbert's proof theory in Göttingen).
- **Target Scope (`restricted-constructive-fragment`):** Formalizes Ackermann's original three-variable function $\varphi(a, b, n)$ (pp. 119–120) with his exact initial-value helper $\alpha(a, n)$ (`ackAlpha`: $0$ for $n=0$, $1$ for $n=1$, $a$ for $n \ge 2$), giving $\varphi(a, 0, 1) = \alpha(a, 0) = 0$, $\varphi(a, 0, 2) = \alpha(a, 1) = 1$, and $\varphi(a, 0, 3) = \alpha(a, 2) = a$ (for $n \ge 3$, $\varphi(a, 0, n) = \alpha(a, n-1) = a$, so $\varphi(a, b, 0) = a + b$, $\varphi(a, b, 1) = a \cdot b$, $\varphi(a, b, 2) = a^b$, and $\varphi(a, b, 3)$ is iterated exponentiation starting from $a$ at $b = 0$). Excludes the metamathematical majorization proof (pp. 121–133) that $\varphi$ is not primitive recursive.
- **Existing Lean Check & Readiness:** Mathlib defines only the later 2-variable Péter–Robinson simplification. TNDLib maps Ackermann's authentic 3-variable definition in [`tests/packages/L03_Ackermann.lean`](../tests/packages/L03_Ackermann.lean). **Readiness:** `statement-mapped-package`.

#### L04 — Gerhard Gentzen (1933 dissertation / 1934–1935 published)
- **Citation:** Gerhard Gentzen, *Untersuchungen über das logische Schließen I, II*, Mathematische Zeitschrift **39**, pp. 176–210 (Part I, printed 1934) and pp. 405–431 (Part II, printed 1935).
- **Date Reconciliation:** Submitted as Gentzen's doctoral dissertation at Göttingen and received by *Mathematische Zeitschrift* on 30 December 1933; Part I appeared in 1934 and Part II in 1935 in Volume 39 (bound volume imprint 1935).
- **Primary Source:** [GDZ / MathDoc record (`MZ_1935__39_168546`)](https://geodesic.mathdoc.fr/item/MZ_1935__39_168546/).
- **German/DACH Connection:** Georg-August-Universität Göttingen (doctoral studies 1929–1933 under Hermann Weyl and Paul Bernays; assistant to David Hilbert 1934–1943).
- **Target Scope (`restricted-constructive-fragment`):** Restricted to the propositional fragment of the intuitionistic sequent calculus $\mathbf{LJ}$ (structural rules *Verdünnung*, *Zusammenziehung*, *Vertauschung* and the *Hauptsatz* cut-elimination theorem via double induction on mix grade and rank).
- **Constructivity & Readiness:** Gentzen's double induction is entirely finitary and constructive. Held in `screened-backlog` until inductive derivation trees and sequent context manipulation are added.

#### L05 — Kurt Gödel (1930 announced & submitted / 1931 published)
- **Citation:** Kurt Gödel, *Über formal unentscheidbare Sätze der Principia Mathematica und verwandter Systeme I*, Monatshefte für Mathematik und Physik **38** (1931), pp. 173–198.
- **Date Reconciliation:** Announced at the Königsberg conference in September 1930, communicated in abstract to the Vienna Academy of Sciences on 23 October 1930, and full paper received (*Eingegangen*) on 17 November 1930; published in *Monatshefte für Mathematik und Physik* Volume 38 in 1931.
- **Primary Source:** [Primary German transcription/scan (`goedel.pdf`)](https://www.w-k-essler.de/pdfs/goedel.pdf).
- **German/DACH Connection:** Universität Wien (Dr. phil. 1930 under Hans Hahn; Habilitation 1932; Privatdozent in Vienna until 1938).
- **Target Scope (`restricted-constructive-fragment`):** Targets an abstract syntactic representation of Satz VI (pp. 187–190) preserving Gödel's explicit $\omega$-consistency (*$\omega$-Widerspruchsfreiheit*) premise rather than substituting Rosser's 1936 strengthening.
- **Constructivity & Readiness:** Gödel specifically designed the proof of Satz VI to be finitary and intuitionistically acceptable, avoiding semantic truth in the standard model. Held in `screened-backlog` due to extensive Gödel-numbering and primitive-recursive representability (Satz V) prerequisites.

#### L06 — Paul Lorenzen (1950 submitted / 1951 published)
- **Citation:** Paul Lorenzen, *Algebraische und logistische Untersuchungen über freie Verbände*, The Journal of Symbolic Logic **16**(2) (June 1951), pp. 81–106.
- **Date Reconciliation:** Received by *The Journal of Symbolic Logic* on 3 August 1950 (bearing a Bonn institutional byline); published in June 1951. English translation by Stefan Neuwirth available at [arXiv:1710.08138](https://arxiv.org/pdf/1710.08138).
- **Primary Source:** [JSTOR record (`2266681`)](https://www.jstor.org/stable/2266681) and [arXiv:1710.08138](https://arxiv.org/pdf/1710.08138).
- **German/DACH Connection:** Rheinische Friedrich-Wilhelms-Universität Bonn (where Lorenzen habilitated in 1946 and taught until 1956, before moving to Kiel and founding the Erlangen School of operative/constructive mathematics).
- **Target Scope (`restricted-constructive-fragment`):** Formalizes Lorenzen's §1 (pp. 81–86) constructive theory of lattice-ordered divisibility cones (`TNDLib.Lorenzen.LOrder`), including left additive order cancellation (`TNDLib.Lorenzen.orderCancelLeft`), explicit meet and join operations (`TNDLib.Lorenzen.meet`, `TNDLib.Lorenzen.join`), universal lower/upper bound laws, idempotence, commutativity, and relative primality (`TNDLib.Lorenzen.RelPrime`). Excludes §2's infinitary inductive systems and the embedding theorem into direct products of linearly ordered groups.
- **Constructivity & Readiness:** Lorenzen's primary motivation in this paper is eliminating Zorn's Lemma and classical transfinite induction from Krull/Prüfer divisibility theory. **Readiness:** `active-mission` (`mission-l06-lorenzen`).

---

### Part III: Modern German/DACH Algorithm and Certificate Research (`M01`–`M06`)

#### M01 — Ross M. McConnell, Kurt Mehlhorn, Stefan Näher, Pascal Schweitzer (2010 manuscript / 2011 published)
- **Citation:** Ross M. McConnell, Kurt Mehlhorn, Stefan Näher, and Pascal Schweitzer, *Certifying Algorithms*, Computer Science Review **5**(2) (May 2011), pp. 119–161.
- **Date Reconciliation:** Circulated as an MPI-INF research manuscript in 2010; published in *Computer Science Review* Volume 5, Issue 2 in May 2011.
- **Primary Source:** [MPI-INF author manuscript (`CertifyingAlgorithms.pdf`)](https://people.mpi-inf.mpg.de/~mehlhorn/ftp/CertifyingAlgorithms.pdf).
- **German/DACH Connection:** Max-Planck-Institut für Informatik (MPI-INF) and Universität des Saarlandes in Saarbrücken (Kurt Mehlhorn and Pascal Schweitzer), and Universität Trier (Stefan Näher, Professor of Computer Science).
- **Target Scope (`restricted-constructive-fragment`):** Formalizes executable witness checking (§2, pp. 121–125) and string pattern matching occurrence/non-occurrence mismatch certificates (§9.5, pp. 142–143) in `TNDLib/Certifying.lean`, plus a cross-mission universal pattern-table falsifier certificate (`TNDLib.Certifying.StreamDiscrepancyCert`, `TNDLib.Certifying.diagonalStreamCert`) that imports Mission H01's promoted Cantor diagonal discrepancy theorem (`TNDLib.Cantor.diagonalDiscrepancy`).
- **Constructivity & Readiness:** Certifying algorithms are inherently constructive: every positive or negative output is accompanied by an explicit witness verified in `Type`/`Bool` without classical existence assumptions. **Readiness:** `active-mission` (`mission-m01-certifying`).

#### M02 — Hans-Peter Lehmann, Peter Sanders, Stefan Walzer (2023 preprint / 2025 published)
- **Citation:** Hans-Peter Lehmann, Peter Sanders, and Stefan Walzer, *ShockHash: Near Optimal-Space Minimal Perfect Hashing Beyond Brute-Force*, Algorithmica **87** (2025), pp. 427–461.
- **Date Reconciliation:** Posted as arXiv preprint `2308.09561` in August 2023 and presented at ALENEX 2024; extended journal version published open-access in *Algorithmica* Volume 87 in 2025.
- **Primary Source:** [Springer Open Access (`10.1007/s00453-025-01321-z`)](https://link.springer.com/article/10.1007/s00453-025-01321-z) and [KIT repository (`1000187076`)](https://publikationen.bibliothek.kit.edu/1000187076).
- **German/DACH Connection:** Karlsruher Institut für Technologie (KIT), Institute of Theoretical Informatics, Algorithm Engineering group (Lehmann, Sanders, and Walzer).
- **Target Scope (`restricted-constructive-fragment`):** Formalizes the deterministic combinatorics of ShockHash (§2–§3): two-choice candidate slot tables (`TwoChoiceHash`), 1-bit selector vectors (`SelectorBits`), injective slot placement (`CollisionFree`), pseudoforest orientation certificates where every slot has in-degree at most 1 (`IsPseudoforestOrientation`, `orientation_implies_collision_free`), and worked 2-key collision-free verification. Excludes random-graph threshold asymptotics and expected construction time.
- **Existing Lean Check & Readiness:** Statement-mapped in [`tests/packages/M02_ShockHash.lean`](../tests/packages/M02_ShockHash.lean). **Readiness:** `statement-mapped-package`.

#### M03 — Ulrich Meyer, Hung Tran, Konstantinos Tsakalidis (2023 conference / 2024 journal)
- **Citation:** Ulrich Meyer, Hung Tran, and Konstantinos Tsakalidis, *Certifying Induced Subgraphs in Large Graphs*, WALCOM 2023, LNCS **13973**, pp. 159–170 (extended version in *International Journal of Foundations of Computer Science* **35**, 2024).
- **Date Reconciliation:** Published in WALCOM 2023 proceedings in March 2023; extended journal issue published in 2024. Section references are pinned to §3.2 of the 2023 WALCOM manuscript.
- **Primary Source:** [Goethe University Frankfurt author PDF (`walcom23.pdf`)](https://ae.cs.uni-frankfurt.de/public_files/walcom23.pdf).
- **German/DACH Connection:** Goethe-Universität Frankfurt am Main, Institute for Computer Science, Algorithm Engineering group (Prof. Dr. Ulrich Meyer and Dr. Hung Tran).
- **Target Scope (`restricted-constructive-fragment`):** Restricted to the §3.2 threshold-graph elimination/construction sequence certificate checker; excludes external-memory I/O complexity bounds. **Readiness:** `screened-backlog`.

#### M04 — Robert Geisberger, Peter Sanders, Dominik Schultes, Daniel Delling (2008)
- **Citation:** Robert Geisberger, Peter Sanders, Dominik Schultes, and Daniel Delling, *Contraction Hierarchies: Faster and Simpler Hierarchical Routing in Road Networks*, WEA 2008, LNCS **5038** (2008), pp. 319–333.
- **Date Reconciliation:** Presented at WEA 2008 (May/June 2008) and published in Springer LNCS Volume 5038 in 2008.
- **Primary Source:** [Conference paper PDF (`geisberger-et-al-wea2008.pdf`)](https://ai.dmi.unibas.ch/research/reading_group/geisberger-et-al-wea2008.pdf).
- **German/DACH Connection:** Universität Karlsruhe (TH), now Karlsruher Institut für Technologie (KIT), Institute of Theoretical Informatics (all four authors).
- **Target Scope (`restricted-constructive-fragment`):** Shortcut unpacking weight/endpoint preservation and single-node contraction shortest-path preservation with explicit witness paths over natural-number edge weights. **Readiness:** `screened-backlog` (blocked on finite weighted-path infrastructure).

#### M05 — Kurt Mehlhorn, Adrian Neumann, Jens M. Schmidt (2013 preprint / 2017 journal)
- **Citation:** Kurt Mehlhorn, Adrian Neumann, and Jens M. Schmidt, *Certifying 3-Edge-Connectivity*, Algorithmica **77**(2) (2017), pp. 309–335.
- **Date Reconciliation:** Posted as arXiv preprint `1304.1476` in April 2013 and presented at WG 2013; journal article published in *Algorithmica* Volume 77 in 2017.
- **Primary Source:** [University of Rostock author manuscript (`Mehlhorn2017.pdf`)](https://algo.uni-rostock.de/storages/uni-rostock/Alle_IEF/Inf_ALGO/Publications/Mehlhorn2017.pdf).
- **German/DACH Connection:** Max-Planck-Institut für Informatik (MPI-INF) in Saarbrücken (Mehlhorn, Neumann, Schmidt), Technische Universität Ilmenau, and Universität Rostock (Schmidt).
- **Target Scope (`restricted-constructive-fragment`):** Soundness of a finite construction-trace certificate checker starting from the 2-vertex triple-edge multigraph $K_2^3$ via Mader's operations (edge addition, edge-pair subdivision, vertex splitting). **Readiness:** `screened-backlog` (requires edge-identity multigraphs rather than simple Boolean adjacency relations).

#### M06 — Monika Henzinger, Satish Rao, Di Wang (2017 conference / 2019 fixed arXiv v2 / 2020 journal)
- **Citation:** Monika Henzinger, Satish Rao, and Di Wang, *Local Flow Partitioning for Faster Edge Connectivity*, SIAM Journal on Computing **49**(1) (2020), pp. 1–36.
- **Date Reconciliation:** Preliminary version presented at SODA 2017 (pp. 1919–1938) with arXiv preprint `1704.01254v1` (2017), revised in `1704.01254v2` (2019), and published in *SIAM J. Comput.* in 2020. Section numbers are pinned to `arXiv:1704.01254v2`.
- **Primary Source:** [arXiv fixed revision (`1704.01254v2`)](https://arxiv.org/pdf/1704.01254v2).
- **German/DACH Connection:** Universität Wien (Faculty of Computer Science, Theory and Applications of Algorithms group, where Monika Henzinger was Professor 2009–2023) and Institute of Science and Technology Austria (ISTA, Klosterneuburg, 2023–present).
- **Target Scope (`supporting-lemma`):** Restricted to the local Unit-Flow push/relabel mass-conservation invariant and terminal level/excess arithmetic lemmas (§3 of `1704.01254v2`); excludes the global $O(m \log^2 n)$ minimum-cut runtime analysis. **Readiness:** `screened-backlog`.
