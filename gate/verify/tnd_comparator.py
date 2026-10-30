"""Run Choir's original comparator behind TND's outer Docker boundary.

Workspace construction and task resolution run from the maintained base. The
upstream comparator, its child Lake builds, and exporters run inside an
unprivileged network-free container. No host credentials or checkout are mounted.
The production entry point requires the maintained validated resource policy and
uses quota-owned build storage; that policy is currently disabled.
The separately executed TND checker remains the constructive certification gate.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from audit.resource_stages import QuotaStages
from audit.run import (
    IMAGE,
    certified_resource_limits,
    command,
    ensure_container_removed,
    pinned_lean_root,
    require_default_seccomp,
)
from gate.verify.comparator import Outcome, classify_output
from gate.verify.comparator_cli import (
    _applicability_reason,
    _resolve_pr_target,
    materialize_workspace,
)
from gate.verify.tnd_fetch import trusted_metadata, verify_fetched
from gate.verify.tnd_policy import inspect_tree

PROJECT = Path(__file__).resolve().parents[2]


def require_development_helper_policy() -> None:
    """Prevent the unbounded helper from surviving a future production enablement."""
    policy = json.loads((PROJECT / ".choir/certification.json").read_text())
    if (
        not isinstance(policy.get("schema_version"), int)
        or isinstance(policy.get("schema_version"), bool)
        or policy.get("schema_version") != 1
        or policy.get("source_binding_validated") is not False
        or policy.get("resource_boundary_validated") is not False
        or policy.get("resource_limits") is not None
    ):
        raise ValueError("unbounded comparator helper is development-only")


def approved_target(registry: dict, source: str, declaration: str) -> bool:
    """Issue metadata is a pointer; the base-committed registry is authority."""
    return registry.get("schema_version") == 1 and any(
        task.get("source_path") == source and declaration in task.get("expected_exports", [])
        for task in registry.get("tasks", [])
    )


def docker_arguments(
    workspace: Path, build: Path, tools: Path, lean: Path, comparator: Path
) -> list[str]:
    args = [
        "docker",
        "run",
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
        "--cpus",
        "2",
        "--memory",
        "3g",
        "--memory-swap",
        "3g",
        "--shm-size",
        "64m",
        "--log-driver",
        "none",
        "--pids-limit",
        "128",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=256m",
        "--workdir",
        "/work",
        "--env",
        "PATH=/opt/lean/bin:/tools:/usr/bin:/bin",
        "--env",
        "HOME=/tmp",
        "--env",
        "LEAN_NUM_THREADS=2",
        "--env",
        "COMPARATOR_LANDRUN=/tools/landrun",
        "--env",
        "COMPARATOR_LEAN4EXPORT=/checker/.lake/packages/lean4export/.lake/build/bin/lean4export",
    ]
    for host, guest, readonly in [
        (workspace, "/work", True),
        (build, "/work/.lake", False),
        (tools, "/tools", True),
        (lean, "/opt/lean", True),
        (comparator, "/checker", True),
    ]:
        if "," in str(host):
            raise ValueError("commas in mount paths are unsupported")
        args += ["--mount", f"type=bind,src={host},dst={guest}" + (",readonly" if readonly else "")]
    return [*args, IMAGE, "lake", "env", "/checker/.lake/build/bin/comparator", "config.json"]


def run_container(
    workspace: Path, build: Path, tools: Path, lean: Path, comparator: Path
) -> subprocess.CompletedProcess:
    """Development-only unbounded helper retained for focused sandbox tests."""
    require_development_helper_policy()
    require_default_seccomp()
    # Docker cannot create a nested mount point inside the read-only source mount.
    (workspace / ".lake").mkdir(exist_ok=True)
    name = "tnd-comparator-" + uuid.uuid4().hex
    invocation = docker_arguments(workspace, build, tools, lean, comparator)
    invocation[2:2] = ["--name", name]
    try:
        try:
            # Shares the audit runner's 2 MiB combined output limit, 900 second
            # deadline, and process-group termination on resource-limit failure.
            return command(invocation)
        except subprocess.CalledProcessError as error:
            # Comparator failures have structured diagnostics to classify below.
            # Resource-limit and launch errors must instead propagate unchanged.
            return subprocess.CompletedProcess(
                invocation,
                error.returncode,
                error.stdout,
                error.stderr,
            )
    finally:
        # Killing the Docker client does not reliably stop its container. This
        # fresh name also identifies a container whose client failed during start.
        ensure_container_removed(name)


def verify(args: argparse.Namespace) -> None:
    if os.getuid() == 0:
        raise ValueError("run comparator as an unprivileged user")
    certification = json.loads((PROJECT / ".choir/certification.json").read_text())
    build_limit, export_limit = certified_resource_limits(certification)
    quota_parent = getattr(args, "quota_parent", None)
    if not isinstance(quota_parent, Path) or not quota_parent.is_absolute():
        raise ValueError("a canonical absolute --quota-parent is required")
    target = _resolve_pr_target(args.repo, args.pr)
    if isinstance(target, str):
        raise ValueError(f"a registered approved task is required: {target}")
    base, head, source, declaration, _body = target
    if (base, head) != (args.base, args.head):
        raise ValueError("PR head or base changed since this workflow started")
    # Do not rely only on workflow step ordering: revalidate the exact current
    # GitHub file envelope and prove that every accepted <=256 KiB blob is
    # already local under the 1 MiB aggregate bound. This performs no fetch.
    # It must precede materialize_workspace's ordinary host writes.
    changes = trusted_metadata(args.repo, args.pr, base, head)
    verify_fetched(PROJECT, base, head, changes)
    inspect_tree(base, head)
    registry = json.loads(Path("audit/tasks.json").read_text())
    if not approved_target(registry, source, declaration):
        raise ValueError("linked task does not match the maintained approved-task registry")
    reason = _applicability_reason(base, source, declaration)
    if reason:
        raise ValueError(f"comparator cannot verify the registered task: {reason}")
    lean = pinned_lean_root()
    comparator = args.comparator.resolve()
    command(["docker", "image", "inspect", "--format", "{{.Id}}", IMAGE])
    with tempfile.TemporaryDirectory(prefix="tnd-comparator-") as directory:
        root = Path(directory)
        workspace, utilities = root / "workspace", root / "tools"
        for path in (workspace, utilities):
            path.mkdir()
        materialize_workspace(base, head, source, declaration, ("propext", "Quot.sound"), workspace)
        # The selected foundation has no Lake package dependencies. Do not allow
        # an implicit package fetch inside the network-free proof environment.
        manifest = workspace / "lake-manifest.json"
        if manifest.exists() and json.loads(manifest.read_text()).get("packages"):
            raise ValueError("sandbox dependency provisioning is required for this foundation")
        shutil.copyfile(args.landrun, utilities / "landrun")
        (utilities / "landrun").chmod(0o755)
        # Comparator queries Git's location even for a dependency-free project.
        # A stub refuses unexpected Git use instead of mounting host utilities.
        for name, script in {
            "which": '#!/bin/sh\ncommand -v "$1"\n',
            "git": '#!/bin/sh\necho "Git is unavailable in the proof sandbox" >&2\nexit 125\n',
        }.items():
            path = utilities / name
            path.write_text(script)
            path.chmod(0o755)
        # Classification occurs only after named-container cleanup and both
        # quota mounts have been verified and unmounted successfully.
        with QuotaStages(quota_parent, build_limit, export_limit) as quota:
            result = quota.comparator(
                workspace, utilities, lean, comparator, arguments=docker_arguments
            )
        output = (result.stdout + b"\n" + result.stderr).decode("utf-8", errors="replace")
        outcome, message, _full = classify_output(result.returncode, output)
        print(output[-64000:])
        if outcome != Outcome.MATCH:
            raise ValueError(f"comparator did not verify the task: {outcome.value}: {message}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--comparator", required=True, type=Path)
    parser.add_argument("--landrun", required=True, type=Path)
    parser.add_argument(
        "--quota-parent",
        required=True,
        type=Path,
        help="trusted canonical host directory for fresh bounded comparator storage",
    )
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
