/-
Development-only source admission prototype. Candidate files are parsed as data.
This program never imports or elaborates a candidate module or command.
-/
import Lean

open Lean

namespace TNDAdmission

structure SourceSpec where
  path : String
  module_name : String
  namespace_name : String
  imports : Array String
  declarations : Array String
  universes : Array String
  deriving FromJson

structure Config where
  source_files : Array SourceSpec
  deriving FromJson

/-- Closed list of parser node kinds reviewed for the initial plain-term corpus. -/
def permittedKinds : Array Name := (#[
  "null", "fieldIdx", "hygieneInfo", "num",
  "term_↔_", "term_∧_", "term_∨_", "term¬_", "term{_:_//_}", "term∃_,_",
  "term_+_", "term_*_", "term_=_", "term_≤_", "term_<_", "term_++_", "term_×_", "term_∈_", "term[_]", "term_::_",
  "Lean.binderIdent", "Lean.explicitBinders", "Lean.unbracketedExplicitBinders",
  "Lean.Parser.Module.header", "Lean.Parser.Module.import",
  "Lean.Parser.Command.declId", "Lean.Parser.Command.declModifiers",
  "Lean.Parser.Command.declSig", "Lean.Parser.Command.optDeclSig",
  "Lean.Parser.Command.declValSimple", "Lean.Parser.Command.declValEqns",
  "Lean.Parser.Command.declaration", "Lean.Parser.Command.definition",
  "Lean.Parser.Command.theorem", "Lean.Parser.Command.docComment",
  "Lean.Parser.Command.end", "Lean.Parser.Command.eoi",
  "Lean.Parser.Command.moduleDoc", "Lean.Parser.Command.namespace",
  "Lean.Parser.Command.universe",
  "Lean.Parser.Term.anonymousCtor", "Lean.Parser.Term.app", "Lean.Parser.Term.arrow",
  "Lean.Parser.Term.basicFun", "Lean.Parser.Term.dotIdent", "Lean.Parser.Term.depArrow",
  "Lean.Parser.Term.explicitBinder", "Lean.Parser.Term.forall", "Lean.Parser.Term.fun",
  "Lean.Parser.Term.implicitBinder", "Lean.Parser.Term.type",
  "Lean.Parser.Term.hole", "Lean.Parser.Term.hygienicLParen", "Lean.Parser.Term.instBinder",
  "Lean.Parser.Term.match", "Lean.Parser.Term.matchAlt", "Lean.Parser.Term.matchAlts", "Lean.Parser.Term.matchDiscr",
  "Lean.Parser.Term.matchAltsWhereDecls", "Lean.Parser.Term.paren", "Lean.Parser.Term.proj",
  "Lean.Parser.Term.prop", "Lean.Parser.Term.tuple", "Lean.Parser.Term.typeSpec",
  "Lean.Parser.Termination.suffix"
] : Array String).map (fun s => s.splitOn "." |>.foldl Name.str .anonymous)

partial def isEmptySyntax : Syntax → Bool
  | .node _ kind args => kind == `null && args.all isEmptySyntax
  | _ => false

partial def isOnlyDocumentation : Syntax → Bool
  | .node _ kind args =>
    kind == ``Parser.Command.docComment || (kind == `null && args.all isOnlyDocumentation)
  | _ => false

partial def checkTree (stx : Syntax) (depth : Nat := 0) : Except String Unit := do
  if depth > 128 then throw "syntax exceeds maximum nesting depth"
  match stx with
  | .missing => throw "missing syntax is not admissible"
  | .ident _ _ id _ =>
    if id.getRoot == `_root_ then throw "root-qualified names are not admissible"
    -- autoParam evaluates tactic Syntax during elaboration; ordinary constructor
    -- terms can build that Syntax without a quotation or string literal.
    if #[`autoParam, `optParam, `outParam, `semiOutParam,
         `Lean, `IO, `BaseIO, `EIO, `EStateM, `ST,
         `String, `Char, `unsafeCast].any (·.isPrefixOf id) then
      throw "reflective/effectful references are outside the admitted subset"
  | .atom .. => pure ()
  | .node _ kind args =>
    unless permittedKinds.contains kind do throw s!"unsupported syntax kind: {kind}"
    if kind == ``Parser.Command.declModifiers && !args.all isOnlyDocumentation then
      throw "declaration attributes and modifiers are not admissible"
    if kind == ``Parser.Termination.suffix && !args.all isEmptySyntax then
      throw "termination annotations are not admissible"
    for arg in args do checkTree arg (depth + 1)

