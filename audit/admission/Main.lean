/-
Reviewed source-admission parser. Candidate files are parsed strictly as data.
This program never imports or elaborates a candidate module or command.
-/
import Lean

open Lean

namespace TNDAdmission

def profileName := "constructive-source-v1"

structure DataSpec where
  name : String
  kind : String
  fields : Array String
  constructors : Array String
  shape : String
  deriving FromJson, ToJson

structure SourceSpec where
  path : String
  module_name : String
  namespaces : Array String
  imports : Array String
  declarations : Array String
  universes : Array String
  data_declarations : Array DataSpec
  deriving ToJson

instance : FromJson SourceSpec where
  fromJson? j := do
    let path ← j.getObjValAs? String "path"
    let module_name ← j.getObjValAs? String "module_name"
    let namespaces ← match j.getObjVal? "namespaces" with
      | .ok rawNs => fromJson? rawNs
      | .error _ =>
        let ns ← j.getObjValAs? String "namespace_name"
        pure (if ns.isEmpty then #[] else #[ns])
    let imports ← j.getObjValAs? (Array String) "imports"
    let declarations ← j.getObjValAs? (Array String) "declarations"
    let universes ← j.getObjValAs? (Array String) "universes"
    let data_declarations ← match j.getObjVal? "data_declarations" with
      | .ok rawData => fromJson? rawData
      | .error _ => pure #[]
    return {
      path, module_name, namespaces, imports,
      declarations, universes, data_declarations
    }

structure Config where
  profile : Option String := none
  source_files : Array SourceSpec
  deriving FromJson

/-- Canonical data-declaration syntax excluding all source locations. -/
partial def syntaxKey : Syntax → String
  | .missing => "missing"
  | .ident _ _ name _ => "I" ++ (toJson name.toString).compress
  | .atom _ atom => "A" ++ (toJson atom).compress
  | .node _ kind args =>
    "N" ++ (toJson kind.toString).compress ++ "[" ++
      String.intercalate "," (args.toList.map syntaxKey) ++ "]"

/-- Closed list of parser node kinds reviewed for the constructive corpus. -/
def permittedKinds : Array Name := (#[
  "null", "fieldIdx", "hygieneInfo", "num",
  "term_↔_", "term_∧_", "term_∨_", "term¬_", "term{_:_//_}", "term∃_,_",
  "term_+_", "term_-_", "term_*_", "term_=_", "term_≤_", "term_<_", "term_>_", "term_≥_",
  "term_++_", "term_×_", "term_∈_", "term[_]", "term_::_",
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
  "Lean.Parser.Termination.suffix",
  "Lean.Parser.Command.structure", "Lean.Parser.Command.structureTk",
  "Lean.Parser.Command.structFields", "Lean.Parser.Command.structSimpleBinder",
  "Lean.Parser.Command.optDeriving", "Lean.Parser.Command.inductive", "Lean.Parser.Command.ctor",
  "termIfThenElse", "termDepIfThenElse", "term_≠_", "term_∉_", "term_⊆_",
  "Lean.Parser.Term.explicit", "Lean.Parser.Term.let",
  "Lean.Parser.Term.letConfig", "Lean.Parser.Term.letDecl", "Lean.Parser.Term.letId",
  "Lean.Parser.Term.letIdDecl", "Lean.Parser.Term.have", "Lean.Parser.Term.haveDecl",
  "Lean.Parser.Term.haveIdDecl", "Lean.Parser.Term.haveId", "Lean.Parser.Term.haveIdLhs",
  "Lean.Parser.Term.namedArgument",
  "Lean.Parser.Term.subst", "Lean.Parser.Term.typeAscription", "Lean.Parser.Term.inferInstanceAs",
  "Lean.calc", "Lean.calcFirstStep", "Lean.calcStep", "Lean.calcSteps"
] : Array String).map (fun s => s.splitOn "." |>.foldl Name.str .anonymous)

partial def isEmptySyntax : Syntax → Bool
  | .node _ kind args => kind == `null && args.all isEmptySyntax
  | _ => false

partial def isOnlyDocumentation : Syntax → Bool
  | .node _ kind args =>
    kind == ``Parser.Command.docComment || (kind == `null && args.all isOnlyDocumentation)
  | _ => false

def tokenIs (stx : Syntax) (text : String) : Bool := stx.isAtom && stx.getAtomVal == text

def simpleIdentifier (stx : Syntax) : Bool :=
  if stx.isIdent then
    match stx.getId with
    | .str .anonymous shortName =>
      !shortName.isEmpty && shortName.toList.all (fun c => c.isAlphanum || c == '_')
    | _ => false
  else false

