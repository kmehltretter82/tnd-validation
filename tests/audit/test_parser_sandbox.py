"""Development parser isolation contract; these tests do not certify it."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from audit import run as runner
from audit.admission import sandbox

PROJECT = Path(__file__).resolve().parents[2]
ACCEPTED = json.dumps(
    {
        "status": "admitted-source-syntax",
        "scope": "approved-library-source-only",
        "development_only": True,
    }
)


def run_container(source, stage, lean):
    return sandbox.admit_into_container(
        source,
        stage,
        lean,
        image=runner.IMAGE,
        cleanup=runner.ensure_container_removed,
        check_seccomp=lambda: None,
    )


class ParserSandboxTests(unittest.TestCase):
    def setUp(self):
        docker = patch.object(sandbox.shutil, "which", return_value="/usr/bin/docker")
        docker.start()
        self.addCleanup(docker.stop)

    def test_container_has_only_read_only_host_mounts_and_bounded_resources(self):
        path = Path("/trusted")
        args = sandbox.docker_arguments(
            runner.IMAGE, path, path, path, path, "tnd-parser-" + "a" * 32
        )
        mounts = [args[i + 1] for i, value in enumerate(args) if value == "--mount"]
        self.assertEqual(len(mounts), 4)
        self.assertTrue(all(value.endswith(",readonly") for value in mounts))
        self.assertIn("dst=/source,readonly", mounts[0])
        self.assertFalse(any("docker.sock" in value for value in mounts))
        for value in (
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
            self.assertIn(value, args)
        self.assertIn("core=0:0", args)
        self.assertIn("cpu=60:60", args)
        self.assertEqual(args[args.index("--network") + 1], "none")
        self.assertEqual(
            args[-5:], ["/opt/lean/bin/lean", "--run", "/Main.lean", "/policy.json", "/source"]
        )

    def test_unpinned_image_and_unsafe_mount_paths_are_rejected(self):
        path = Path("/trusted")
        self.assertEqual(runner.IMAGE, sandbox.admit.MAINTAINED_IMAGE)
        with self.assertRaisesRegex(ValueError, "maintained SHA-256 pin"):
            sandbox.docker_arguments(
                "ubuntu:latest", path, path, path, path, "tnd-parser-" + "a" * 32
            )
        for image in ("ubuntu@sha256:" + "a" * 64, "--env=BAD@sha256:" + "a" * 64):
            with self.assertRaisesRegex(ValueError, "maintained SHA-256 pin"):
                sandbox.docker_arguments(image, path, path, path, path, "tnd-parser-" + "a" * 32)
        with self.assertRaisesRegex(ValueError, "commas"):
            sandbox.docker_arguments(
                runner.IMAGE, Path("/bad,path"), path, path, path, "tnd-parser-" + "a" * 32
            )
        with (
            patch.object(sandbox.os, "getuid", return_value=0),
            self.assertRaisesRegex(ValueError, "unprivileged"),
        ):
            sandbox.docker_arguments(runner.IMAGE, path, path, path, path, "tnd-parser-" + "a" * 32)

    def test_parser_output_is_consumed_only_after_verified_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary) / "staged"
            result = subprocess.CompletedProcess([], 0, ACCEPTED, "")
            events = []

            def parse(args, **kwargs):
                events.append(("parse", args[args.index("--name") + 1]))
                return result

            def cleanup(name):
                events.append(("cleanup", name))

            with (
                patch.object(sandbox.admit, "run_parser", side_effect=parse),
                patch.object(runner, "ensure_container_removed", side_effect=cleanup),
            ):
                report = run_container(PROJECT, stage, Path("/opt/lean"))
            self.assertEqual([e[0] for e in events], ["parse", "cleanup"])
            self.assertEqual(events[0][1], events[1][1])
            self.assertEqual(report["parser_isolation"], "development-docker")
            self.assertTrue(report["development_only"])

    def test_missing_docker_client_does_not_start_a_container(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary) / "staged"
            with (
                patch.object(sandbox.shutil, "which", return_value=None),
                patch.object(sandbox.admit, "run_parser") as run,
                self.assertRaisesRegex(ValueError, "Docker client is unavailable"),
            ):
                run_container(PROJECT, stage, Path("/opt/lean"))
            run.assert_not_called()

    def test_untrusted_daemon_and_hash_mismatch_never_start_parser(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (
                patch.object(sandbox.admit, "run_parser") as run,
                patch.object(runner, "ensure_container_removed") as cleanup,
                self.assertRaisesRegex(ValueError, "seccomp"),
            ):
                sandbox.admit_into_container(
                    PROJECT,
                    root / "unconfined",
                    root,
                    image=runner.IMAGE,
                    cleanup=cleanup,
                    check_seccomp=lambda: (_ for _ in ()).throw(ValueError("seccomp")),
                )
            run.assert_not_called()
            cleanup.assert_not_called()
            with (
                patch.object(sandbox.admit, "run_parser") as run,
                patch.object(runner, "ensure_container_removed") as cleanup,
                self.assertRaisesRegex(ValueError, "exact Git source hashes"),
            ):
                sandbox.admit_into_container(
                    PROJECT,
                    root / "mismatch",
                    root,
                    image=runner.IMAGE,
                    cleanup=cleanup,
                    check_seccomp=lambda: None,
                    expected_hashes={},
                )
            run.assert_not_called()
            cleanup.assert_not_called()

    def test_timeout_and_cleanup_failure_cannot_issue_admission(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary) / "timeout"
            with (
                patch.object(
                    sandbox.admit, "run_parser", side_effect=subprocess.TimeoutExpired("docker", 90)
                ),
                patch.object(runner, "ensure_container_removed") as cleanup,
                self.assertRaises(subprocess.TimeoutExpired),
            ):
                run_container(PROJECT, stage, Path("/opt/lean"))
            cleanup.assert_called_once()
            stage = Path(temporary) / "cleanup-failure"
            with (
                patch.object(
                    sandbox.admit,
                    "run_parser",
                    return_value=subprocess.CompletedProcess([], 0, ACCEPTED, ""),
                ),
                patch.object(
                    runner,
                    "ensure_container_removed",
                    side_effect=ValueError("container remains"),
                ),
                self.assertRaisesRegex(ValueError, "container remains"),
            ):
                run_container(PROJECT, stage, Path("/opt/lean"))

    def test_parser_rejection_and_changed_snapshot_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary) / "rejection"
            rejected = subprocess.CompletedProcess([], 1, '{"status":"rejected"}', "")
            with (
                patch.object(sandbox.admit, "run_parser", return_value=rejected),
                patch.object(runner, "ensure_container_removed") as cleanup,
                self.assertRaisesRegex(ValueError, "parser rejected"),
            ):
                run_container(PROJECT, stage, Path("/opt/lean"))
            cleanup.assert_called_once()

            stage = Path(temporary) / "tampered"

            def mutate(args, **kwargs):
                (stage / "TNDLib/Nat.lean").write_text("changed")
                return subprocess.CompletedProcess([], 0, ACCEPTED, "")

            with (
                patch.object(sandbox.admit, "run_parser", side_effect=mutate),
                patch.object(runner, "ensure_container_removed"),
                self.assertRaisesRegex(ValueError, "bytes changed"),
            ):
                run_container(PROJECT, stage, Path("/opt/lean"))


if __name__ == "__main__":
    unittest.main()
