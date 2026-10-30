"""Development orchestration tests; no Docker, sudo, or real mounts."""
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from audit.resource_boundary import Limits


def comparator_arguments(workspace, build, tools, lean, comparator):
    """Stub only the comparator argument factory; its real flags have separate tests."""
    return ["docker", "run", "--mount", f"type=bind,src={build},dst=/work/.lake"]


# The real Docker argument factory is covered by the comparator integration tests.
SPEC = importlib.util.spec_from_file_location(
    "tnd_resource_stages_test", Path(__file__).parents[2] / "audit/resource_stages.py"
)
stages = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stages)


class ResourceStageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp_path = Path(temporary.name)
        self.events = []
        comparator_patch = patch.object(stages, "_comparator_arguments", comparator_arguments)
        comparator_patch.start()
        self.addCleanup(comparator_patch.stop)
        tmp_path, events = self.tmp_path, self.events

        class FakeBoundary:
            def record_container(self, _name):
                pass

            def __init__(self, *_args):
                self.paths = {name: tmp_path / name for name in ("build", "export")}
                for path in self.paths.values():
                    path.mkdir()

            def __enter__(self):
                events.append("mount")
                return self

            def verify(self, name):
                events.append("verify-" + name)
                return self.paths[name]

            def close(self):
                events.append("unmount")

        with patch.object(stages, "ExperimentalBoundary", FakeBoundary):
            self.item = stages.DevelopmentQuotaStages(
                tmp_path, Limits(65536, 64), Limits(65536, 64)
            )

    def test_build_export_verifies_and_reaps_before_unmount(self):
        quota, tmp_path = (self.item, self.events), self.tmp_path
        item, events = quota
        invocations = []

        def command(args):
            events.append("run")
            invocations.append(args)
            if "/opt/tnd-export" in args[-1]:
                (tmp_path / "export/export.ndjson").write_bytes(b"{}\n")
            return subprocess.CompletedProcess(args, 0, b"", b"")

        def reap(name):
            events.append("reap")
            self.assertEqual(name, invocations[-1][invocations[-1].index("--name") + 1])

        with (patch.object(stages.run, "require_default_seccomp"),
              patch.object(stages.run, "command", side_effect=command),
              patch.object(stages.run, "ensure_container_removed", side_effect=reap), item):
            self.assertEqual(item.build_export(stages.run.IMAGE, tmp_path, tmp_path, tmp_path),
                             b"{}\n")
        self.assertEqual([event for event in events if event in {"run", "reap", "unmount"}],
                         ["run", "reap", "run", "reap", "unmount"])
        for index, event in enumerate(events):
            if event == "run":
                self.assertEqual(events[index - 2:index], ["verify-build", "verify-export"])
        build, export = invocations
        self.assertTrue(any(f"src={tmp_path}/build,dst=/work/.lake" in x for x in build))
        self.assertTrue(any(f"src={tmp_path}/build,dst=/work/.lake,readonly" in x for x in export))
        self.assertTrue(any(f"src={tmp_path}/export,dst=/output" in x for x in export))


    def test_cleanup_failure_retains_mounts(self):
        quota, tmp_path = (self.item, self.events), self.tmp_path
        item, events = quota
        with (patch.object(stages.run, "require_default_seccomp"),
              patch.object(stages.run, "command"),
              patch.object(stages.run, "ensure_container_removed",
                           side_effect=ValueError("daemon")),
              self.assertRaisesRegex(ValueError, "mounts retained"), item):
            item.build_export(stages.run.IMAGE, tmp_path, tmp_path, tmp_path)
        self.assertTrue(item.container_uncertain)
        self.assertNotIn("unmount", events)


    def test_build_failure_reaps_before_unmount_and_never_exports(self):
        quota, tmp_path = (self.item, self.events), self.tmp_path
        item, events = quota
        with (patch.object(stages.run, "require_default_seccomp"),
              patch.object(stages.run, "command", side_effect=ValueError("build failed")) as run,
              patch.object(stages.run, "ensure_container_removed",
                           side_effect=lambda _: events.append("reap")),
              self.assertRaisesRegex(ValueError, "build failed"), item):
            item.build_export(stages.run.IMAGE, tmp_path, tmp_path, tmp_path)
        run.assert_called_once()
        self.assertEqual(events[-2:], ["reap", "unmount"])


    def test_comparator_uses_quota_and_retains_failure_diagnostics(self):
        quota, tmp_path = (self.item, self.events), self.tmp_path
        item, events = quota
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        calls = []

        def command(args):
            calls.append(args)
            raise subprocess.CalledProcessError(2, args, b"failed", b"diagnostic")

        with (patch.object(stages.run, "require_default_seccomp"),
              patch.object(stages.run, "command", side_effect=command),
              patch.object(stages.run, "ensure_container_removed",
                           side_effect=lambda _: events.append("reap")), item):
            result = item.comparator(workspace, tmp_path, tmp_path, tmp_path)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, b"failed")
            with self.assertRaisesRegex(ValueError, "unused"):
                item.comparator(workspace, tmp_path, tmp_path, tmp_path)
        self.assertEqual(
            [event for event in events if event in {"reap", "unmount"}],
            ["reap", "unmount"],
        )
        self.assertEqual(events[-3:], ["verify-build", "verify-export", "unmount"])
        self.assertTrue(any(f"src={tmp_path}/build,dst=/work/.lake" in x for x in calls[0]))


    def test_comparator_post_exit_mount_change_blocks_diagnostics(self):
        quota, tmp_path = (self.item, self.events), self.tmp_path
        item, events = quota
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        verify = item.boundary.verify
        checks = 0

        def reject_after_exit(name):
            nonlocal checks
            checks += 1
            if checks == 4:
                raise ValueError("mount changed after comparator exit")
            return verify(name)

        with (patch.object(stages.run, "require_default_seccomp"),
              patch.object(stages.run, "command",
                           return_value=subprocess.CompletedProcess([], 0, b"match", b"")) as run,
              patch.object(stages.run, "ensure_container_removed",
                           side_effect=lambda _: events.append("reap")),
              patch.object(item.boundary, "verify", side_effect=reject_after_exit),
              self.assertRaisesRegex(ValueError, "mount changed after"), item):
            item.comparator(workspace, tmp_path, tmp_path, tmp_path)
        run.assert_called_once()
        self.assertEqual(
            [event for event in events if event in {"reap", "unmount"}],
            ["reap", "unmount"],
        )


    def test_verification_failure_never_launches(self):
        quota, tmp_path = (self.item, self.events), self.tmp_path
        item, events = quota
        with (patch.object(stages.run, "require_default_seccomp"),
              patch.object(stages.run, "command") as command,
              patch.object(item.boundary, "verify", side_effect=ValueError("mount changed")),
              self.assertRaisesRegex(ValueError, "mount changed"), item):
            item.build_export(stages.run.IMAGE, tmp_path, tmp_path, tmp_path)
        command.assert_not_called()
        self.assertEqual(events[-1], "unmount")


    def test_changed_mount_between_build_and_export_blocks_export(self):
        quota, tmp_path = (self.item, self.events), self.tmp_path
        item, events = quota
        verify = item.boundary.verify
        checks = 0

        def reject_later(name):
            nonlocal checks
            checks += 1
            if checks == 5:
                raise ValueError("mount changed")
            return verify(name)

        with (patch.object(stages.run, "require_default_seccomp"),
              patch.object(stages.run, "command") as command,
              patch.object(stages.run, "ensure_container_removed",
                           side_effect=lambda _: events.append("reap")),
              patch.object(item.boundary, "verify", side_effect=reject_later),
              self.assertRaisesRegex(ValueError, "mount changed"), item):
            item.build_export(stages.run.IMAGE, tmp_path, tmp_path, tmp_path)
        command.assert_called_once()
        self.assertEqual(events[-2:], ["reap", "unmount"])


    def test_symlink_export_is_rejected(self):
        quota, tmp_path = (self.item, self.events), self.tmp_path
        item, _ = quota

        def command(args):
            if "/opt/tnd-export" in args[-1]:
                (tmp_path / "export/export.ndjson").symlink_to(Path("/etc/passwd"))
            return subprocess.CompletedProcess(args, 0, b"", b"")

        with (patch.object(stages.run, "require_default_seccomp"),
              patch.object(stages.run, "command", side_effect=command),
              patch.object(stages.run, "ensure_container_removed"),
              self.assertRaises(OSError), item):
            item.build_export(stages.run.IMAGE, tmp_path, tmp_path, tmp_path)


if __name__ == "__main__":
    unittest.main()