/-- Local binders may use ordinary Unicode names without introducing qualification. -/
def localIdentifier (stx : Syntax) : Bool :=
  if stx.isIdent then
    match stx.getId with
    | .str .anonymous shortName => !shortName.isEmpty
    | _ => false
  else false

/-- Validate the optional/configuration slots of admitted pure-term forms. -/
def checkTermShape (stx : Syntax) : Except String Unit := do
  let kind := stx.getKind
  if kind == `termIfThenElse then
    unless stx.getNumArgs == 6 && tokenIs stx[0] "if" && tokenIs stx[2] "then" &&
        tokenIs stx[4] "else" do throw "unsupported conditional shape"
  if kind == `termDepIfThenElse then
    unless stx.getNumArgs == 8 && tokenIs stx[0] "if" &&
        stx[1].isOfKind ``binderIdent && stx[1].getNumArgs == 1 &&
        localIdentifier stx[1][0] && tokenIs stx[2] ":" &&
        tokenIs stx[4] "then" && tokenIs stx[6] "else" do
      throw "unsupported dependent conditional shape"
  if kind == ``Parser.Term.let then
    unless stx.getNumArgs == 5 && tokenIs stx[0] "let" &&
        stx[1].isOfKind ``Parser.Term.letConfig && stx[1].getNumArgs == 1 &&
        isEmptySyntax stx[1][0] && stx[2].isOfKind ``Parser.Term.letDecl &&
        stx[2].getNumArgs == 1 && stx[2][0].isOfKind ``Parser.Term.letIdDecl &&
        isEmptySyntax stx[3] do throw "only plain identifier lets are admissible"
  if kind == ``Parser.Term.letIdDecl then
    unless stx.getNumArgs == 5 && stx[0].isOfKind ``Parser.Term.letId &&
        stx[0].getNumArgs == 1 && localIdentifier stx[0][0] &&
        isEmptySyntax stx[1] && tokenIs stx[3] ":=" do
      throw "configured, parameterized, or pattern lets are not admissible"
  if kind == ``Parser.Term.namedArgument then
    unless stx.getNumArgs == 5 && tokenIs stx[0] "(" && localIdentifier stx[1] &&
        tokenIs stx[2] ":=" && tokenIs stx[4] ")" do
      throw "unsupported named argument shape"

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
    checkTermShape stx
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

def shortDeclName (body : Syntax) : Except String String := do
  let id := body[1]
  unless id.isOfKind ``Parser.Command.declId && id.getNumArgs == 2 &&
      simpleIdentifier id[0] && isEmptySyntax id[1] do
    throw "unsupported declaration identifier"
  return id[0].getId.toString

/-- Closed shapes for the exact maintained structures and nonrecursive sums. -/
def checkDataDeclaration (body : Syntax) (name : String) (spec : SourceSpec) :
    Except String Unit := do
  let matching := spec.data_declarations.filter (fun entry => entry.name == name)
  unless matching.size == 1 do throw "unapproved data declaration"
  let some approved := matching[0]? | throw "missing reviewed data declaration"
  unless syntaxKey body == approved.shape do throw "data declaration differs from reviewed shape"
  if body.isOfKind ``Parser.Command.structure then
    unless approved.kind == "structure" && body.getNumArgs == 6 &&
        body[0].isOfKind ``Parser.Command.structureTk && body[0].getNumArgs == 1 &&
        tokenIs body[0][0] "structure" && isEmptySyntax body[3] &&
        body[4].getNumArgs == 3 && tokenIs body[4][0] "where" &&
        isEmptySyntax body[4][1] && body[4][2].isOfKind ``Parser.Command.structFields &&
        body[4][2].getNumArgs == 1 && body[5].isOfKind ``Parser.Command.optDeriving &&
        body[5].getArgs.all isEmptySyntax do
      throw "only plain structures without extends, constructor names, or deriving are admissible"
    let mut fields := #[]
    for field in body[4][2][0].getArgs do
      unless field.isOfKind ``Parser.Command.structSimpleBinder && field.getNumArgs == 4 &&
          field[0].isOfKind ``Parser.Command.declModifiers &&
          field[0].getArgs.all isOnlyDocumentation && simpleIdentifier field[1] &&
          field[2].isOfKind ``Parser.Command.optDeclSig && isEmptySyntax field[2][0] &&
          field[2][1].getNumArgs == 1 && field[2][1][0].isOfKind ``Parser.Term.typeSpec &&
          isEmptySyntax field[3] do
        throw "only plain typed fields without defaults or modifiers are admissible"
      fields := fields.push field[1].getId.toString
    unless fields == approved.fields && approved.constructors.isEmpty do
      throw "structure field inventory differs from policy"
  else if body.isOfKind ``Parser.Command.inductive then
    unless approved.kind == "inductive" && body.getNumArgs == 8 && tokenIs body[0] "inductive" &&
        body[3].getNumArgs == 1 && tokenIs body[3][0] "where" &&
        isEmptySyntax body[5] && body[6].isOfKind ``Parser.Command.optDeriving &&
        body[6].getArgs.all isEmptySyntax && isEmptySyntax body[7] do
      throw "only maintained plain inductive sums are admissible"
    let mut constructors := #[]
    for ctor in body[4].getArgs do
      unless ctor.isOfKind ``Parser.Command.ctor && ctor.getNumArgs == 5 &&
          isOnlyDocumentation ctor[0] && tokenIs ctor[1] "|" &&
          ctor[2].isOfKind ``Parser.Command.declModifiers &&
          ctor[2].getArgs.all isOnlyDocumentation && simpleIdentifier ctor[3] &&
          ctor[4].isOfKind ``Parser.Command.optDeclSig do throw "unsupported constructor shape"
      constructors := constructors.push ctor[3].getId.toString
    unless constructors == approved.constructors && approved.fields.isEmpty do
      throw "constructor inventory differs from policy"
  else throw "unsupported data declaration kind"

