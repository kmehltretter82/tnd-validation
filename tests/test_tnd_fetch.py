"""Proof-submission metadata and filtered-fetch boundary tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from gate.verify import tnd_fetch

BASE = "a" * 40
HEAD = "b" * 40
OID = "c" * 40
REPO = "owner/tndlib"


def pr_metadata(**changes):
    result = {
        "number": 7,
        "state": "open",
        "changed_files": 1,
        "base": {"ref": "main", "sha": BASE, "repo": {"full_name": REPO}},
        "head": {"sha": HEAD},
    }
    result.update(changes)
    return result


def file_metadata(**changes):
    result = {
        "filename": "tasks/map_exists.lean",
        "status": "modified",
        "additions": 3,
        "deletions": 1,
        "changes": 4,
        "sha": OID,
    }
    result.update(changes)
    return result


def api_fixture(monkeypatch, metadata=None, files=None):
    metadata = pr_metadata() if metadata is None else metadata
    files = [file_metadata()] if files is None else files

    def api(endpoint):
        return files if endpoint.endswith("/files?per_page=100") else metadata

    monkeypatch.setattr(tnd_fetch, "_api", api)


def test_trusted_metadata_accepts_small_exact_proof_change(monkeypatch):
    api_fixture(monkeypatch)
    changes = tnd_fetch.trusted_metadata(REPO, 7, BASE, HEAD)
    assert changes == [tnd_fetch.Change("tasks/map_exists.lean", "modified", 3, 1, OID)]


@pytest.mark.parametrize(
    "metadata,files,match",
    [
        (pr_metadata(state="closed"), [file_metadata()], "trusted event"),
        (pr_metadata(changed_files=9), [file_metadata()], "size policy"),
        (pr_metadata(base={"ref": "other", "sha": BASE, "repo": {"full_name": REPO}}),
         [file_metadata()], "trusted event"),
        (pr_metadata(), [file_metadata(filename="audit/run.py")], "protected paths"),
        (pr_metadata(), [file_metadata(status="renamed")], "metadata violates"),
        (pr_metadata(), [file_metadata(changes=5)], "metadata violates"),
        (pr_metadata(), [file_metadata(changes=1_001, additions=1_001, deletions=0)],
         "metadata violates"),
        (pr_metadata(), [file_metadata(), file_metadata()], "incomplete or inconsistent"),
    ],
)
def test_trusted_metadata_rejects_untrusted_or_large_changes(
    monkeypatch, metadata, files, match,
):
    api_fixture(monkeypatch, metadata, files)
    with pytest.raises(ValueError, match=match):
        tnd_fetch.trusted_metadata(REPO, 7, BASE, HEAD)


def test_filtered_fetch_uses_exact_sha_shallow_filter_and_rejects_ignored_filter(
    tmp_path, monkeypatch,
):
    calls = []

    def command(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, b"", b"")

    def git(_checkout, *args, **_kwargs):
        if args[:2] == ("rev-parse", "refs/tnd/pr-7"):
            return (HEAD + "\n").encode()
        if args[:2] == ("cat-file", "-t"):
            return b"commit\n"
        raise AssertionError(args)

    monkeypatch.setattr(tnd_fetch, "bounded_command", command)
    monkeypatch.setattr(tnd_fetch, "_git", git)
    assert tnd_fetch.filtered_fetch(tmp_path, 7, HEAD) == "refs/tnd/pr-7"
    fetch = calls[0][0]
    assert "--depth=1" in fetch
    assert "--no-tags" in fetch
    assert "--no-recurse-submodules" in fetch
    assert f"--filter=blob:limit={tnd_fetch.MAX_SOURCE_BYTES + 1}" in fetch
    assert f"+{HEAD}:refs/tnd/pr-7" in fetch
    assert "refs/pull/7/head" not in fetch
    assert calls[0][1]["env"]["GIT_NO_LAZY_FETCH"] == "1"

    def ignored(args, **_kwargs):
        return subprocess.CompletedProcess(
            args, 0, b"", b"warning: filtering not recognized by server, ignoring\n"
        )

    monkeypatch.setattr(tnd_fetch, "bounded_command", ignored)
    with pytest.raises(ValueError, match="did not honor"):
        tnd_fetch.filtered_fetch(tmp_path, 7, HEAD)


def test_fetched_tree_must_match_api_and_contain_small_blob(monkeypatch, tmp_path):
    change = tnd_fetch.Change("tasks/map_exists.lean", "modified", 3, 1, OID)

    def git(_checkout, *args, **_kwargs):
        if args[0] == "diff":
            return b"tasks/map_exists.lean\0"
        if args[0] == "ls-tree":
            return f"100644 blob {OID}\ttasks/map_exists.lean\0".encode()
        if args[:2] == ("cat-file", "-t"):
            return b"blob\n"
        if args[:2] == ("cat-file", "-s"):
            return b"1024\n"
        raise AssertionError(args)

    monkeypatch.setattr(tnd_fetch, "_git", git)
    assert tnd_fetch.verify_fetched(tmp_path, BASE, HEAD, [change]) == 1024

    def missing(_checkout, *args, **kwargs):
        if args[:2] == ("cat-file", "-t"):
            raise subprocess.CalledProcessError(1, ["git", *args])
        return git(_checkout, *args, **kwargs)

    monkeypatch.setattr(tnd_fetch, "_git", missing)
    with pytest.raises(ValueError, match="absent from the bounded filtered fetch"):
        tnd_fetch.verify_fetched(tmp_path, BASE, HEAD, [change])


def test_fetched_tree_rejects_large_or_different_diff(monkeypatch, tmp_path):
    change = tnd_fetch.Change("tasks/map_exists.lean", "modified", 3, 1, OID)

    def git(_checkout, *args, **_kwargs):
        if args[0] == "diff":
            return b"TNDLib/Other.lean\0"
        raise AssertionError(args)

    monkeypatch.setattr(tnd_fetch, "_git", git)
    with pytest.raises(ValueError, match="diff differs"):
        tnd_fetch.verify_fetched(tmp_path, BASE, HEAD, [change])

    def large(_checkout, *args, **_kwargs):
        if args[0] == "diff":
            return b"tasks/map_exists.lean\0"
        if args[0] == "ls-tree":
            return f"100644 blob {OID}\ttasks/map_exists.lean\0".encode()
        if args[:2] == ("cat-file", "-t"):
            return b"blob\n"
        if args[:2] == ("cat-file", "-s"):
            return str(tnd_fetch.MAX_SOURCE_BYTES + 1).encode()
        raise AssertionError(args)

    monkeypatch.setattr(tnd_fetch, "_git", large)
    with pytest.raises(ValueError, match="exceeds the 256 KiB"):
        tnd_fetch.verify_fetched(tmp_path, BASE, HEAD, [change])


def test_fetched_tree_enforces_aggregate_candidate_blob_bound(monkeypatch, tmp_path):
    changes = [
        tnd_fetch.Change(f"tasks/Proof{i}.lean", "modified", 1, 0, f"{i + 1:040x}")
        for i in range(5)
    ]
    by_path = {change.path: change for change in changes}

    def git(_checkout, *args, **_kwargs):
        if args[0] == "diff":
            return b"\0".join(path.encode() for path in by_path) + b"\0"
        if args[0] == "ls-tree":
            path = args[-1]
            oid = by_path[path].oid
            return f"100644 blob {oid}\t{path}\0".encode()
        if args[:2] == ("cat-file", "-t"):
            return b"blob\n"
        if args[:2] == ("cat-file", "-s"):
            return str(tnd_fetch.MAX_SOURCE_BYTES).encode()
        raise AssertionError(args)

    monkeypatch.setattr(tnd_fetch, "_git", git)
    with pytest.raises(ValueError, match="1 MiB aggregate"):
        tnd_fetch.verify_fetched(tmp_path, BASE, HEAD, changes)


def test_bounded_command_stops_output_flood():
    with pytest.raises(ValueError, match="output exceeded"):
        tnd_fetch.bounded_command(
            [sys.executable, "-c", "import os\nwhile True: os.write(1, b'x' * 65536)"],
            output_limit=1024,
            timeout=10,
        )


def test_cli_help_starts_in_isolated_python():
    script = Path(tnd_fetch.__file__).resolve()
    result = subprocess.run(
        [sys.executable, "-I", str(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout


def test_local_git_server_filter_includes_limit_and_omits_larger_blob(tmp_path):
    """Exercise blob:limit semantics without reaching any network service."""

    def git(cwd, *args, check=True):
        return subprocess.run(
            ["git", "-C", str(cwd), *args],
            check=check,
            capture_output=True,
            env={
                **os.environ,
                "GIT_AUTHOR_NAME": "Fixture",
                "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                "GIT_COMMITTER_NAME": "Fixture",
                "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
                "GIT_TERMINAL_PROMPT": "0",
            },
        )

    remote, seed = tmp_path / "remote.git", tmp_path / "seed"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    git(remote, "config", "uploadpack.allowFilter", "true")
    git(remote, "config", "uploadpack.allowAnySHA1InWant", "true")
    subprocess.run(["git", "init", "-q", str(seed)], check=True)
    git(seed, "checkout", "-qb", "main")
    source = seed / "tasks/map_exists.lean"
    source.parent.mkdir(parents=True)
    source.write_text("theorem base : True := True.intro\n")
    git(seed, "add", ".")
    git(seed, "commit", "-qm", "base")
    git(seed, "remote", "add", "origin", f"file://{remote}")
    git(seed, "push", "-q", "origin", "main")

    def publish(number, contents):
        git(seed, "checkout", "-q", "main")
        git(seed, "checkout", "-qB", f"proof-{number}")
        source.write_bytes(contents)
        git(seed, "add", str(source.relative_to(seed)))
        git(seed, "commit", "-qm", f"proof {number}")
        head = git(seed, "rev-parse", "HEAD").stdout.decode().strip()
        oid = git(seed, "rev-parse", "HEAD:tasks/map_exists.lean").stdout.decode().strip()
        git(seed, "push", "-q", "--force", "origin", f"HEAD:refs/pull/{number}/head")
        return head, oid

    at_limit = b"/-" + b"x" * (tnd_fetch.MAX_SOURCE_BYTES - 5) + b"-/\n"
    assert len(at_limit) == tnd_fetch.MAX_SOURCE_BYTES
    included_head, included_oid = publish(7, at_limit)
    included = tmp_path / "included"
    subprocess.run(
        ["git", "clone", "-q", "--depth=1", "--no-tags", "--single-branch", "--branch", "main",
         f"file://{remote}", str(included)],
        check=True,
    )
    tnd_fetch.filtered_fetch(included, 7, included_head)
    assert git(included, "cat-file", "-s", included_oid).stdout.strip() == str(
        tnd_fetch.MAX_SOURCE_BYTES
    ).encode()

    omitted_head, omitted_oid = publish(8, at_limit + b"x")
    omitted = tmp_path / "omitted"
    subprocess.run(
        ["git", "clone", "-q", "--depth=1", "--no-tags", "--single-branch", "--branch", "main",
         f"file://{remote}", str(omitted)],
        check=True,
    )
    tnd_fetch.filtered_fetch(omitted, 8, omitted_head)
    absent = subprocess.run(
        ["git", "-C", str(omitted), "cat-file", "-e", f"{omitted_oid}^{{blob}}"],
        env={**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0"},
        capture_output=True,
        check=False,
    )
    assert absent.returncode != 0
