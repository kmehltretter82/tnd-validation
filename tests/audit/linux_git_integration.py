#!/usr/bin/env python3
"""Run development-only Git/admission/build/export fixtures on Linux Docker.

This calls the maintained runner stages, not guarded production ``verify()``.
The published readiness flag must remain false and no certificate is issued.
See audit/admission/README.md for supported modes and prerequisites.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

PROJECT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("tnd_integration_runner", PROJECT / "audit/run.py")
driver = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(driver)
IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")


def use_embedded_lean(args: list[str], original_image: str, embedded_image: str) -> list[str]:
    """Remove only the Lean bind and select an explicit immutable local image ID."""
    if not IMAGE_ID.fullmatch(embedded_image):
        raise ValueError("embedded image must be an immutable sha256 image ID")
    cmd = list(args)
    mounts = [i for i, arg in enumerate(cmd) if ",dst=/opt/lean,readonly" in arg]
    if len(mounts) != 1 or mounts[0] == 0 or cmd[mounts[0] - 1] != "--mount":
        raise ValueError("expected one read-only Lean mount")
    del cmd[mounts[0] - 1 : mounts[0] + 1]
    if cmd.count(original_image) != 1:
        raise ValueError("expected one runner image")
    cmd[cmd.index(original_image)] = embedded_image
    return cmd


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def commit(repo: Path, message: str) -> str:
    git(repo, "add", "--all")
    git(
        repo,
        "-c",
        "user.name=TND fixture",
        "-c",
        "user.email=tnd-fixture@example.invalid",
        "commit",
        "-qm",
        message,
    )
    return git(repo, "rev-parse", "HEAD")


def adapt_embedded_mode(image: str) -> None:
    """Use image Lean for runner stages; Docker's real seccomp gate is unchanged."""
    if not IMAGE_ID.fullmatch(image):
        raise ValueError("embedded image must be an immutable sha256 image ID")
    original_args = driver.docker_arguments
    original_parser_args = driver.parser_sandbox.docker_arguments
    original_checker_args = driver.checker_sandbox.docker_arguments

    def build_args(*args, **kwargs):
        return use_embedded_lean(original_args(*args, **kwargs), args[0], image)

    def parser_args(*args, **kwargs):
        return use_embedded_lean(original_parser_args(*args, **kwargs), args[0], image)

    def checker_args(*args, **kwargs):
        return use_embedded_lean(original_checker_args(*args, **kwargs), args[0], image)

    driver.docker_arguments = build_args
    driver.parser_sandbox.docker_arguments = parser_args
    driver.checker_sandbox.docker_arguments = checker_args


def exercise_hostile(repo: Path, workspace: Path, base: str, lean_root: Path, image: str) -> None:
    git(repo, "switch", "-q", "--detach", base)
    (repo / "TNDLib/Evil.lean").write_text(
        "import Init\nnamespace TNDLib.Evil\naxiom bad : False\nend TNDLib.Evil\n"
    )
    evil = commit(repo, "unimported source")
    try:
        driver.admitted_snapshot(repo, evil, workspace / "hostile-extra", lean_root, image=image)
    except ValueError as exc:
        if "source module inventory differs" not in str(exc) or "TNDLib/Evil.lean" not in str(exc):
            raise
    else:
        raise AssertionError("unimported module was admitted")
    print(json.dumps({"case": "unimported_module_rejected", "passed": True}), flush=True)

    git(repo, "switch", "-q", "--detach", base)
    source = repo / "TNDLib.lean"
    source.write_text(
        source.read_text() + "\n#eval IO.FS.writeBinFile "
        '".lake/build/lib/lean/TNDLib/Nat.olean" ByteArray.empty\n'
    )
    attack = commit(repo, "artifact overwrite attempt")
    try:
        driver.admitted_snapshot(
            repo, attack, workspace / "hostile-overwrite", lean_root, image=image
        )
    except ValueError as exc:
        if "parser rejected source" not in str(exc):
            raise
    else:
        raise AssertionError("artifact overwrite was admitted")
    print(json.dumps({"case": "artifact_overwrite_rejected", "passed": True}), flush=True)


