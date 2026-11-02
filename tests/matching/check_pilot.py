#!/usr/bin/env python3
"""Fresh-checkout mathematical replay of an exact matching-pilot commit.

The report explicitly retains the unsupported production-admission boundary.
It is development evidence, never a production certification artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = "TNDLib.Matching.Pilot"
NAMESPACE = "TNDLib.Matching"


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def run(command: list[str], cwd: Path, *, output: Path | None = None) -> str:
    if output is not None:
        with output.open("w") as handle:
            subprocess.run(command, cwd=cwd, check=True, stdout=handle, timeout=300)
        return ""
    result = subprocess.run(
        command, cwd=cwd, check=False, capture_output=True, text=True, timeout=300,
    )
    if result.returncode:
        raise RuntimeError(f"command failed: {command}\n{result.stdout}\n{result.stderr}")
    return result.stdout


def canonical_snapshot(snapshot: Path, revision: str, destination: Path) -> dict[str, str]:
    """Exercise the actual maintained source boundary against the candidate tree."""
    spec = importlib.util.spec_from_file_location("matching_audit_runner", ROOT / "audit/run.py")
    audit_runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit_runner)
    destination.mkdir()
    hashes = audit_runner.source_snapshot(snapshot, revision, destination)
    if any(path.startswith("pilot/") for path in hashes):
        raise RuntimeError("experimental matching source entered the canonical audit stage")
    return hashes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "audit/output/matching/full")
    args = parser.parse_args()
    if re.fullmatch(r"[0-9a-f]{40}", args.revision) is None:
        parser.error("revision must be a full lowercase Git commit SHA")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    run([
        sys.executable, "-m", "gate.verify.production_profile", "--repo", str(ROOT),
        "--revision", args.revision,
    ], ROOT)
    run(["lake", "build"], ROOT / "audit")
    checker = ROOT / "audit/.lake/build/bin/tnd-check"
    exporter = ROOT / "audit/.lake/build/bin/tnd-export"
    manifest = ROOT / "audit/matching/pilot-exports.json"
    with tempfile.TemporaryDirectory(prefix="tnd-pilot-checkout-") as temporary:
        snapshot = Path(temporary) / "library"
        run(["git", "clone", "--no-hardlinks", str(ROOT), str(snapshot)], ROOT)
        run(["git", "checkout", "--detach", args.revision], snapshot)
        if run(["git", "rev-parse", "HEAD"], snapshot).strip() != args.revision:
            raise RuntimeError("fresh checkout resolved a different candidate")
        canonical_hashes = canonical_snapshot(
            snapshot, args.revision, Path(temporary) / "canonical-source",
        )
        maintained = (
            "lean-toolchain", "lakefile.toml", "audit/Check.lean", "audit/ExportPublic.lean",
        )
        for relative in maintained:
            if digest(snapshot / relative) != digest(ROOT / relative):
                raise RuntimeError(f"candidate differs from maintained replay tooling: {relative}")
        sources = {
            str(path.relative_to(snapshot)): digest(path)
            for source_root in (snapshot / "TNDLib", snapshot / "pilot")
            for path in sorted(source_root.rglob("*.lean"))
        }
        run(["lake", "build", "TNDLib", MODULE], snapshot)
        tests = sorted((snapshot / "tests/matching").glob("*.lean"))
        test_log = ""
        for path in tests:
            test_log += str(path.relative_to(snapshot)) + "\n"
            test_log += run(["lake", "env", "lean", str(path)], snapshot)
        (output / "lean-tests.log").write_text(test_log)
        export = output / "pilot.ndjson"
        run(["lake", "env", str(exporter), MODULE, NAMESPACE], snapshot, output=export)
        checked = json.loads(run([
            str(checker), str(manifest), str(export), str(export),
        ], ROOT))
        if checked.get("status") != "verified-proof-objects":
            raise RuntimeError(f"pilot proof replay failed: {checked}")
        proposal_admission = json.loads(run([
            "lake", "env", "lean", "--run", str(ROOT / "audit/admission/Main.lean"),
            str(ROOT / "audit/matching/proposal-policy.json"), str(snapshot),
        ], ROOT))
        if proposal_admission.get("status") != "admitted-source-syntax":
            raise RuntimeError("the plain-term receiver transition was not admitted")
        probe = subprocess.run([
            "lake", "env", "lean", "--run", str(ROOT / "audit/admission/Main.lean"),
            str(ROOT / "audit/matching/basic-policy-probe.json"), str(snapshot),
        ], cwd=ROOT, check=False, capture_output=True, text=True, timeout=180)
        full_admission = json.loads(probe.stdout)
        if probe.returncode != 1 or "structure" not in full_admission.get("reason", ""):
            raise RuntimeError("full-source boundary changed; review the evidence profile")
        for path, expected in sources.items():
            if digest(snapshot / path) != expected:
                raise RuntimeError(f"candidate source changed during replay: {path}")
        report = {
            "profile": "matching-pilot-development-v1", "development_only": True,
            "revision": args.revision, "source_sha256": sources,
            "canonical_source_snapshot_sha256": canonical_hashes,
            "manifest_sha256": digest(manifest), "export_sha256": digest(export),
            "checker_binary_sha256": digest(checker),
            "exporter_binary_sha256": digest(exporter),
            "lean_test_files": [str(path.relative_to(snapshot)) for path in tests],
            "proposal_source_admission": proposal_admission,
            "production_source_admission": full_admission,
            "production_certification": False, "proof_objects": checked,
        }
        (output / "pilot-replay.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({
            "status": "development-pilot-proof-replay-passed", "revision": args.revision,
            "declarations": len(checked["declarations"]),
            "production_source_admitted": False, "report": str(output / "pilot-replay.json"),
        }))


if __name__ == "__main__":
    main()
