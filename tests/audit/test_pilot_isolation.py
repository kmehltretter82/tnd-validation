"""Tracked development sources cannot enter the canonical audit's source stage."""

import hashlib
import importlib.util
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "tnd_pilot_isolation_runner", PROJECT / "audit/run.py"
)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class PilotIsolationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="tnd-pilot-isolation-")
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name)
        self.repo = self.workspace / "repository"
        self.target = self.workspace / "canonical"
        self.repo.mkdir()
        self.target.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        policy, _ = runner.admission.policy_for()
        self.approved = {entry["path"] for entry in policy["source_files"]}
        self.expected = {}
        for name in self.approved:
            contents = (PROJECT / name).read_bytes()
            destination = self.repo / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(contents)
            self.expected[name] = hashlib.sha256(contents).hexdigest()
        for name, contents in runner.PUBLISHED_PACKAGE.items():
            (self.repo / name).write_bytes(contents)

    def add_source(self, name, contents=b"import Init\naxiom unreviewed : False\n"):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)

    def commit(self):
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run([
            "git", "-C", str(self.repo), "-c", "user.name=Isolation fixture",
            "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture",
        ], check=True)
        return subprocess.check_output(
            ["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True,
        ).strip()

    def test_tracked_pilot_sources_are_excluded_from_the_canonical_stage(self):
        # Include both real current development source and an unreviewed module.
        # Neither may be copied into the source subsequently admitted and built.
        source = "pilot/TNDLib/Matching/Basic.lean"
        self.add_source(source, (PROJECT / source).read_bytes())
        self.add_source("pilot/TNDLib/Matching/Unreviewed.lean")
        hashes = runner.source_snapshot(self.repo, self.commit(), self.target)
        self.assertEqual(hashes, self.expected)
        self.assertEqual(
            {path.relative_to(self.target).as_posix() for path in self.target.rglob("*.lean")},
            self.approved,
        )
        self.assertFalse((self.target / "pilot").exists())
        self.assertFalse((self.target / "TNDLib/Matching").exists())
        self.assertNotIn(b"unreviewed", b"".join(
            (self.target / name).read_bytes() for name in sorted(self.approved)
        ))

        # Production builds use this separately maintained minimal project,
        # rather than the candidate package's optional development target.
        package = tomllib.loads((self.target / "lakefile.toml").read_text())
        self.assertEqual((self.target / "lakefile.toml").read_text(), runner.LAKEFILE)
        self.assertEqual(package["defaultTargets"], ["TNDLib"])
        self.assertEqual(package["lean_lib"], [{"name": "TNDLib"}])
        self.assertNotIn("pilot", (self.target / "lakefile.toml").read_text())

    def test_unrelated_auxiliary_source_roots_are_rejected(self):
        wrong_paths = (
            "Pilot.lean", "pilot/Other.lean", "pilot/TNDLib/Other.lean",
            "pilot/TNDLib/Matching.lean", "pilot/TNDLib/MatchingExtra/Evil.lean",
        )
        for name in wrong_paths:
            with self.subTest(name=name):
                self.add_source(name)
                with self.assertRaisesRegex(ValueError, "unapproved Lean source"):
                    runner.source_snapshot(self.repo, self.commit(), self.target)
                self.assertEqual(list(self.target.rglob("*.lean")), [])
                (self.repo / name).unlink()

    def test_canonical_matching_path_still_requires_source_inventory_approval(self):
        self.add_source("TNDLib/Matching/Unreviewed.lean")
        with self.assertRaisesRegex(ValueError, "inventory differs"):
            runner.source_snapshot(self.repo, self.commit(), self.target)
        self.assertEqual(list(self.target.rglob("*.lean")), [])

    def test_candidate_cannot_extend_the_fixed_package_configuration(self):
        config = self.repo / "lakefile.toml"
        config.write_bytes(config.read_bytes() + b'\n[[lean_lib]]\nname = "Unreviewed"\n')
        with self.assertRaisesRegex(ValueError, "published package differs"):
            runner.source_snapshot(self.repo, self.commit(), self.target)
        self.assertEqual(list(self.target.rglob("*.lean")), [])

    def test_checked_in_package_matches_the_exact_maintained_bytes(self):
        for name, expected in runner.PUBLISHED_PACKAGE.items():
            with self.subTest(name=name):
                self.assertEqual((PROJECT / name).read_bytes(), expected)


if __name__ == "__main__":
    unittest.main()
