# Matching source-admission review

Status: a separate development profile is implemented, 2026-11-01.
The production parser, production admission policy, certification flags, and
production source inventory remain unchanged. The pilot is now
isolated under `pilot/` as the explicit `TNDMatchingPilot` Lake target. Its
logical modules retain the `TNDLib.Matching` namespace. The original production
root and inventory continue to cover only the existing six modules.

## Observed boundary

The new matching modules compile and their proof objects can be independently
replayed. The separate development profile below accepts their source, while
the unchanged production source-admission path continues to reject them.
These are separate facts: replay validates the elaborated declarations, while
source admission constrains the elaboration features that may interpret source.

When first placed inside the production source directory, the pilot failed
the unchanged `source_bytes` guard with `source module inventory mismatch`.
Isolating development sources restored the original inventory without weakening
that guard. Promoting these sources would still require reviewed source-root
mapping, header, command-shape, and import-graph changes.

Supplying a supplemental inventory with `Basic.lean` and its
actual internal import then fails Python `policy_for` with
`prototype module imports must be exactly Init`. That function also requires
direct root imports of every source module. The new files instead form a small
dependency DAG below `TNDLib.Matching`. Adding files to a manifest alone does
not admit them. Both Python failures were reproduced directly without building
or elaborating candidate source.

A direct run of the unchanged maintained Lean parser with a supplemental policy
for `Basic.lean` and its actual `TNDLib.Finite` import returned:

```json
{"reason":"unsupported syntax kind: Lean.Parser.Command.structure","status":"rejected"}
```

This supplemental diagnostic bypasses only the Python policy-shape check; it
is not a passing end-to-end admission run. Its purpose was to locate the first
actual parser rejection after supplying the correct file/header inventory.

`AdmissionProbe.lean` parses the actual files as data using the trusted `Init`
grammar and inventories their syntax kinds and tree shapes. It does not import
candidate headers, elaborate candidate commands, or run candidate initializers.
`admission-observed.json` records the production parser digest, source snapshot
digests, and observed kind differences. A digest identifies the probed snapshot;
subsequent edits require another probe before making claims about current bytes.

Reproduce the syntax inventory from the library root with:

```sh
lake env lean --run audit/matching/AdmissionProbe.lean \
  pilot/TNDLib/Matching/*.lean > /tmp/tnd-matching-ast.json
```

The probe is diagnostic tooling, not a safe entry point for arbitrary hostile
unbounded files. Production admission must retain its existing byte, depth,
resource, time, and output limits.

## Refinement already made to minimize the extension

`Basic.blockingPairDecidable` was the sole source-level instance declaration.
It is now an ordinary named `def` returning constructive `Decidable` evidence.
The checker and its correctness theorem pass that evidence explicitly.

This preserves public declaration names and mathematical semantics while
avoiding new instance-registration command semantics, priorities, local/scoped
instance handling, and `attrKind` support. The full Pilot build and existing
Basic examples pass after this refinement. `inferInstanceAs` remains a term
used to construct the named decision from the fixed trusted core instances;
it does not register a new candidate instance.

Private proof-helper modifiers were also identified during the initial scan.
They should remain excluded from the admitted source profile: use stable
ordinary helper names and include them in the maintained inventory. Private
name mangling should not be accommodated with an open-ended export prefix.

## Minimal remaining grammar delta

The observed source needs the following closed families in addition to the
existing plain-term grammar. Do not enable all Lean commands or accept unknown
nodes by recursively checking their children.

### Plain data declarations

Observed structure families are `Preferences`, `PerfectMatching`, algorithm
`State`, and the proposition-valued invariant package `Valid`. The two result
families are the nonrecursive `StepResult` and `Outcome` sums.

New command node kinds:

- `Lean.Parser.Command.structure`
- `Lean.Parser.Command.structureTk`
- `Lean.Parser.Command.structFields`
- `Lean.Parser.Command.structSimpleBinder`
- `Lean.Parser.Command.optDeriving`
- `Lean.Parser.Command.inductive`
- `Lean.Parser.Command.ctor`

Adding these kind names is insufficient. Add shape validators with maintained
per-declaration inventories of field names and constructor names, alongside the
existing exact source declaration inventory:

- A `structure` body has arity 6 in the pinned parser. Require the plain
  `structure` token in slot 0; reject `class`. Slot 1 is the existing simple
  `declId`. Validate the parameter/type signature in slot 2. Require the
  `extends` slot 3 empty. Slot 4 is the three-item `where` block; require its
  optional explicit constructor slot empty. Slot 5 is `optDeriving` containing
  only an empty optional node.
