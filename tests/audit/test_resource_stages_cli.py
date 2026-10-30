"""Exercise only the development CLI's wiring; no Docker or privileged mounts."""
import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from audit import resource_stages as stages


class DevelopmentCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.exporter = self.root / "exporter"
        self.exporter.write_text("exporter")
        self.output = self.root / "result.ndjson"
        self.common = [
            "--scratch-parent", str(self.root), "--build-bytes", "65536", "--build-inodes", "64",
            "--export-bytes", "65536", "--export-inodes", "64",
        ]
        self.build_args = [
            *self.common, "build-export", "--source", str(self.root), "--lean", str(self.root),
            "--exporter", str(self.exporter), "--output", str(self.output),
        ]

    def test_build_artifact_written_only_after_successful_close(self):
        events = []
        testcase = self

        class FakeQuota:
            def __init__(self, parent, build, export):
                testcase.assertEqual(parent, testcase.root)
                testcase.assertEqual((build.bytes, export.inodes), (65536, 64))

            def __enter__(self):
                return self

            def build_export(self, image, source, lean, exporter):
                testcase.assertEqual(image, stages.run.IMAGE)
                testcase.assertEqual((source, lean, exporter),
                                     (testcase.root, testcase.root, testcase.exporter))
                events.append("build")
                return b"{}\n"

            def __exit__(self, *_args):
                testcase.assertFalse(testcase.output.exists())
                events.append("closed")

        with (patch.object(stages, "DevelopmentQuotaStages", FakeQuota),
              redirect_stderr(io.StringIO())):
            self.assertEqual(stages.main(self.build_args), 0)
        self.assertEqual(events, ["build", "closed"])
        self.assertEqual(self.output.read_bytes(), b"{}\n")
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)

    def test_cleanup_failure_does_not_write_output(self):
        class FakeQuota:
            def __init__(self, *_args):
                pass

            def __enter__(self):
                return self

            def build_export(self, *_args):
                return b"{}\n"

            def __exit__(self, *_args):
                raise ValueError("cleanup failed")

        with (patch.object(stages, "DevelopmentQuotaStages", FakeQuota),
              redirect_stderr(io.StringIO()), self.assertRaisesRegex(ValueError, "cleanup failed")):
            stages.main(self.build_args)
        self.assertFalse(self.output.exists())

    def test_invalid_limits_or_existing_output_reject_before_mount(self):
        bad = list(self.build_args)
        bad[bad.index("--build-bytes") + 1] = "0"
        with (patch.object(stages, "DevelopmentQuotaStages") as quota,
              self.assertRaisesRegex(ValueError, "limits")):
            stages.main(bad)
        quota.assert_not_called()
        self.output.write_bytes(b"existing")
        with (patch.object(stages, "DevelopmentQuotaStages") as quota,
              self.assertRaisesRegex(ValueError, "new file")):
            stages.main(self.build_args)
        quota.assert_not_called()
        self.assertEqual(self.output.read_bytes(), b"existing")

    def test_comparator_reports_failure_after_cleanup(self):
        events = []
        root = self.root

        class FakeQuota:
            def __init__(self, *_args):
                pass

            def __enter__(self):
                return self

            def comparator(self, workspace, tools, lean, comparator):
                self_args = (workspace, tools, lean, comparator)
                if self_args != (root, root, root, root):
                    raise AssertionError(self_args)
                events.append("comparator")
                return subprocess.CompletedProcess([], 2, b"failure", b"diagnostic")

            def __exit__(self, *_args):
                events.append("closed")

        class Stream:
            def __init__(self):
                self.buffer = io.BytesIO()

            def write(self, _text):
                pass

        stdout, stderr = Stream(), Stream()
        args = [*self.common, "comparator", "--workspace", str(root), "--tools", str(root),
                "--lean", str(root), "--comparator", str(root)]
        with (patch.object(stages, "DevelopmentQuotaStages", FakeQuota),
              patch.object(stages.sys, "stdout", stdout),
              patch.object(stages.sys, "stderr", stderr)):
            self.assertEqual(stages.main(args), 1)
        self.assertEqual(events, ["comparator", "closed"])
        self.assertEqual(stdout.buffer.getvalue(), b"failure")
        self.assertEqual(stderr.buffer.getvalue(), b"diagnostic")
