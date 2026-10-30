#!/usr/bin/env python3
"""Trusted Linux driver: isolate elaboration/export, then replay proof objects.

Run this file, the checker, inventory and policy from the maintained base.
Never run a pull request's copy of audit/ or its Lake configuration.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import re
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Callable
from pathlib import Path, PurePosixPath

TOOLCHAIN = "leanprover/lean4:v4.35.0"
COMPARATOR_REV = "e3dcf3083fc53d44b27a4431fabf7d43181583f5"
EXPORTER_REV = "5a9a355dc6c5fd82b69058d433e2ae2e8dfbf8fe"
LAKEFILE = """name = "tnd_candidate"
version = "0.0.0"
defaultTargets = ["TNDLib"]
[[lean_lib]]
name = "TNDLib"
"""
SHA = re.compile(r"[0-9a-f]{40}\Z")

# The audit deliberately supplies a separate minimal Lake project when
# compiling candidate sources. The published package must independently match
# this maintained policy, or a successful audit could describe a different
# package from the one downstream users actually build.
PUBLISHED_PACKAGE = {
    "lakefile.toml": (
        b'name = "tndlib"\nversion = "0.1.0"\ndefaultTargets = ["TNDLib"]\n'
        b'\n[[lean_lib]]\nname = "TNDLib"\n'
    ),
    "lake-manifest.json": (
        b'{"version": "1.3.0",\n "packagesDir": ".lake/packages",\n'
        b' "packages": [],\n "name": "tndlib",\n "lakeDir": ".lake",\n'
        b' "fixedToolchain": false}\n'
    ),
    "lean-toolchain": (TOOLCHAIN + "\n").encode(),
}

_admission_path = Path(__file__).resolve().parent / "admission" / "admit.py"
_admission_spec = importlib.util.spec_from_file_location("tnd_source_admission", _admission_path)
admission = importlib.util.module_from_spec(_admission_spec)
_admission_spec.loader.exec_module(admission)
IMAGE = admission.MAINTAINED_IMAGE
_sandbox_path = Path(__file__).resolve().parent / "admission" / "sandbox.py"
_sandbox_spec = importlib.util.spec_from_file_location("tnd_parser_sandbox", _sandbox_path)
parser_sandbox = importlib.util.module_from_spec(_sandbox_spec)
_sandbox_spec.loader.exec_module(parser_sandbox)
_checker_path = Path(__file__).resolve().parent / "checker_sandbox.py"
_checker_spec = importlib.util.spec_from_file_location("tnd_checker_sandbox", _checker_path)
checker_sandbox = importlib.util.module_from_spec(_checker_spec)
_checker_spec.loader.exec_module(checker_sandbox)
if checker_sandbox.IMAGE != IMAGE or checker_sandbox.COMPARATOR_REV != COMPARATOR_REV:
    raise RuntimeError("checker policy pins differ from trusted runner")
_resource_path = Path(__file__).resolve().parent / "resource_boundary.py"
_resource_spec = importlib.util.spec_from_file_location("tnd_resource_boundary", _resource_path)
resource_boundary = importlib.util.module_from_spec(_resource_spec)
sys.modules[_resource_spec.name] = resource_boundary
try:
    _resource_spec.loader.exec_module(resource_boundary)
except BaseException:
    sys.modules.pop(_resource_spec.name, None)
    raise


def certified_resource_limits(policy: dict) -> tuple[object, object]:
    """Require an explicitly validated, bounded production filesystem policy."""
    if (
        not isinstance(policy.get("schema_version"), int)
        or isinstance(policy.get("schema_version"), bool)
        or policy.get("schema_version") != 1
        or policy.get("source_binding_validated") is not True
        or policy.get("resource_boundary_validated") is not True
    ):
        raise ValueError(
            "source or resource boundary is unvalidated; production certification is disabled"
        )
    quota = policy.get("resource_limits")
    expected = {
        "schema_version",
        "build_bytes",
        "build_inodes",
        "export_bytes",
        "export_inodes",
    }
    if (
        not isinstance(quota, dict)
        or set(quota) != expected
        or not isinstance(quota.get("schema_version"), int)
        or isinstance(quota.get("schema_version"), bool)
        or quota.get("schema_version") != 1
    ):
        raise ValueError("validated resource policy must contain the exact quota schema")
    values = [
        quota["build_bytes"],
        quota["build_inodes"],
        quota["export_bytes"],
        quota["export_inodes"],
    ]
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise ValueError("validated resource limits must be integers")
    build = resource_boundary.Limits(quota["build_bytes"], quota["build_inodes"])
    export = resource_boundary.Limits(quota["export_bytes"], quota["export_inodes"])
    build.validate()
    export.validate()
    return build, export


def command(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Bound both elapsed time and combined output of every subprocess."""
    as_text = kwargs.pop("text", False)
    proc = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True, **kwargs
    )
    data = {"stdout": bytearray(), "stderr": bytearray()}
    started = time.monotonic()
    total = 0
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(proc.stdout, selectors.EVENT_READ, "stdout")
            selector.register(proc.stderr, selectors.EVENT_READ, "stderr")
            while selector.get_map():
                if time.monotonic() - started > 900:
                    raise subprocess.TimeoutExpired(args, 900)
                for key, _ in selector.select(timeout=0.2):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    total += len(chunk)
                    if total > 2 * 1024 * 1024:
                        raise ValueError("subprocess output exceeded 2 MiB")
                    data[key.data].extend(chunk)
            code = proc.wait(timeout=5)
    except BaseException:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        raise
    finally:
        proc.stdout.close()
        proc.stderr.close()
    out, err = bytes(data["stdout"]), bytes(data["stderr"])
    if as_text:
        out, err = out.decode("utf-8"), err.decode("utf-8")
    if code:
        raise subprocess.CalledProcessError(code, args, out, err)
    return subprocess.CompletedProcess(args, code, out, err)


