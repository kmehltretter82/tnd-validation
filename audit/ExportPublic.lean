/-
Copyright (c) 2026 TND contributors. Released under the Apache 2.0 license.
This tool runs inside the untrusted build container. Its output is untrusted
data until Check.lean compares it and replays it through the kernel.
-/
import Export

open Lean

def main (args : List String) : IO Unit := do
  let [moduleName, namespaceName] := args
    | throw <| IO.userError "usage: tnd-export MODULE NAMESPACE"
  initSearchPath (← findSysroot)
  let env ← importModules #[{ module := moduleName.toName }] {}
  let ns := namespaceName.toName
  let roots := env.constants.toList.filterMap fun (name, _) =>
    if ns.isPrefixOf name && !name.isInternal then some name else none
  if roots.isEmpty then throw <| IO.userError "no public declarations in namespace"
  -- Keep the kernel primitives and policy axioms in both exports, so a
  -- contributor cannot replace their declarations while retaining their names.
  let primitives := [``Nat.add, ``Nat.sub, ``Nat.mul, ``Nat.pow, ``Nat.gcd,
    ``Nat.div, ``Nat.mod, ``Nat.beq, ``Nat.ble, ``Nat.land, ``Nat.lor, ``Nat.xor,
    ``Nat.shiftLeft, ``Nat.shiftRight, ``String.ofList, ``Char.ofNat, ``List,
    ``eagerReduce, ``Nat, ``String, ``String.mk, ``Char, ``optParam, ``autoParam,
    ``semiOutParam, ``outParam, ``Quot, ``Quot.mk, ``Quot.lift, ``Quot.ind,
    ``propext, ``Quot.sound]
  M.run env do
    let _ ← initState env []
    dumpMetadata
    for name in roots ++ primitives do
      modify fun state => { state with noMDataExprs := {} }
      dumpConstant name
