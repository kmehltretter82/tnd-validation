"""Bounded, filtered acquisition of one proof-submission commit.

This maintained-base helper reduces the amount of contributor-controlled Git
data written before source admission.  It is not a filesystem quota: Git and
the host still need native resource-boundary validation before certification.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import selectors
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gate.verify.tnd_policy import rejected_paths

SHA = re.compile(r"[0-9a-f]{40}\Z")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
MAX_CHANGED_FILES = 8
MAX_CHANGED_LINES = 2_000
MAX_FILE_LINES = 1_000
MAX_SOURCE_BYTES = 256 * 1024
MAX_TOTAL_SOURCE_BYTES = 1024 * 1024
# Git's blob:limit omits objects whose size is at least the limit.  Adding one
# includes every source accepted at MAX_SOURCE_BYTES while omitting larger ones.
GIT_BLOB_LIMIT = MAX_SOURCE_BYTES + 1
MAX_API_OUTPUT = 4 * 1024 * 1024
MAX_COMMAND_OUTPUT = 512 * 1024
COMMAND_TIMEOUT = 120


@dataclass(frozen=True)
class Change:
    path: str
    status: str
    additions: int
    deletions: int
    oid: str | None


def bounded_command(
    argv: list[str],
    *,
    cwd: Path | None = None,
    output_limit: int = MAX_COMMAND_OUTPUT,
    timeout: int = COMMAND_TIMEOUT,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run one metadata/fetch command with bounded time and combined output."""
    process = subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    streams = {"stdout": bytearray(), "stderr": bytearray()}
    total = 0
    started = time.monotonic()
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            while selector.get_map():
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(argv, timeout)
                for key, _ in selector.select(timeout=min(0.2, remaining)):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    total += len(chunk)
                    if total > output_limit:
                        raise ValueError("proof-submission command output exceeded limit")
                    streams[key.data].extend(chunk)
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise subprocess.TimeoutExpired(argv, timeout)
            code = process.wait(timeout=remaining)
    except BaseException:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        raise
    finally:
        process.stdout.close()
        process.stderr.close()
    stdout, stderr = bytes(streams["stdout"]), bytes(streams["stderr"])
    if code:
        raise subprocess.CalledProcessError(code, argv, stdout, stderr)
    return subprocess.CompletedProcess(argv, code, stdout, stderr)


def _environment() -> dict[str, str]:
    env = dict(os.environ)
    env.update(GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    return env


def _git(checkout: Path, *args: str, output_limit: int = MAX_COMMAND_OUTPUT) -> bytes:
    return bounded_command(
        ["git", "-C", str(checkout), *args],
        output_limit=output_limit,
        env=_environment(),
    ).stdout


def _api(endpoint: str) -> Any:
    result = bounded_command(
        ["gh", "api", "--method", "GET", endpoint],
        output_limit=MAX_API_OUTPUT,
        env=dict(os.environ),
    )
    return json.loads(result.stdout)


def _integer(record: dict[str, Any], name: str) -> int:
    value = record.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"GitHub changed-file metadata has invalid {name}")
    return value


def trusted_metadata(repo: str, pr: int, base: str, head: str) -> list[Change]:
    """Validate exact PR metadata and a deliberately small changed-file set."""
    repo_parts = repo.split("/")
    if (
        not REPOSITORY.fullmatch(repo)
        or any(part in {".", ".."} for part in repo_parts)
        or isinstance(pr, bool)
        or pr < 1
        or not SHA.fullmatch(base)
        or not SHA.fullmatch(head)
    ):
        raise ValueError("repository, PR number, base, or head is invalid")
    metadata = _api(f"repos/{repo}/pulls/{pr}")
    if not isinstance(metadata, dict):
        raise ValueError("GitHub returned invalid pull-request metadata")
    base_record, head_record = metadata.get("base"), metadata.get("head")
    changed_files = metadata.get("changed_files")
    base_repo = base_record.get("repo") if isinstance(base_record, dict) else None
    if (
        type(metadata.get("number")) is not int
        or metadata.get("number") != pr
        or metadata.get("state") != "open"
        or not isinstance(base_record, dict)
        or not isinstance(head_record, dict)
        or not isinstance(base_repo, dict)
        or base_record.get("ref") != "main"
        or base_record.get("sha") != base
        or head_record.get("sha") != head
        or base_repo.get("full_name") != repo
        or isinstance(changed_files, bool)
        or not isinstance(changed_files, int)
        or not 1 <= changed_files <= MAX_CHANGED_FILES
    ):
        raise ValueError("GitHub PR metadata differs from the trusted event or size policy")

    records = _api(f"repos/{repo}/pulls/{pr}/files?per_page=100")
    if not isinstance(records, list) or len(records) != changed_files:
        raise ValueError("GitHub changed-file listing is incomplete or inconsistent")
    changes: list[Change] = []
    seen: set[str] = set()
    total_lines = 0
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("GitHub changed-file record is invalid")
        path, status, oid = record.get("filename"), record.get("status"), record.get("sha")
        additions = _integer(record, "additions")
        deletions = _integer(record, "deletions")
        lines = _integer(record, "changes")
        if (
            not isinstance(path, str)
            or not path
            or len(path.encode("utf-8")) > 512
            or path in seen
            or status not in {"added", "modified", "removed"}
            or lines != additions + deletions
            or not 1 <= lines <= MAX_FILE_LINES
            or (status != "removed" and (not isinstance(oid, str) or not SHA.fullmatch(oid)))
            or (
                status == "removed"
                and oid is not None
                and (not isinstance(oid, str) or not SHA.fullmatch(oid))
            )
        ):
            raise ValueError("GitHub changed-file metadata violates proof-submission policy")
        seen.add(path)
        total_lines += lines
        changes.append(Change(path, status, additions, deletions, oid))
    if total_lines > MAX_CHANGED_LINES:
        raise ValueError("proof submission changes too many lines")
    refused = rejected_paths(change.path for change in changes)
    if refused:
        raise ValueError(f"proof submissions cannot change protected paths: {refused!r}")
    return changes


