/-
Copyright (c) 2026 TND contributors. Released under the Apache 2.0 license.

The primitive list and kernel replay procedure are adapted from
leanprover/comparator Main.lean at e3dcf3083fc53d44b27a4431fabf7d43181583f5,
Copyright (c) 2025 Lean FRO, LLC, author Henrik Böving, Apache 2.0.

Only trusted checker code is loaded. Candidate inputs are NDJSON data,
never Lean source, plugins, initialization code, or .olean files.
-/
import Comparator
import Export.Parse
import Lean
import Lean.Replay

open Lean

namespace TNDAudit

structure Config where
  namespace_name : String := "TNDLib"
  expected_exports : Array String
  display_exports : Array String := #[]
  source_paths : Std.TreeMap String String := {}
  descriptions : Std.TreeMap String String := {}
  contributors : Std.TreeMap String String := {}
  citations : Std.TreeMap String String := {}
  deriving FromJson, ToJson

def permittedAxioms : Array Name := #[``propext, ``Quot.sound]

def primitives : Array Name := #[
  ``Nat.add, ``Nat.sub, ``Nat.mul, ``Nat.pow, ``Nat.gcd, ``Nat.div, ``Nat.mod,
  ``Nat.beq, ``Nat.ble, ``Nat.land, ``Nat.lor, ``Nat.xor, ``Nat.shiftLeft,
  ``Nat.shiftRight, ``String.ofList, ``Char.ofNat, ``List, ``eagerReduce, ``Nat,
  ``String, ``String.mk, ``Char, ``optParam, ``autoParam, ``semiOutParam, ``outParam]

def parseExport (path : String) : IO Export.ExportedEnv := do
  let handle ← IO.FS.Handle.mk path .read
  Export.parseStream (IO.FS.Stream.ofHandle handle)

