"""Recovery touches only what a valid lease names; no real mounts are made."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parents[2]
for name, relative in (
    ("tnd_resource_boundary", "audit/resource_boundary.py"),
    ("tnd_resource_recovery", "audit/resource_recovery.py"),
):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, ROOT / relative)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
boundary = sys.modules["tnd_resource_boundary"]
recovery = sys.modules["tnd_resource_recovery"]
FLAGS = frozenset({"rw", "nodev", "nosuid", "noexec"})
CONTAINER = "tnd-audit-" + "a" * 32


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.parent = Path(directory.name).resolve()
        self.root = self.parent / "tnd-boundary-abc123"
        self.root.mkdir(mode=0o700)
        (self.root / "build").mkdir()
        (self.root / "export").mkdir()
        self.lease = self.parent / "tnd-boundary-abc123.lease"
        self.mounts = [
            boundary.Mount(11, self.root / "build", "tmpfs", FLAGS),
            boundary.Mount(12, self.root / "export", "tmpfs", FLAGS),
        ]
        self.unmounted = []
        info = self.root.lstat()
        self.write_lease(root_identity=[info.st_dev, info.st_ino])
        self.docker = []
        for target, replacement in (
            ("_mounts", lambda: list(self.mounts)),
            ("_run", self.fake_run),
            ("_process_start", lambda _pid: None),
            ("processes_naming", lambda _root: []),
        ):
            patcher = patch.object(recovery, target, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(recovery.subprocess, "run", self.fake_docker)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_lease(self, **changes):
        current = json.loads(self.lease.read_text()) if self.lease.exists() else {
            "schema_version": 1, "root": str(self.root), "root_identity": [0, 0],
            "owner_pid": 4242, "owner_start": 99, "containers": [],
        }
        current.update(changes)
        self.lease.write_text(json.dumps(current))
        self.lease.chmod(0o600)

    def fake_run(self, argv):
        path = Path(argv[-1])
        self.unmounted.append(path)
        self.mounts = [m for m in self.mounts if m.path != path]

    def fake_docker(self, argv, **_kwargs):
        self.docker.append(argv[:3])
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    def recover(self):
        return recovery.recover(self.lease, self.parent, wait=0)

    def assert_refused_and_retained(self, pattern):
        before = list(self.mounts)
        with self.assertRaisesRegex(recovery.Refused, pattern):
            self.recover()
        self.assertEqual(self.unmounted, [])
        self.assertEqual(self.mounts, before)
        self.assertTrue(self.root.is_dir())

    def test_recovers_exact_mounts_in_reverse_order_and_removes_paths(self):
        self.assertEqual(self.recover(), "recovered")
        self.assertEqual(self.unmounted, [self.root / "export", self.root / "build"])
        self.assertFalse(self.root.exists())
        self.assertFalse(self.lease.exists())

    def test_partial_setup_with_one_mount_recovers(self):
        self.mounts = self.mounts[:1]
        self.assertEqual(self.recover(), "recovered")
        self.assertEqual(self.unmounted, [self.root / "build"])

    def test_named_containers_are_removed_before_any_unmount(self):
        self.write_lease(containers=[CONTAINER])
        order = []
        original = self.fake_docker
        with (
            patch.object(
                recovery, "_run", lambda argv: (order.append("umount"), self.fake_run(argv)),
            ),
            patch.object(recovery.subprocess, "run",
                         lambda argv, **kw: (order.append(argv[1]), original(argv, **kw))[1]),
        ):
            self.recover()
        self.assertEqual(order[:4], ["rm", "container", "rm", "container"])
        self.assertEqual(set(order[4:]), {"umount"})

    def test_attached_client_exits_only_after_its_container_is_removed(self):
        self.write_lease(containers=[CONTAINER])
        removed = []
        original = self.fake_docker

        def docker(argv, **kwargs):
            removed.append(argv[1])
            return original(argv, **kwargs)

        with (
            patch.object(recovery.subprocess, "run", docker),
            patch.object(recovery, "processes_naming",
                         lambda _root: [] if "rm" in removed else [77]),
        ):
            self.assertEqual(self.recover(), "recovered")

    def test_container_appearing_after_helpers_exit_is_caught(self):
        self.write_lease(containers=[CONTAINER])
        listings = iter(["", CONTAINER])

        def docker(argv, **_kwargs):
            out = next(listings) if argv[1] == "container" else ""
            return subprocess.CompletedProcess(argv, 0, stdout=out, stderr="")

        with patch.object(recovery.subprocess, "run", docker):
            self.assert_refused_and_retained("not confirmed absent")

    def test_owner_exiting_within_the_wait_allows_recovery(self):
        answers = iter([99, None])
        with (
            patch.object(recovery, "_process_start", lambda _pid: next(answers)),
            patch.object(recovery.time, "sleep"),
        ):
            self.assertEqual(recovery.recover(self.lease, self.parent, wait=5), "recovered")

    def test_surviving_owner_is_killed_only_when_asked_and_by_exact_pid(self):
        kills = []
        alive = {"value": True}

        def kill(pid, sig):
            kills.append((pid, sig))
            alive["value"] = False

        with (
            patch.object(recovery, "_process_start",
                         lambda _pid: 99 if alive["value"] else None),
            patch.object(recovery.os, "kill", kill),
            patch.object(recovery.time, "sleep"),
        ):
            self.assert_refused_and_retained("still running")
            self.assertEqual(kills, [])
            self.assertEqual(
                recovery.recover(self.lease, self.parent, wait=0, terminate_owner=True),
                "recovered",
            )
        self.assertEqual(kills, [(4242, recovery.signal.SIGKILL)])

    def test_reused_pid_is_never_killed(self):
        with (
            patch.object(recovery, "_process_start", lambda _pid: 100),
            patch.object(recovery.os, "kill", side_effect=AssertionError("must not kill")),
        ):
            self.assertEqual(
                recovery.recover(self.lease, self.parent, wait=0, terminate_owner=True),
                "recovered",
            )

    def test_unkillable_owner_is_refused_and_retained(self):
        with (
            patch.object(recovery, "_process_start", lambda _pid: 99),
            patch.object(recovery.os, "kill"),
            patch.object(recovery.time, "monotonic", side_effect=iter(range(0, 1000, 10))),
            patch.object(recovery.time, "sleep"),
            self.assertRaisesRegex(recovery.Refused, "still running"),
        ):
            recovery.recover(self.lease, self.parent, wait=0, terminate_owner=True)
        self.assertEqual(self.unmounted, [])

    def test_container_not_confirmed_absent_retains_mounts(self):
        self.write_lease(containers=[CONTAINER])
        with patch.object(
            recovery.subprocess, "run",
            lambda argv, **_: subprocess.CompletedProcess(argv, 0, stdout=CONTAINER, stderr=""),
        ):
            self.assert_refused_and_retained("not confirmed absent")

    def test_daemon_failure_is_not_absence(self):
        self.write_lease(containers=[CONTAINER])
        with patch.object(
            recovery.subprocess, "run",
            lambda argv, **_: subprocess.CompletedProcess(argv, 1, stdout="", stderr="down"),
        ):
            self.assert_refused_and_retained("not confirmed absent")

    def test_live_owner_is_never_reconciled(self):
        with patch.object(recovery, "_process_start", lambda _pid: 99):
            self.assert_refused_and_retained("still running")

    def test_reused_pid_is_not_the_owner(self):
        with patch.object(recovery, "_process_start", lambda _pid: 100):
            self.assertEqual(self.recover(), "recovered")

    def test_unknown_owner_start_is_refused(self):
        self.write_lease(owner_start=None)
        self.assert_refused_and_retained("no owner start")

    def test_process_still_naming_root_is_refused(self):
        with patch.object(recovery, "processes_naming", lambda _root: [77]):
            self.assert_refused_and_retained("still name the root")

    def test_helper_exiting_within_the_wait_allows_recovery(self):
        answers = iter([[77], []])
        with (
            patch.object(recovery, "processes_naming", lambda _root: next(answers)),
            patch.object(recovery.time, "sleep"),
        ):
            self.assertEqual(recovery.recover(self.lease, self.parent, wait=5), "recovered")

    def test_unexpected_mount_shapes_are_refused(self):
        build = self.root / "build"
        for label, mount in (
            ("nested", boundary.Mount(13, build / "nested", "tmpfs", FLAGS)),
            ("stacked", boundary.Mount(13, build, "tmpfs", FLAGS)),
            ("foreign", boundary.Mount(13, self.root / "other", "tmpfs", FLAGS)),
            ("root", boundary.Mount(13, self.root, "tmpfs", FLAGS)),
        ):
            with self.subTest(label):
                self.mounts.append(mount)
                self.assert_refused_and_retained("unexpected or nested|stacked")
                self.mounts.pop()

    def test_wrong_filesystem_or_missing_flags_are_refused(self):
        build = self.root / "build"
        for mount in (
            boundary.Mount(11, build, "ext4", FLAGS),
            boundary.Mount(11, build, "tmpfs", frozenset({"rw", "nodev", "nosuid"})),
        ):
            with self.subTest(mount=mount):
                self.mounts[0] = mount
                self.assert_refused_and_retained("expected restricted tmpfs")

    def test_replaced_root_identity_is_refused(self):
        self.write_lease(root_identity=[1, 2])
        self.assert_refused_and_retained("identity differs")

    def test_unexpected_content_stops_removal_without_a_sweep(self):
        (self.root / "build" / "kept").write_text("not ours to delete")
        with self.assertRaises(OSError):
            self.recover()
        self.assertTrue((self.root / "build" / "kept").exists())
        self.assertTrue(self.lease.exists())

    def test_lease_cannot_redirect_recovery_elsewhere(self):
        elsewhere = tempfile.TemporaryDirectory()
        self.addCleanup(elsewhere.cleanup)
        for root in (
            str(Path(elsewhere.name) / "tnd-boundary-abc123"),
            str(self.parent / "tnd-boundary-other"),
            str(self.parent / "unrelated"),
            str(self.root / "build"),
            None,
        ):
            with self.subTest(root=root):
                self.write_lease(root=root)
                self.assert_refused_and_retained("direct child")

    def test_malformed_lease_contents_are_refused(self):
        for change, pattern in (
            ({"schema_version": 2}, "schema"),
            ({"extra": 1}, "schema"),
            ({"containers": ["postgres"]}, "unrecognized container"),
            ({"containers": [f"{CONTAINER}; rm -rf /"]}, "unrecognized container"),
            ({"owner_pid": 0}, "invalid owner"),
            ({"owner_pid": True}, "invalid owner"),
            ({"root_identity": "x"}, "root identity"),
        ):
            original = self.lease.read_text()
            with self.subTest(change=change):
                self.write_lease(**change)
                self.assert_refused_and_retained(pattern)
            self.lease.write_text(original)

    def test_invalid_json_group_writable_and_symlink_leases_are_refused(self):
        original = self.lease.read_text()
        self.lease.write_text("{not json")
        self.assert_refused_and_retained("valid JSON")
        self.lease.write_text(original)
        self.lease.chmod(0o660)
        self.assert_refused_and_retained("private regular")
        self.lease.chmod(0o600)
        target = self.parent / "real"
        self.lease.rename(target)
        self.lease.symlink_to(target)
        self.assert_refused_and_retained("cannot be opened")

    def test_stale_lease_is_removed_only_when_nothing_is_mounted(self):
        (self.root / "build").rmdir()
        (self.root / "export").rmdir()
        self.root.rmdir()
        self.assert_refused_and_retained_missing_root()
        self.mounts = []
        self.assertEqual(self.recover(), "stale-lease-removed")
        self.assertFalse(self.lease.exists())

    def assert_refused_and_retained_missing_root(self):
        with self.assertRaisesRegex(recovery.Refused, "missing root"):
            self.recover()
        self.assertTrue(self.lease.exists())

    def test_cli_reports_refusal_with_nonzero_status_and_no_lease_is_success(self):
        with (
            patch.object(recovery.sys, "platform", "linux"),
            patch.object(recovery.os, "geteuid", return_value=1000),
            patch.object(recovery, "_check_parent_chain"),
            patch.object(recovery, "_process_start", lambda _pid: 99),
            patch("builtins.print") as printed,
        ):
            self.assertEqual(recovery.main(["--parent", str(self.parent), "--wait", "0"]), 1)
            self.assertIn("refused", printed.call_args.args[0])
            self.lease.unlink()
            self.assertEqual(recovery.main(["--parent", str(self.parent)]), 0)


    def test_unsafe_parent_is_a_clean_refusal(self):
        with (
            patch.object(recovery.sys, "platform", "linux"),
            patch.object(recovery.os, "geteuid", return_value=1000),
            patch.object(recovery, "_check_parent_chain", side_effect=ValueError("unsafe")),
            patch("builtins.print") as printed,
        ):
            self.assertEqual(recovery.main(["--parent", str(self.parent)]), 1)
        self.assertIn("recovery refused: unsafe", printed.call_args.args[0])
        self.assertTrue(self.lease.exists())


class LeaseLifecycleTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.parent = Path(directory.name).resolve()
        self.root = self.parent / "tnd-boundary-x"
        self.root.mkdir(mode=0o700)
        info = self.root.lstat()
        self.owner = boundary.ExperimentalBoundary(
            self.parent, boundary.Limits(4096, 16), boundary.Limits(4096, 16)
        )
        self.owner.root = self.root
        self.owner.root_identity = (info.st_dev, info.st_ino)
        self.owner.lease = self.parent / "tnd-boundary-x.lease"

    def test_lease_is_private_atomic_and_names_containers_before_start(self):
        self.owner._write_lease()
        self.assertEqual(self.owner.lease.stat().st_mode & 0o777, 0o600)
        self.owner.record_container(CONTAINER)
        lease = json.loads(self.owner.lease.read_text())
        self.assertEqual(lease["containers"], [CONTAINER])
        self.assertEqual(lease["owner_pid"], os.getpid())
        self.assertEqual(lease["root"], str(self.root))
        self.assertEqual(sorted(p.name for p in self.parent.iterdir()),
                         ["tnd-boundary-x", "tnd-boundary-x.lease"])

    def test_every_quota_workflow_has_an_independent_always_recovery_step(self):
        import yaml  # noqa: PLC0415

        for name in ("verify-tnd", "audit-main", "verify-comparator"):
            with self.subTest(name):
                parsed = yaml.safe_load((ROOT / f".github/workflows/{name}.yml").read_text())
                jobs = parsed["jobs"]
                steps = [
                    step for body in jobs.values() for step in body.get("steps", [])
                    if "--quota-parent" in step.get("run", "")
                    or "audit.resource_recovery" in step.get("run", "")
                ]
                self.assertEqual(len(steps), 2)
                self.assertIn("--quota-parent", steps[0]["run"])
                self.assertIn("audit.resource_recovery", steps[1]["run"])
                self.assertIn("--terminate-owner", steps[1]["run"])
                self.assertEqual(steps[1]["if"], "always()")


if __name__ == "__main__":
    unittest.main()
