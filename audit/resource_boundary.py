"""Experimental trusted-host tmpfs lifecycle; not yet a validated boundary.

The guarded production route in ``audit/run.py`` now depends on this helper,
but both readiness flags remain false until it has been reviewed and exercised
on the target native-Linux runner. It must only be called by maintainer-controlled
code on an unprivileged host account. It does not itself parse source or start
candidate containers.
"""
from __future__ import annotations

import json
import os
import re
import signal
import stat
import subprocess
import sys
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Limits:
    """Filesystem maximums; budgets are examples, not production policy."""

    bytes: int
    inodes: int

    def validate(self) -> None:
        if (isinstance(self.bytes, bool) or not isinstance(self.bytes, int)
                or self.bytes < 4096 or self.bytes > 4 * 1024**3
                or isinstance(self.inodes, bool) or not isinstance(self.inodes, int)
                or not 16 <= self.inodes <= 1_000_000):
            raise ValueError("invalid experimental tmpfs limits")


@dataclass(frozen=True)
class Mount:
    mount_id: int
    path: Path
    fstype: str
    options: frozenset[str]


def _unescape(value: str) -> str:
    """Decode only the escapes defined by proc(5); reject malformed escapes."""
    if re.search(r"\\(?!040|011|012|134)", value):
        raise ValueError("unexpected mountinfo path escape")
    return re.sub(r"\\(040|011|012|134)", lambda m: chr(int(m.group(1), 8)), value)


def parse_mountinfo(contents: str) -> list[Mount]:
    mounts = []
    for line in contents.splitlines():
        fields = line.split()
        if "-" not in fields:
            raise ValueError("invalid mountinfo record")
        separator = fields.index("-")
        if separator < 6 or len(fields) < separator + 4:
            raise ValueError("invalid mountinfo fields")
        mount_id = int(fields[0])
        if mount_id <= 0:
            raise ValueError("invalid mount ID")
        mounts.append(Mount(mount_id, Path(_unescape(fields[4])), fields[separator + 1],
                            frozenset(fields[5].split(","))))
    return mounts


def _mounts() -> list[Mount]:
    return parse_mountinfo(Path("/proc/self/mountinfo").read_text())


