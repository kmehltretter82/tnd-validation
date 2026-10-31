# Source-admission semantic review

This document records the reviewed meaning of the syntax accepted by
`Main.lean` for the pinned Lean 4.35.0 prototype. It is development evidence,
not a proof that elaboration is side-effect-free and not authorization to set
`source_binding_validated` to `true`.

The admission parser reads contributor files as data. Its own executable is
trusted code that imports `Lean`, but the parser environment supplied to
`parseHeader` and `parseCommand` loads only the pinned distribution's `Init`.
It never imports or elaborates a candidate module. A separately isolated build
later elaborates only the exact admitted bytes. Thus this review has two
distinct trusted surfaces:

1. `Main.lean`, the pinned parser, and the closed set of parser extensions
   loaded by `Init` decide whether bytes are admitted.
2. The pinned Lean elaborator, kernel, equation compiler, typeclass search, and
   `Init` macros process the admitted bytes during the later build.

Neither surface is supplied by a contributor. Both remain trusted and
version-sensitive.

## Global syntax rules

Every syntax node is traversed to a maximum depth of 128. Missing syntax is
rejected. Atoms are accepted only as children of a permitted node. Identifiers
are checked independently of their parent node: root-qualified names and direct
references rooted at `autoParam`, `optParam`, `outParam`, `semiOutParam`,
`Lean`, `IO`, `BaseIO`, `EIO`, `EStateM`, `ST`, `String`, `Char`, or
`unsafeCast` are rejected. Quoted identifiers do not evade this check.

This is deliberately a direct-source restriction, not a claim that the trusted
`Init` environment has no declarations whose types or implementations mention
these names. For example, ordinary operator classes can internally use
`outParam`. Indirect trusted dependencies are assessed again from exported
declarations and proof objects.

The exact permitted node kinds and their reachable elaboration mechanisms are
grouped below. No other node kind is accepted.

### Parser payloads and fixed notation

| Permitted kinds | Reachable mechanism and boundary |
| --- | --- |
| `null`, `fieldIdx`, `hygieneInfo` | Parser-owned wrappers or payloads. Their children are still traversed. An empty `null` is also used for absent optional grammar fields; it cannot conceal an unsupported child. `fieldIdx` participates in projection syntax, and `hygieneInfo` carries trusted parser hygiene data. |
| `num` | The trusted numeral elaborator and `OfNat` instance synthesis. Candidate instance commands are unavailable. Other literal families, including strings and characters, have different node kinds and are rejected. |
| `term_↔_`, `term_∧_`, `term_∨_`, `term¬_`, `term∃_,_` | Fixed `Init` logical notation expands to the corresponding trusted logical constants and binders. There is no candidate-defined notation or macro environment. |
| `term{_:_//_}` | Fixed subtype-constructor notation. Expected-type elaboration and ordinary applications are used; no command or tactic is run. |
| `term_+_`, `term_*_`, `term_=_`, `term_≤_`, `term_<_`, `term_++_`, `term_×_`, `term_∈_` | Fixed `Init` notation, name resolution, and where applicable typeclass synthesis for arithmetic, append, products, and membership. The candidate cannot register instances or syntax, but an approved declaration may receive an instance as an explicit parameter. Exact statement and dependency checks remain mandatory. |
| `term[_]`, `term_::_` | Fixed list-literal and list-constructor macros from `Init`; their element terms are recursively checked. Array, quotation, interpolation, and file-inclusion syntax is not included. |

Macro expansion in this section is trusted closed `Init` behavior. Admission
does not inspect only the expansion and does not prove that the implementation
of those trusted macros is correct.

### Module and command structure