- Traverse only the actual `structFields` group in that `where` block. Each
  observed `structSimpleBinder` has arity 4: modifiers, a simple field
  identifier, its optional signature, and a default-value slot. Require
  documentation-only modifiers, an approved unique field name, the reviewed
  plain typed-field signature, and an empty default slot. Reject defaults even
  when their expression would otherwise be an allowed pure term.
- An observed `inductive` body has arity 8. Validate the simple family name,
  parameter signature, plain `where`, and exact constructor sequence. Each
  `ctor` has arity 5: optional documentation, `|`, modifiers, identifier, and
  signature. Require approved simple constructor names and documentation-only
  modifiers. Keep the optional suffix slots and deriving clause empty.
- Limit the first patch to these maintained nonrecursive result sums. Validate
  their reviewed signatures, including where the result family occurs; do not
  silently admit new recursive, mutual, indexed, nested, or derived families.
- Track source names separately from compiler-generated declarations. Every
  constructor, projection, recursor, equation helper, and other exported
  declaration still needs its exact checked inventory and dependency audit.
  Do not accept arbitrary generated names merely because they share a prefix.

### Pure term forms

The actual additional term kinds are:

- Ordinary and proof-binding conditionals: `termIfThenElse` and
  `termDepIfThenElse`.
- Identifier lets: `Lean.Parser.Term.let`, `letConfig`, `letDecl`, `letId`, and
  `letIdDecl` (the abbreviated entries here have the same parser prefix).
- Explicit arguments and type hints: `Lean.Parser.Term.explicit`,
  `namedArgument`, `typeAscription`, `show`, `fromTerm`, `inferInstanceAs`.
- Equality substitution: `Lean.Parser.Term.subst`.
- Calculation chains: `Lean.calc`, `Lean.calcFirstStep`, `Lean.calcStep`, and
  `Lean.calcSteps`.
- Trusted-core notation nodes: `term_≠_`, `term_∉_`, and `term_⊆_`.

These forms build pure terms or constrain their elaboration using the fixed
trusted grammar. Every nested type, condition, branch, value, and proof must
still pass the recursive node and identifier checks. In particular:

- Plain `if` has arity 6; proof-binding `if` has arity 8. Check their fixed
  tokens and proof binder shape, then recursively validate all term children.
- The observed `let` has arity 5. Its `letConfig` contains only an empty
  optional node. Permit only a single `letIdDecl` with a simple identifier,
  optional plain type, `:=`, and checked value. Reject configuration flags,
  recursive lets, pattern lets, `letI`, and local instance registration.
- Calculation steps require explicit checked proof terms. A `by` block nested
  inside a calculation is still unsupported. Do not add tactic or elaborator
  quotation nodes.
- Keep the current bans on root-qualified and reflective/effectful references.
  `@` and named arguments must not bypass identifier traversal.
- Keep termination annotations, local `where` declarations, attributes,
  `unsafe`, `partial`, `noncomputable`, syntax extensions, commands that execute
  code, strings/character construction, and custom elaboration outside the
  admitted language.

`Lean.Name.toString` renders symbolic names with quotation marks such as
`«term_≠_»`; those marks are presentation, not additional parser kinds. Compare
actual `Name` values when implementing the allowlist.

## Maintained import-DAG validation

Keep exact import lists in the trusted policy and exact header comparison in
the Lean parser. Replace the one-level Python restriction with a closed DAG
check over the complete maintained source inventory:

1. Validate unique module names, ordinary normalized paths, and the exact
   module-name-to-path correspondence. Reject duplicate imports and modules.
2. Permit `Init` as the sole external library leaf for this profile. Every
   other import must name a listed local source module. Continue rejecting
   `Lean`, `Std`, Mathlib, unknown packages, and dynamic/native/modified imports.
3. Reject cycles, self-imports, and importing root `TNDLib` from a library
   child. Validate a deterministic topological ordering or compute it from
   the maintained graph. No candidate header selects an unreviewed edge.
4. Require the root aggregator's transitive import closure to cover exactly
   all maintained source modules. Alternatively, keep redundant direct root
   imports of every module for the first patch, but do not equate direct
   coverage with general DAG validation.
5. Keep task imports fixed to the reviewed root module. Preserve the complete
   ordinary-file inventory, symlink rejection, exact immutable snapshot hashes,
   and fresh isolated build behavior.

The source parser must still load only trusted `Init`; it must not import the
candidate DAG to obtain syntax extensions. Candidate modules are parsed
individually against that same fixed grammar. Building the admitted bytes is a
later isolated stage with its own resource boundary.