def require_default_seccomp() -> None:
    """Require Docker to report its built-in profile; this is not kernel attestation."""
    try:
        result = command(["docker", "info", "--format", "{{json .SecurityOptions}}"], text=True)
        options = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise ValueError("cannot verify Docker built-in seccomp profile") from exc
    if not isinstance(options, list) or any(not isinstance(option, str) for option in options):
        raise ValueError("invalid Docker security options")
    seccomp = [option for option in options if option.startswith("name=seccomp")]
    if seccomp != ["name=seccomp,profile=builtin"]:
        raise ValueError("Docker built-in seccomp profile is required")


def git(repo: Path, *args: str) -> bytes:
    return command(["git", "-C", str(repo), *args]).stdout


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pinned_lean_root() -> Path:
    """Resolve and validate the verified install or selected elan toolchain.

    CI exports ``TND_LEAN_ROOT`` from ``audit/install_lean.py``; a development
    host falls back to elan. Either way the binary must pass every check below.
    """
    env = dict(os.environ)
    verified_root = env.pop("TND_LEAN_ROOT", None)
    for name in (
        "ELAN_TOOLCHAIN",
        "LEAN_SYSROOT",
        "LEAN_PATH",
        "LEAN_SRC_PATH",
        "LEAN_PLUGIN_PATH",
    ):
        env.pop(name, None)
    resolved = (
        verified_root
        if verified_root is not None
        else command(
            ["elan", "run", TOOLCHAIN, "lean", "--print-prefix"], text=True, env=env
        ).stdout.strip()
    )
    if not resolved or "\n" in resolved or not Path(resolved).is_absolute():
        raise ValueError("elan returned an invalid Lean toolchain prefix")
    root = Path(resolved).resolve()
    binary = root / "bin/lean"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise ValueError("pinned Lean binary is missing or not executable")
    if binary.resolve().parent != (root / "bin").resolve():
        raise ValueError("pinned Lean binary resolves outside its toolchain")
    reported = command([str(binary), "--print-prefix"], text=True, env=env).stdout.strip()
    if not reported or "\n" in reported or not Path(reported).is_absolute():
        raise ValueError("Lean binary returned an invalid toolchain prefix")
    if Path(reported).resolve() != root:
        raise ValueError("Lean binary reports a different toolchain prefix")
    version = command([str(binary), "--version"], text=True, env=env).stdout
    if not re.search(r"\bversion 4\.35\.0(?:,|\s|\))", version):
        raise ValueError("actual Lean binary does not match 4.35.0")
    return root