| Permitted kinds | Reachable mechanism and boundary |
| --- | --- |
| `Lean.Parser.Module.header`, `Lean.Parser.Module.import` | Header parsing only. Each import must have the unmodified parser shape and exactly match the maintained policy. Library modules import exactly `Init`; the root imports exactly all approved modules; a task solution imports exactly `TNDLib`. Candidate modules are not imported by the admission process. |
| `Lean.Parser.Command.moduleDoc`, `Lean.Parser.Command.docComment` | Documentation tokens are inert parser data. A declaration's modifier field may contain documentation only. Nested comments are handled by the trusted lexer; executable text after a closed comment is parsed separately and rejected unless otherwise permitted. |
| `Lean.Parser.Command.universe` | Declares exactly the maintained universe-name sequence, in the maintained position. Only the approved task currently has universe declarations. Universe inference remains part of trusted elaboration, while the checker compares the resulting statement. |
| `Lean.Parser.Command.namespace`, `Lean.Parser.Command.end` | Opens and closes exactly one maintained namespace with exact matching names. Extra, nested, unmatched, qualified, or root namespace escapes are rejected. |
| `Lean.Parser.Command.declaration`, `Lean.Parser.Command.definition`, `Lean.Parser.Command.theorem` | The only executable top-level commands. Each must be a plain `def` or `theorem` inside the approved namespace and have an exact approved unqualified name. The declaration inventory must match policy exactly. No `axiom`, `opaque`, `instance`, `initialize`, `run_cmd`, macro, syntax, notation, evaluation, option, or attribute command is admitted. |
| `Lean.Parser.Command.declModifiers` | The wrapper is necessary for ordinary declarations, but every non-documentation child is rejected. This excludes `private`, `protected`, `unsafe`, `partial`, `noncomputable`, and attributes. |
| `Lean.Parser.Command.declId`, `Lean.Parser.Command.declSig`, `Lean.Parser.Command.optDeclSig` | Ordinary declaration names, binders, and result types. Top-level names are checked against policy. Auto-implicit insertion, binder inference, coercions, and typeclass search are trusted elaborator behavior; the independently exported declaration type is compared with the approved challenge. |
| `Lean.Parser.Command.declValSimple` | A `:=` body containing a recursively checked term. It reaches ordinary term elaboration only. Tactic blocks, quotations, scoped options, and other term forms have unlisted kinds and are rejected. |
| `Lean.Parser.Command.declValEqns` | Pattern/equation declarations. The trusted equation compiler may create helper declarations and invoke termination checking. The maintained export inventory covers all public generated declarations, and proof dependency closure plus kernel replay covers generated dependencies. |
| `Lean.Parser.Command.eoi` | Accepted only when the parser has reached the physical end of the input. Other terminal commands, including `exit` and mid-file imports, are rejected before the command inventory check. |

`Lean.Parser.Term.matchAltsWhereDecls` is needed as an empty parser wrapper in
ordinary equation and match syntax. A nonempty `where` block introduces the
separate unlisted kind `Lean.Parser.Term.whereDecls` and is rejected. Thus a
nested helper declaration cannot bypass the top-level declaration inventory.

### Binders, functions, and types

| Permitted kinds | Reachable mechanism and boundary |
| --- | --- |
| `Lean.binderIdent`, `Lean.explicitBinders`, `Lean.unbracketedExplicitBinders`, `Lean.Parser.Term.explicitBinder`, `Lean.Parser.Term.implicitBinder`, `Lean.Parser.Term.instBinder` | Ordinary explicit, implicit, and instance binders. Instance binders permit normal trusted typeclass synthesis; they do not register a global instance. Direct use of Lean's four elaboration-special type annotations is rejected by identifier. |
| `Lean.Parser.Term.arrow`, `Lean.Parser.Term.depArrow`, `Lean.Parser.Term.forall` | Pi-type and universal-quantifier elaboration. Auto-implicit insertion can occur under Lean's pinned defaults. The checker compares the complete elaborated statement, including inserted parameters and assumptions. |
| `Lean.Parser.Term.fun`, `Lean.Parser.Term.basicFun` | Lambda/function syntax elaborated to kernel lambdas. This includes anonymous binder forms used by the maintained corpus; it does not enable tactic syntax. |
| `Lean.Parser.Term.type`, `Lean.Parser.Term.prop` | `Type` and `Prop` elaboration with the maintained universes. Other universe or sort syntax must still be composed solely of permitted children and pass the exact statement comparison. |
| `Lean.Parser.Term.typeSpec` | Ordinary type ascription. It can guide expected-type elaboration, coercion insertion, and typeclass synthesis, but cannot install an elaborator. |