## Threat model and required negative controls

The boundary is meant to prevent source elaboration from installing custom
commands/macros, invoking candidate elaborator callbacks, importing unreviewed
code, or changing which bytes are compiled. It does not prove mathematical
source fidelity by counting syntax nodes. Kernel replay, axiom auditing,
statement comparison, and review of the source-to-paper map remain separate.

Before routing a production audit through the extension, require negative
fixtures covering at least:

- `class` substituted for `structure`; `extends`; an explicit constructor name;
  changed/duplicate fields; pure and tactic field defaults; deriving clauses;
  field/constructor attributes; private/protected/unsafe modifiers.
- Extra, missing, duplicate, recursive, mutual, or indexed constructors; altered
  family signatures; hidden generated declarations outside the exact inventory.
- Candidate `instance`, local/scoped instances, priority syntax, `letI`,
  `let rec`, configured lets, pattern lets, and attached `where` declarations.
- `by` in a field type, default, `if` condition/branch, named argument, let value,
  and calculation step; syntax quotations and reflective/effectful references
  under `@`, `show`, `inferInstanceAs`, and equality substitution.
- Unknown import edges, cycles, self-imports, root-child cycles, duplicate
  imports, missing root reachability, imported `Lean`/Mathlib, and modified
  import syntax. A malicious imported file must never execute during parsing.
- Post-admission byte changes, extra `.olean` or non-source files under the
  candidate tree, path aliases/symlinks, oversized source, deep syntax, timeout,
  truncated output, malformed JSON, and a parser that fails after partial work.

Positive controls must cover every admitted AST form actually used by the
matching corpus, including empty optional deriving/extends/default slots,
ordinary and dependent `if`, typed/untyped identifier lets, the three rank
notation nodes, `calc`, `@`, named arguments, `show`, and substitution. Re-run
all existing admission fixtures to demonstrate that the expanded profile does
not accidentally admit previously rejected tactics, attributes, callbacks, or
artifacts.

## Implemented development profile

`audit/matching/Main.lean` implements the narrow profile described above. Its
accepted report identifies `profile: matching-plain-term-v1`,
`scope: matching-pilot-source-only`, and `development_only: true`. It parses
only listed source files and never imports candidate headers. The staging
boundary and import-DAG checks belong to the separate trusted source driver.

`source-policy.json` lists the thirteen pilot modules and existing constructive
`TNDLib/Finite.lean` leaf. Every top-level declaration and namespace block is
explicit. `StableMatch.lean` needs two sibling namespace blocks; the parser
checks their exact sequence and forbids nested, repeated, or unlisted blocks.
All data declarations have both human-readable field/constructor inventories
and an exact canonical AST shape. The latter pins their reviewed parameter,
field, and result-family signatures instead of admitting a general new class
of recursive or indexed declarations.

Local/proof/named-argument binders accept ordinary unqualified Unicode names.
A positive `(α := Nat)` fixture exposed that `Char.isAlphanum` is ASCII-only;
using that declaration-name rule for local binders rejected valid ordinary
Lean arguments. This local-name correction preserves the global declaration
and field inventories and still subjects all identifiers to the root-qualified
and reflective/effectful prefix bans.

The normal CLI accepts an explicit maintained policy and root:

```sh
lake env lean --run audit/matching/Main.lean \
  audit/matching/source-policy.json .
```

A maintenance-only `--describe ROOT PATHS...` mode emits a distinct
`description-only` report for reviewing proposed policy metadata. Normal
admission never describes candidate bytes to create or update its own policy.
The fixture harness describes its fixed trusted fixture once, then changes
only candidate text while retaining that same policy.

Run the actual-source and hostile grammar fixtures with:

```sh
python3 audit/matching/test_admission.py \
  --output audit/matching/admission-fixture-results.json
```

The receipt is written only after the full suite succeeds and binds the
production parser, development parser, maintained source policy, and fixture
harness digests. The suite includes an unreviewed candidate module containing
an initializer that would write a sentinel; the file must remain inert. The
harness verifies ordinary positive syntax and hostile command/default/deriving,
instance, import, reflection, tactic, inventory, malformed-input, and depth
cases. It is a development grammar regression test, not acceptance of the
production sandbox/resource boundary.

Before any production adoption, independently review the delta, reconcile the
whole language/semantic threat model, retain all applicable original negative
controls, and exercise exact immutable bytes through staging, isolated build,
export, independent replay, and source-to-statement checks. Passing these
fixtures does not prove semantic completeness or authorize changing either
production certification flag.
