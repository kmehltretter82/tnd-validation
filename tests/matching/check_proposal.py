#!/usr/bin/env python3
"""Replay the exact plain-term proposal prototype as development evidence.

This uses an isolated source snapshot and the existing maintained parser,
exporter, and independent checker. It neither admits the full matching model
nor produces the production evidence profile or enables certification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = "TNDLib.Matching.Proposal"
SOURCE = Path("pilot/TNDLib/Matching/Proposal.lean")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str], *, cwd: Path, output: Path | None = None) -> str:
    if output is None:
        result = subprocess.run(
            command, cwd=cwd, check=True, capture_output=True, text=True, timeout=180,
        )
        return result.stdout
    with output.open("w") as handle:
        subprocess.run(
            command, cwd=cwd, check=True, stdout=handle, timeout=180,
        )
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "audit/output/matching")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    policy = ROOT / "audit/matching/proposal-policy.json"
    manifest = ROOT / "audit/matching/proposal-exports.json"
    checker = ROOT / "audit/.lake/build/bin/tnd-check"
    exporter = ROOT / "audit/.lake/build/bin/tnd-export"
    run(["lake", "build"], cwd=ROOT / "audit")
    source_hash = digest(ROOT / SOURCE)
    with tempfile.TemporaryDirectory(prefix="tnd-proposal-replay-") as temporary:
        snapshot = Path(temporary)
        for relative in (SOURCE, Path("lakefile.toml"), Path("lean-toolchain")):
            target = snapshot / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / relative).read_bytes())
        if digest(snapshot / SOURCE) != source_hash:
            raise RuntimeError("proposal source changed while creating the snapshot")
        admission = json.loads(run([
            "lake", "env", "lean", "--run", str(ROOT / "audit/admission/Main.lean"),
            str(policy), str(snapshot),
        ], cwd=ROOT))
        if admission.get("status") != "admitted-source-syntax":
            raise RuntimeError(f"proposal syntax refused: {admission}")
        run(["lake", "build", MODULE], cwd=snapshot)
        export_path = output / "proposal.ndjson"
        run(["lake", "env", str(exporter), MODULE, MODULE], cwd=snapshot, output=export_path)
        if digest(snapshot / SOURCE) != source_hash:
            raise RuntimeError("proposal source changed during compilation/export")
        result = json.loads(run([
            str(checker), str(manifest), str(export_path), str(export_path),
        ], cwd=ROOT))
        if result.get("status") != "verified-proof-objects":
            raise RuntimeError(f"proposal replay refused: {result}")
        if any(entry["axioms"] for entry in result["declarations"]):
            raise RuntimeError("the proposal prototype unexpectedly depends on axioms")
        report = {
            "profile": "matching-pilot-development-v1",
            "development_only": True,
            "scope": "single-receiver proposal transition; full matching model not admitted",
            "source_sha256": source_hash,
            "policy_sha256": digest(policy),
            "manifest_sha256": digest(manifest),
            "export_sha256": digest(export_path),
            "parser_sha256": digest(ROOT / "audit/admission/Main.lean"),
            "checker_binary_sha256": digest(checker),
            "exporter_binary_sha256": digest(exporter),
            "admission": admission,
            "proof_objects": result,
        }
        (output / "proposal-replay.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({
            "status": "development-proposal-replay-passed",
            "declarations": len(result["declarations"]),
            "axioms": [], "report": str(output / "proposal-replay.json"),
        }))


if __name__ == "__main__":
    main()