def _approved_source_entries(repo: Path, revision: str) -> dict[str, bytes]:
    """Validate the fixed library inventory before copying any candidate blob."""
    policy, _ = admission.policy_for()
    approved = {entry["path"] for entry in policy["source_files"]}
    records = [
        record
        for record in git(
            repo, "ls-tree", "-rz", revision, "--", "TNDLib.lean", "TNDLib"
        ).split(b"\0")
        if record
    ]
    entries: dict[str, bytes] = {}
    for record in records:
        metadata, raw_path = record.split(b"\t", 1)
        mode, kind, oid = metadata.split()
        name = raw_path.decode("utf-8")
        path = PurePosixPath(name)
        if mode not in (b"100644", b"100755") or kind != b"blob":
            raise ValueError(f"non-regular source entry: {name}")
        if path.is_absolute() or ".." in path.parts or not name.endswith(".lean"):
            raise ValueError(f"unexpected source entry: {name}")
        if not (name == "TNDLib.lean" or name.startswith("TNDLib/")):
            raise ValueError(f"source outside library: {name}")
        if name in entries:
            raise ValueError(f"duplicate source entry: {name}")
        entries[name] = oid
    if set(entries) != approved:
        raise ValueError(
            "source module inventory differs from maintained admission policy: "
            f"missing={sorted(approved - set(entries))}, "
            f"extra={sorted(set(entries) - approved)}"
        )
    return entries


def source_snapshot(repo: Path, revision: str, destination: Path) -> dict[str, str]:
    """Copy only ordinary tracked Lean source files, never links or build products."""
    if not SHA.fullmatch(revision):
        raise ValueError("base and head must be full commit hashes")
    git(repo, "cat-file", "-e", revision + "^{commit}")
    # Root-level or unapproved source trees could create importable modules that
    # a root-only TNDLib export never sees. Auxiliary source is restricted to
    # explicitly separate development/task trees, which are never library roots.
    tracked = git(repo, "ls-tree", "-rz", "--name-only", revision).split(b"\0")
    names = {record.decode("utf-8") for record in tracked if record}
    if "lakefile.lean" in names or any(
        name == ".lake" or name.startswith(".lake/") for name in names
    ):
        raise ValueError("unapproved alternate Lake configuration or tracked build artifacts")
    for name, expected in PUBLISHED_PACKAGE.items():
        record = git(repo, "ls-tree", "-z", revision, "--", name)
        entries = [entry for entry in record.split(b"\0") if entry]
        if len(entries) != 1:
            raise ValueError(f"missing published package policy file: {name}")
        metadata, raw_name = entries[0].split(b"\t", 1)
        mode, kind, oid = metadata.split()
        if raw_name.decode("utf-8") != name or mode != b"100644" or kind != b"blob":
            raise ValueError(f"published package policy file must be regular: {name}")
        if git(repo, "cat-file", "blob", oid.decode()) != expected:
            raise ValueError(f"published package differs from approved policy: {name}")
    for record in tracked:
        if not record:
            continue
        name = record.decode("utf-8")
        if name.endswith(".lean") and not (
            name == "TNDLib.lean" or name.startswith(("TNDLib/", "tasks/", "tests/", "audit/"))
        ):
            raise ValueError(f"unapproved Lean source outside library and auxiliary trees: {name}")
    entries = _approved_source_entries(repo, revision)
    files: dict[str, str] = {}
    total = 0
    for name, oid in sorted(entries.items()):
        content = git(repo, "cat-file", "blob", oid.decode())
        total += len(content)
        if (
            not 0 < len(content) <= admission.MAX_FILE
            or total > admission.MAX_TOTAL
            or b"\0" in content
        ):
            raise ValueError("tracked source exceeds maintained staging limits")
        content.decode("utf-8", errors="strict")
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        files[name] = hashlib.sha256(content).hexdigest()
    if "TNDLib.lean" not in files:
        raise ValueError("missing TNDLib.lean root module")
    (destination / "lakefile.toml").write_text(LAKEFILE)
    (destination / "lean-toolchain").write_text(TOOLCHAIN + "\n")
    (destination / ".lake").mkdir()
    return files


