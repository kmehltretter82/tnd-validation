"""Exercise the real tmpfs boundary on an expendable native-Linux host.

Development evidence only: it performs real privileged mounts through
`resource_boundary.py`, so it refuses to run without an explicit scratch parent
and is not collected by the test suites. Passing does not validate a production
runner or change a certification flag. Prints one JSON report.

    python3 tests/audit/linux_boundary_smoke.py --scratch "$HOME/tnd-scratch"
"""
from __future__ import annotations

import argparse
import errno
import importlib.util
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "tnd_resource_boundary", ROOT / "audit/resource_boundary.py"
)
boundary = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = boundary
SPEC.loader.exec_module(boundary)
RECOVERY_SPEC = importlib.util.spec_from_file_location(
    "tnd_resource_recovery", ROOT / "audit/resource_recovery.py"
)
recovery = importlib.util.module_from_spec(RECOVERY_SPEC)
sys.modules[RECOVERY_SPEC.name] = recovery
RECOVERY_SPEC.loader.exec_module(recovery)

IMAGE = "ubuntu@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac"
BYTES = 8 * 1024 * 1024
INODES = 256
LIMITS = boundary.Limits(BYTES, INODES)
SUDO = ["/usr/bin/sudo", "-n"]


def run(argv, **kwargs):
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    kwargs.setdefault("timeout", 120)
    return subprocess.run(argv, check=False, **kwargs)


def expect_errno(action, *codes):
    try:
        action()
    except OSError as error:
        return error.errno in codes
    return False


