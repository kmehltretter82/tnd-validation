"""The Lean bootstrap accepts only the reviewed archive bytes."""

import hashlib
import importlib.util
import io
import subprocess
import sys
import tarfile
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).parents[2]
SPEC = importlib.util.spec_from_file_location(
    "tnd_install_lean", ROOT / "audit/install_lean.py"
)
installer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = installer
SPEC.loader.exec_module(installer)
REAL_RUN = subprocess.run


def fixture_archive(path: Path, version: str = "4.35.0", self_prefix: bool = True) -> None:
    """Write a plain tar named like the release; `tar --zstd` is patched out."""
    prefix = 'cd "$(dirname "$0")/.." && pwd' if self_prefix else "echo /elsewhere"
    script = (
        '#!/bin/sh\ncase "$1" in\n'
        f"  --print-prefix) {prefix} ;;\n"
        f'  --version) echo "Lean (version {version}, Release)" ;;\n'
        "esac\n"
    ).encode()
    with tarfile.open(path, "w") as tar:
        info = tarfile.TarInfo("lean-4.35.0-linux/bin/lean")
        info.size = len(script)
        info.mode = 0o755
        tar.addfile(info, io.BytesIO(script))


def asset_for(path: Path) -> "installer.Asset":
    return installer.Asset(
        path.name, path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest()
    )


def plain_tar(argv, **kwargs):
    """Run the real extraction arguments on an uncompressed fixture."""
    return REAL_RUN([arg for arg in argv if arg != "--zstd"], **kwargs)


class SelectionTests(unittest.TestCase):
    def test_each_supported_architecture_has_one_reviewed_asset(self):
        self.assertEqual(
            installer.select_asset("Linux", "x86_64").name, "lean-4.35.0-linux.tar.zst"
        )
        self.assertEqual(
            installer.select_asset("Linux", "aarch64").name,
            "lean-4.35.0-linux_aarch64.tar.zst",
        )
        for asset in installer.ASSETS.values():
            self.assertRegex(asset.sha256, r"^[0-9a-f]{64}$")
            self.assertGreater(asset.size, 0)

    def test_unreviewed_platforms_are_refused(self):
        for system, machine in (
            ("Darwin", "arm64"), ("Linux", "riscv64"), ("Linux", "arm64"), ("Windows", "x86_64"),
        ):
            with self.subTest(system=system, machine=machine), self.assertRaises(ValueError):
                installer.select_asset(system, machine)

    def test_repository_toolchain_matches_the_installer_pin(self):
        installer.check_toolchain_pin(ROOT / "lean-toolchain")
        installer.check_toolchain_pin(ROOT / "audit/lean-toolchain")

    def test_changed_toolchain_pin_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lean-toolchain"
            path.write_bytes(b"leanprover/lean4:v4.36.0\n")
            with self.assertRaises(ValueError):
                installer.check_toolchain_pin(path)


class VerificationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.dir = Path(directory.name).resolve()
        self.archive = self.dir / "fixture.tar"
        fixture_archive(self.archive)
        self.asset = asset_for(self.archive)
        self.dest = self.dir / "lean"

    def fetch(self, _asset, target):
        target.write_bytes(self.archive.read_bytes())

    def install(self, **kwargs):
        with patch.object(installer.subprocess, "run", side_effect=plain_tar):
            return installer.install(self.asset, self.dest, fetch=self.fetch, **kwargs)

    def assert_nothing_left(self):
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["fixture.tar"])

    def test_verified_archive_installs_at_the_exact_destination(self):
        self.assertEqual(self.install(), self.dest)
        self.assertTrue((self.dest / "bin/lean").is_file())
        self.assertEqual(
            sorted(p.name for p in self.dir.iterdir()), ["fixture.tar", "lean"]
        )

    def test_wrong_digest_is_refused_before_any_extraction(self):
        wrong = installer.Asset(self.asset.name, self.asset.size, "0" * 64)
        with patch.object(installer.subprocess, "run") as run, self.assertRaisesRegex(
            ValueError, "SHA-256"
        ):
            installer.install(wrong, self.dest, fetch=self.fetch)
        run.assert_not_called()
        self.assert_nothing_left()

    def test_wrong_size_is_refused_before_any_extraction(self):
        wrong = installer.Asset(self.asset.name, self.asset.size + 1, self.asset.sha256)
        with patch.object(installer.subprocess, "run") as run, self.assertRaisesRegex(
            ValueError, "size"
        ):
            installer.install(wrong, self.dest, fetch=self.fetch)
        run.assert_not_called()
        self.assert_nothing_left()

    def test_symlinked_download_is_refused(self):
        def link(_asset, target):
            target.symlink_to(self.archive)

        with self.assertRaisesRegex(ValueError, "regular file"):
            installer.install(self.asset, self.dest, fetch=link)
        self.assert_nothing_left()

    def test_failed_download_leaves_nothing_behind(self):
        def fail(_asset, _target):
            raise subprocess.CalledProcessError(22, "curl")

        with self.assertRaises(subprocess.CalledProcessError):
            installer.install(self.asset, self.dest, fetch=fail)
        self.assert_nothing_left()

    def test_existing_destination_and_symlink_are_never_reused(self):
        self.dest.mkdir()
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.install()
        self.dest.rmdir()
        self.dest.symlink_to(self.dir)
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.install()

    def test_noncanonical_or_relative_destination_is_refused(self):
        for dest in (Path("relative/lean"), self.dir / "missing/lean"):
            with self.subTest(dest=dest), self.assertRaises((ValueError, OSError)):
                installer.install(self.asset, dest, fetch=self.fetch)

    def test_wrong_reported_version_removes_the_install(self):
        fixture_archive(self.archive, version="4.34.0")
        self.asset = asset_for(self.archive)
        with self.assertRaisesRegex(ValueError, "4.35.0"):
            self.install()
        self.assert_nothing_left()

    def test_wrong_reported_prefix_removes_the_install(self):
        fixture_archive(self.archive, self_prefix=False)
        self.asset = asset_for(self.archive)
        with self.assertRaisesRegex(ValueError, "prefix"):
            self.install()
        self.assert_nothing_left()

    def test_cli_reports_refusal_without_a_traceback(self):
        with (
            patch.object(installer.platform, "system", return_value="Darwin"),
            patch.object(installer.platform, "machine", return_value="arm64"),
            redirect_stderr(io.StringIO()) as stderr,
        ):
            self.assertEqual(installer.main(["--dest", str(self.dest)]), 1)
        self.assertIn("no reviewed Lean archive", stderr.getvalue())
        self.assert_nothing_left()


class WorkflowContractTests(unittest.TestCase):
    def test_trusted_bootstrap_uses_only_the_verified_installer(self):
        action = yaml.safe_load((ROOT / ".github/actions/setup-verifier/action.yml").read_text())
        steps = action["runs"]["steps"]
        runs = [step.get("run", "") for step in steps]
        install = next(i for i, run in enumerate(runs) if "audit/install_lean.py" in run)
        readiness = next(i for i, run in enumerate(runs) if "tnd_readiness" in run)
        build = next(i for i, run in enumerate(runs) if "lake build" in run)
        self.assertLess(readiness, install)
        self.assertLess(install, build)
        self.assertNotIn("elan", "\n".join(runs))

    def test_maintainer_ci_does_not_download_an_unverified_installer(self):
        text = (ROOT / ".github/workflows/maintainer-ci.yml").read_text()
        self.assertIn("audit/install_lean.py", text)
        self.assertNotIn("elan", text)


if __name__ == "__main__":
    unittest.main()
