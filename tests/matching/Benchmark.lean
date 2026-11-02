import TNDLib.Matching.Pilot

/-! Small development timings; this is not a complexity or resource-boundary proof. -/

namespace MatchingBenchmark
open TNDLib.Matching

def preferences (n : Nat) : Preferences n :=
  ⟨fun _ receiver => receiver, fun _ proposer => proposer,
    fun _ {_ _} equality => equality, fun _ {_ _} equality => equality⟩

def measure (n : Nat) : IO Unit := do
  let started ← IO.monoMsNow
  let input := preferences n
  let output := stableMatch input
  let partners := List.ofFn (fun proposer : Fin n => (output.val.partner proposer).val)
  let stable := checkStable input output.val
  let inverse := (List.ofFn (fun i : Fin n => i)).all fun i =>
    decide (output.val.inverse (output.val.partner i) = i) &&
      decide (output.val.partner (output.val.inverse i) = i)
  unless stable && inverse do
    throw (IO.userError "computed matching failed independent finite checks")
  -- Printing forces the data before the end timestamp.
  IO.println s!"n={n}, partners={partners}, stable={stable}, inverse={inverse}"
  let finished ← IO.monoMsNow
  IO.println s!"elapsed_ms={finished - started}"

end MatchingBenchmark

def main : IO Unit := do
  for size in [0, 1, 2, 3, 8, 16] do
    MatchingBenchmark.measure size