def fill_bytes(path: Path) -> dict:
    written = 0
    chunk = b"x" * (1024 * 1024)
    enospc = False
    with (path / "fill").open("wb", buffering=0) as stream:
        try:
            for _ in range(BYTES // len(chunk) + 8):
                written += stream.write(chunk)
        except OSError as error:
            enospc = error.errno == errno.ENOSPC
    (path / "fill").unlink()
    return {"enospc": enospc, "written": written, "within_limit": written <= BYTES}


def fill_inodes(path: Path) -> dict:
    created = 0
    enospc = False
    try:
        for index in range(INODES + 64):
            (path / f"f{index}").touch()
            created += 1
    except OSError as error:
        enospc = error.errno == errno.ENOSPC
    for index in range(created):
        (path / f"f{index}").unlink()
    return {"enospc": enospc, "created": created, "within_limit": created <= INODES}


def sparse_then_dirty(path: Path) -> dict:
    """A sparse file may claim any size; dirtying it must still hit the quota."""
    target = path / "sparse"
    with target.open("wb") as stream:
        stream.truncate(1024**3)
    enospc = False
    with target.open("r+b", buffering=0) as stream:
        try:
            for _ in range(BYTES // (1024 * 1024) + 8):
                stream.write(b"x" * (1024 * 1024))
        except OSError as error:
            enospc = error.errno == errno.ENOSPC
    allocated = target.stat().st_blocks * 512
    target.unlink()
    return {"enospc": enospc, "allocated": allocated, "within_limit": allocated <= BYTES}


def noexec(path: Path) -> bool:
    target = path / "true"
    shutil.copy2("/usr/bin/true", target)
    refused = expect_errno(lambda: subprocess.run([str(target)], check=False), errno.EACCES)
    target.unlink()
    return refused


def container(build: Path, export: Path, script: str, *, build_mode: str = "rw") -> dict:
    """Run under the same restrictions the production stages intend to use."""
    name = f"tnd-smoke-{os.getpid()}-{time.monotonic_ns()}"
    result = run([
        "docker", "run", "--rm", "--name", name, "--network", "none", "--read-only",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--user", f"{os.getuid()}:{os.getgid()}", "--memory", "256m", "--pids-limit", "64",
        "--tmpfs", "/tmp:size=1m,noexec,nosuid,nodev",
        "--mount",
        f"type=bind,src={build},dst=/build" + (",readonly" if build_mode == "ro" else ""),
        "--mount", f"type=bind,src={export},dst=/export",
        IMAGE, "sh", "-c", script,
    ])
    return {"status": result.returncode, "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()[-300:]}


def docker_checks(build: Path, export: Path) -> dict:
    report = {}
    visible = container(build, export, "echo from-container > /build/marker && id -u")
    report["daemon_sees_host_mount"] = (
        visible["status"] == 0 and (build / "marker").read_text() == "from-container\n"
    )
    report["container_uid_is_runner"] = visible["stdout"] == str(os.getuid())
    (build / "marker").unlink()
    over = container(
        build, export, "dd if=/dev/zero of=/build/over bs=1M count=32 2>&1; echo status=$?",
    )
    report["container_byte_quota"] = "No space left" in over["stdout"]
    (build / "over").unlink(missing_ok=True)
    inodes = container(
        build, export,
        # `touch`, not `: >`: a failed redirection on a special builtin exits sh.
        'i=0; while touch "/build/n$i" 2>/dev/null; do i=$((i+1)); '
        '[ "$i" -gt 1024 ] && break; done; echo "$i"',
    )
    report["container_inode_quota"] = inodes["stdout"].isdigit() and int(inodes["stdout"]) <= INODES
    for path in build.iterdir():
        path.unlink()
    frozen = container(build, export, "touch /build/nope; echo status=$?", build_mode="ro")
    report["read_only_stage_cannot_write_build"] = "status=1" in frozen["stdout"]
    probes = container(
        build, export,
        "touch /root-fs 2>/dev/null; echo fs=$?; "
        "(cat /proc/net/route | wc -l); ls /var/run/docker.sock 2>/dev/null; echo sock=$?",
    )
    report["root_fs_read_only"] = "fs=1" in probes["stdout"]
    report["no_docker_socket"] = "sock=2" in probes["stdout"]
    lines = probes["stdout"].splitlines()
    report["no_network_routes"] = len(lines) > 1 and lines[1] == "1"
    if probes["status"] != 0 or len(lines) < 2:
        report["probe_failure"] = probes
    exec_probe = container(
        build, export, "cp /usr/bin/true /build/t && /build/t; echo status=$?; rm -f /build/t",
    )
    report["container_noexec_on_quota"] = "status=126" in exec_probe["stdout"]
    return report


def tamper_checks(parent: Path) -> dict:
    report = {}
    with boundary.ExperimentalBoundary(parent, LIMITS, LIMITS) as owner:
        build = owner.verify("build")
        nested = build / "nested"
        nested.mkdir()
        run([*SUDO, "/usr/bin/mount", "-t", "tmpfs", "tmpfs", str(nested)])
        report["nested_mount_refused"] = refuses(lambda: owner.verify("build"))
        report["close_refused_with_nested_mount"] = refuses(owner.close)
        run([*SUDO, "/usr/bin/umount", str(nested)])
        nested.rmdir()

        original = owner.mount_ids["build"]
        run([*SUDO, "/usr/bin/mount", "-t", "tmpfs", "-o",
             f"size={BYTES},nr_inodes={INODES},mode=0700,uid={os.getuid()},gid={os.getgid()},"
             "nodev,nosuid,noexec", "tmpfs", str(build)])
        report["stacked_replacement_refused"] = refuses(lambda: owner.verify("build"))
        run([*SUDO, "/usr/bin/umount", str(build)])
        report["original_restored"] = (
            owner.mount_ids["build"] == original and owner.verify("build") == build
        )

        os.chmod(build, 0o755)
        report["mode_change_refused"] = refuses(lambda: owner.verify("build"))
        os.chmod(build, 0o000)
        # Teardown must not depend on what a container did to the mount root.
    report["closed_after_candidate_chmod"] = owner.root is None
    report["no_residue"] = not any(parent.iterdir())
    return report


def refuses(action) -> bool:
    try:
        action()
    except ValueError:
        return True
    return False


CRASH_CHILD = """
import importlib.util, json, subprocess, sys, time, uuid
from pathlib import Path
spec = importlib.util.spec_from_file_location("b", sys.argv[1])
b = importlib.util.module_from_spec(spec); sys.modules["b"] = b; spec.loader.exec_module(b)
limits = b.Limits(1024 * 1024, 64)
owner = b.ExperimentalBoundary(Path(sys.argv[2]), limits, limits)
owner.create()
name = ""
if sys.argv[3] != "none":
    name = "tnd-audit-" + uuid.uuid4().hex
    owner.record_container(name)
    subprocess.run(["docker", "run", "-d", "--name", name, "--network", "none",
                    "--mount", f"type=bind,src={owner.root / 'build'},dst=/build",
                    sys.argv[3], "sleep", "600"], check=True, stdout=subprocess.DEVNULL)
print(json.dumps({"root": str(owner.root), "container": name}), flush=True)
time.sleep(600)
"""


def spawn_owner(parent: Path, image: str = "none"):
    child = subprocess.Popen(
        [sys.executable, "-c", CRASH_CHILD, str(SPEC.origin), str(parent), image],
        stdout=subprocess.PIPE, text=True,
    )
    details = json.loads(child.stdout.readline())
    child.stdout.close()
    return child, Path(details["root"]), details["container"]


def kill_owner(child) -> None:
    child.send_signal(signal.SIGKILL)
    child.wait(timeout=30)


def lease_of(root: Path) -> Path:
    return root.with_name(root.name + ".lease")


def refused(root: Path, parent: Path, wait: float = 0.0) -> bool:
    """Whether recovery refuses, having left the root and its mounts in place."""
    before = [m.mount_id for m in boundary._mounts() if m.path.parent == root]
    try:
        recovery.recover(lease_of(root), parent, wait=wait)
    except recovery.Refused:
        after = [m.mount_id for m in boundary._mounts() if m.path.parent == root]
        return before == after and root.exists() and lease_of(root).exists()
    return False


def clean(root: Path) -> bool:
    return not root.exists() and not lease_of(root).exists() and not any(
        root in (m.path, m.path.parent) for m in boundary._mounts()
    )


def crash_check(parent: Path, *, docker: bool) -> dict:
    """SIGKILL real owners; recovery must take exactly what each lease names."""
    report = {}
    child, root, _ = spawn_owner(parent)
    neighbor_child, neighbor, _ = spawn_owner(parent)
    report["mounts_survive_sigkill"] = None
    report["live_owner_refused"] = refused(root, parent)
    kill_owner(child)
    report["mounts_survive_sigkill"] = len(
        [m for m in boundary._mounts() if m.path.parent == root]
    )
    helper = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(600)", str(root / "build")],
        stdout=subprocess.DEVNULL,
    )
    report["surviving_helper_refused"] = refused(root, parent)
    helper.kill()
    helper.wait(timeout=30)
    nested = root / "build/nested"
    nested.mkdir()
    run([*SUDO, "/usr/bin/mount", "-t", "tmpfs", "tmpfs", str(nested)])
    report["nested_mount_refused"] = refused(root, parent)
    run([*SUDO, "/usr/bin/umount", "--", str(nested)])
    nested.rmdir()
    report["recovered"] = recovery.recover(lease_of(root), parent, wait=0) == "recovered"
    report["recovery_left_nothing"] = clean(root)
    report["live_neighbor_untouched"] = (
        neighbor.exists() and lease_of(neighbor).exists()
        and len([m for m in boundary._mounts() if m.path.parent == neighbor]) == 2
    )
    kill_owner(neighbor_child)
    report["neighbor_recovered_after_exit"] = (
        recovery.recover(lease_of(neighbor), parent, wait=0) == "recovered" and clean(neighbor)
    )
    if docker:
        child, root, name = spawn_owner(parent, IMAGE)
        kill_owner(child)
        running = run(["docker", "ps", "-q", "--filter", f"name=^/{name}$"]).stdout.strip()
        report["container_survives_owner_kill"] = bool(running)
        report["recovered_with_container"] = (
            recovery.recover(lease_of(root), parent, wait=0) == "recovered"
        )
        report["container_removed"] = not run(
            ["docker", "ps", "-aq", "--filter", f"name=^/{name}$"]
        ).stdout.strip()
        report["recovery_left_nothing_with_container"] = clean(root)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", required=True, type=Path)
    parser.add_argument("--no-docker", action="store_true")
    args = parser.parse_args()
    if sys.platform != "linux" or os.getuid() == 0:
        raise SystemExit("requires an unprivileged native-Linux account")
    parent = Path(tempfile.mkdtemp(prefix="smoke-", dir=args.scratch.resolve()))
    report = {
        "development_only": True,
        "kernel": platform.release(),
        "machine": platform.machine(),
        "limits": {"bytes": BYTES, "inodes": INODES},
    }
    with boundary.ExperimentalBoundary(parent, LIMITS, LIMITS) as owner:
        build, export = owner.verify("build"), owner.verify("export")
        mounts = {m.path: m for m in boundary._mounts()}
        report["mount_options"] = sorted(mounts[build].options)
        vfs = os.statvfs(build)
        report["statvfs"] = {"bytes": vfs.f_frsize * vfs.f_blocks, "inodes": vfs.f_files}
        report["bytes"] = fill_bytes(build)
        report["inodes"] = fill_inodes(build)
        report["sparse"] = sparse_then_dirty(build)
        report["export_quota_independent"] = fill_bytes(export)
        report["noexec_refused"] = noexec(build)
        if not args.no_docker:
            report["docker"] = docker_checks(build, export)
        (build / "left-behind").write_text("discarded by unmount")
    report["closed_nonempty"] = owner.root is None
    report["no_residue_after_close"] = not any(parent.iterdir())
    report["tamper"] = tamper_checks(parent)
    report["crash"] = crash_check(parent, docker=not args.no_docker)
    parent.rmdir()
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
