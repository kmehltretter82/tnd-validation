"""Exercise subprocess limits and Docker cleanup without starting a daemon."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from audit import resource_stages
from audit import run as audit_runner
from audit.resource_boundary import Limits
from gate.verify import comparator, tnd_comparator


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(tnd_comparator, "require_default_seccomp", lambda: None)
    paths = tuple(tmp_path / name for name in ("workspace", "build", "tools", "lean", "checker"))
    for path in paths:
        path.mkdir()
    calls = tmp_path / "docker-calls.jsonl"
    binary = tmp_path / "docker"
    binary.write_text(f"#!{sys.executable}\n" + '''
import json
import os
import sys
import time

with open(os.environ["TND_TEST_CALLS"], "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
    # The timeout fixture is killed with SIGKILL while it is sleeping. Flush
    # the launch record first so the test observes the command that actually
    # started instead of depending on interpreter buffering behavior.
    log.flush()
if sys.argv[1] == "rm":
    sys.exit(0)
if sys.argv[1:3] == ["container", "ls"]:
    sys.exit(0)
mode = os.environ["TND_TEST_MODE"]
if mode == "flood":
    os.write(1, b"x" * 1100000)
    os.write(2, b"y" * 1100000)
elif mode == "timeout":
    time.sleep(30)
elif mode == "nonzero":
    os.write(1, b"comparison failed")
    os.write(2, b"diagnostic")
    sys.exit(2)
else:
    os.write(1, b"complete\\xff")
    os.write(2, b"diagnostic")
''')
    binary.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("TND_TEST_CALLS", str(calls))
    monkeypatch.setenv("TND_TEST_MODE", "success")
    return paths, calls


def test_unconfined_daemon_prevents_comparator_start(sandbox, monkeypatch):
    paths, calls = sandbox

    def reject():
        raise ValueError("seccomp")

    monkeypatch.setattr(tnd_comparator, "require_default_seccomp", reject)
    with pytest.raises(ValueError, match="seccomp"):
        tnd_comparator.run_container(*paths)
    assert not calls.exists()


def test_unbounded_helper_refuses_any_enabled_boundary(tmp_path, monkeypatch):
    (tmp_path / ".choir").mkdir()
    policy = {
        "schema_version": 1,
        "source_binding_validated": False,
        "resource_boundary_validated": True,
        "resource_limits": None,
    }
    (tmp_path / ".choir/certification.json").write_text(json.dumps(policy))
    monkeypatch.setattr(tnd_comparator, "PROJECT", tmp_path)
    with pytest.raises(ValueError, match="development-only"):
        tnd_comparator.require_development_helper_policy()


def test_container_resource_options(sandbox):
    paths, _ = sandbox
    args = tnd_comparator.docker_arguments(*paths)
    assert "--pull=never" in args
    for option, value in (("--memory", "3g"), ("--memory-swap", "3g"),
                          ("--shm-size", "64m"), ("--log-driver", "none")):
        assert args[args.index(option) + 1] == value
    assert not any("seccomp=" in arg or arg == "--privileged" for arg in args)


def test_quota_prototype_uses_real_comparator_arguments(sandbox, monkeypatch):
    paths, _ = sandbox
    workspace, build, tools, lean, checker = paths
    events = []

    class FakeBoundary:
        def record_container(self, _name):
            pass

        def __init__(self, *_args):
            pass

        def __enter__(self):
            return self

        def verify(self, name):
            events.append("verify-" + name)
            return build

        def close(self):
            events.append("unmount")

    def command(args):
        events.append("run")
        expected = tnd_comparator.docker_arguments(workspace, build, tools, lean, checker)
        name_index = args.index("--name")
        assert name_index == 2
        assert args[:name_index] + args[name_index + 2:] == expected
        return subprocess.CompletedProcess(args, 0, b"ok", b"")

    monkeypatch.setattr(resource_stages, "ExperimentalBoundary", FakeBoundary)
    monkeypatch.setattr(audit_runner, "require_default_seccomp", lambda: None)
    monkeypatch.setattr(audit_runner, "command", command)
    monkeypatch.setattr(audit_runner, "ensure_container_removed", lambda _: events.append("reap"))
    with resource_stages.DevelopmentQuotaStages(
        workspace, Limits(65536, 64), Limits(65536, 64)
    ) as item:
        assert item.comparator(workspace, tools, lean, checker).stdout == b"ok"
    assert [event for event in events if event in {"run", "reap", "unmount"}] == [
        "run", "reap", "unmount",
    ]
    assert events[-3:] == ["verify-build", "verify-export", "unmount"]


def test_production_comparator_checks_disabled_policy_before_target_lookup(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(tnd_comparator.os, "getuid", lambda: 1000)
    monkeypatch.setattr(
        tnd_comparator,
        "_resolve_pr_target",
        lambda *_args: calls.append("target"),
    )
    args = SimpleNamespace(quota_parent=tmp_path.resolve(), repo="owner/repo", pr=1)
    with pytest.raises(ValueError, match="production certification is disabled"):
        tnd_comparator.verify(args)
    assert calls == []


def test_production_comparator_requires_absolute_quota_parent_before_target_lookup(
    monkeypatch,
):
    calls = []
    limits = Limits(65536, 64)
    monkeypatch.setattr(tnd_comparator.os, "getuid", lambda: 1000)
    monkeypatch.setattr(
        tnd_comparator, "certified_resource_limits", lambda _policy: (limits, limits)
    )
    monkeypatch.setattr(
        tnd_comparator,
        "_resolve_pr_target",
        lambda *_args: calls.append("target"),
    )
    args = SimpleNamespace(quota_parent=Path("relative"), repo="owner/repo", pr=1)
    with pytest.raises(ValueError, match="absolute --quota-parent"):
        tnd_comparator.verify(args)
    assert calls == []


@pytest.mark.parametrize("reason", [
    "accepted source blob is absent from the bounded filtered fetch",
    "accepted source blob exceeds the 256 KiB fetch policy",
    "fetched Git diff differs from trusted changed-file metadata",
    "accepted source blobs exceed the 1 MiB aggregate fetch policy",
])
def test_comparator_refuses_unverified_candidate_blobs_before_materializing(
    tmp_path, monkeypatch, reason,
):
    base, head = "a" * 40, "b" * 40
    limits = Limits(65536, 64)
    materialize = []
    metadata_calls = []
    monkeypatch.setattr(tnd_comparator.os, "getuid", lambda: 1000)
    monkeypatch.setattr(
        tnd_comparator, "certified_resource_limits", lambda _policy: (limits, limits)
    )
    monkeypatch.setattr(
        tnd_comparator,
        "_resolve_pr_target",
        lambda *_args: (base, head, "tasks/map_exists.lean", "TNDTask.mapExists", ""),
    )
    monkeypatch.setattr(
        tnd_comparator,
        "trusted_metadata",
        lambda *args: metadata_calls.append(args) or ["bounded-change"],
    )
    monkeypatch.setattr(
        tnd_comparator,
        "verify_fetched",
        lambda *_args: (_ for _ in ()).throw(ValueError(reason)),
    )
    monkeypatch.setattr(
        tnd_comparator,
        "materialize_workspace",
        lambda *_args: materialize.append(True),
    )
    monkeypatch.setattr(
        tnd_comparator,
        "pinned_lean_root",
        lambda: (_ for _ in ()).throw(AssertionError("Lean resolved before fetch assertion")),
    )
    args = SimpleNamespace(
        quota_parent=tmp_path.resolve(), repo="owner/tndlib", pr=7,
        base=base, head=head,
    )
    with pytest.raises(ValueError, match=reason):
        tnd_comparator.verify(args)
    assert metadata_calls == [("owner/tndlib", 7, base, head)]
    assert materialize == []


def _exercise_production_quota(tmp_path, monkeypatch, *, cleanup_fails: bool):
    base, head = "a" * 40, "b" * 40
    lean = tmp_path / "lean"
    comparator = tmp_path / "comparator"
    landrun = tmp_path / "landrun"
    quota_parent = tmp_path / "quota"
    for path in (lean, comparator, quota_parent):
        path.mkdir()
    landrun.write_text("trusted launcher")
    limits = Limits(65536, 64)
    events = []

    class FakeQuota:
        def __init__(self, parent, build, export):
            assert (parent, build, export) == (quota_parent, limits, limits)
            events.append("quota-created")

        def __enter__(self):
            events.append("quota-entered")
            return self

        def comparator(self, workspace, tools, lean_root, checker, *, arguments):
            assert workspace.name == "workspace"
            assert tools.name == "tools"
            assert (lean_root, checker) == (lean, comparator)
            assert arguments is tnd_comparator.docker_arguments
            assert not (workspace.parent / "build").exists()
            events.append("container-finished")
            return subprocess.CompletedProcess([], 0, b"match", b"diagnostic")

        def __exit__(self, *_args):
            events.append("quota-unmounted")
            if cleanup_fails:
                raise ValueError("quota cleanup failed")

    def classify(returncode, output):
        assert returncode == 0 and "match" in output
        assert events[-1] == "quota-unmounted"
        events.append("classified")
        return tnd_comparator.Outcome.MATCH, "ok", output

    def materialize(_base, _head, _source, _decl, _axioms, workspace):
        (workspace / "lake-manifest.json").write_text('{"packages": []}')

    monkeypatch.setattr(tnd_comparator.os, "getuid", lambda: 1000)
    monkeypatch.setattr(
        tnd_comparator, "certified_resource_limits", lambda _policy: (limits, limits)
    )
    monkeypatch.setattr(
        tnd_comparator,
        "_resolve_pr_target",
        lambda *_args: (base, head, "tasks/map_exists.lean", "TNDTask.mapExists", ""),
    )
    monkeypatch.setattr(tnd_comparator, "inspect_tree", lambda *_args: None)
    monkeypatch.setattr(tnd_comparator, "trusted_metadata", lambda *_args: ["bounded-change"])
    monkeypatch.setattr(tnd_comparator, "verify_fetched", lambda *_args: 64)
    monkeypatch.setattr(tnd_comparator, "_applicability_reason", lambda *_args: None)
    monkeypatch.setattr(tnd_comparator, "pinned_lean_root", lambda: lean)
    monkeypatch.setattr(tnd_comparator, "materialize_workspace", materialize)
    monkeypatch.setattr(tnd_comparator, "QuotaStages", FakeQuota)
    monkeypatch.setattr(tnd_comparator, "classify_output", classify)
    monkeypatch.setattr(
        tnd_comparator,
        "run_container",
        lambda *_args: (_ for _ in ()).throw(AssertionError("unbounded helper used")),
    )
    monkeypatch.setattr(
        tnd_comparator, "command", lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0)
    )
    args = SimpleNamespace(
        repo="owner/repo",
        pr=7,
        base=base,
        head=head,
        comparator=comparator,
        landrun=landrun,
        quota_parent=quota_parent,
    )
    if cleanup_fails:
        with pytest.raises(ValueError, match="quota cleanup failed"):
            tnd_comparator.verify(args)
        assert "classified" not in events
    else:
        tnd_comparator.verify(args)
        assert events[-2:] == ["quota-unmounted", "classified"]


def test_production_comparator_classifies_only_after_quota_unmount(tmp_path, monkeypatch):
    _exercise_production_quota(tmp_path, monkeypatch, cleanup_fails=False)


def test_production_comparator_cleanup_failure_prevents_classification(tmp_path, monkeypatch):
    _exercise_production_quota(tmp_path, monkeypatch, cleanup_fails=True)


def assert_removed_same_container(calls):
    launch, cleanup, listing = [json.loads(line) for line in calls.read_text().splitlines()]
    name = launch[launch.index("--name") + 1]
    assert name.startswith("tnd-comparator-")
    assert cleanup == ["rm", "-f", name]
    assert listing == [
        "container", "ls", "-a", "--filter", f"name=^/{name}$", "--format", "{{.Names}}",
    ]
    return name


def test_normal_exit_keeps_bounded_binary_output_and_removes_container(sandbox):
    paths, calls = sandbox
    result = tnd_comparator.run_container(*paths)
    assert result.returncode == 0
    assert result.stdout == b"complete\xff"
    assert result.stderr == b"diagnostic"
    assert (paths[0] / ".lake").is_dir()
    assert_removed_same_container(calls)


def test_failure_keeps_diagnostics_for_classification_and_removes_container(sandbox, monkeypatch):
    paths, calls = sandbox
    monkeypatch.setenv("TND_TEST_MODE", "nonzero")
    result = tnd_comparator.run_container(*paths)
    assert result.returncode == 2
    assert result.stdout == b"comparison failed"
    assert result.stderr == b"diagnostic"
    assert_removed_same_container(calls)


def test_combined_output_flood_fails_closed_and_removes_container(sandbox, monkeypatch):
    paths, calls = sandbox
    monkeypatch.setenv("TND_TEST_MODE", "flood")
    # Neither stream alone exceeds the cap; the combined output must be bounded.
    with pytest.raises(ValueError, match="output exceeded 2 MiB"):
        tnd_comparator.run_container(*paths)
    assert_removed_same_container(calls)


def test_deadline_kills_client_then_removes_container(sandbox, monkeypatch):
    paths, calls = sandbox
    monkeypatch.setenv("TND_TEST_MODE", "timeout")

    def maintained_clock():
        # Let the fake client actually start before advancing the runner's
        # deadline. Fixed tick counts race process scheduling in a full suite.
        if not calls.exists() or not calls.read_text():
            return 0
        return 901

    # Advance only the maintained runner's clock, not subprocess/pytest clocks.
    monkeypatch.setattr(audit_runner, "time", SimpleNamespace(monotonic=maintained_clock))
    processes = []
    popen = subprocess.Popen

    def record_process(*args, **kwargs):
        process = popen(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", record_process)
    with pytest.raises(subprocess.TimeoutExpired) as failure:
        tnd_comparator.run_container(*paths)
    assert failure.value.timeout == 900
    assert processes[0].returncode is not None
    assert processes[0].returncode < 0
    assert_removed_same_container(calls)


def test_start_failure_still_attempts_container_cleanup(sandbox, monkeypatch):
    paths, calls = sandbox

    def fail(_args):
        raise OSError("Docker client start failed")

    monkeypatch.setattr(tnd_comparator, "command", fail)
    with pytest.raises(OSError, match="Docker client start failed"):
        tnd_comparator.run_container(*paths)
    cleanup, listing = [json.loads(line) for line in calls.read_text().splitlines()]
    assert cleanup[:2] == ["rm", "-f"]
    assert cleanup[2].startswith("tnd-comparator-")
    assert listing[:2] == ["container", "ls"]


def test_cleanup_timeout_cannot_be_reported_as_success(sandbox, monkeypatch):
    paths, _calls = sandbox

    def fail(args, **kwargs):
        assert args[:3] == ["docker", "rm", "-f"]
        assert kwargs["stdout"] == subprocess.DEVNULL
        assert kwargs["stderr"] == subprocess.DEVNULL
        assert kwargs["timeout"] == 30
        raise subprocess.TimeoutExpired(args, 30)

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(subprocess.TimeoutExpired) as failure:
        tnd_comparator.run_container(*paths)
    assert failure.value.timeout == 30


def test_repeated_runs_have_distinct_cleanup_names(sandbox):
    paths, calls = sandbox
    tnd_comparator.run_container(*paths)
    first = assert_removed_same_container(calls)
    calls.unlink()
    tnd_comparator.run_container(*paths)
    assert assert_removed_same_container(calls) != first


def test_task_outside_the_published_library_gets_a_workspace_library():
    base = 'name = "tndlib"\n\n[[lean_lib]]\nname = "TNDLib"\n'
    libs = comparator.lean_lib_names(comparator.workspace_lakefile(base, "tasks.map_exists"))
    assert libs == ["TNDLib", "Challenge", "Solution", "ChoirBase", "tasks"]
    published = comparator.lean_lib_names(comparator.workspace_lakefile(base, "TNDLib.Logic"))
    assert published.count("TNDLib") == 1
    assert "tasks" not in comparator.lean_lib_names(comparator.workspace_lakefile(base))
    assert "tasks" not in comparator.lean_lib_names(base)
    for reserved in ("Solution.x", "Challenge", "ChoirBase.tasks.map_exists"):
        with pytest.raises(comparator.ComparatorConfigError):
            comparator.workspace_lakefile(base, reserved)
