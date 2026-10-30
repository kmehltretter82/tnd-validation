"""Checks for the portable development harness; no Docker daemon is needed."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "tnd_linux_git_integration", Path(__file__).with_name("linux_git_integration.py")
)
harness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(harness)


class IntegrationHarnessTests(unittest.TestCase):
    def test_embedded_mode_changes_only_lean_mount_and_image(self):
        original = [
            "docker",
            "run",
            "--read-only",
            "--network",
            "none",
            "--mount",
            "type=bind,src=/source,dst=/source,readonly",
            "--mount",
            "type=bind,src=/lean,dst=/opt/lean,readonly",
            "image@sha256:" + "a" * 64,
            "lean",
            "--run",
        ]
        image_id = "sha256:" + "b" * 64
        result = harness.use_embedded_lean(original, original[-3], image_id)
        self.assertEqual(result, [*original[:7], image_id, "lean", "--run"])
        self.assertIn("--read-only", result)
        self.assertIn("none", result)
        self.assertEqual(original[7], "--mount")

    def test_embedded_mode_rejects_mutable_image_or_missing_mount(self):
        with self.assertRaisesRegex(ValueError, "immutable"):
            harness.use_embedded_lean([], "unused", "ubuntu:latest")
        with self.assertRaisesRegex(ValueError, "Lean mount"):
            harness.use_embedded_lean(["docker", "image"], "image", "sha256:" + "a" * 64)

    def test_embedded_checker_keeps_image_validation_and_seccomp_gate(self):
        driver = harness.driver
        embedded = "sha256:" + "b" * 64
        seccomp = driver.require_default_seccomp
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = [root / name for name in ("config", "base", "head", "checker")]
            for path in files:
                path.write_text("x")
            with (
                patch.object(driver, "docker_arguments", driver.docker_arguments),
                patch.object(
                    driver.parser_sandbox,
                    "docker_arguments",
                    driver.parser_sandbox.docker_arguments,
                ),
                patch.object(
                    driver.checker_sandbox,
                    "docker_arguments",
                    driver.checker_sandbox.docker_arguments,
                ),
                patch.object(driver.checker_sandbox.os, "getuid", return_value=1000),
            ):
                harness.adapt_embedded_mode(embedded)
                self.assertIs(driver.require_default_seccomp, seccomp)
                args = driver.checker_sandbox.docker_arguments(
                    driver.IMAGE, *files, root, "tnd-checker-" + "a" * 32
                )
                self.assertIn(embedded, args)
                self.assertNotIn(driver.IMAGE, args)
                self.assertFalse(any(",dst=/opt/lean,readonly" in value for value in args))
                with self.assertRaisesRegex(ValueError, "maintained SHA-256 pin"):
                    driver.checker_sandbox.docker_arguments(
                        "ubuntu:latest", *files, root, "tnd-checker-" + "a" * 32
                    )

    def test_unconfined_daemon_stops_before_creating_fixtures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lean = root / "lean/bin"
            lean.mkdir(parents=True)
            (lean / "lean").touch()
            checker, exporter = root / "checker", root / "exporter"
            checker.touch()
            exporter.touch()
            args = SimpleNamespace(
                checker=checker,
                exporter=exporter,
                lean_root=lean.parent,
                embedded_image=None,
                image=harness.driver.IMAGE,
                work_dir=root,
            )
            with (
                patch.object(harness.os, "getuid", return_value=1000),
                patch.object(harness.platform, "system", return_value="Linux"),
                patch.object(
                    harness.driver,
                    "require_default_seccomp",
                    side_effect=ValueError("Docker built-in seccomp profile is required"),
                ),
                patch.object(harness, "git") as git,
                self.assertRaisesRegex(ValueError, "seccomp"),
            ):
                harness.run(args)
            git.assert_not_called()


if __name__ == "__main__":
    unittest.main()