/-- Parse to actual EOI, rejecting import/exit terminals and every parser error. -/
partial def parseStrict (env : Environment) (path contents : String) : IO (Syntax × Array Syntax) := do
  let input := Parser.mkInputContext contents path
  let (header, state, messages) ← Parser.parseHeader input
  if messages.hasErrors || state.recovering then throw <| IO.userError "invalid module header"
  let rec commands (state : Parser.ModuleParserState) (out : Array Syntax) : IO (Array Syntax) := do
    let (command, next, errors) := Parser.parseCommand input { env, options := {} } state {}
    if errors.hasErrors || next.recovering then throw <| IO.userError "invalid command syntax"
    if command.isOfKind ``Parser.Command.eoi then
      unless input.atEnd next.pos do throw <| IO.userError "EOI before end of source"
      return out.push command
    if Parser.isTerminalCommand command then throw <| IO.userError "non-EOI terminal command"
    unless state.pos < next.pos do throw <| IO.userError "parser did not consume input"
    commands next (out.push command)
  return (header.raw, ← commands state #[])

def checkHeader (header : Syntax) (spec : SourceSpec) : Except String Unit := do
  unless header.isOfKind ``Parser.Module.header && header.getNumArgs == 3 do
    throw "unexpected module header shape"
  unless isEmptySyntax header[0] && isEmptySyntax header[1] do
    throw "module/prelude modifiers are not admissible"
  let mut imports := #[]
  for item in header[2].getArgs do
    unless item.isOfKind ``Parser.Module.import && item.getNumArgs == 6 do
      throw "unexpected import shape"
    unless #[item[0], item[1], item[3], item[5]].all isEmptySyntax do
      throw "modified imports are not admissible"
    unless item[4].isIdent do throw "import must be a module identifier"
    imports := imports.push item[4].getId.toString
  unless imports == spec.imports do throw "imports differ from approved module inventory"

def checkCommands (commands : Array Syntax) (spec : SourceSpec) : Except String Unit := do
  let mut opened := false
  let mut closed := false
  let mut declarations : Array String := #[]
  let mut universes : Array String := #[]
  for command in commands do
    checkTree command
    if command.isOfKind ``Parser.Command.moduleDoc || command.isOfKind ``Parser.Command.eoi then
      pure ()
    else if command.isOfKind ``Parser.Command.universe then
      if opened || closed || !universes.isEmpty || spec.universes.isEmpty then
        throw "unexpected universe declaration"
      unless command.getNumArgs == 2 && command[1].getArgs.all Syntax.isIdent do
        throw "unsupported universe declaration"
      universes := command[1].getArgs.map (fun id => id.getId.toString)
      unless universes == spec.universes do throw "unapproved universe names"
    else if command.isOfKind ``Parser.Command.namespace then
      if spec.namespace_name.isEmpty || opened || closed then throw "unexpected namespace"
      unless command.getNumArgs == 2 && command[1].isIdent &&
          command[1].getId.toString == spec.namespace_name do throw "unapproved namespace"
      opened := true
    else if command.isOfKind ``Parser.Command.end then
      unless opened && !closed && command[1].getNumArgs == 2 &&
          command[1][0].isIdent && command[1][0].getId.toString == spec.namespace_name &&
          isEmptySyntax command[1][1] do throw "unmatched namespace end"
      closed := true
    else if command.isOfKind ``Parser.Command.declaration then
      unless opened && !closed && command.getNumArgs == 2 do throw "declaration outside approved namespace"
      let body := command[1]
      unless body.isOfKind ``Parser.Command.theorem || body.isOfKind ``Parser.Command.definition do
        throw "only plain theorem and definition commands are admissible"
      let id := body[1]
      unless id.isOfKind ``Parser.Command.declId && id.getNumArgs == 2 &&
          id[0].isIdent && isEmptySyntax id[1] do throw "unsupported declaration identifier"
      let .str .anonymous shortName := id[0].getId
        | throw "qualified declaration names are not admissible"
      unless !shortName.isEmpty && shortName.toList.all (fun c => c.isAlphanum || c == '_') do
        throw "unsupported declaration name"
      let name := spec.namespace_name ++ "." ++ shortName
      unless spec.declarations.contains name && !declarations.contains name do
        throw "unapproved or duplicate source declaration"
      declarations := declarations.push name
    else throw s!"unsupported command: {command.getKind}"
  unless spec.namespace_name.isEmpty || (opened && closed) do throw "namespace was not closed"
  unless declarations.qsort (· < ·) == spec.declarations.qsort (· < ·) do
    throw "source declaration inventory differs from policy"
  unless universes == spec.universes do throw "universe inventory differs from policy"

def checkRoot (env : Environment) (cfg : Config) (sourceRoot : String) : IO Json := do
  for spec in cfg.source_files do
    let path := System.FilePath.mk sourceRoot / spec.path
    let (header, commands) ← parseStrict env spec.path (← IO.FS.readFile path)
    IO.ofExcept <| checkTree header
    IO.ofExcept <| checkHeader header spec
    IO.ofExcept <| checkCommands commands spec
  return Json.mkObj [("status", toJson "admitted-source-syntax"),
    ("scope", toJson "approved-library-source-only"), ("development_only", toJson true)]

end TNDAdmission

unsafe def main (args : List String) : IO UInt32 := do
  try
    let (batch, policyPath, sourceArgument) ← match args with
      | [policy, root] => pure (false, policy, root)
      | ["--batch", policy, roots] => pure (true, policy, roots)
      | _ => throw <| IO.userError "usage: Main.lean [--batch] POLICY SOURCE_ROOT_OR_ROOTS_JSON"
    unless Lean.versionString == "4.35.0" do throw <| IO.userError "admission requires pinned Lean 4.35.0"
    initSearchPath (← findSysroot)
    enableInitializersExecution
    -- Only the trusted distribution's Init is loaded, never the source headers.
    let env ← importModules #[{ module := `Init }] {} (loadExts := true)
    let cfg : TNDAdmission.Config ← IO.ofExcept <| fromJson? (← IO.ofExcept <| Json.parse (← IO.FS.readFile policyPath))
    if batch then
      let roots : Array String ← IO.ofExcept <| fromJson? (← IO.ofExcept <| Json.parse (← IO.FS.readFile sourceArgument))
      let mut reports : Array Json := #[]
      for root in roots do
        let report ← try TNDAdmission.checkRoot env cfg root catch error =>
          pure <| Json.mkObj [("status", toJson "rejected"), ("reason", toJson error.toString)]
        reports := reports.push report
      IO.println (toJson reports).compress
    else
      IO.println (← TNDAdmission.checkRoot env cfg sourceArgument).compress
    return 0
  catch error =>
    IO.println <| (Json.mkObj [("status", toJson "rejected"), ("reason", toJson error.toString)]).compress
    return 1
