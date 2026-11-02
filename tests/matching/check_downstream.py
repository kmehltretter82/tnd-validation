#!/usr/bin/env python3
"""Consume the matching pilot from an exact local Git revision in a clean project."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONSUMER = """import TNDLib.Matching.Pilot

namespace Consumer
open TNDLib.Matching

def commonPreferences (n : Nat) : Preferences n :=
  ⟨fun _ receiver => receiver, fun _ proposer => proposer,
    fun _ {_ _} equality => equality, fun _ {_ _} equality => equality⟩

def result := stableMatch (commonPreferences 3)

-- A downstream user invokes the generic theorem, not a finite test as a proof.
theorem genericCorrect (n : Nat) :
    Stable (commonPreferences n) (stableMatch (commonPreferences n)).val :=
  stableMatch_stable (commonPreferences n)

example : result.val.partner (2 : Fin 3) = (2 : Fin 3) := rfl
example : result.val.inverse (1 : Fin 3) = (1 : Fin 3) := rfl
example : checkStable (commonPreferences 3) result.val = true :=
  (checkStable_eq_true_iff (commonPreferences 3) result.val).mpr result.property

-- Check the actual output via a separately written enumeration predicate.
def noBlocking : Bool :=
  (List.ofFn (fun i : Fin 3 => i)).all fun proposer =>
    (List.ofFn (fun j : Fin 3 => j)).all fun receiver =>
      decide (¬ ((commonPreferences 3).proposerRank proposer receiver <
          (commonPreferences 3).proposerRank proposer (result.val.partner proposer) ∧
        (commonPreferences 3).receiverRank receiver proposer <
          (commonPreferences 3).receiverRank receiver (result.val.inverse receiver)))

example : noBlocking = true := rfl

#eval (List.ofFn (fun p : Fin 3 => (result.val.partner p).val))
#eval noBlocking
end Consumer
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    if re.fullmatch(r"[0-9a-f]{40}", args.revision) is None:
        parser.error("revision must be a full lowercase Git commit SHA")
    subprocess.run([
        sys.executable, "-m", "gate.verify.production_profile", "--repo", str(ROOT),
        "--revision", args.revision,
    ], cwd=ROOT, check=True, timeout=30)
    toolchain = subprocess.run(
        ["git", "show", f"{args.revision}:lean-toolchain"], cwd=ROOT,
        check=True, capture_output=True,
    ).stdout
    with tempfile.TemporaryDirectory(prefix="tnd-matching-consumer-") as directory:
        consumer = Path(directory)
        (consumer / "lean-toolchain").write_bytes(toolchain)
        (consumer / "lakefile.toml").write_text(
            'name = "matching_consumer"\nversion = "0.1.0"\n'
            'defaultTargets = ["Consumer"]\n\n[[lean_lib]]\nname = "Consumer"\n\n'
            '[[require]]\nname = "tndlib"\n'
            f'git = {json.dumps(str(ROOT))}\nrev = "{args.revision}"\n'
        )
        (consumer / "Consumer.lean").write_text(CONSUMER)
        subprocess.run(["lake", "update"], cwd=consumer, check=True, timeout=180)
        manifest = json.loads((consumer / "lake-manifest.json").read_text())
        packages = manifest["packages"]
        if len(packages) != 1 or packages[0]["name"] != "tndlib":
            raise RuntimeError("consumer has an unexpected direct or transitive dependency")
        if packages[0]["rev"] != args.revision:
            raise RuntimeError("Lake resolved a different library revision")
        subprocess.run(["lake", "build"], cwd=consumer, check=True, timeout=180)
        execution = subprocess.run(
            ["lake", "env", "lean", "Consumer.lean"], cwd=consumer, check=True, timeout=180,
            capture_output=True, text=True,
        )
        print(execution.stdout, end="")
        lines = execution.stdout.strip().splitlines()
        matching, no_blocking = json.loads(lines[-2]), json.loads(lines[-1])
        if matching != [0, 1, 2] or no_blocking is not True:
            raise RuntimeError("consumer execution disagrees with the expected example")
        print(json.dumps({
            "status": "matching-downstream-passed", "revision": args.revision,
            "packages": ["tndlib"], "transitive_packages": [],
            "computed_matching": matching, "independent_no_blocking": no_blocking,
        }))


if __name__ == "__main__":
    main()
