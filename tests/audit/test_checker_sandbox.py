"""Development checker isolation contract; no daemon or Lean install required."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from audit import checker_sandbox as isolated
from audit import run as driver

GOOD = json.dumps(
    {
        "schema_version": 1,
        "status": "verified-proof-objects",
        "toolchain": "4.35.0",
        "comparator_revision": driver.COMPARATOR_REV,
        "declarations": [{"name": "TNDLib.test"}],
    }
)


class CheckerSandboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.files = [self.root / name for name in ("config", "challenge", "solution", "checker")]
        for path in self.files:
            path.write_text("fixture")
        self.lean = self.root / "lean"
        self.lean.mkdir()
        self.name = "tnd-checker-" + "a" * 32
        self.docker = patch.object(isolated.shutil, "which", return_value="/usr/bin/docker")
        self.docker.start()
        self.addCleanup(self.docker.stop)

    def args(self):
        return isolated.docker_arguments(driver.IMAGE, *self.files, self.lean, self.name)

    def run_checker(self):
        return isolated.run_isolated_checker(
            driver.IMAGE,
            *self.files,
            self.lean,
            check_seccomp=driver.require_default_seccomp,
            cleanup=driver.ensure_container_removed,
        )

    def test_no_writable_host_mounts_and_resource_controls(self):
        args = self.args()
        mounts = [args[i + 1] for i, arg in enumerate(args) if arg == "--mount"]
        self.assertEqual(len(mounts), 5)
        self.assertTrue(all(mount.endswith(",readonly") for mount in mounts))
        self.assertFalse(any("docker.sock" in mount for mount in mounts))
        for flag in (
            "--read-only",
            "--pull=never",
            "--cap-drop",
            "--security-opt",
            "--memory",
            "--memory-swap",
            "--pids-limit",
            "--cpus",
            "--log-driver",
        ):
            self.assertIn(flag, args)
        self.assertEqual(args[args.index("--network") + 1], "none")
        self.assertEqual(args[args.index("--memory") + 1], "3g")
        self.assertEqual(args[args.index("--memory-swap") + 1], "3g")
        self.assertIn("core=0:0", args)
        self.assertIn("cpu=60:60", args)
        self.assertEqual(
            args[-4:], ["/opt/tnd-check", "/config.json", "/challenge.ndjson", "/solution.ndjson"]
        )

    def test_rejects_unsafe_inputs(self):
        path = self.files[0]
        path.unlink()
        path.symlink_to(self.files[1])
        with self.assertRaisesRegex(ValueError, "regular"):
            self.args()
        path.unlink()
        path.write_bytes(b"")
        with self.assertRaisesRegex(ValueError, "nonempty"):
            self.args()
        with self.assertRaisesRegex(ValueError, "maintained SHA-256 pin"):
            isolated.docker_arguments("ubuntu:latest", *self.files, self.lean, self.name)
        with self.assertRaisesRegex(ValueError, "maintained SHA-256 pin"):
            isolated.docker_arguments(
                "--env=BAD@sha256:" + "a" * 64, *self.files, self.lean, self.name
            )
        with (
            patch.object(isolated.os, "getuid", return_value=0),
            self.assertRaisesRegex(ValueError, "unprivileged"),
        ):
            isolated.docker_arguments(driver.IMAGE, *self.files, self.lean, self.name)

    def test_oversized_export_is_rejected_before_docker(self):
        with self.files[1].open("wb") as output:
            output.truncate(isolated.MAX_EXPORT + 1)
        with (
            patch.object(isolated.admit, "run_parser") as execute,
            self.assertRaisesRegex(ValueError, "size limit"),
        ):
            self.run_checker()
        execute.assert_not_called()

    def test_missing_docker_fails_before_seccomp_or_execution(self):
        with (
            patch.object(isolated.shutil, "which", return_value=None),
            patch.object(driver, "require_default_seccomp") as seccomp,
            patch.object(isolated.admit, "run_parser") as execute,
            self.assertRaisesRegex(ValueError, "Docker client is unavailable"),
        ):
            self.run_checker()
        seccomp.assert_not_called()
        execute.assert_not_called()

    def test_seccomp_is_checked_before_launch(self):
        with (
            patch.object(driver, "require_default_seccomp", side_effect=ValueError("seccomp")),
            patch.object(isolated.admit, "run_parser") as execute,
            patch.object(driver, "ensure_container_removed") as cleanup,
            self.assertRaisesRegex(ValueError, "seccomp"),
        ):
            self.run_checker()
        execute.assert_not_called()
        cleanup.assert_not_called()

    def test_accepted_result_is_used_only_after_confirmed_cleanup(self):
        events = []

        def execute(args, **kwargs):
            events.append(("run", args[args.index("--name") + 1]))
            return subprocess.CompletedProcess(args, 0, GOOD, "")

        def cleanup(name):
            events.append(("cleanup", name))

        with (
            patch.object(driver, "require_default_seccomp"),
            patch.object(isolated.admit, "run_parser", side_effect=execute),
            patch.object(driver, "ensure_container_removed", side_effect=cleanup),
        ):
            report = self.run_checker()
        self.assertEqual([event[0] for event in events], ["run", "cleanup"])
        self.assertEqual(events[0][1], events[1][1])
        self.assertTrue(report["development_only"])
        self.assertEqual(report["status"], "development-proof-check")

    def test_timeout_and_cleanup_failure_are_never_accepted(self):
        with (
            patch.object(driver, "require_default_seccomp"),
            patch.object(
                isolated.admit, "run_parser", side_effect=subprocess.TimeoutExpired("docker", 90)
            ),
            patch.object(driver, "ensure_container_removed") as cleanup,
            self.assertRaises(subprocess.TimeoutExpired),
        ):
            self.run_checker()
        cleanup.assert_called_once()
        with (
            patch.object(driver, "require_default_seccomp"),
            patch.object(
                isolated.admit,
                "run_parser",
                return_value=subprocess.CompletedProcess([], 0, GOOD, ""),
            ),
            patch.object(
                driver, "ensure_container_removed", side_effect=ValueError("still running")
            ),
            self.assertRaisesRegex(ValueError, "still running"),
        ):
            self.run_checker()

    def test_failure_and_malformed_success_fail_closed(self):
        missing = json.loads(GOOD)
        missing["declarations"] = []
        wrong_schema = json.loads(GOOD)
        wrong_schema["schema_version"] = True
        for code, output in [
            (1, '{"status":"rejected"}'),
            (0, "{}"),
            (0, "not json"),
            (0, json.dumps(missing)),
            (0, json.dumps(wrong_schema)),
        ]:
            with (
                self.subTest(code=code, output=output),
                patch.object(driver, "require_default_seccomp"),
                patch.object(
                    isolated.admit,
                    "run_parser",
                    return_value=subprocess.CompletedProcess([], code, output, ""),
                ),
                patch.object(driver, "ensure_container_removed") as cleanup,
                self.assertRaises(ValueError),
            ):
                self.run_checker()
            cleanup.assert_called_once()

    def test_real_bounded_launcher_rejects_output_flood_and_cleans_up(self):
        fake_docker = self.root / "docker"
        fake_docker.write_text(
            f"#!{sys.executable}\nimport os\nwhile True: os.write(1, b'x' * 65536)\n"
        )
        fake_docker.chmod(0o755)
        with (
            patch.object(isolated.shutil, "which", return_value=str(fake_docker)),
            patch.object(driver, "require_default_seccomp"),
            patch.object(driver, "ensure_container_removed") as cleanup,
            self.assertRaisesRegex(ValueError, "output exceeded"),
        ):
            self.run_checker()
        cleanup.assert_called_once()


if __name__ == "__main__":
    unittest.main()