def checkCommands (commands : Array Syntax) (spec : SourceSpec) : Except String Unit := do
  let mut current : Option String := none
  let mut visited : Array String := #[]
  let mut declarations : Array String := #[]
  let mut dataDeclarations : Array String := #[]
  let mut universes : Array String := #[]
  for command in commands do
    checkTree command
    if command.isOfKind ``Parser.Command.moduleDoc || command.isOfKind ``Parser.Command.eoi then
      pure ()
    else if command.isOfKind ``Parser.Command.universe then
      unless visited.isEmpty && current.isNone && universes.isEmpty && !spec.universes.isEmpty do
        throw "unexpected universe declaration"
      unless command.getNumArgs == 2 && command[1].getArgs.all Syntax.isIdent do
        throw "unsupported universe declaration"
      universes := command[1].getArgs.map (fun id => id.getId.toString)
      unless universes == spec.universes do throw "unapproved universe names"
    else if command.isOfKind ``Parser.Command.namespace then
      unless current.isNone && visited.size < spec.namespaces.size &&
          command.getNumArgs == 2 && command[1].isIdent &&
          command[1].getId.toString == spec.namespaces[visited.size]! &&
          !visited.contains command[1].getId.toString do throw "unexpected namespace block"
      let name := command[1].getId.toString
      current := some name
      visited := visited.push name
    else if command.isOfKind ``Parser.Command.end then
      let some name := current | throw "namespace end without an open block"
      unless command.getNumArgs == 2 && command[1].getNumArgs == 2 &&
          command[1][0].isIdent && command[1][0].getId.toString == name &&
          isEmptySyntax command[1][1] do throw "unmatched namespace end"
      current := none
    else if command.isOfKind ``Parser.Command.declaration then
      let some namespaceName := current | throw "declaration outside approved namespace"
      unless command.getNumArgs == 2 do throw "unsupported declaration wrapper"
      let body := command[1]
      unless body.isOfKind ``Parser.Command.theorem || body.isOfKind ``Parser.Command.definition ||
          body.isOfKind ``Parser.Command.structure || body.isOfKind ``Parser.Command.inductive do
        throw "only plain theorem, definition, and reviewed data commands are admissible"
      let shortName ← shortDeclName body
      let name := namespaceName ++ "." ++ shortName
      unless spec.declarations.contains name && !declarations.contains name do
        throw "unapproved or duplicate source declaration"
      declarations := declarations.push name
      if body.isOfKind ``Parser.Command.structure || body.isOfKind ``Parser.Command.inductive then
        checkDataDeclaration body name spec
        dataDeclarations := dataDeclarations.push name
    else throw s!"unsupported command: {command.getKind}"
  unless current.isNone && visited == spec.namespaces do throw "namespace was not closed or differs from policy"
  unless declarations.qsort (· < ·) == spec.declarations.qsort (· < ·) do
    throw "source declaration inventory differs from policy"
  unless dataDeclarations.qsort (· < ·) ==
      (spec.data_declarations.map (·.name)).qsort (· < ·) do
    throw "data declaration inventory differs from policy"
  unless universes == spec.universes do throw "universe inventory differs from policy"

