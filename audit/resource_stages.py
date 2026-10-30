"""Quota-owned container stages behind a disabled validation policy.

The helper's mounts are visible only in its own namespace; this prototype does
not establish that the Docker daemon sees them, nor supervise host crashes or
privileged descendants. Production callers must first require the maintained
resource-boundary validation flag and exact limits; both remain disabled.
"""
from __future__ import annotations

import argparse
import os
import stat
import subprocess
import sys
import uuid
from collections.abc import Callable
from pathlib import Path

from audit import run
from audit.resource_boundary import ExperimentalBoundary, Limits

ComparatorArguments = Callable[[Path, Path, Path, Path, Path], list[str]]


def _development_comparator_arguments(
    workspace: Path, build: Path, tools: Path, lean: Path, comparator: Path
) -> list[str]:
    # CLI-only lazy import: the production comparator injects its already-loaded
    # factory, avoiding a resource_stages <-> tnd_comparator import cycle.
    from gate.verify.tnd_comparator import docker_arguments  # noqa: PLC0415

    return docker_arguments(workspace, build, tools, lean, comparator)


# Test/CLI patch point retained without importing the comparator eagerly.
_comparator_arguments = _development_comparator_arguments


class QuotaStages:
    """Own quotas for one build/export or comparator run, with guarded teardown."""

    def __init__(self, parent: Path, build: Limits, export: Limits):
        self.boundary = ExperimentalBoundary(parent, build, export)
        self.active = False
        self.used = False
        self.container_uncertain = False

    def __enter__(self) -> QuotaStages:
        if self.active or self.used:
            raise ValueError("quota boundary cannot be reused")
        self.boundary.__enter__()
        self.active = True
        return self

    def __exit__(self, _kind, _value, _traceback) -> None:
        self.active = False
        if self.container_uncertain:
            raise ValueError("container absence unconfirmed; quota mounts retained for recovery")
        self.boundary.close()

    def _start_once(self) -> None:
        if not self.active or self.used:
            raise ValueError("quota stages require an active, unused boundary")
        self.used = True

    def _launch(self, invocation: list[str], name: str, *, comparator: bool = False):
        run.require_default_seccomp()
        # Check both mounts immediately before each launch. This verifies only
        # this process's namespace, not the Docker daemon's mount namespace.
        self.boundary.verify("build")
        self.boundary.verify("export")
        self.boundary.record_container(name)
        self.container_uncertain = True
        try:
            try:
                return run.command(invocation)
            except subprocess.CalledProcessError as error:
                if not comparator:
                    raise
                return subprocess.CompletedProcess(
                    invocation, error.returncode, error.stdout, error.stderr
                )
        finally:
            # Do not permit unmount unless the exact named container's absence
            # was independently confirmed, including after launch failure.
            run.ensure_container_removed(name)
            self.container_uncertain = False

    def build_export(
        self, image: str, source: Path, lean_root: Path, exporter: Path,
        module: str = "TNDLib", namespace: str = "TNDLib",
    ) -> bytes:
        self._start_once()
        build = self.boundary.verify("build")
        output = self.boundary.verify("export")
        for stage in ("build", "export"):
            name = "tnd-audit-" + uuid.uuid4().hex
            invocation = run.docker_arguments(
                image, source, build, output, lean_root, exporter, module, namespace, stage=stage
            )
            invocation[2:2] = ["--name", name]
            self._launch(invocation, name)
        # Recheck the output mount after the container has been reaped, and
        # copy a bounded regular file before the tmpfs is unmounted.
        output = self.boundary.verify("export")
        fd = os.open(output / "export.ndjson", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= 128 * 1024 * 1024:
                raise ValueError("export must be a regular nonempty file of at most 128 MiB")
            result = handle.read(128 * 1024 * 1024 + 1)
            if len(result) > 128 * 1024 * 1024:
                raise ValueError("export exceeds 128 MiB limit")
        return result

    def comparator(
        self,
        workspace: Path,
        tools: Path,
        lean: Path,
        comparator: Path,
        arguments: ComparatorArguments | None = None,
    ) -> subprocess.CompletedProcess:
        self._start_once()
        build = self.boundary.verify("build")
        (workspace / ".lake").mkdir(exist_ok=True)
        name = "tnd-comparator-" + uuid.uuid4().hex
        argument_factory = arguments or _comparator_arguments
        invocation = argument_factory(workspace, build, tools, lean, comparator)
        invocation[2:2] = ["--name", name]
        result = self._launch(invocation, name, comparator=True)
        # Do not return diagnostics for classification until both mount
        # identities still satisfy the validated policy after container exit.
        self.boundary.verify("build")
        self.boundary.verify("export")
        return result


# Compatibility name for the explicitly development-only CLI and its tests.
DevelopmentQuotaStages = QuotaStages


def _existing_path(path: Path, *, directory: bool) -> Path:
    resolved = path.resolve(strict=True)
    if not (resolved.is_dir() if directory else resolved.is_file()):
        raise ValueError(f"invalid development input: {path}")
    return resolved


def main(argv: list[str] | None = None) -> int:
    """Run a local experiment, without issuing an audit or certification."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch-parent", type=Path, required=True)
    parser.add_argument("--build-bytes", type=int, required=True)
    parser.add_argument("--build-inodes", type=int, required=True)
    parser.add_argument("--export-bytes", type=int, required=True)
    parser.add_argument("--export-inodes", type=int, required=True)
    commands = parser.add_subparsers(dest="stage", required=True)
    build = commands.add_parser("build-export")
    build.add_argument("--source", type=Path, required=True)
    build.add_argument("--lean", type=Path, required=True)
    build.add_argument("--exporter", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    compare = commands.add_parser("comparator")
    compare.add_argument("--workspace", type=Path, required=True)
    compare.add_argument("--tools", type=Path, required=True)
    compare.add_argument("--lean", type=Path, required=True)
    compare.add_argument("--comparator", type=Path, required=True)
    args = parser.parse_args(argv)

    # Do not canonicalize the supplied scratch parent: the lifecycle helper
    # itself requires an already canonical path and validates its ancestors.
    parent = args.scratch_parent
    build_limits = Limits(args.build_bytes, args.build_inodes)
    export_limits = Limits(args.export_bytes, args.export_inodes)
    build_limits.validate()
    export_limits.validate()
    lean = _existing_path(args.lean, directory=True)
    if args.stage == "build-export":
        source = _existing_path(args.source, directory=True)
        exporter = _existing_path(args.exporter, directory=False)
        output_parent = _existing_path(args.output.parent, directory=True)
        output_path = output_parent / args.output.name
        if not args.output.name or output_path.exists() or output_path.is_symlink():
            raise ValueError("development output must be a new file")
    else:
        workspace = _existing_path(args.workspace, directory=True)
        tools = _existing_path(args.tools, directory=True)
        comparator = _existing_path(args.comparator, directory=True)

    print("Development only: this run does not certify sources or quota enforcement.",
          file=sys.stderr)
    with DevelopmentQuotaStages(parent, build_limits, export_limits) as quota:
        if args.stage == "build-export":
            contents = quota.build_export(run.IMAGE, source, lean, exporter)
        else:
            result = quota.comparator(workspace, tools, lean, comparator)

    if args.stage == "build-export":
        # Only publish a new local development artifact after successful cleanup.
        fd = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(contents)
        return 0
    sys.stdout.buffer.write(result.stdout)
    sys.stderr.buffer.write(result.stderr)
    return 0 if result.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
