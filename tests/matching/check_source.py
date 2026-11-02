#!/usr/bin/env python3
"""Admit and replay an exact pilot snapshot using the separate development dialect.

Only maintained policy/tooling is loaded. Candidate Git blobs are parsed as
data before compilation. Passing never activates production certification.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
PROFILE = "matching-plain-term-v1"
MODULE = "TNDLib.Matching.Pilot"
NAMESPACE = "TNDLib.Matching"
MAX_FILE = 256 * 1024
MAX_TOTAL = 1024 * 1024


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def git(*args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args], check=True, capture_output=True, timeout=30,
    ).stdout


def validate_policy(policy: dict) -> list[dict]:
    if policy.get("profile") != PROFILE or not isinstance(policy.get("source_files"), list):
        raise ValueError("unexpected maintained development profile")
    specs = policy["source_files"]
    modules = {spec["module_name"]: spec for spec in specs}
    paths = {spec["path"] for spec in specs}
    if len(modules) != len(specs) or len(paths) != len(specs) or MODULE not in modules:
        raise ValueError("duplicate or incomplete maintained module inventory")
    for spec in specs:
        path = PurePosixPath(spec["path"])
        relative = spec["path"].removeprefix("pilot/")
        if (
            path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts)
            or relative != spec["module_name"].replace(".", "/") + ".lean"
            or (spec["path"] != "TNDLib/Finite.lean"
                and not spec["path"].startswith("pilot/TNDLib/Matching/"))
            or len(set(spec["imports"])) != len(spec["imports"])
        ):
            raise ValueError("invalid maintained source path or import list")
        if any(name != "Init" and name not in modules for name in spec["imports"]):
            raise ValueError("unapproved external module in maintained import graph")
    visited, active = set(), set()

    def visit(name: str) -> None:
        if name == "Init" or name in visited:
            return
        if name in active:
            raise ValueError("cycle in maintained import graph")
        active.add(name)
        for dependency in modules[name]["imports"]:
            visit(dependency)
        active.remove(name)
        visited.add(name)

    visit(MODULE)
    if visited != set(modules):
        raise ValueError("maintained inventory has modules unreachable from the pilot root")
    return specs


def stage(revision: str, specs: list[dict], destination: Path) -> dict[str, str]:
    expected = {spec["path"] for spec in specs}
    records = git(
        "ls-tree", "-rz", revision, "--", "TNDLib/Finite.lean",
        "pilot/TNDLib/Matching/",
    ).split(b"\0")
    entries = {}
    for record in records:
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, kind, oid = metadata.split()
        path = raw_path.decode("utf-8")
        if mode != b"100644" or kind != b"blob" or path not in expected:
            raise ValueError("candidate contains an unapproved pilot file or file mode")
        entries[path] = oid.decode("ascii")
    if set(entries) != expected:
        raise ValueError("candidate source inventory differs from maintained policy")
    hashes, total = {}, 0
    for path, oid in entries.items():
        size = int(git("cat-file", "-s", oid))
        if not 0 < size <= MAX_FILE:
            raise ValueError("candidate source exceeds maintained per-file limit")
        content = git("cat-file", "blob", oid)
        total += len(content)
        if not 0 < len(content) <= MAX_FILE or total > MAX_TOTAL or b"\0" in content:
            raise ValueError("candidate source exceeds maintained staging limits")
        content.decode("utf-8", errors="strict")
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        hashes[path] = hashlib.sha256(content).hexdigest()
    for path in ("lakefile.toml", "lean-toolchain"):
        (destination / path).write_bytes((ROOT / path).read_bytes())
    return hashes


def freeze_tools(destination: Path, inputs: list[Path]) -> list[Path]:
    """Compile/parse against exact copies of the maintained tool inputs."""
    destination.mkdir()
    outputs = []
    for path in inputs:
        target = destination / path.name
        target.write_bytes(path.read_bytes())
        outputs.append(target)
    return outputs


def maintained_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def lake_executable() -> str:
    lake = shutil.which("lake")
    if lake is None:
        raise FileNotFoundError("Lake executable is unavailable")
    return str(Path(lake).absolute())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "audit/output/matching/source")
    args = parser.parse_args()
    if re.fullmatch(r"[0-9a-f]{40}", args.revision) is None:
        parser.error("revision must be a full lowercase Git commit SHA")
    policy = ROOT / "audit/matching/source-policy.json"
    dialect = ROOT / "audit/matching/Main.lean"
    manifest = ROOT / "audit/matching/pilot-exports.json"
    lake = lake_executable()
    runner = maintained_module("matching_source_runner", ROOT / "audit/run.py")
    profile = maintained_module(
        "matching_production_profile", ROOT / "gate/verify/production_profile.py",
    )
    profile.check_repository(ROOT, args.revision)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tnd-admitted-matching-") as directory:
        temporary = Path(directory)
        canonical, snapshot = temporary / "canonical", temporary / "pilot"
        canonical.mkdir()
        snapshot.mkdir()
        canonical_hashes = runner.source_snapshot(ROOT, args.revision, canonical)
        policy, dialect, manifest = freeze_tools(
            temporary / "maintained-tools", [policy, dialect, manifest],
        )
        specs = validate_policy(json.loads(policy.read_text()))
        hashes = stage(args.revision, specs, snapshot)
        for relative in ("lakefile.toml", "lean-toolchain"):
            if (snapshot / relative).read_bytes() != runner.PUBLISHED_PACKAGE[relative]:
                raise ValueError("maintained package inputs changed while staging")
        admitted = runner.admission.run_parser([
            lake, "env", "lean", "--run", str(dialect), str(policy), str(snapshot),
        ], cwd=ROOT, env=dict(os.environ, LEAN_NUM_THREADS="2"), timeout=240)
        if admitted.returncode:
            raise RuntimeError(f"development source rejected: {admitted.stdout}\n{admitted.stderr}")
        admission = json.loads(admitted.stdout)
        if (
            admission.get("profile") != PROFILE
            or admission.get("status") != "admitted-source-syntax"
            or admission.get("scope") != "matching-pilot-source-only"
            or admission.get("development_only") is not True
            or admission.get("source_files") != len(specs)
        ):
            raise ValueError("invalid development admission report")
        subprocess.run(["lake", "build", MODULE], cwd=snapshot, check=True, timeout=240)
        subprocess.run(["lake", "build"], cwd=ROOT / "audit", check=True, timeout=240)
        export = output / "pilot.ndjson"
        exporter = ROOT / "audit/.lake/build/bin/tnd-export"
        checker = ROOT / "audit/.lake/build/bin/tnd-check"
        with export.open("wb") as handle:
            subprocess.run(
                ["lake", "env", str(exporter), MODULE, NAMESPACE], cwd=snapshot,
                check=True, stdout=handle, timeout=240,
            )
        replay = subprocess.run(
            [str(checker), str(manifest), str(export), str(export)], cwd=ROOT,
            check=True, capture_output=True, text=True, timeout=240,
        )
        for path, expected in hashes.items():
            if digest(snapshot / path) != expected:
                raise ValueError("source bytes changed after admission")
        proof_objects = json.loads(replay.stdout)
        if proof_objects.get("status") != "verified-proof-objects":
            raise ValueError("independent checker did not report proof-object verification")
        report = {
            "profile": PROFILE, "development_only": True, "revision": args.revision,
            "source_sha256": hashes, "policy_sha256": digest(policy),
            "parser_sha256": digest(dialect), "manifest_sha256": digest(manifest),
            "maintained_runner_sha256": digest(ROOT / "audit/run.py"),
            "driver_sha256": digest(Path(__file__).resolve()),
            "package_input_sha256": {
                path: digest(snapshot / path) for path in ("lakefile.toml", "lean-toolchain")
            },
            "checker_binary_sha256": digest(checker), "exporter_binary_sha256": digest(exporter),
            "export_sha256": digest(export), "admission": admission,
            "canonical_source_sha256": canonical_hashes,
            "proof_objects": proof_objects, "production_certification": False,
        }
        (output / "source-replay.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"status": "development-source-replay-passed", "revision": args.revision}))


if __name__ == "__main__":
    main()