/-- Validate that approved source modules form a closed, acyclic import DAG
    and that every `TNDLib.*` library module is reachable from `TNDLib`. -/
def checkImportGraph (specs : Array SourceSpec) : Except String Unit := do
  let moduleNames := specs.map (·.module_name)
  let mut seenModules : Array String := #[]
  for spec in specs do
    if seenModules.contains spec.module_name then
      throw s!"duplicate module in admission policy: {spec.module_name}"
    seenModules := seenModules.push spec.module_name
    for imp in spec.imports do
      unless imp == "Init" || moduleNames.contains imp do
        throw s!"import outside approved module DAG: {imp}"
  let importsOf (m : String) : Array String :=
    match specs.find? (·.module_name == m) with
    | some s => s.imports.filter (· != "Init")
    | none => #[]
  let step (frontier : Array String) : Array String :=
    frontier.foldl (fun acc m =>
      (importsOf m).foldl (fun a imp => if a.contains imp then a else a.push imp) acc
    ) frontier
  let reachableFrom (start : String) : Array String :=
    Nat.repeat step specs.size (importsOf start)
  for spec in specs do
    if (reachableFrom spec.module_name).contains spec.module_name then
      throw s!"import graph contains a cycle involving {spec.module_name}"
  if moduleNames.contains "TNDLib" then
    let rootReachable := reachableFrom "TNDLib"
    for spec in specs do
      if spec.module_name.startsWith "TNDLib." && !rootReachable.contains spec.module_name then
        throw s!"unimported library module: {spec.module_name}"

def describeSource (header : Syntax) (commands : Array Syntax) (path : String) : Except String SourceSpec := do
  let mut namespaces := #[]
  let mut current := ""
  let mut declarations := #[]
  let mut universes := #[]
  let mut data := #[]
  for command in commands do
    if command.isOfKind ``Parser.Command.namespace then
      current := command[1].getId.toString
      namespaces := namespaces.push current
    if command.isOfKind ``Parser.Command.universe then
      universes := command[1].getArgs.map (fun id => id.getId.toString)
    if command.isOfKind ``Parser.Command.declaration then
      let body := command[1]
      let name := current ++ "." ++ (← shortDeclName body)
      declarations := declarations.push name
      if body.isOfKind ``Parser.Command.structure then
        data := data.push ⟨name, "structure",
          body[4][2][0].getArgs.map (fun field => field[1].getId.toString), #[], syntaxKey body⟩
      if body.isOfKind ``Parser.Command.inductive then
        data := data.push ⟨name, "inductive", #[],
          body[4].getArgs.map (fun ctor => ctor[3].getId.toString), syntaxKey body⟩
  let modulePath := if path.startsWith "pilot/" then path.drop 6 |>.toString else path
  let moduleName := (modulePath.dropEnd 5).toString.replace "/" "."
  return ⟨path, moduleName, namespaces, header[2].getArgs.map (fun item => item[4].getId.toString),
    declarations, universes, data⟩

def checkRoot (env : Environment) (cfg : Config) (sourceRoot : String) : IO Json := do
  if let some prof := cfg.profile then
    unless prof == profileName || prof == "matching-plain-term-v1" do
      throw <| IO.userError "unknown source-admission profile"
  IO.ofExcept <| checkImportGraph cfg.source_files
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
    unless Lean.versionString == "4.35.0" do throw <| IO.userError "admission requires pinned Lean 4.35.0"
    initSearchPath (← findSysroot)
    enableInitializersExecution
    -- Only the trusted distribution's Init is loaded, never the source headers.
    let env ← importModules #[{ module := `Init }] {} (loadExts := true)
    match args with
    | "--describe" :: root :: paths =>
      let mut specs := #[]
      for path in paths do
        let file := System.FilePath.mk root / path
        let (header, commands) ← TNDAdmission.parseStrict env path (← IO.FS.readFile file)
        specs := specs.push (← IO.ofExcept <| TNDAdmission.describeSource header commands path)
      IO.println (Json.mkObj [("status", toJson "description-only"),
        ("profile", toJson TNDAdmission.profileName), ("source_files", toJson specs)]).compress
    | _ =>
      let (batch, policyPath, sourceArgument) ← match args with
        | [policy, root] => pure (false, policy, root)
        | ["--batch", policy, roots] => pure (true, policy, roots)
        | _ => throw <| IO.userError "usage: Main.lean [--batch] POLICY SOURCE_ROOT_OR_ROOTS_JSON"
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