### Terms and pattern matching

| Permitted kinds | Reachable mechanism and boundary |
| --- | --- |
| `Lean.Parser.Term.app` | Ordinary application, implicit-argument insertion, unification, coercion insertion, and typeclass synthesis against the trusted environment and earlier admitted declarations. Direct identifier restrictions still apply to every identifier in the application. |
| `Lean.Parser.Term.dotIdent` | Expected-type-directed shorthand such as `.isTrue`. Resolution is performed by the pinned elaborator against existing declarations; the candidate cannot register new syntax or elaborators. |
| `Lean.Parser.Term.proj`, `fieldIdx` | Named and numeric projection elaboration. It can consult trusted structure metadata and unfold types for resolution. It does not execute a candidate command. |
| `Lean.Parser.Term.anonymousCtor` | Expected-type-directed constructor elaboration for `⟨...⟩`, including recursively checked fields. The expected structure and its constructors remain visible in the exported proof term. |
| `Lean.Parser.Term.paren`, `Lean.Parser.Term.hygienicLParen` | Grouping and trusted hygiene wrappers; their contents are recursively checked. |
| `Lean.Parser.Term.tuple` | Trusted tuple notation, expanded to nested products/constructors; each component is recursively checked. |
| `Lean.Parser.Term.hole` | An explicit `_` creates an elaboration metavariable. It may be solved by expected-type unification or ordinary instance synthesis; it does not contain tactic syntax. Any unresolved metavariable makes the later build fail. Because this is an inference surface, it must be reconsidered if Lean changes hole synthesis behavior. |
| `Lean.Parser.Term.match`, `Lean.Parser.Term.matchDiscr`, `Lean.Parser.Term.matchAlt`, `Lean.Parser.Term.matchAlts`, `Lean.Parser.Term.matchAltsWhereDecls` | Trusted match elaboration, pattern checking, recursor selection, and generated helper declarations. Pattern terms and bodies are recursively checked. Nonempty local `where` declarations are rejected as described above. Export inventory, dependency traversal, and kernel replay are still required. |
| `Lean.Parser.Termination.suffix` | The parser wrapper may occur, but every child must be an empty `null`. Explicit `termination_by` or `decreasing_by` material is rejected. Structural termination and the pinned default termination machinery can still run for equation definitions. |

## Special elaboration and execution paths

The following paths motivated restrictions beyond the syntax-kind whitelist:

- `autoParam` stores tactic syntax in a type and can cause the elaborator to
  execute it when an argument is omitted. Syntax data can be constructed
  without quotation or string-literal syntax, so the identifier itself is
  rejected.
- `optParam`, `outParam`, and `semiOutParam` alter argument insertion or
  unification. They are not ordinary type constructors for this policy and are
  rejected directly.
- Before the `outParam` fix, an exact Lean 4.35.0 probe showed that a modified
  approved declaration using `outParam` in its result type was both admitted
  and compiled. The parser blacklist now covers both remaining type-annotation
  gadgets, and the 67-case suite contains rejection regressions.
- Direct references under `Lean` are rejected. In particular this excludes the
  `Lean.reduceBool`/`Lean.reduceNat` native-reduction mechanism and its related
  proof axioms, which can invoke the compiler/interpreter during kernel
  checking. Tactic entry points such as `native_decide` are independently
  excluded because tactic syntax is not permitted.
