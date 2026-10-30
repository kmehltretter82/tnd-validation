"""Host-side protocol tests; no sudo, Docker, or actual mounts are invoked."""
import importlib.util
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

SPEC = importlib.util.spec_from_file_location(
    "tnd_resource_boundary", Path(__file__).parents[2] / "audit/resource_boundary.py"
)
boundary = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = boundary
SPEC.loader.exec_module(boundary)
REAL_RUN = boundary._run


class FakeHost:
    def __init__(self):
        self.mounts = []
        self.operations = []
        self.capacity = 65536
        self.inodes = 64
        self.fail_mount = None
        self.fail_after_mount = None
        self.fail_unmount = False

    def run(self, args):
        self.operations.append(args)
        path = Path(args[-1])
        if args[2] == "/usr/bin/mount":
            if path.name == self.fail_mount:
                raise subprocess.CalledProcessError(1, args)
            self.mounts.append(boundary.Mount(len(self.operations), path, "tmpfs",
                                              frozenset({"rw", "nodev", "nosuid", "noexec"})))
            if path.name == self.fail_after_mount:
                raise subprocess.CalledProcessError(1, args)
        elif args[2] == "/usr/bin/umount":
            if self.fail_unmount:
                raise subprocess.CalledProcessError(1, args)
            self.mounts = [entry for entry in self.mounts if entry.path != path]
        else:
            raise AssertionError(args)

    def statvfs(self, _path):
        return SimpleNamespace(f_frsize=4096, f_blocks=self.capacity // 4096, f_files=self.inodes)


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.parent = Path(self.tmp.name).resolve()
        self.host = FakeHost()
        self.patches = [
            patch.object(boundary.sys, "platform", "linux"),
            patch.object(boundary.os, "geteuid", return_value=os.getuid()),
            patch.object(boundary, "_mounts", side_effect=lambda: list(self.host.mounts)),
            patch.object(boundary, "_run", side_effect=self.host.run),
            patch.object(boundary.os, "statvfs", side_effect=self.host.statvfs),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.tmp.cleanup()

    def new(self):
        return boundary.ExperimentalBoundary(
            self.parent, boundary.Limits(65536, 64), boundary.Limits(65536, 64)
        )

    def test_success_mounts_with_restrictions_and_unmounts_in_reverse(self):
        with self.new() as item:
            root = item.root
            self.assertEqual(item.verify("build"), root / "build")
            self.assertEqual(item.verify("export"), root / "export")
            self.assertEqual(os.stat(root).st_mode & 0o777, 0o700)
        self.assertFalse(root.exists())
        self.assertEqual([Path(args[2]).name for args in self.host.operations],
                         ["mount", "mount", "umount", "umount"])
        self.assertEqual([Path(args[-1]).name for args in self.host.operations],
                         ["build", "export", "export", "build"])
        for args in self.host.operations[:2]:
            options = args[args.index("-o") + 1]
            self.assertIn("size=65536,nr_inodes=64", options)
            for flag in ("nodev", "nosuid", "noexec", "mode=0700"):
                self.assertIn(flag, options)

    def test_failed_mount_quarantines_private_path(self):
        self.host.fail_mount = "export"
        item = self.new()
        with self.assertRaisesRegex(ValueError, "independent recovery"), item:
            self.fail("must not enter")
        self.assertTrue(item.root.is_dir())
        self.assertEqual([m.path.name for m in self.host.mounts], ["build"])
        self.assertFalse(any(args[2] == "/usr/bin/umount" for args in self.host.operations))
        # Fake host only: emulate a supervisor proving the helper stopped.
        item.uncertain_mount = False
        item.close()

    def test_failed_mount_after_attachment_is_quarantined(self):
        self.host.fail_after_mount = "export"
        item = self.new()
        with self.assertRaisesRegex(ValueError, "independent recovery"), item:
            self.fail("must not enter")
        self.assertEqual([m.path.name for m in self.host.mounts], ["build", "export"])
        self.assertTrue(item.root.is_dir())
        self.assertFalse(any(args[2] == "/usr/bin/umount" for args in self.host.operations))
        item.uncertain_mount = False
        item.close()

    def test_exception_in_body_still_unmounts(self):
        with self.assertRaisesRegex(ValueError, "body"), self.new():
            raise ValueError("body")
        self.assertEqual(self.host.mounts, [])

    def test_replaced_or_nested_mount_refuses_cleanup(self):
        item = self.new()
        item.create()
        original = self.host.mounts[0]
        self.host.mounts[0] = boundary.Mount(999, original.path, "tmpfs", original.options)
        with self.assertRaisesRegex(ValueError, "identity"):
            item.verify("build")
        with self.assertRaisesRegex(ValueError, "identity"):
            item.close()
        self.assertFalse(any(args[2] == "/usr/bin/umount" and args[-1] == str(original.path)
                             for args in self.host.operations))
        self.host.mounts[0] = original
        self.host.mounts.append(
            boundary.Mount(1000, original.path / "child", "tmpfs", original.options)
        )
        with self.assertRaisesRegex(ValueError, "identity"):
            item.verify("build")
        self.host.mounts.pop()
        item.close()

    def test_unmount_failure_preserves_owned_root(self):
        item = self.new()
        item.create()
        self.host.fail_unmount = True
        with self.assertRaises(subprocess.CalledProcessError):
            item.close()
        self.assertTrue(item.root.exists())
        self.assertEqual(len(self.host.mounts), 2)
        self.host.fail_unmount = False
        with self.assertRaisesRegex(ValueError, "independent recovery"):
            item.close()
        # Fake host only: emulate a supervisor proving the helper stopped.
        item.uncertain_mount = False
        item.close()

    def test_oversized_or_unbounded_quota_is_rejected(self):
        item = self.new()
        item.create()
        self.host.capacity = 65536 * 2
        with self.assertRaisesRegex(ValueError, "quota capacity"):
            item.verify("build")
        self.host.capacity = 65536
        self.host.inodes = 0
        with self.assertRaisesRegex(ValueError, "quota capacity"):
            item.verify("build")
        self.host.inodes = 65
        with self.assertRaisesRegex(ValueError, "quota capacity"):
            item.verify("build")
        self.host.inodes = 64
        self.host.capacity = 0
        with self.assertRaisesRegex(ValueError, "quota capacity"):
            item.verify("build")
        self.host.capacity = 65536
        item.close()

    def test_missing_flags_or_root_permissions_are_rejected(self):
        item = self.new()
        item.create()
        original = self.host.mounts[0]
        self.host.mounts[0] = boundary.Mount(original.mount_id, original.path, "tmpfs",
                                             frozenset({"rw", "nodev", "nosuid"}))
        with self.assertRaisesRegex(ValueError, "flags"):
            item.verify("build")
        self.host.mounts[0] = original
        item.root.chmod(0o755)
        with self.assertRaisesRegex(ValueError, "permissions"):
            item.verify("build")
        item.root.chmod(0o700)
        item.close()

    def test_mutable_quota_root_permissions_do_not_prevent_safe_teardown(self):
        item = self.new()
        item.create()
        root = item.root
        (root / "export").chmod(0o000)
        with self.assertRaisesRegex(ValueError, "permissions"):
            item.verify("export")
        item.close()
        self.assertFalse(root.exists())
        self.assertEqual(self.host.mounts, [])

    def test_mac_or_root_never_mounts(self):
        item = self.new()
        with (patch.object(boundary.sys, "platform", "darwin"),
              self.assertRaisesRegex(ValueError, "Linux")):
            item.create()
        with (patch.object(boundary.os, "geteuid", return_value=0),
              self.assertRaisesRegex(ValueError, "unprivileged")):
            item.create()
        with (patch.object(boundary.os, "geteuid", return_value=os.getuid() + 1),
              self.assertRaisesRegex(ValueError, "unprivileged")):
            item.create()
        with (patch.object(boundary.os, "getegid", return_value=os.getgid() + 1),
              self.assertRaisesRegex(ValueError, "unprivileged")):
            item.create()
        self.assertEqual(self.host.operations, [])

    def test_writable_parent_or_ancestor_is_rejected_before_mount(self):
        item = self.new()
        self.parent.chmod(0o777)
        try:
            with self.assertRaisesRegex(ValueError, "ancestor"):
                item.create()
            self.assertIsNone(item.root)
            self.assertEqual(self.host.operations, [])
        finally:
            self.parent.chmod(0o700)

        child = self.parent / "child"
        child.mkdir(mode=0o700)
        self.parent.chmod(0o777)
        try:
            item = boundary.ExperimentalBoundary(
                child, boundary.Limits(65536, 64), boundary.Limits(65536, 64)
            )
            with self.assertRaisesRegex(ValueError, "ancestor"):
                item.create()
            self.assertIsNone(item.root)
            self.assertEqual(self.host.operations, [])
        finally:
            self.parent.chmod(0o700)

    def test_parent_permissions_changed_after_creation_prevent_unmount(self):
        item = self.new()
        item.create()
        self.parent.chmod(0o777)
        try:
            with self.assertRaisesRegex(ValueError, "ancestor"):
                item.close()
            self.assertFalse(any(args[2] == "/usr/bin/umount" for args in self.host.operations))
        finally:
            self.parent.chmod(0o700)
        item.close()

    def test_mountinfo_escapes_and_malformed_records(self):
        info = "29 23 0:25 / /tmp/a\\040b rw,nosuid,nodev,noexec - tmpfs tmpfs rw,size=64k\n"
        mount, = boundary.parse_mountinfo(info)
        self.assertEqual(mount.path, Path("/tmp/a b"))
        self.assertIn("noexec", mount.options)
        with self.assertRaises(ValueError):
            boundary.parse_mountinfo("bad record")
        with self.assertRaises(ValueError):
            boundary.parse_mountinfo(info.replace("\\040", "\\777"))

    def test_privileged_helper_timeout_kills_its_process_group(self):
        process = Mock(pid=123)
        process.communicate.side_effect = [subprocess.TimeoutExpired("mount", 30), (None, b"")]
        with (patch.object(boundary.subprocess, "Popen", return_value=process) as launch,
              patch.object(boundary.os, "killpg") as kill,
              self.assertRaises(subprocess.TimeoutExpired)):
            REAL_RUN(["/usr/bin/sudo", "-n", "/usr/bin/mount"])
        self.assertTrue(launch.call_args.kwargs["start_new_session"])
        kill.assert_called_once_with(123, signal.SIGKILL)
        self.assertEqual(process.communicate.call_count, 2)

    def test_helper_descendant_retaining_pipe_does_not_hang_timeout(self):
        process = Mock(pid=123)
        process.communicate.side_effect = [subprocess.TimeoutExpired("mount", 30),
                                           subprocess.TimeoutExpired("mount", 2)]
        with (patch.object(boundary.subprocess, "Popen", return_value=process),
              patch.object(boundary.os, "killpg"),
              self.assertRaises(subprocess.TimeoutExpired) as error):
            REAL_RUN(["/usr/bin/sudo", "-n", "/usr/bin/mount"])
        self.assertEqual(error.exception.timeout, 30)
        process.stderr.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
