#!/usr/bin/env python3
"""Development-only Docker isolation for the trusted source parser.

The host still snapshots candidate bytes, generates the maintained policy and
checks hashes; the parser sees only read-only mounts. Integration does not
validate the source-binding boundary or enable certification.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import uuid
from collections.abc import Callable
from pathlib import Path

HERE = Path(__file__).resolve().parent
_admission_spec = importlib.util.spec_from_file_location("tnd_sandbox_admit", HERE / "admit.py")
admit = importlib.util.module_from_spec(_admission_spec)
_admission_spec.loader.exec_module(admit)


def docker_arguments(
    image: str, source: Path, policy: Path, parser: Path, lean_root: Path, name: str
) -> list[str]:
    """Construct a no-network, resource-capped parser with no writable host mounts."""
    if image != admit.MAINTAINED_IMAGE:
        raise ValueError("parser image must match the maintained SHA-256 pin")
    if not re.fullmatch(r"tnd-parser-[0-9a-f]{32}", name):
        raise ValueError("invalid parser container name")
    if os.getuid() == 0:
        raise ValueError("run the development parser as an unprivileged user")
    mounts = [
        (source, "/source"),
        (policy, "/policy.json"),
        (parser, "/Main.lean"),
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
        "2g",
        "--memory-swap",
        "2g",
        "--shm-size",
        "64m",
        "--pids-limit",
        "128",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=32m,mode=1777",
        "--workdir",
        "/source",
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
        if not host.is_absolute() or "," in str(host):
            raise ValueError("parser mount paths must be absolute and contain no commas")
        args += ["--mount", f"type=bind,src={host},dst={target},readonly"]
    return [*args, image, "/opt/lean/bin/lean", "--run", "/Main.lean", "/policy.json", "/source"]


def admit_into_container(
    source: Path,
    staged: Path,
    lean_root: Path,
    *,
    image: str,
    cleanup: Callable[[str], None],
    check_seccomp: Callable[[], None],
    expected_hashes: dict[str, str] | None = None,
    task_id: str | None = None,
    role: str = "solution",
) -> dict:
    """Stage and parse exact source bytes in a disposable parser container."""
    staged = staged.absolute()
    staged.mkdir(parents=True, exist_ok=False)
    hashes = admit.snapshot(source.resolve(), staged, task_id, role)
    if expected_hashes is not None and hashes != expected_hashes:
        raise ValueError("admission snapshot differs from exact Git source hashes")
    check_seccomp()
    config, task = admit.policy_for(task_id, role)
    policy_path = staged.with_name(staged.name + "-parser-policy.json")
    policy_path.write_text(json.dumps(config))
    name = "tnd-parser-" + uuid.uuid4().hex
    args = docker_arguments(image, staged, policy_path, admit.HERE / "Main.lean", lean_root, name)
    docker = shutil.which("docker")
    if docker is None:
        raise ValueError("Docker client is unavailable")
    # The bounded launcher uses execv(), which does not search PATH.
    args[0] = docker
    try:
        result = admit.run_parser(args, cwd=admit.HERE, env=dict(os.environ))
    finally:
        # A killed Docker CLI does not guarantee that its container is gone.
        # Never consume its output unless exact-name removal was confirmed.
        cleanup(name)
    if result.returncode:
        raise ValueError("parser rejected source: " + (result.stdout + result.stderr)[-6000:])
    report = json.loads(result.stdout)
    if report != {
        "status": "admitted-source-syntax",
        "scope": "approved-library-source-only",
        "development_only": True,
    }:
        raise ValueError("unexpected parser output")
    admit.verify_exact(staged, hashes)
    report.update(
        source_sha256=hashes,
        policy_sha256=hashlib.sha256(admit.POLICY.read_bytes()).hexdigest(),
        parser_sha256=hashlib.sha256((admit.HERE / "Main.lean").read_bytes()).hexdigest(),
        parser_isolation="development-docker",
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