def _check_checkout(checkout: Path, repo: str, base: str) -> Path:
    checkout = checkout.resolve(strict=True)
    if not checkout.is_dir():
        raise ValueError("trusted checkout is not a directory")
    current = _git(checkout, "rev-parse", "HEAD").decode().strip()
    if current != base:
        raise ValueError("trusted checkout HEAD differs from the event base")
    remote = _git(checkout, "remote", "get-url", "origin").decode().strip()
    if remote not in {f"https://github.com/{repo}", f"https://github.com/{repo}.git"}:
        raise ValueError("origin is not the expected GitHub repository")
    return checkout


def filtered_fetch(checkout: Path, pr: int, head: str) -> str:
    """Fetch the exact event SHA shallowly while omitting source blobs over 256 KiB."""
    target = f"refs/tnd/pr-{pr}"
    result = bounded_command(
        [
            "git",
            "-C",
            str(checkout),
            "-c",
            "protocol.version=2",
            "-c",
            "fetch.writeCommitGraph=false",
            "fetch",
            "--force",
            "--no-tags",
            "--no-recurse-submodules",
            "--depth=1",
            f"--filter=blob:limit={GIT_BLOB_LIMIT}",
            "origin",
            f"+{head}:{target}",
        ],
        cwd=checkout,
        env=_environment(),
    )
    warning = result.stderr.decode("utf-8", errors="replace").lower()
    if "filtering not recognized" in warning or "does not support filter" in warning:
        raise ValueError("Git server did not honor the required object filter")
    fetched = _git(checkout, "rev-parse", target).decode().strip()
    if fetched != head or _git(checkout, "cat-file", "-t", head).strip() != b"commit":
        raise ValueError("filtered fetch did not produce the exact event head commit")
    return target


def verify_fetched(
    checkout: Path, base: str, head: str, changes: list[Change],
) -> int:
    """Match the fetched tree to API paths and require every accepted blob locally."""
    diff = _git(
        checkout,
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        "--no-renames",
        "--name-only",
        "-z",
        base,
        head,
        "--",
        output_limit=64 * 1024,
    )
    paths = [item.decode("utf-8") for item in diff.split(b"\0") if item]
    expected = [change.path for change in changes]
    if len(paths) != len(set(paths)) or set(paths) != set(expected):
        raise ValueError("fetched Git diff differs from trusted changed-file metadata")
    refused = rejected_paths(paths)
    if refused:
        raise ValueError(f"proof submissions cannot change protected paths: {refused!r}")

    total_bytes = 0
    for change in changes:
        entry = _git(checkout, "ls-tree", "-z", head, "--", change.path)
        if change.status == "removed":
            if entry:
                raise ValueError("GitHub reported a removal that remains in the fetched tree")
            continue
        rows = [row for row in entry.split(b"\0") if row]
        if len(rows) != 1:
            raise ValueError("accepted source is missing from the fetched tree")
        metadata, raw_path = rows[0].split(b"\t", 1)
        mode, kind, oid = metadata.split()
        if (
            mode != b"100644"
            or kind != b"blob"
            or raw_path.decode("utf-8") != change.path
            or oid.decode() != change.oid
        ):
            raise ValueError(
                "accepted source path, type, or object ID differs from GitHub metadata"
            )
        try:
            object_kind = _git(checkout, "cat-file", "-t", change.oid or "").strip()
            size_raw = _git(checkout, "cat-file", "-s", change.oid or "").strip()
            size = int(size_raw)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            raise ValueError(
                "accepted source blob is absent from the bounded filtered fetch"
            ) from error
        if object_kind != b"blob" or not 0 < size <= MAX_SOURCE_BYTES:
            raise ValueError("accepted source blob exceeds the 256 KiB fetch policy")
        total_bytes += size
        if total_bytes > MAX_TOTAL_SOURCE_BYTES:
            raise ValueError("accepted source blobs exceed the 1 MiB aggregate fetch policy")
    return total_bytes


def prepare_submission(checkout: Path, repo: str, pr: int, base: str, head: str) -> dict[str, Any]:
    """Validate metadata, acquire the exact commit, and enforce path/type policy."""
    checkout = _check_checkout(checkout, repo, base)
    changes = trusted_metadata(repo, pr, base, head)
    target = filtered_fetch(checkout, pr, head)
    source_bytes = verify_fetched(checkout, base, head, changes)
    return {
        "status": "filtered-proof-submission",
        "scope": "risk-reduction-not-filesystem-quota",
        "head_sha": head,
        "base_sha": base,
        "ref": target,
        "changed_files": len(changes),
        "changed_lines": sum(change.additions + change.deletions for change in changes),
        "maximum_source_bytes": MAX_SOURCE_BYTES,
        "maximum_total_source_bytes": MAX_TOTAL_SOURCE_BYTES,
        "source_bytes": source_bytes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, default=Path("."))
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args(argv)
    try:
        report = prepare_submission(args.checkout, args.repo, args.pr, args.base, args.head)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"proof-submission fetch rejected: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
