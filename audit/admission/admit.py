#!/usr/bin/env python3
"""Development-only admission of a fixed plain-term Lean corpus.

Run this maintained copy, never a contributor's copy. Only an immutable source
snapshot matching the reported hashes may subsequently be compiled. This does
not enable certification or replace proof-object/axiom verification.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
POLICY = HERE / "policy.json"
MAX_FILE = 256 * 1024
MAX_TOTAL = 1024 * 1024
MAX_PARSER_OUTPUT = 1024 * 1024
PARSER_TIMEOUT = 90
MAINTAINED_IMAGE = "ubuntu@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac"


def run_parser(
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: float = PARSER_TIMEOUT,
    output_limit: int = MAX_PARSER_OUTPUT,
) -> subprocess.CompletedProcess:
    """Bound elapsed time and combined stdout/stderr of the isolated process group."""
    process = subprocess.Popen(
        [sys.executable, str(HERE / "limited.py"), *args],
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    result = {"stdout": bytearray(), "stderr": bytearray()}
    started = time.monotonic()
    total = 0
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            while selector.get_map():
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(args, timeout)
                for key, _ in selector.select(timeout=min(0.2, remaining)):
                    data = os.read(key.fileobj.fileno(), 65536)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    total += len(data)
                    if total > output_limit:
                        raise ValueError("source parser output exceeded limit")
                    result[key.data].extend(data)
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise subprocess.TimeoutExpired(args, timeout)
            code = process.wait(timeout=remaining)
    except BaseException:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        raise
    finally:
        process.stdout.close()
        process.stderr.close()
    return subprocess.CompletedProcess(
        args, code, result["stdout"].decode("utf-8"), result["stderr"].decode("utf-8")
    )


def policy_for(task_id: str | None = None, role: str = "solution") -> tuple[dict, dict | None]:
    policy = json.loads(POLICY.read_text())
    specs = policy["source_files"]
    expected = {entry["path"] for entry in specs}
    if len(expected) != len(specs) or "TNDLib.lean" not in expected:
        raise ValueError("invalid trusted source inventory")
    modules = {entry["module_name"] for entry in specs if entry["path"] != "TNDLib.lean"}
    aggregator = next(entry for entry in specs if entry["path"] == "TNDLib.lean")
    if set(aggregator["imports"]) != modules or len(aggregator["imports"]) != len(modules):
        raise ValueError("trusted aggregator does not cover every source module")
    for entry in specs:
        if entry["module_name"].replace(".", "/") + ".lean" != entry["path"]:
            raise ValueError("module path does not match trusted policy")
        if entry["path"] != "TNDLib.lean" and entry["imports"] != ["Init"]:
            raise ValueError("prototype module imports must be exactly Init")
    if role not in {"challenge", "solution"}:
        raise ValueError("unknown task admission role")
    task = None
    if task_id is not None:
        matching = [entry for entry in policy["task_files"] if entry["id"] == task_id]
        if len(matching) != 1:
            raise ValueError("task is absent from maintained admission policy")
        task = matching[0]
        if (
            task["path"] != "Task.lean"
            or task["module_name"] != "Task"
            or task["imports"] != ["TNDLib"]
        ):
            raise ValueError("invalid maintained task module policy")
        if role == "solution":
            specs = [*specs, task]
    return {"source_files": specs}, task


def source_bytes(source: Path, expected: set[str]) -> dict[str, bytes]:
    actual = {p.name for p in source.glob("*.lean")}
    directory = source / "TNDLib"
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("library source directory must be ordinary")
    for parent, directories, files in os.walk(directory, followlinks=False):
        for name in directories:
            if (Path(parent) / name).is_symlink():
                raise ValueError("source directory symlinks are forbidden")
        for name in files:
            actual.add((Path(parent) / name).relative_to(source).as_posix())
    if actual != expected:
        raise ValueError(
            f"source module inventory mismatch: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )
    blobs, total = {}, 0
    for name in sorted(expected):
        if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts:
            raise ValueError("invalid trusted source path")
        fd = os.open(source / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_FILE:
                raise ValueError("source must be an ordinary nonempty file within size limit")
            contents = handle.read(MAX_FILE + 1)
        if len(contents) > MAX_FILE or b"\0" in contents:
            raise ValueError("binary or oversized source is forbidden")
        contents.decode("utf-8", errors="strict")
        total += len(contents)
        if total > MAX_TOTAL:
            raise ValueError("source snapshot exceeds size limit")
        blobs[name] = contents
    return blobs


def snapshot(
    source: Path, target: Path, task_id: str | None = None, role: str = "solution"
) -> dict[str, str]:
    config, task = policy_for(task_id, role)
    expected = {entry["path"] for entry in config["source_files"]}
    if task is not None:
        expected.add(task["path"])
    blobs = source_bytes(source, expected)
    hashes = {name: hashlib.sha256(content).hexdigest() for name, content in blobs.items()}
    if (
        task is not None
        and role == "challenge"
        and hashes[task["path"]] != task["challenge_sha256"]
    ):
        raise ValueError("challenge must match the exact maintained placeholder bytes")
    for name, contents in blobs.items():
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(contents)
    return hashes


def verify_exact(source: Path, expected_hashes: dict[str, str]) -> None:
    actual = {
        name: hashlib.sha256(content).hexdigest()
        for name, content in source_bytes(source, set(expected_hashes)).items()
    }
    if actual != expected_hashes:
        raise ValueError("admitted source bytes changed")


def admit_into(
    lean: Path,
    source: Path,
    staged: Path,
    *,
    expected_hashes: dict[str, str] | None = None,
    task_id: str | None = None,
    role: str = "solution",
) -> dict:
    """Parse fresh staged bytes; callers must build this exact directory read-only."""
    lean = lean.resolve()
    # No candidate files or environments enter Lean's module search path.
    env = dict(os.environ)
    for name in ("LEAN_PATH", "LEAN_SRC_PATH", "LEAN_SYSROOT", "LEAN_PLUGIN_PATH"):
        env.pop(name, None)
    env["PATH"] = str(lean.parent) + os.pathsep + "/usr/bin:/bin"
    env["LEAN_NUM_THREADS"] = "2"
    staged.mkdir(parents=True, exist_ok=False)
    hashes = snapshot(source.resolve(), staged, task_id, role)
    if expected_hashes is not None and hashes != expected_hashes:
        raise ValueError("admission snapshot differs from exact Git source hashes")
    config, task = policy_for(task_id, role)
    config_path = staged.with_name(staged.name + "-parser-policy.json")
    config_path.write_text(json.dumps(config))
    checked = run_parser(
        [str(lean), "--run", str(HERE / "Main.lean"), str(config_path), str(staged)],
        cwd=HERE,
        env=env,
    )
    if checked.returncode:
        raise ValueError("parser rejected source: " + (checked.stdout + checked.stderr)[-6000:])
    report = json.loads(checked.stdout)
    if report != {
        "status": "admitted-source-syntax",
        "scope": "approved-library-source-only",
        "development_only": True,
    }:
        raise ValueError("unexpected parser output")
    verify_exact(staged, hashes)
    report.update(
        source_sha256=hashes,
        policy_sha256=hashlib.sha256(POLICY.read_bytes()).hexdigest(),
        parser_sha256=hashlib.sha256((HERE / "Main.lean").read_bytes()).hexdigest(),
    )
    if task is not None:
        report.update(
            scope="approved-library-and-task-source",
            task={
                "id": task_id,
                "role": role,
                "source_path": task["source_path"],
                "compiled_path": task["path"],
                "challenge_exact_bytes": role == "challenge",
            },
        )
    return report


def admit(lean: Path, source: Path, task_id: str | None = None, role: str = "solution") -> dict:
    with tempfile.TemporaryDirectory(prefix="tnd-admission-") as temporary:
        return admit_into(lean, source, Path(temporary) / "source", task_id=task_id, role=role)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument(
        "--task", help="Maintained task id; input must include its Task.lean snapshot"
    )
    parser.add_argument("--role", choices=("challenge", "solution"), default="solution")
    args = parser.parse_args()
    try:
        print(json.dumps(admit(args.lean, args.source, args.task, args.role), sort_keys=True))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
