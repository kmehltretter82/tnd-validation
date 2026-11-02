/-
Development-only parser diagnostic for the matching case study.
Source is read as data and parsed with the trusted Init grammar. This program
never imports, elaborates, compiles, or executes candidate source commands.
It is not an admission decision or a replacement for admission/Main.lean.
-/
import Lean

open Lean

namespace TNDMatchingAdmissionProbe

partial def collectKinds (stx : Syntax) (out : Array Name := #[]) : Array Name :=
  match stx with
  | .node _ kind children =>
    children.foldl (fun acc child => collectKinds child acc)
      (if out.contains kind then out else out.push kind)
  | _ => out

partial def shape (depth : Nat) (stx : Syntax) : Json :=
  match stx with
  | .missing => Json.mkObj [("missing", toJson true)]
  | .ident _ _ identifier _ => Json.mkObj [("identifier", toJson identifier.toString)]
  | .atom _ atom => Json.mkObj [("atom", toJson atom)]
  | .node _ kind children =>
    Json.mkObj [("kind", toJson kind.toString), ("arity", toJson children.size),
      ("children", if depth = 0 then Json.arr #[] else Json.arr (children.map (shape (depth - 1))))]

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

end TNDMatchingAdmissionProbe

unsafe def main (paths : List String) : IO UInt32 := do
  initSearchPath (← findSysroot)
  enableInitializersExecution
  let env ← importModules #[{ module := `Init }] {} (loadExts := true)
  let mut reports := #[]
  for path in paths do
    let contents ← IO.FS.readFile path
    let (header, commands) ← TNDMatchingAdmissionProbe.parseStrict env path contents
    let kinds := commands.foldl
      (fun acc command => TNDMatchingAdmissionProbe.collectKinds command acc)
      (TNDMatchingAdmissionProbe.collectKinds header)
    reports := reports.push <| Json.mkObj [
      ("path", toJson path),
      ("kinds", toJson ((kinds.map Name.toString).qsort (· < ·))),
      ("commands", Json.arr (commands.map (TNDMatchingAdmissionProbe.shape 8)))]
  IO.println (Json.arr reports).compress
  return 0