def exercise_git(args, workspace: Path, lean_root: Path, checker: Path, exporter: Path) -> None:
    repo = workspace / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    for name in ("TNDLib.lean", "lakefile.toml", "lake-manifest.json", "lean-toolchain"):
        shutil.copy2(PROJECT / name, repo / name)
    shutil.copytree(PROJECT / "TNDLib", repo / "TNDLib")
    shutil.copytree(PROJECT / "tasks", repo / "tasks")
    base = commit(repo, "baseline")

    nat = repo / "TNDLib/Nat.lean"
    old = nat.read_text()
    before = "sumTo n + (n + 1) := rfl"
    if old.count(before) != 1:
        raise ValueError("fixture source no longer matches expected baseline")
    nat.write_text(old.replace(before, "sumTo n + (n + 1) := Eq.refl _"))
    shutil.copy2(PROJECT / "tests/tasks/MapExistsSolution.lean", repo / "tasks/map_exists.lean")
    head = commit(repo, "constructive solution")

    exports = {}
    for label, revision in (("base", base), ("head", head)):
        scratch = workspace / ("library-" + label)
        source, hashes, admission = driver.admitted_snapshot(
            repo, revision, scratch, lean_root, image=args.image
        )
        exports[label] = driver.build_export(args.image, source, scratch, lean_root, exporter)
        driver.admission.verify_exact(source, admission["source_sha256"])
        if hashes != admission["source_sha256"]:
            raise ValueError("Git and admitted source hashes disagree")
    checked = driver.checker_sandbox.run_isolated_checker(
        args.image,
        PROJECT / "audit/exports.json",
        exports["base"],
        exports["head"],
        checker,
        lean_root,
        check_seccomp=driver.require_default_seccomp,
        cleanup=driver.ensure_container_removed,
    )
    proof = checked["proof_check"]
    if (
        proof.get("status") != "verified-proof-objects"
        or proof.get("toolchain") != "4.35.0"
        or len(proof["declarations"]) != 37
    ):
        raise ValueError("library checker did not accept expected declarations")
    print(json.dumps({"case": "constructive_git_library", "passed": True}), flush=True)

    options = SimpleNamespace(base=base, head=head, image=args.image)
    tasks = driver.verify_tasks(
        options,
        repo,
        PROJECT / "audit",
        workspace,
        lean_root,
        exporter,
        checker,
        driver.build_export,
    )
    if len(tasks) != 1 or tasks[0]["status"] != "verified-task-proof":
        raise ValueError("registered task did not pass")
    print(json.dumps({"case": "registered_git_task", "passed": True}), flush=True)
    exercise_hostile(repo, workspace, base, lean_root, args.image)
    policy = json.loads((PROJECT / ".choir/certification.json").read_text())
    if (
        policy.get("source_binding_validated") is not False
        or policy.get("resource_boundary_validated") is not False
        or policy.get("resource_limits") is not None
    ):
        raise ValueError("certification readiness unexpectedly changed")
    print(
        json.dumps(
            {
                "status": "passed",
                "scope": "development-only",
                "cases": 4,
                "mode": "embedded-image" if args.embedded_image else "host-linux",
                "base": base,
                "head": head,
            }
        ),
        flush=True,
    )


def run(args: argparse.Namespace) -> None:
    policy = json.loads((PROJECT / ".choir/certification.json").read_text())
    if (
        policy.get("source_binding_validated") is not False
        or policy.get("resource_boundary_validated") is not False
        or policy.get("resource_limits") is not None
    ):
        raise ValueError("this development harness requires certification to remain disabled")
    if os.getuid() == 0:
        raise ValueError("run as an unprivileged user")
    checker, exporter = args.checker.resolve(), args.exporter.resolve()
    if not checker.is_file() or not exporter.is_file():
        raise ValueError("supply existing Linux checker and exporter binaries")
    if args.image != driver.IMAGE:
        raise ValueError("runner image must match the maintained SHA-256 pin")
    if args.embedded_image:
        adapt_embedded_mode(args.embedded_image)
        lean_root = PROJECT  # removed from Docker arguments in embedded mode
    else:
        if platform.system() != "Linux" or args.lean_root is None:
            raise ValueError("host mode requires Linux and an explicit --lean-root")
        lean_root = args.lean_root.resolve()
        if not (lean_root / "bin/lean").is_file():
            raise ValueError("--lean-root must contain bin/lean")
    # No mock or override: fail before staging/running if daemon policy is unsafe.
    driver.require_default_seccomp()
    if not args.embedded_image:
        version = driver.command([str(lean_root / "bin/lean"), "--version"], text=True).stdout
        if not re.search(r"\bversion 4\.35\.0(?:,|\s|\))", version):
            raise ValueError("host Lean binary does not match 4.35.0")
    work_dir = args.work_dir.resolve() if args.work_dir else None
    with tempfile.TemporaryDirectory(prefix="tnd-linux-git-", dir=work_dir) as temporary:
        exercise_git(args, Path(temporary).resolve(), lean_root, checker, exporter)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checker", type=Path, required=True, help="trusted Linux checker binary")
    parser.add_argument(
        "--exporter", type=Path, required=True, help="trusted Linux exporter binary"
    )
    parser.add_argument(
        "--lean-root", type=Path, help="host-visible Lean 4.35 sysroot (Linux mode)"
    )
    parser.add_argument(
        "--image", default=driver.IMAGE, help="must match the maintained runner image"
    )
    parser.add_argument("--embedded-image", help="explicit local sha256 image ID with Lean inside")
    parser.add_argument("--work-dir", type=Path, help="existing Docker-visible temporary directory")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
