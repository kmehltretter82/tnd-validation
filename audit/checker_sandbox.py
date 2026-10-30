#!/usr/bin/env python3
"""Development-only isolation prototype for untrusted proof-object replay.

The still-disabled audit runner uses this developmental boundary. It does not
certify source binding. Invoke only with the maintained checker and policy.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import stat
import uuid
from collections.abc import Callable
from pathlib import Path

HERE = Path(__file__).resolve().parent
_admission_spec = importlib.util.spec_from_file_location(
    "tnd_checker_admit", HERE / "admission" / "admit.py"
)
admit = importlib.util.module_from_spec(_admission_spec)
_admission_spec.loader.exec_module(admit)
IMAGE = admit.MAINTAINED_IMAGE
COMPARATOR_REV = "e3dcf3083fc53d44b27a4431fabf7d43181583f5"

MAX_CONFIG = 1024 * 1024
MAX_EXPORT = 128 * 1024 * 1024


def regular_file(path: Path, maximum: int) -> Path:
    """Reject symlinks, special files, and unexpectedly large or empty inputs."""
    if not path.is_absolute() or "," in str(path):
        raise ValueError("checker mount paths must be absolute and contain no commas")
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= maximum:
        raise ValueError(f"checker mount must be a regular nonempty file within size limit: {path}")
    return path


def docker_arguments(
    image: str,
    config: Path,
    challenge: Path,
    solution: Path,
    checker: Path,
    lean_root: Path,
    name: str,
) -> list[str]:
    if image != IMAGE:
        raise ValueError("checker image must match the maintained SHA-256 pin")
    if not re.fullmatch(r"tnd-checker-[0-9a-f]{32}", name):
        raise ValueError("invalid checker container name")
    if os.getuid() == 0:
        raise ValueError("run the development checker as an unprivileged user")
    for path, maximum in (
        (config, MAX_CONFIG),
        (challenge, MAX_EXPORT),
        (solution, MAX_EXPORT),
        (checker, 512 * 1024 * 1024),
    ):
        regular_file(path, maximum)
    if (
        not lean_root.is_absolute()
        or "," in str(lean_root)
        or lean_root.is_symlink()
        or not lean_root.is_dir()
    ):
        raise ValueError("Lean root must be an absolute ordinary directory without commas")
    mounts = [
        (config, "/config.json"),
        (challenge, "/challenge.ndjson"),
        (solution, "/solution.ndjson"),
        (checker, "/opt/tnd-check"),
        (lean_root, "/opt/lean"),
    ]
    args = [
        "docker",
        "run",
        "--name",
        name,
        "--rm",
        "--pull=never",
        "--network",
        "none",
        "--read-only",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--log-driver",
        "none",
        "--ulimit",
        "core=0:0",
        "--ulimit",
        "cpu=60:60",
        "--cpus",
        "2",
        "--memory",
        "3g",
        "--memory-swap",
        "3g",
        "--pids-limit",
        "128",
        "--shm-size",
        "16m",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=32m,mode=1777",
        "--workdir",
        "/tmp",
        "--env",
        "PATH=/opt/lean/bin:/usr/bin:/bin",
        "--env",
        "HOME=/tmp",
        "--env",
        "LEAN_SYSROOT=/opt/lean",
        "--env",
        "LEAN_NUM_THREADS=2",
    ]
    for host, target in mounts:
        args += ["--mount", f"type=bind,src={host},dst={target},readonly"]
    return [*args, image, "/opt/tnd-check", "/config.json", "/challenge.ndjson", "/solution.ndjson"]


def run_isolated_checker(
    image: str,
    config: Path,
    challenge: Path,
    solution: Path,
    checker: Path,
    lean_root: Path,
    *,
    check_seccomp: Callable[[], None],
    cleanup: Callable[[str], None],
) -> dict:
    """Replay proof-object data and return development evidence after verified cleanup."""
    name = "tnd-checker-" + uuid.uuid4().hex
    args = docker_arguments(image, config, challenge, solution, checker, lean_root, name)
    docker = shutil.which("docker")
    if docker is None:
        raise ValueError("Docker client is unavailable")
    check_seccomp()
    args[0] = docker
    try:
        result = admit.run_parser(args, cwd=Path(__file__).resolve().parent, env=dict(os.environ))
    finally:
        cleanup(name)
    if result.returncode:
        raise ValueError(
            "checker rejected proof objects: " + (result.stdout + result.stderr)[-6000:]
        )
    report = json.loads(result.stdout)
    if (
        not isinstance(report, dict)
        or type(report.get("schema_version")) is not int
        or report["schema_version"] != 1
        or report.get("status") != "verified-proof-objects"
        or report.get("toolchain") != "4.35.0"
        or report.get("comparator_revision") != COMPARATOR_REV
        or not isinstance(report.get("declarations"), list)
        or not report["declarations"]
    ):
        raise ValueError("unexpected checker report")
    return {"status": "development-proof-check", "development_only": True, "proof_check": report}