- Direct effectful and reflective roots, strings, characters, and
  `unsafeCast` are rejected. This is conservative and incomplete by itself:
  trusted `Init` contains safe constants with external or alternative runtime
  implementations. Ordinary elaboration and kernel reduction use their
  logical definitions; the admitted syntax contains no command that evaluates
  a candidate term and no permitted native-reduction entry point. This claim
  must be re-audited against the exact pinned Lean sources.

The closed syntax set also excludes `by`, `sorry`, quotations, `eval%`,
`include_str`, custom macros/elaborators, scoped options, attributes,
initializers, and evaluation commands. Negative fixtures exercise these
boundaries. A negative fixture demonstrates current behavior; it is not a
general proof that every parser ambiguity or future extension is harmless.

## What the proof-object boundary still proves

Source admission does not decide constructivity or accept a theorem merely
because it compiles. The later independent checker must still:

- compare the exact public declaration inventory, including generated public
  helpers;
- keep definitions immutable relative to the approved challenge and compare
  every theorem statement, so inferred parameters and changed assumptions are
  visible;
- traverse raw exported declaration types and bodies for their complete axiom
  closure, permitting only the maintained policy axioms;
- parse contributor output as data, independently replay the exported
  declarations through Lean's kernel, and reject missing or forged objects;
- bind the report to the exact Git source bytes, toolchain, policy, challenge,
  and solution inputs.

These checks address proof meaning and artifact identity. They do not make the
source parser or elaborator untrusted, and they do not contain resource use or
prove the operating system isolation boundary.

## Remaining assumptions and release blockers

- The precise Lean 4.35.0 parser, elaborator, kernel, compiler, `Init` sources,
  and supported primitives are trusted. A binary version string alone is not a
  semantic audit.
- The accepted identifier set has not been proven complete by formal means.
  Resolution through trusted constants, coercions, typeclasses, macros, and
  generated declarations remains part of the trusted elaboration surface.
- CPU, memory, process, network, and temporary-filesystem controls must be
  demonstrated on the native Linux runner with the actual default seccomp
  profile. The production build/export quota path is wired but has only mock
  coverage; exact limits, daemon mount visibility, exhaustion, and recovery
  remain unvalidated.
- Exact-byte staging and post-export rechecks reduce source/artifact races, but
  host path, mount-namespace, privileged-helper, and crash-recovery assumptions
  require the native Linux resource-boundary validation.
- The complete GitHub required-check and merge ordering must be validated
  separately. Source semantics do not close the merge-time rerun race.

Certification therefore remains disabled even when every local admission
fixture passes.

## Mandatory review for a Lean or policy change

Any Lean toolchain change, newly permitted syntax kind, new identifier
exception, or change to the imported module set invalidates this review. Keep
certification disabled until a maintainer performs and records all of the
following against the exact proposed Lean source revision and binaries:

1. Diff the parser AST kinds produced by the complete accepted corpus and task
   corpus. Explain every added, removed, renamed, or differently shaped node.
2. Audit the implementations registered for every permitted syntax kind and
   fixed notation under the new `Init`, including macro expansion, term
   elaborators, equation/match compilation, hole synthesis, coercion and
   typeclass search, termination handling, and module parsing.
3. Search the new elaborator and kernel sources for special type annotations,
   automatic/default parameters, native-reduction or interpreter hooks,
   compile-time evaluation, file inclusion, reflection, unsafe casts, and new
   syntax that can install or execute code. Update direct restrictions and
   proof-object prohibited dependencies as required.
4. Re-run the complete positive and negative admission suite, add a regression
   for every discovered semantic change, and show that the exact initial
   corpus and maintained task still elaborate from admitted read-only bytes.
5. Re-run the split build/export and independent proof-object checker in the
   production-like native Linux isolation boundary, including hostile-source,
   cleanup, timeout, memory, output, and filesystem-quota cases.
6. Review and update this document with exact evidence. A passing version check
   or unchanged syntax-kind names is insufficient approval.

The same process applies when broadening contribution syntax even without a
Lean bump: permission follows reviewed semantics, not parser-node spelling.