def _run(argv: list[str]) -> None:
    proc = subprocess.Popen(argv, start_new_session=True, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        _, stderr = proc.communicate(timeout=30)
    except BaseException:
        with suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
        try:
            proc.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            # A privileged descendant can retain the pipe in another process
            # group. Never wait forever or treat group termination as proof
            # that all privileged descendants stopped.
            if proc.stderr is not None:
                proc.stderr.close()
        raise
    if proc.returncode:
        raise subprocess.CalledProcessError(proc.returncode, argv, stderr=stderr)


def _process_start(pid: int) -> int | None:
    """Return the kernel start time that distinguishes `pid` from a reused one."""
    try:
        stat_line = Path(f"/proc/{pid}/stat").read_text()
        return int(stat_line.rsplit(")", 1)[1].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def _is_child(path: Path, parent: Path) -> bool:
    return path != parent and parent in path.parents


def _check_parent_chain(parent: Path) -> None:
    """Reject ancestors whose entries can be replaced by unrelated users.

    Trusted-owned sticky directories protect trusted-owned child entries, but
    same-UID and privileged actors remain trusted.
    """
    for path in (parent, *parent.parents):
        info = path.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid not in (0, os.getuid())
                or (info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX)):
            raise ValueError("scratch ancestor ownership or permissions are unsafe")


class ExperimentalBoundary:
    """Own two dedicated host mounts with conservative, nonrecursive cleanup.

    Abrupt failure leaves the mounts in place; the lease written before the
    first mount lets `resource_recovery.py` reconcile them independently. The
    caller must ensure every client container has stopped before cleanup.
    """

    def __init__(self, parent: Path, build: Limits, export: Limits):
        build.validate()
        export.validate()
        self.parent = parent
        self.limits = {"build": build, "export": export}
        self.root: Path | None = None
        self.mount_ids: dict[str, int] = {}
        self.root_identity: tuple[int, int] | None = None
        self.uncertain_mount = False
        self.containers: list[str] = []
        self.lease: Path | None = None

    def __enter__(self) -> ExperimentalBoundary:
        try:
            self.create()
        except BaseException:
            # If verification fails, cleanup may itself fail closed and leave
            # the exact private path for operator recovery.
            self.close()
            raise
        return self

    def __exit__(self, _kind, _value, _traceback) -> None:
        self.close()

    def create(self) -> None:
        if (sys.platform != "linux" or os.getuid() == 0 or os.geteuid() == 0
                or os.getuid() != os.geteuid() or os.getgid() != os.getegid()):
            raise ValueError("experimental mounts require an unprivileged Linux host")
        if self.root is not None:
            raise ValueError("boundary already created")
        if not self.parent.is_absolute() or self.parent.resolve(strict=True) != self.parent:
            raise ValueError("scratch parent must be an existing canonical absolute path")
        _check_parent_chain(self.parent)
        self.root = Path(tempfile.mkdtemp(prefix="tnd-boundary-", dir=self.parent))
        info = self.root.lstat()
        self.root_identity = (info.st_dev, info.st_ino)
        self._check_root()
        self.lease = self.root.with_name(self.root.name + ".lease")
        self._write_lease()
        for name, limit in self.limits.items():
            self._check_root()
            path = self.root / name
            path.mkdir(mode=0o700)
            if any(m.path == path or _is_child(m.path, path) for m in _mounts()):
                raise ValueError("unexpected pre-existing mount")
            opts = (f"size={limit.bytes},nr_inodes={limit.inodes},mode=0700,"
                    f"uid={os.getuid()},gid={os.getgid()},nodev,nosuid,noexec")
            try:
                _run(["/usr/bin/sudo", "-n", "/usr/bin/mount", "-t", "tmpfs", "-o", opts,
                      "tmpfs", str(path)])
            except BaseException:
                # Killing a sudo process group does not prove all privileged
                # descendants are gone. A late helper could still act on the
                # pathname; quarantine it for independently supervised recovery.
                self.uncertain_mount = True
                raise
            finally:
                # A mount can succeed even if its client exits abnormally.
                # Record only an unambiguous exact tmpfs mount before raising.
                matches = [m for m in _mounts() if m.path == path]
                if len(matches) == 1 and matches[0].fstype == "tmpfs":
                    self.mount_ids[name] = matches[0].mount_id
            if name not in self.mount_ids:
                raise ValueError("expected tmpfs mount was not established")
            self.verify(name)

    def _write_lease(self) -> None:
        """Atomically record what recovery may touch, before it can exist."""
        pid = os.getpid()
        contents = json.dumps({
            "schema_version": 1,
            "root": str(self.root),
            "root_identity": list(self.root_identity),
            "owner_pid": pid,
            "owner_start": _process_start(pid),
            "containers": self.containers,
        })
        partial = self.lease.with_name(self.lease.name + ".tmp")
        fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(contents)
        os.replace(partial, self.lease)

    def record_container(self, name: str) -> None:
        """Name a container in the lease before it is started."""
        self.containers.append(name)
        self._write_lease()

    def _check_root(self) -> None:
        if self.root is None or self.root_identity is None:
            raise ValueError("boundary not created")
        _check_parent_chain(self.parent)
        info = self.root.lstat()
        if (not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700
                or info.st_uid != os.getuid() or (info.st_dev, info.st_ino) != self.root_identity):
            raise ValueError("scratch root identity or permissions changed")

    def _mount_identity(self, name: str) -> tuple[Path, Mount]:
        self._check_root()
        if name not in self.limits or name not in self.mount_ids:
            raise ValueError("unrecognized or unmounted quota")
        path = self.root / name
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("quota mountpoint is no longer an ordinary directory")
        mounts = _mounts()
        matches = [mount for mount in mounts if mount.path == path]
        if (len(matches) != 1 or matches[0].mount_id != self.mount_ids[name]
                or matches[0].fstype != "tmpfs"
                or any(_is_child(mount.path, path) for mount in mounts)):
            raise ValueError("quota mount identity or nested mounts differ")
        return path, matches[0]

    def verify(self, name: str) -> Path:
        path, mount = self._mount_identity(name)
        info = path.lstat()
        if (stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.getuid()
                or info.st_gid != os.getgid()):
            raise ValueError("quota mount ownership or permissions changed")
        if not {"nodev", "nosuid", "noexec"}.issubset(mount.options):
            raise ValueError("quota mount flags differ")
        vfs = os.statvfs(path)
        capacity = vfs.f_frsize * vfs.f_blocks
        if (not 0 < capacity <= self.limits[name].bytes
                or not 0 < vfs.f_files <= self.limits[name].inodes):
            raise ValueError("quota capacity or inode limit is absent or too large")
        return path

    def close(self) -> None:
        """Unmount exact recorded mounts; leave uncertain resources untouched."""
        if self.root is None:
            return
        self._check_root()
        if self.uncertain_mount:
            raise ValueError("abnormal mount helper requires independent recovery; path retained")
        for name in reversed(tuple(self.limits)):
            path = self.root / name
            if name not in self.mount_ids:
                # Refuse removal if setup failed after an unexpected mount.
                if any(m.path == path or _is_child(m.path, path) for m in _mounts()):
                    raise ValueError("unexpected mount prevents cleanup")
                if path.exists():
                    path.rmdir()
                continue
            # A candidate with write access can change mount-root permissions
            # or fill its quota. That must not prevent teardown of the same
            # uniquely recorded mount after all containers have stopped.
            self._mount_identity(name)
            old_id = self.mount_ids[name]
            try:
                _run(["/usr/bin/sudo", "-n", "/usr/bin/umount", "--", str(path)])
            except BaseException:
                # The privileged unmount helper can likewise outlive its
                # client; do not retry or remove paths without supervision.
                self.uncertain_mount = True
                raise
            mounts = _mounts()
            if any(
                m.mount_id == old_id or m.path == path or _is_child(m.path, path) for m in mounts
            ):
                raise ValueError("quota unmount did not complete")
            del self.mount_ids[name]
            path.rmdir()
        self.root.rmdir()
        self.lease.unlink(missing_ok=True)
        self.root = None
        self.root_identity = None
