"""Reconcile leased quota mounts after an abnormal boundary exit.

Runs as an independent `if: always()` step: `finally` blocks do not survive
SIGKILL, and a helper the boundary could not account for must not be raced by
the code that lost track of it. This touches only resources a valid lease names,
and any mismatch is a refusal that leaves them for host disposal. It never
sweeps. It cannot issue evidence; a refusal only fails the job. See "Recovery"
in RESOURCE-BOUNDARY-DESIGN.md for what the process scan does and does not show.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import time
from pathlib import Path

try:
    from audit.resource_boundary import (
        _check_parent_chain,
        _is_child,
        _mounts,
        _process_start,
        _run,
    )
except ImportError:  # Loaded by path from the test suite and the Linux harness.
    from tnd_resource_boundary import (
        _check_parent_chain,
        _is_child,
        _mounts,
        _process_start,
        _run,
    )

ROOT_NAME = re.compile(r"tnd-boundary-[A-Za-z0-9_]+\Z")
CONTAINER_NAME = re.compile(r"tnd-(?:audit|comparator)-[0-9a-f]{32}\Z")
REQUIRED_FLAGS = {"nodev", "nosuid", "noexec"}
QUOTAS = ("export", "build")


class Refused(Exception):
    """Recovery cannot safely proceed; every resource stays where it is."""


def read_lease(path: Path, parent: Path) -> dict:
    """Validate a lease without following links or trusting its paths."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as error:
        raise Refused(f"lease cannot be opened: {error.strerror}") from error
    with os.fdopen(fd, encoding="utf-8") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 64 * 1024):
            raise Refused("lease is not a small private regular file")
        try:
            lease = json.load(stream)
        except ValueError as error:
            raise Refused("lease is not valid JSON") from error
    if not isinstance(lease, dict) or set(lease) != {
        "schema_version", "root", "root_identity", "owner_pid", "owner_start", "containers",
    } or lease["schema_version"] != 1:
        raise Refused("lease has an unexpected schema")
    root = lease["root"]
    if (not isinstance(root, str) or Path(root).parent != parent
            or ROOT_NAME.fullmatch(Path(root).name) is None
            or path.name != Path(root).name + ".lease"):
        raise Refused("lease does not name its own direct child of the parent")
    identity = lease["root_identity"]
    if (not isinstance(identity, list) or len(identity) != 2
            or not all(type(item) is int for item in identity)):
        raise Refused("lease has an invalid root identity")
    if type(lease["owner_pid"]) is not int or lease["owner_pid"] <= 0:
        raise Refused("lease has an invalid owner")
    containers = lease["containers"]
    if not isinstance(containers, list) or not all(
        isinstance(name, str) and CONTAINER_NAME.fullmatch(name) for name in containers
    ):
        raise Refused("lease names an unrecognized container")
    return lease


def require_owner_gone(lease: dict) -> None:
    """Never reconcile beneath a live job; an unknowable start time is not gone."""
    if lease["owner_start"] is None:
        raise Refused("lease has no owner start time")
    if _process_start(lease["owner_pid"]) == lease["owner_start"]:
        raise Refused("lease owner is still running")


def processes_naming(root: Path) -> list[int]:
    needle = os.fsencode(root)
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            if needle in (entry / "cmdline").read_bytes():
                found.append(int(entry.name))
        except OSError:
            continue  # It exited, which is what we are waiting for.
    return found


def await_helpers(root: Path, wait: float) -> None:
    deadline = time.monotonic() + wait
    while (found := processes_naming(root)):
        if time.monotonic() >= deadline:
            raise Refused(f"processes still name the root: {found}")
        time.sleep(min(1.0, wait))


def remove_containers(names: list[str]) -> None:
    for name in names:
        subprocess.run(
            ["docker", "rm", "-f", name], check=False, timeout=60,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        listed = subprocess.run(
            ["docker", "container", "ls", "-a", "--filter", f"name=^/{name}$",
             "--format", "{{.Names}}"],
            check=False, timeout=60, capture_output=True, text=True,
        )
        if listed.returncode != 0 or listed.stdout.strip():
            raise Refused(f"container {name} is not confirmed absent")


def release_mounts(root: Path) -> None:
    """Unmount the exact expected tmpfs mounts, or touch none of them."""
    expected = {root / name for name in QUOTAS}
    mounts = [m for m in _mounts() if m.path == root or _is_child(m.path, root)]
    if any(m.path not in expected for m in mounts):
        raise Refused("root holds an unexpected or nested mount")
    if len({m.path for m in mounts}) != len(mounts):
        raise Refused("a quota mountpoint holds stacked mounts")
    for mount in mounts:
        if mount.fstype != "tmpfs" or not REQUIRED_FLAGS.issubset(mount.options):
            raise Refused(f"{mount.path.name} is not the expected restricted tmpfs")
    for mount in sorted(mounts, key=lambda item: QUOTAS.index(item.path.name)):
        _run(["/usr/bin/sudo", "-n", "/usr/bin/umount", "--", str(mount.path)])
        if any(m.mount_id == mount.mount_id or m.path == mount.path for m in _mounts()):
            raise Refused(f"{mount.path.name} did not detach")


def recover(lease_path: Path, parent: Path, *, wait: float = 30.0) -> str:
    lease = read_lease(lease_path, parent)
    root = Path(lease["root"])
    if not root.exists() and not root.is_symlink():
        if any(m.path == root or _is_child(m.path, root) for m in _mounts()):
            raise Refused("mount remains below a missing root")
        lease_path.unlink()
        return "stale-lease-removed"
    info = root.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or [info.st_dev, info.st_ino] != lease["root_identity"]):
        raise Refused("root identity differs from its lease")
    require_owner_gone(lease)
    await_helpers(root, wait)
    remove_containers(lease["containers"])
    release_mounts(root)
    for name in QUOTAS:
        path = root / name
        if path.exists():
            path.rmdir()
    root.rmdir()
    lease_path.unlink()
    return "recovered"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", required=True, type=Path)
    parser.add_argument("--wait", type=float, default=30.0)
    args = parser.parse_args(argv)
    if sys.platform != "linux" or os.geteuid() == 0:
        print("recovery requires an unprivileged Linux host", file=sys.stderr)
        return 1
    parent = args.parent
    if not parent.is_absolute() or parent.resolve(strict=True) != parent:
        print("recovery parent must be canonical and absolute", file=sys.stderr)
        return 1
    try:
        _check_parent_chain(parent)
    except (OSError, ValueError) as error:
        print(f"recovery refused: {error}", file=sys.stderr)
        return 1
    results = {}
    for lease_path in sorted(parent.glob("tnd-boundary-*.lease")):
        try:
            results[lease_path.name] = recover(lease_path, parent, wait=args.wait)
        except (Refused, OSError, ValueError, subprocess.SubprocessError) as error:
            results[lease_path.name] = f"refused: {error}"
    print(json.dumps(results, indent=2, sort_keys=True))
    return 1 if any(value.startswith("refused") for value in results.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