def docker_arguments(
    image: str,
    source: Path,
    build: Path,
    output: Path,
    lean_root: Path,
    exporter: Path,
    module: str = "TNDLib",
    namespace: str = "TNDLib",
    *,
    stage: str = "build",
) -> list[str]:
    if image != IMAGE:
        raise ValueError("build image must match the maintained SHA-256 pin")
    if not all(re.fullmatch(r"[A-Za-z][A-Za-z0-9_.]*", name) for name in (module, namespace)):
        raise ValueError("invalid trusted module or namespace")
    if stage not in {"build", "export"}:
        raise ValueError("invalid isolated stage")
    mounts = [
        (source, "/work", "ro"),
        (build, "/work/.lake", "rw" if stage == "build" else "ro"),
        (lean_root, "/opt/lean", "ro"),
    ]
    if stage == "export":
        mounts += [(output, "/output", "rw"), (exporter, "/opt/tnd-export", "ro")]
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
        "2g",
        "--memory-swap",
        "2g",
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
        "PATH=/opt/lean/bin:/usr/bin:/bin",
        "--env",
        "HOME=/tmp",
        "--env",
        "LEAN_NUM_THREADS=2",
        "--env",
        "LEAN_SYSROOT=/opt/lean",
    ]
    for host, guest, access in mounts:
        if "," in str(host):
            raise ValueError("commas in mount paths are unsupported")
        args += [
            "--mount",
            f"type=bind,src={host},dst={guest}" + (",readonly" if access == "ro" else ""),
        ]
    script = f"lake build {module}"
    if stage == "export":
        script = (
            "export LEAN_PATH=/work/.lake/build/lib/lean\n"
            f"/opt/tnd-export {module} {namespace} > /output/export.ndjson"
        )
    return [*args, image, "sh", "-eu", "-c", script]