def kernelReplay (solution : Export.ExportedEnv) : IO Unit := do
  let env ← Lean.mkEmptyEnvironment
  let quotTargets := [`Quot.mk, `Quot.lift, `Quot.ind]
  let constMap := quotTargets.foldl (init := solution.constMap) (·.erase ·)
  let kernelEnv ← env.toKernelEnv.replay constMap
  for name in `Quot :: quotTargets do
    if let some original := solution.constMap[name]? then
      let some replayed := kernelEnv.find? name
        | throw <| IO.userError s!"kernel missing quotient primitive: {name}"
      if original != replayed then
        throw <| IO.userError s!"kernel quotient primitive mismatch: {name}"

/-- Walk raw exported declarations, including types, opaque bodies, inductive
constructors and recursor rules. No contributor-provided axiom cache is used. -/
partial def axiomClosure (env : Export.ExportedEnv) (roots : Array Name) :
    Except String (Array Name) := do
  go roots {} {}
where
  go (todo : Array Name) (seen axioms : Std.HashSet Name) :
      Except String (Array Name) := do
    if todo.isEmpty then return axioms.toArray.qsort Name.lt
    let name := todo.back!
    let todo := todo.pop
    if seen.contains name then return ← go todo seen axioms
    let some info := env.constMap[name]?
      | throw s!"missing dependency: {name}"
    let axioms := if info.isAxiom then axioms.insert name else axioms
    let collect : StateM (Array Name) Unit := Comparator.runForUsedConsts info fun dep =>
      modify (fun xs : Array Name => xs.push dep)
    let deps := collect.run #[] |>.2
    go (todo ++ deps) (seen.insert name) axioms

def publicNames (env : Export.ExportedEnv) (ns : Name) : Array Name :=
  env.constOrder.filter (fun name => ns.isPrefixOf name && !name.isInternal)
    |>.qsort Name.lt

def kind (info : ConstantInfo) : String :=
  match info with
  | .thmInfo _ => "theorem"
  | .defnInfo _ => "definition"
  | .axiomInfo _ => "axiom"
  | .opaqueInfo _ => "opaque"
  | .inductInfo _ => "inductive"
  | .ctorInfo _ => "constructor"
  | .recInfo _ => "recursor"
  | .quotInfo _ => "quotient"

def verify (cfg : Config) (challenge solution : Export.ExportedEnv) : IO Json := do
  let expected := cfg.expected_exports.map String.toName |>.qsort Name.lt
  if expected.isEmpty then throw <| IO.userError "empty certified export inventory"
  if expected.toList.eraseDups.length != expected.size then
    throw <| IO.userError "duplicate certified export name"
  if cfg.display_exports.toList.eraseDups.length != cfg.display_exports.size then
    throw <| IO.userError "duplicate display export name"
  let displayed := cfg.display_exports.toList.mergeSort (· ≤ ·)
  unless cfg.descriptions.keys == displayed && cfg.contributors.keys == displayed &&
      cfg.citations.keys == displayed do
    throw <| IO.userError "display metadata keys differ from display export inventory"
  for name in cfg.display_exports do
    unless cfg.expected_exports.contains name do
      throw <| IO.userError s!"display export absent from inventory: {name}"
    let some description := cfg.descriptions[name]?
      | throw <| IO.userError s!"display export lacks an explanation: {name}"
    let some contributor := cfg.contributors[name]?
      | throw <| IO.userError s!"display export lacks contributor attribution: {name}"
    let some citation := cfg.citations[name]?
      | throw <| IO.userError s!"display export lacks a source citation: {name}"
    if description.toList.all Char.isWhitespace || contributor.toList.all Char.isWhitespace ||
        citation.toList.all Char.isWhitespace then
      throw <| IO.userError s!"display metadata is blank: {name}"
  let ns := cfg.namespace_name.toName
  for (label, env) in [("challenge", challenge), ("solution", solution)] do
    if publicNames env ns != expected then
      throw <| IO.userError s!"{label} exported declaration inventory differs from approved manifest"
  let theoremNames := expected.filter fun name =>
    match challenge.constMap[name]? with
    | some (.thmInfo _) => true
    | _ => false
  let immutableNames := expected.filter (!theoremNames.contains ·)
  -- All definitions are immutable; definition-hole checking is deliberately
  -- disabled. A new definition must first receive maintainer approval.
  IO.ofExcept <| Comparator.compareAt challenge solution
    (theoremNames ++ permittedAxioms) #[] (primitives ++ immutableNames)
  let mut entries := #[]
  for name in expected do
    let some info := solution.constMap[name]?
      | throw <| IO.userError s!"missing approved export: {name}"
    let allAxioms ← IO.ofExcept <| axiomClosure solution #[name]
    let statementAxioms ← IO.ofExcept <| axiomClosure solution info.type.getUsedConstants
    for axiomName in allAxioms do
      unless permittedAxioms.contains axiomName do
        throw <| IO.userError s!"prohibited axiom {axiomName} in {name}"
    entries := entries.push <| Json.mkObj [
      ("name", toJson name.toString), ("kind", toJson (kind info)),
      ("display", toJson (cfg.display_exports.contains name.toString)),
      ("source_path", toJson (cfg.source_paths[name.toString]?)),
      ("description", toJson (cfg.descriptions[name.toString]?.getD "")),
      ("contributor", toJson (cfg.contributors[name.toString]?.getD "")),
      ("citation", toJson (cfg.citations[name.toString]?.getD "")),
      ("statement", toJson (toString info.type)),
      ("axioms", toJson (allAxioms.map Name.toString)),
      ("statement_axioms", toJson (statementAxioms.map Name.toString))]
  kernelReplay solution
  return Json.mkObj [
    ("schema_version", toJson (1 : Nat)),
    ("status", toJson "verified-proof-objects"),
    ("toolchain", toJson Lean.versionString),
    ("comparator_revision", toJson "e3dcf3083fc53d44b27a4431fabf7d43181583f5"),
    ("permitted_axioms", toJson (permittedAxioms.map Name.toString)),
    ("declarations", toJson entries)]

end TNDAudit

def main (args : List String) : IO UInt32 := do
  try
    let [configPath, challengePath, solutionPath] := args
      | throw <| IO.userError "usage: tnd-check CONFIG CHALLENGE.ndjson SOLUTION.ndjson"
    let cfg ← IO.ofExcept <| fromJson? (← IO.ofExcept <| Json.parse (← IO.FS.readFile configPath))
    let result ← TNDAudit.verify cfg (← TNDAudit.parseExport challengePath)
      (← TNDAudit.parseExport solutionPath)
    IO.println result.compress
    return 0
  catch error =>
    IO.println <| (Json.mkObj [("schema_version", toJson (1 : Nat)),
      ("status", toJson "rejected"), ("reason", toJson error.toString)]).compress
    return 1
