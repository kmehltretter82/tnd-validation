"""Purely local transformation guards for the promotion rehearsal."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "tnd_promotion_rehearsal", Path(__file__).with_name("promotion_rehearsal.py")
)
rehearsal = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rehearsal)


class PromotionRehearsalTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name)
        self.project = Path(__file__).resolve().parents[2]
        self.solution = (self.project / "tests/tasks/MapExistsSolution.lean").read_bytes()
        self.repo = self.workspace / "repo"
        rehearsal.copy_baseline(self.project, self.repo)

    def promote(self):
        baseline = rehearsal.initialize_repository(self.repo)
        accepted = rehearsal.accept_solution(self.repo, self.solution)
        promoted = rehearsal.promote(self.repo, self.solution)
        return baseline, accepted, promoted

    def test_temporary_promotion_updates_every_policy_surface(self):
        self.assertFalse((self.repo / ".choir/orchestrator.toml").exists())
        self.assertEqual(
            sorted(path.name for path in (self.repo / ".choir").iterdir()),
            ["certification.json"],
        )
        real_paths = [
            self.project / "TNDLib.lean",
            self.project / "audit/exports.json",
            self.project / "audit/admission/policy.json",
            self.project / "tasks/map_exists.lean",
        ]
        before = {path: path.read_bytes() for path in real_paths}
        baseline, accepted, promoted = self.promote()
        self.assertEqual(len({baseline, accepted, promoted}), 3)
        rehearsal.validate_promoted_tree(self.repo)
        source = (self.repo / rehearsal.PROMOTED_PATH).read_text()
        self.assertIn("import Init", source)
        self.assertIn("namespace " + rehearsal.PROMOTED_NAMESPACE, source)
        self.assertNotIn("sorry", source)
        self.assertNotIn("TNDTask", source)
        exports = json.loads((self.repo / "audit/exports.json").read_text())
        self.assertIn(rehearsal.PROMOTED_DECLARATION, exports["expected_exports"])
        self.assertEqual(
            exports["source_paths"][rehearsal.PROMOTED_DECLARATION],
            rehearsal.PROMOTED_PATH,
        )
        self.assertEqual(
            set(rehearsal._git(self.repo, "diff", "--name-only", "HEAD^", "HEAD")
                .decode().splitlines()),
            {
                "TNDLib.lean",
                rehearsal.PROMOTED_PATH,
                "audit/admission/policy.json",
                "audit/exports.json",
            },
        )
        for path, contents in before.items():
            self.assertEqual(path.read_bytes(), contents)

    def test_solution_bytes_and_structure_are_exact(self):
        promoted = rehearsal.promoted_source(self.solution, self.solution).decode()
        self.assertIn("theorem mapExists", promoted)
        for tampered in (
            self.solution + b"\n",
            self.solution.replace(b"TNDTask", b"OtherTask", 1),
            self.solution.replace(b"Exists.elim", b"Classical.choice", 1),
        ):
            with self.subTest(tampered=tampered[-40:]), self.assertRaises(ValueError):
                rehearsal.promoted_source(tampered, self.solution)

    def test_enabled_boundary_or_incomplete_metadata_fails_closed(self):
        policy_path = self.repo / ".choir/certification.json"
        policy = json.loads(policy_path.read_text())
        for field, value in (
            ("schema_version", True),
            ("source_binding_validated", True),
            ("resource_boundary_validated", True),
            ("resource_limits", {}),
        ):
            invalid = dict(policy)
            invalid[field] = value
            policy_path.write_text(json.dumps(invalid))
            with self.subTest(field=field), self.assertRaisesRegex(
                ValueError, "certification boundary"
            ):
                rehearsal.require_development_only(self.repo)
        policy_path.write_text(json.dumps(policy))

        rehearsal.copy_baseline(self.project, self.workspace / "second")
        self.repo = self.workspace / "second"
        self.promote()
        exports_path = self.repo / "audit/exports.json"
        exports = json.loads(exports_path.read_text())
        del exports["citations"][rehearsal.PROMOTED_DECLARATION]
        exports_path.write_text(json.dumps(exports))
        with self.assertRaisesRegex(ValueError, "metadata"):
            rehearsal.validate_promoted_tree(self.repo)

    def test_unexpected_promotion_file_is_rejected(self):
        self.promote()
        (self.repo / "TNDLib/Untracked.lean").write_text("import Init\n")
        with self.assertRaisesRegex(ValueError, "exactly cover"):
            rehearsal.validate_promoted_tree(self.repo)


if __name__ == "__main__":
    unittest.main()