def ensure_container_removed(name: str) -> None:
    """Do not proceed while a build container might still alter its artifacts."""
    subprocess.run(
        ["docker", "rm", "-f", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
        check=False,
    )
    # `docker run --rm` normally removes the container before the cleanup
    # call; a failed rm alone cannot distinguish that from a daemon failure.
    # Require a successful independent query proving the exact name is absent.
    listed = command(
        [
            "docker",
            "container",
            "ls",
            "-a",
            "--filter",
            f"name=^/{name}$",
            "--format",
            "{{.Names}}",
        ],
        text=True,
    )
    if listed.stdout.strip():
        raise ValueError(f"container cleanup did not remove {name}")


def _read_export(output: Path) -> bytes:
    """Copy one bounded ordinary export after its producing container stopped."""
    result = output / "export.ndjson"
    # O_NOFOLLOW avoids symlink substitution; O_NONBLOCK avoids blocking on a
    # malicious FIFO. Docker has stopped all container processes before this.
    fd = os.open(result, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= 128 * 1024 * 1024:
            raise ValueError("export must be a regular nonempty file of at most 128 MiB")
        contents = handle.read(128 * 1024 * 1024 + 1)
        if len(contents) > 128 * 1024 * 1024:
            raise ValueError("export exceeds 128 MiB limit")
    return contents


def _persist_checked_export(scratch: Path, contents: bytes) -> Path:
    """Publish a checked copy only after all quota cleanup has succeeded."""
    target = scratch / "checked-input.ndjson"
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(contents)
    return target


def build_export(
    image: str,
    source: Path,
    scratch: Path,
    lean_root: Path,
    exporter: Path,
    module: str = "TNDLib",
    namespace: str = "TNDLib",
) -> Path:
    """Development-only unbounded build used by isolated regression harnesses."""
    build, output = scratch / "build", scratch / "output"
    build.mkdir(parents=True)
    output.mkdir()
    # Docker's non-root user is the invoking UID, so only these fresh directories
    # are writable. No credentials, Docker socket, checker or reference exports
    # are mounted in the container.
    for stage in ("build", "export"):
        require_default_seccomp()
        name = "tnd-audit-" + uuid.uuid4().hex
        invocation = docker_arguments(
            image, source, build, output, lean_root, exporter, module, namespace, stage=stage
        )
        invocation[2:2] = ["--name", name]
        try:
            command(invocation)
        finally:
            # Reap each stage before launching the next, including on timeout.
            ensure_container_removed(name)
    return _persist_checked_export(scratch, _read_export(output))


def bounded_build_export(
    image: str,
    source: Path,
    scratch: Path,
    lean_root: Path,
    exporter: Path,
    quota_parent: Path,
    build_limit: object,
    export_limit: object,
    module: str = "TNDLib",
    namespace: str = "TNDLib",
) -> Path:
    """Build and export only inside verified quota mounts, then tear them down."""
    boundary = resource_boundary.ExperimentalBoundary(quota_parent, build_limit, export_limit)
    boundary.__enter__()
    container_uncertain = False
    try:
        for stage in ("build", "export"):
            require_default_seccomp()
            # Recheck both identities immediately before every launch. The
            # target Linux validation must additionally prove daemon visibility.
            build = boundary.verify("build")
            output = boundary.verify("export")
            name = "tnd-audit-" + uuid.uuid4().hex
            invocation = docker_arguments(
                image,
                source,
                build,
                output,
                lean_root,
                exporter,
                module,
                namespace,
                stage=stage,
            )
            invocation[2:2] = ["--name", name]
            boundary.record_container(name)
            container_uncertain = True
            try:
                command(invocation)
            finally:
                ensure_container_removed(name)
                container_uncertain = False
        # Recheck after every candidate container has been independently reaped.
        boundary.verify("build")
        contents = _read_export(boundary.verify("export"))
    except BaseException as error:
        if container_uncertain:
            # A container might still mutate either mount. Retain the exact
            # mounts for independently supervised recovery; never unmount here.
            raise ValueError(
                "container absence unconfirmed; quota mounts retained for recovery"
            ) from error
        boundary.close()
        raise
    boundary.close()
    return _persist_checked_export(scratch, contents)


def bind_declarations(proof: dict, inventory: dict, sources: dict, head: str) -> None:
    for declaration in proof.get("declarations", []):
        path = inventory.get("source_paths", {}).get(declaration["name"])
        if path not in sources:
            raise ValueError(f"missing approved source path for {declaration['name']}")
        if declaration.get("source_path") != path:
            raise ValueError("checker source mapping differs from approved inventory")
        declaration["source_sha"] = head
        declaration["source_blob_sha256"] = sources[path]


def check_proof(
    image: str, config: Path, challenge: Path, solution: Path, checker: Path, lean_root: Path
) -> dict:
    """Run isolated replay; its development wrapper cannot be used as certification."""
    checked = checker_sandbox.run_isolated_checker(
        image,
        config,
        challenge,
        solution,
        checker,
        lean_root,
        check_seccomp=require_default_seccomp,
        cleanup=ensure_container_removed,
    )
    if (
        not isinstance(checked, dict)
        or checked.get("status") != "development-proof-check"
        or checked.get("development_only") is not True
    ):
        raise ValueError("checker isolation did not return development evidence")
    proof = checked.get("proof_check")
    if (
        not isinstance(proof, dict)
        or proof.get("status") != "verified-proof-objects"
        or proof.get("toolchain") != "4.35.0"
    ):
        raise ValueError("isolated checker did not verify proof objects under Lean 4.35.0")
    return proof


def admitted_snapshot(
    repo: Path,
    revision: str,
    scratch: Path,
    lean_root: Path,
    task: dict | None = None,
    role: str = "solution",
    image: str = IMAGE,
) -> tuple[Path, dict, dict]:
    """Copy Git blobs, admit those exact bytes, and build only the admitted copy."""
    raw = scratch / "raw-source"
    raw.mkdir(parents=True)
    git_hashes = source_snapshot(repo, revision, raw)
    admitted_hashes = dict(git_hashes)
    if task is not None:
        path = task["source_path"]
        record = git(repo, "ls-tree", revision, "--", path).split(b"\t", 1)
        if len(record) != 2 or record[1].strip().decode("utf-8") != path:
            raise ValueError(f"approved task missing from revision: {path}")
        mode, kind, oid = record[0].split()
        if mode not in (b"100644", b"100755") or kind != b"blob":
            raise ValueError("task source must be an ordinary file")
        content = git(repo, "cat-file", "blob", oid.decode())
        if not 0 < len(content) <= admission.MAX_FILE or b"\0" in content:
            raise ValueError("task source exceeds maintained staging limits")
        content.decode("utf-8", errors="strict")
        (raw / "Task.lean").write_bytes(content)
        git_hashes[path] = hashlib.sha256(content).hexdigest()
        admitted_hashes["Task.lean"] = git_hashes[path]
    source = scratch / "source"
    report = parser_sandbox.admit_into_container(
        raw,
        source,
        lean_root,
        image=image,
        cleanup=ensure_container_removed,
        check_seccomp=require_default_seccomp,
        expected_hashes=admitted_hashes,
        task_id=task["id"] if task else None,
        role=role,
    )
    if task is not None and report.get("task", {}).get("source_path") != task["source_path"]:
        raise ValueError("task registry and admission policy source paths differ")
    (source / "lakefile.toml").write_text(
        LAKEFILE + ('\n[[lean_lib]]\nname = "Task"\n' if task else "")
    )
    (source / "lean-toolchain").write_text(TOOLCHAIN + "\n")
    (source / "lake-manifest.json").write_text(
        json.dumps(
            {
                "version": "1.3.0",
                "packagesDir": ".lake/packages",
                "packages": [],
                "name": "tnd_candidate",
                "lakeDir": ".lake",
                "fixedToolchain": False,
            }
        )
    )
    (source / ".lake").mkdir()
    return source, git_hashes, report


def verify_tasks(
    args: argparse.Namespace,
    repo: Path,
    audit: Path,
    workspace: Path,
    lean_root: Path,
    exporter: Path,
    checker: Path,
    export_stage: Callable[..., Path],
) -> list[dict]:
    registry = json.loads((audit / "tasks.json").read_text())
    tasks = registry["tasks"]
    by_path = {entry["source_path"]: entry for entry in tasks}
    if len(by_path) != len(tasks):
        raise ValueError("duplicate task source path")
    changed = [
        name.decode("utf-8")
        for name in git(
            repo, "diff", "--name-only", "-z", args.base, args.head, "--", "tasks"
        ).split(b"\0")
        if name
    ]
    reports = []
    for path in changed:
        task = by_path.get(path)
        if task is None or not re.fullmatch(r"tasks/[A-Za-z0-9_]+\.lean", path):
            raise ValueError(f"task edit is not maintainer-approved: {path}")
        if not re.fullmatch(r"[A-Za-z0-9_]+", task["id"]):
            raise ValueError("invalid task id")
        exports = {}
        snapshots = {}
        admissions = {}
        for label, revision in (("base", args.base), ("head", args.head)):
            scratch = workspace / ("task-" + task["id"] + "-" + label)
            source, snapshots[label], admissions[label] = admitted_snapshot(
                repo,
                revision,
                scratch,
                lean_root,
                task,
                "challenge" if label == "base" else "solution",
                args.image,
            )
            exports[label] = export_stage(
                args.image, source, scratch, lean_root, exporter, "Task", task["namespace_name"]
            )
            admission.verify_exact(source, admissions[label]["source_sha256"])
        config = {
            "namespace_name": task["namespace_name"],
            "expected_exports": task["expected_exports"],
            "display_exports": [],
            "descriptions": {},
            "contributors": {},
            "citations": {},
            "source_paths": {name: path for name in task["expected_exports"]},
        }
        config_path = workspace / ("task-" + task["id"] + ".json")
        config_path.write_text(json.dumps(config))
        proof = check_proof(
            args.image, config_path, exports["base"], exports["head"], checker, lean_root
        )
        bind_declarations(proof, config, snapshots["head"], args.head)
        reports.append(
            {
                "id": task["id"],
                "source_path": path,
                "status": "verified-task-proof",
                "source_files": snapshots,
                "proof_check": proof,
                "admission": admissions,
                "export_sha256": {label: digest(file) for label, file in exports.items()},
            }
        )
    return reports


def verify(args: argparse.Namespace) -> dict:
    if platform.system() != "Linux":
        raise ValueError(
            "certification requires the Linux isolated-build runner; "
            "macOS runs are development only"
        )
    if os.getuid() == 0:
        raise ValueError("run verification as an unprivileged user")
    repo = args.repo.resolve()
    audit = Path(__file__).resolve().parent
    certification = json.loads((repo / ".choir/certification.json").read_text())
    build_limit, export_limit = certified_resource_limits(certification)
    quota_parent = getattr(args, "quota_parent", None)
    if not isinstance(quota_parent, Path) or not quota_parent.is_absolute():
        raise ValueError("a canonical absolute --quota-parent is required")
    if args.image != IMAGE:
        raise ValueError("build image must match the maintained SHA-256 pin")
    # Ensure the trusted runner and policy checkout are the specified base. The
    # workflow checks out this commit separately from all candidate sources.
    if git(repo, "rev-parse", "HEAD").decode().strip() != args.base:
        raise ValueError("trusted checkout HEAD must equal --base")
    tracked_changes = git(repo, "status", "--porcelain", "--untracked-files=no")
    if tracked_changes:
        raise ValueError("trusted checkout contains tracked modifications")
    if (repo / "lean-toolchain").read_text().strip() != TOOLCHAIN:
        raise ValueError("repository toolchain differs from the trusted pin")
    checker = audit / ".lake/build/bin/tnd-check"
    exporter = audit / ".lake/build/bin/tnd-export"
    for binary in (checker, exporter):
        if not binary.is_file():
            raise ValueError("build trusted audit tools first: cd audit && lake build")
    lean_root = pinned_lean_root()
    config = audit / "exports.json"
    inventory = json.loads(config.read_text())
    if not inventory.get("expected_exports"):
        raise ValueError("approved export inventory is empty")
    # Presence check only: never pull an image implicitly during untrusted work.
    command(["docker", "image", "inspect", args.image])

    def export_stage(
        image: str,
        source: Path,
        scratch: Path,
        lean: Path,
        tool: Path,
        module: str = "TNDLib",
        namespace: str = "TNDLib",
    ) -> Path:
        return bounded_build_export(
            image,
            source,
            scratch,
            lean,
            tool,
            quota_parent,
            build_limit,
            export_limit,
            module,
            namespace,
        )

    with tempfile.TemporaryDirectory(prefix="tnd-audit-") as tmp:
        workspace = Path(tmp)
        sources = {}
        exports = {}
        admissions = {}
        for label, revision in (("base", args.base), ("head", args.head)):
            source, sources[label], admissions[label] = admitted_snapshot(
                repo, revision, workspace / label, lean_root, image=args.image
            )
            exports[label] = export_stage(
                args.image, source, workspace / label, lean_root, exporter
            )
            admission.verify_exact(source, admissions[label]["source_sha256"])
        proof = check_proof(
            args.image, config, exports["base"], exports["head"], checker, lean_root
        )
        bind_declarations(proof, inventory, sources["head"], args.head)
        tasks = verify_tasks(
            args,
            repo,
            audit,
            workspace,
            lean_root,
            exporter,
            checker,
            export_stage,
        )
        return {
            "schema_version": 1,
            "status": "verified",
            "base_sha": args.base,
            "head_sha": args.head,
            "toolchain": TOOLCHAIN,
            "comparator_revision": COMPARATOR_REV,
            "exporter_revision": EXPORTER_REV,
            "build_image": args.image,
            "resource_boundary": "host-tmpfs-v1",
            "resource_limits": certification["resource_limits"],
            "source_files": sources,
            "admission": admissions,
            "export_sha256": {label: digest(path) for label, path in exports.items()},
            "inventory_sha256": digest(config),
            "checker_sha256": digest(checker),
            "exporter_sha256": digest(exporter),
            "proof_check": proof,
            "tasks": tasks,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--quota-parent",
        type=Path,
        help="trusted canonical host directory for fresh bounded build/export mounts",
    )
    parser.add_argument("--image", default=IMAGE, help="must match the maintained image pin")
    args = parser.parse_args()
    try:
        result = verify(args)
        code = 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        result = {
            "schema_version": 1,
            "status": "rejected",
            "base_sha": args.base,
            "head_sha": args.head,
            "reason": str(error),
        }
        if isinstance(error, subprocess.CalledProcessError):
            result["checker_or_build_output"] = str(error.stdout)[-8000:]
            result["checker_or_build_error"] = str(error.stderr)[-8000:]
        code = 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "report": str(args.output)}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
